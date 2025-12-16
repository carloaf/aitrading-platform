"""
BLUE_PRINT v1.0: Risk Manager - Gestão de Risco Institucional
=============================================================

Sistema de dimensionamento de posição matemático baseado em:
1. Confiança do Regime de Mercado
2. Qualidade do Volume
3. Volatilidade (ATR relativo)

Fórmula: Position_Size = (Capital * Risk_Per_Trade) / Stop_Loss_Distance * Multipliers

Autor: "The Legend" (Wall St. & Faria Lima)
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class VolumeProfile(Enum):
    """Perfil de volume do mercado"""
    HIGH = "high"      # Volume acima da média
    NORMAL = "normal"  # Volume na média
    LOW = "low"        # Volume abaixo da média


class MarketPhase(Enum):
    """Fase do mercado baseada no regime"""
    BULL_TREND = "bull_trend"      # Tendência de alta
    BEAR_TREND = "bear_trend"      # Tendência de baixa
    SIDEWAYS = "sideways"          # Mercado lateral
    VOLATILE = "volatile"          # Alta volatilidade
    CRISIS = "crisis"              # Crise/Pânico


@dataclass
class RiskParameters:
    """Parâmetros de risco para uma posição"""
    position_size: float           # Tamanho da posição (0 a 1)
    risk_per_trade: float          # Risco por trade (%)
    stop_loss_distance: float      # Distância do stop (%)
    take_profit_distance: float    # Distância do take profit (%)
    max_drawdown_allowed: float    # Drawdown máximo permitido (%)
    confidence_multiplier: float   # Multiplicador baseado na confiança
    volume_multiplier: float       # Multiplicador baseado no volume
    atr_multiplier: float          # Multiplicador baseado na volatilidade
    final_multiplier: float        # Multiplicador final combinado
    regime: str                    # Regime atual
    recommendation: str            # Recomendação de ação


class RiskManager:
    """
    Gerenciador de Risco Institucional
    
    Calcula tamanho de posição dinamicamente baseado em:
    - Regime de mercado
    - Qualidade do volume
    - Volatilidade atual
    """
    
    # Fatores de risco por regime (conforme BLUE_PRINT)
    REGIME_RISK_FACTORS = {
        MarketPhase.BULL_TREND: 1.0,    # Agressivo
        MarketPhase.BEAR_TREND: 0.8,    # Moderado
        MarketPhase.SIDEWAYS: 0.6,      # Cauteloso
        MarketPhase.VOLATILE: 0.4,      # Defensivo
        MarketPhase.CRISIS: 0.2         # Ultra-defensivo
    }
    
    # Multiplicadores de volume
    VOLUME_MULTIPLIERS = {
        VolumeProfile.HIGH: 1.0,
        VolumeProfile.NORMAL: 0.8,
        VolumeProfile.LOW: 0.6
    }
    
    def __init__(self, 
                 base_risk_per_trade: float = 0.02,
                 max_position_size: float = 0.25,
                 max_drawdown: float = 0.20):
        """
        Inicializa o Risk Manager
        
        Args:
            base_risk_per_trade: Risco base por trade (2% padrão)
            max_position_size: Tamanho máximo de posição (25% padrão)
            max_drawdown: Drawdown máximo permitido (20% padrão)
        """
        self.base_risk_per_trade = base_risk_per_trade
        self.max_position_size = max_position_size
        self.max_drawdown = max_drawdown
        
        # Kelly Criterion (PASSO 25)
        self.kelly_enabled = False  # Desabilitado por padrão (usar fixed risk)
        self.kelly_fraction = 0.25  # Usar 25% do Kelly (conservador)
        self.min_trades_for_kelly = 30  # Mínimo de trades para confiar nas estatísticas
        
    def calculate_kelly_criterion(self,
                                   win_rate: float,
                                   avg_win: float,
                                   avg_loss: float,
                                   num_trades: int = 0) -> float:
        """
        Calcula Kelly Criterion para otimizar tamanho de posição
        
        FÓRMULA: f = (p*b - q) / b
        Onde:
            p = probabilidade de ganho (win_rate)
            q = probabilidade de perda (1 - win_rate)
            b = ratio avg_win / avg_loss (payoff)
        
        PASSO 25: Implementação conservadora
        - Usa fração de Kelly (0.25x padrão) para reduzir volatilidade
        - Requer mínimo de 30 trades para estatísticas confiáveis
        - Limitado a max 15% do capital (segurança)
        
        Args:
            win_rate: Taxa de acerto (0-1, ex: 0.55 = 55%)
            avg_win: Lucro médio por trade vencedor (absoluto)
            avg_loss: Perda média por trade perdedor (absoluto, positivo)
            num_trades: Número de trades históricos (para validação)
            
        Returns:
            Fração ótima do capital a arriscar (0-1)
            
        Examples:
            >>> # Win rate 55%, avg_win $1500, avg_loss $1000
            >>> kelly = calculate_kelly_criterion(0.55, 1500, 1000, 50)
            >>> # kelly ≈ 0.0825 (8.25% do capital, ou 2.06% com fraction 0.25)
        """
        # Validações
        if win_rate <= 0 or win_rate >= 1:
            logger.warning(f"Kelly: win_rate inválido {win_rate}, usando fixed risk")
            return self.base_risk_per_trade
        
        if avg_win <= 0 or avg_loss <= 0:
            logger.warning(f"Kelly: avg_win/loss inválido ({avg_win}/{avg_loss}), usando fixed risk")
            return self.base_risk_per_trade
        
        if num_trades < self.min_trades_for_kelly:
            logger.info(f"Kelly: apenas {num_trades} trades, insuficiente (min {self.min_trades_for_kelly})")
            return self.base_risk_per_trade
        
        # Calcular componentes
        p = win_rate  # Probabilidade de ganho
        q = 1 - win_rate  # Probabilidade de perda
        b = avg_win / avg_loss  # Payoff ratio
        
        # Fórmula de Kelly
        kelly_full = (p * b - q) / b
        
        # Se Kelly negativo, sistema tem expectativa negativa!
        if kelly_full <= 0:
            logger.warning(f"Kelly NEGATIVO ({kelly_full:.4f}): sistema não lucrativo!")
            return self.base_risk_per_trade * 0.5  # Reduz risco pela metade
        
        # Aplicar fração conservadora
        kelly_fractional = kelly_full * self.kelly_fraction
        
        # Limites de segurança
        kelly_safe = max(0.005, min(kelly_fractional, 0.15))  # Entre 0.5% e 15%
        
        logger.info(f"Kelly: WR={win_rate:.1%} B={b:.2f} → Full={kelly_full:.4f} "
                   f"Fractional={kelly_fractional:.4f} Safe={kelly_safe:.4f}")
        
        return kelly_safe
        
    def calculate_size_multiplier(self,
                                   regime_confidence: float,
                                   volume_profile: VolumeProfile,
                                   volatility_atr_ratio: float,
                                   strategy_sharpe: float = 1.0,
                                   current_drawdown: float = 0.0) -> Dict[str, float]:
        """
        Calcula multiplicadores para dimensionamento de posição
        
        BLUE_PRINT v2.1 - Fórmula INSTITUCIONAL:
        Final_Mult = Confidence_Mult × Volume_Mult × ATR_Mult × Strategy_Mult × DD_Mult
        
        Args:
            regime_confidence: Confiança do regime (0-100%)
            volume_profile: Perfil de volume (HIGH, NORMAL, LOW)
            volatility_atr_ratio: Ratio ATR atual / ATR médio
            strategy_sharpe: Sharpe ratio da estratégia (últimos 30 dias)
            current_drawdown: Drawdown atual do sistema (0-1)
            
        Returns:
            Dicionário com todos os multiplicadores
        """
        # 1. Confiança do Regime (ex: 85.7% -> 0.857)
        conf_mult = min(regime_confidence / 100.0, 1.0)
        
        # 2. Qualidade do Volume
        vol_mult = self.VOLUME_MULTIPLIERS.get(volume_profile, 0.8)
        
        # 3. Volatilidade (Se ATR > 2x média, reduz posição pela metade)
        if volatility_atr_ratio > 2.0:
            atr_mult = 0.5
        elif volatility_atr_ratio > 1.5:
            atr_mult = 0.7
        elif volatility_atr_ratio < 0.5:
            atr_mult = 0.8  # Volatilidade muito baixa também é arriscado
        else:
            atr_mult = 1.0
        
        # 4. NOVO: Performance da Estratégia (Sharpe normalizado)
        # Sharpe 2.0 = 1.0x, Sharpe 1.0 = 0.7x, Sharpe 0.5 = 0.5x
        if strategy_sharpe >= 2.0:
            strategy_mult = 1.2  # Estratégia excelente - aumenta posição
        elif strategy_sharpe >= 1.5:
            strategy_mult = 1.0  # Estratégia boa
        elif strategy_sharpe >= 1.0:
            strategy_mult = 0.8  # Estratégia aceitável
        elif strategy_sharpe >= 0.5:
            strategy_mult = 0.6  # Estratégia fraca
        else:
            strategy_mult = 0.4  # Estratégia ruim - reduz muito
        
        # 5. NOVO: Proteção de Drawdown
        # Se DD > 15%, reduz posição progressivamente
        if current_drawdown > 0.20:
            dd_mult = 0.3  # DD > 20% - modo emergência
        elif current_drawdown > 0.15:
            dd_mult = 0.5  # DD > 15% - reduz pela metade
        elif current_drawdown > 0.10:
            dd_mult = 0.7  # DD > 10% - cauteloso
        else:
            dd_mult = 1.0  # DD < 10% - normal
        
        # Multiplicador final COMPOSTO
        final_mult = conf_mult * vol_mult * atr_mult * strategy_mult * dd_mult
        
        # LIMITAR entre 0.3 (mínimo) e 1.5 (máximo com estratégia excelente)
        final_mult = max(0.3, min(final_mult, 1.5))
        
        return {
            'confidence_multiplier': conf_mult,
            'volume_multiplier': vol_mult,
            'atr_multiplier': atr_mult,
            'strategy_multiplier': strategy_mult,
            'drawdown_multiplier': dd_mult,
            'final_multiplier': final_mult
        }
    
    def calculate_position_size(self,
                                 capital: float,
                                 entry_price: float,
                                 stop_loss_price: float,
                                 regime: MarketPhase,
                                 regime_confidence: float = 80.0,
                                 volume_profile: VolumeProfile = VolumeProfile.NORMAL,
                                 volatility_atr_ratio: float = 1.0,
                                 strategy_sharpe: float = 1.0,
                                 current_drawdown: float = 0.0,
                                 win_rate: Optional[float] = None,
                                 avg_win: Optional[float] = None,
                                 avg_loss: Optional[float] = None,
                                 num_trades: int = 0) -> RiskParameters:
        """
        Calcula tamanho da posição com todos os fatores de risco
        
        BLUE_PRINT v1.0 - Fórmula Completa:
        Position_Size = (Capital * Risk_Per_Trade) / Stop_Loss_Distance * Multipliers
        
        Args:
            capital: Capital disponível
            entry_price: Preço de entrada
            stop_loss_price: Preço do stop-loss
            regime: Fase atual do mercado
            regime_confidence: Confiança do regime (0-100)
            volume_profile: Perfil de volume
            volatility_atr_ratio: Ratio ATR atual / ATR médio
            
        Returns:
            RiskParameters com todos os cálculos
        """
        # Calcular distância do stop
        stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price
        
        # Se stop muito apertado ou muito largo, ajustar
        stop_distance_pct = max(0.01, min(stop_distance_pct, 0.10))  # Entre 1% e 10%
        
        # Fator de risco do regime
        regime_factor = self.REGIME_RISK_FACTORS.get(regime, 0.6)
        
        # Calcular multiplicadores (INSTITUCIONAL v2.1)
        multipliers = self.calculate_size_multiplier(
            regime_confidence, volume_profile, volatility_atr_ratio,
            strategy_sharpe, current_drawdown
        )
        
        # Risco ajustado por trade (PASSO 25: Kelly ou Fixed)
        if self.kelly_enabled and win_rate is not None and avg_win is not None and avg_loss is not None:
            # Usar Kelly Criterion se habilitado e estatísticas disponíveis
            kelly_risk = self.calculate_kelly_criterion(win_rate, avg_win, avg_loss, num_trades)
            adjusted_risk = kelly_risk * regime_factor
            logger.info(f"Kelly Mode: {kelly_risk:.4f} × {regime_factor:.2f} = {adjusted_risk:.4f}")
        else:
            # Usar risco fixo padrão
            adjusted_risk = self.base_risk_per_trade * regime_factor
        
        # Tamanho da posição base
        # Fórmula: (Capital * Risco) / Distância_Stop
        base_position = (capital * adjusted_risk) / stop_distance_pct
        
        # Aplicar multiplicadores
        final_position = base_position * multipliers['final_multiplier']
        
        # Limitar ao máximo permitido
        max_allowed = capital * self.max_position_size
        final_position = min(final_position, max_allowed)
        
        # Converter para porcentagem do capital
        position_size_pct = final_position / capital
        
        # Take profit (2:1 risk/reward por padrão)
        take_profit_distance = stop_distance_pct * 2
        
        # Gerar recomendação
        recommendation = self._generate_recommendation(
            regime, position_size_pct, multipliers['final_multiplier']
        )
        
        return RiskParameters(
            position_size=position_size_pct,
            risk_per_trade=adjusted_risk * 100,  # Em porcentagem
            stop_loss_distance=stop_distance_pct * 100,
            take_profit_distance=take_profit_distance * 100,
            max_drawdown_allowed=self.max_drawdown * 100,
            confidence_multiplier=multipliers['confidence_multiplier'],
            volume_multiplier=multipliers['volume_multiplier'],
            atr_multiplier=multipliers['atr_multiplier'],
            final_multiplier=multipliers['final_multiplier'],
            regime=regime.value,
            recommendation=recommendation
        )
    
    def _generate_recommendation(self, 
                                  regime: MarketPhase, 
                                  position_size: float,
                                  final_mult: float) -> str:
        """Gera recomendação textual baseada nos cálculos"""
        
        if final_mult < 0.3:
            return "⚠️ CAUTELA EXTREMA: Condições desfavoráveis. Considere ficar em caixa."
        elif final_mult < 0.5:
            return "🔶 DEFENSIVO: Reduzir exposição. Posição mínima recomendada."
        elif final_mult < 0.7:
            return "🔷 CAUTELOSO: Condições moderadas. Posição conservadora."
        elif final_mult < 0.9:
            return "🔵 NORMAL: Condições favoráveis. Posição padrão."
        else:
            return "🟢 AGRESSIVO: Condições ideais. Posição máxima permitida."
    
    def should_reduce_position(self,
                                current_drawdown: float,
                                unrealized_pnl_pct: float) -> Dict[str, Any]:
        """
        Verifica se deve reduzir posição baseado no drawdown
        
        Args:
            current_drawdown: Drawdown atual (%)
            unrealized_pnl_pct: PnL não realizado (%)
            
        Returns:
            Dicionário com recomendação de ajuste
        """
        # Níveis de alerta
        warning_level = self.max_drawdown * 0.5   # 50% do max DD
        danger_level = self.max_drawdown * 0.75  # 75% do max DD
        critical_level = self.max_drawdown * 0.9  # 90% do max DD
        
        if current_drawdown >= critical_level:
            return {
                'action': 'CLOSE_ALL',
                'message': '🔴 CRÍTICO: Fechar todas as posições!',
                'severity': 'critical',
                'reduce_by': 1.0  # 100%
            }
        elif current_drawdown >= danger_level:
            return {
                'action': 'REDUCE_50',
                'message': '🟠 PERIGO: Reduzir 50% das posições',
                'severity': 'danger',
                'reduce_by': 0.5
            }
        elif current_drawdown >= warning_level:
            return {
                'action': 'REDUCE_25',
                'message': '🟡 ALERTA: Considerar reduzir 25%',
                'severity': 'warning',
                'reduce_by': 0.25
            }
        else:
            return {
                'action': 'HOLD',
                'message': '🟢 OK: Dentro dos limites de risco',
                'severity': 'normal',
                'reduce_by': 0.0
            }
    
def get_volume_profile(current_volume: float, avg_volume: float) -> VolumeProfile:
    """
    Determina o perfil de volume baseado na comparação com a média
    
    Args:
        current_volume: Volume atual
        avg_volume: Volume médio
        
    Returns:
        VolumeProfile enum
    """
    ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    
    if ratio >= 1.5:
        return VolumeProfile.HIGH
    elif ratio <= 0.7:
        return VolumeProfile.LOW
    else:
        return VolumeProfile.NORMAL


def regime_to_phase(regime_str: str) -> MarketPhase:
    """
    Converte string de regime para MarketPhase enum
    
    Args:
        regime_str: String do regime (BULL, BEAR, SIDEWAYS, VOLATILE)
        
    Returns:
        MarketPhase correspondente
    """
    mapping = {
        'BULL': MarketPhase.BULL_TREND,
        'BEAR': MarketPhase.BEAR_TREND,
        'SIDEWAYS': MarketPhase.SIDEWAYS,
        'VOLATILE': MarketPhase.VOLATILE,
        'UNKNOWN': MarketPhase.CRISIS
    }
    
    return mapping.get(regime_str.upper(), MarketPhase.SIDEWAYS)


# Exemplo de uso
if __name__ == "__main__":
    # Criar risk manager
    rm = RiskManager(
        base_risk_per_trade=0.02,  # 2% por trade
        max_position_size=0.25,     # Máximo 25% do capital
        max_drawdown=0.20           # Drawdown máximo 20%
    )
    
    # Calcular tamanho de posição
    params = rm.calculate_position_size(
        capital=100000.0,           # $100k de capital
        entry_price=45000.0,        # BTC a $45k
        stop_loss_price=43500.0,    # Stop a $43.5k
        regime=MarketPhase.BULL_TREND,
        regime_confidence=85.7,
        volume_profile=VolumeProfile.HIGH,
        volatility_atr_ratio=1.2
    )
    
    print(f"📊 ANÁLISE DE RISCO")
    print(f"=" * 50)
    print(f"Regime: {params.regime}")
    print(f"Tamanho da Posição: {params.position_size:.1%}")
    print(f"Risco por Trade: {params.risk_per_trade:.1f}%")
    print(f"Stop-Loss: {params.stop_loss_distance:.1f}%")
    print(f"Take-Profit: {params.take_profit_distance:.1f}%")
    print(f"Multiplicador Final: {params.final_multiplier:.2f}")
    print(f"Recomendação: {params.recommendation}")
