"""
Estratégia 1: Trend Following com Múltiplos Timeframes
Baseada em EMA + Volume Profile + RSI Divergence

Regras de Entrada (BUY):
1. EMA21 > EMA55 (tendência alta)
2. Volume acima da média 20 períodos
3. RSI entre 40-80 (não sobrecomprado)
4. Confirmação em timeframe maior (se disponível)

Regras de Saída (SELL):
1. EMA21 < EMA55 (fim da tendência)
2. RSI > 80 (sobrecomprado extremo)
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Any
from .base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class TrendFollowingStrategy(BaseStrategy):
    """
    Estratégia de seguimento de tendência com confirmação de volume
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'fast_ema': 21,
            'slow_ema': 55,
            'volume_sma': 20,
            'volume_multiplier': 1.8,  # PLANO_DE_MELHORAMENTO: Institucional
            'rsi_period': 14,
            'rsi_lower': 45,    # BLUE_PRINT: Aumentado de 40 para 45
            'rsi_upper': 70,    # BLUE_PRINT: Reduzido de 80 para 70
            'rsi_exit': 85,
            'adx_threshold': 25  # BLUE_PRINT: Novo parâmetro
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__("Trend Following Strategy", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula EMA rápida/lenta, volume SMA e RSI
        """
        fast_ema = self.parameters['fast_ema']
        slow_ema = self.parameters['slow_ema']
        volume_sma = self.parameters['volume_sma']
        rsi_period = self.parameters['rsi_period']
        
        # Médias Móveis Exponenciais
        df['EMA_fast'] = ta.trend.ema_indicator(df['Close'], window=fast_ema)
        df['EMA_slow'] = ta.trend.ema_indicator(df['Close'], window=slow_ema)
        
        # Cruzamento de EMAs
        df['EMA_cross'] = df['EMA_fast'] - df['EMA_slow']
        df['trend_bullish'] = (df['EMA_fast'] > df['EMA_slow']).astype(int)
        
        # Volume
        df['Volume_SMA'] = df['Volume'].rolling(window=volume_sma).mean()
        df['volume_confirmed'] = (
            df['Volume'] > df['Volume_SMA'] * self.parameters['volume_multiplier']
        ).astype(int)
        
        # RSI com média móvel (PLANO_DE_MELHORAMENTO)
        df['RSI'] = ta.momentum.rsi(df['Close'], window=rsi_period)
        df['RSI_MA'] = df['RSI'].rolling(window=10).mean()  # PLANO: RSI > RSI_MA para momentum
        
        # ATR para stop-loss dinâmico
        df['ATR'] = ta.volatility.average_true_range(
            df['High'], df['Low'], df['Close'], window=14
        )
        
        # PLANO_DE_MELHORAMENTO: ADX com DI+ e DI- para direção
        adx_indicator = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14)
        df['ADX'] = adx_indicator.adx()
        df['DI_plus'] = adx_indicator.adx_pos()   # DI+ (Força compradora)
        df['DI_minus'] = adx_indicator.adx_neg()  # DI- (Força vendedora)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de compra/venda baseados nas condições da estratégia
        
        BLUE_PRINT v1.0 - Refinamento Institucional:
        - Filtro de força de tendência (ADX > 25)
        - RSI não estoura na entrada (45-70)
        - Saída institucional: Preço perde EMA rápida (fraqueza imediata)
        """
        rsi_lower = self.parameters['rsi_lower']
        rsi_upper = self.parameters['rsi_upper']
        rsi_exit = self.parameters['rsi_exit']
        adx_threshold = self.parameters.get('adx_threshold', 25)
        
        # Inicializar coluna de sinais
        df['signal'] = 0
        df['signal_strength'] = 0.0
        
        # === BLUE_PRINT: Condições de COMPRA (Entrada Institucional) ===
        # Filtro 1: ADX > 25 (Tendência Forte - evita whipsaws)
        # Filtro 2: RSI entre 45-70 (não compra estouro)
        # Filtro 3: EMA21 > EMA55 (tendência de alta confirmada)
        
        # OTIMIZAÇÃO #3: Ajuste para alta volatilidade
        # Calcular ATR% para detectar ambientes de alta volatilidade
        df['ATR_pct'] = (df['ATR'] / df['Close']) * 100
        high_volatility = df['ATR_pct'] > 5.0  # ATR > 5% do preço
        
        # Em alta volatilidade, relaxar filtros ADX e RSI
        adx_requirement = np.where(high_volatility, 20, adx_threshold)  # 25 → 20
        rsi_lower_adj = np.where(high_volatility, 40, rsi_lower)  # 45 → 40
        rsi_upper_adj = np.where(high_volatility, 75, rsi_upper)  # 70 → 75
        
        # PLANO_DE_MELHORAMENTO: Adicionar DI+ > DI- (direção) e RSI > RSI_MA (momentum)
        buy_condition = (
            (df['trend_bullish'] == 1) &  # EMA21 > EMA55
            (df['ADX'] > adx_requirement) &  # Tendência forte (ajustável por volatilidade)
            (df['DI_plus'] > df['DI_minus']) &  # PLANO: DI+ > DI- (direção bullish confirmada)
            (df['RSI'] > rsi_lower_adj) &  # RSI não está muito baixo (ajustável)
            (df['RSI'] < rsi_upper_adj) &  # RSI não está sobrecomprado (ajustável)
            (df['RSI'] > df['RSI_MA']) &  # PLANO: RSI acima da sua MA (momentum saudável)
            (df['volume_confirmed'] == 1)  # Volume confirmado
        )
        
        # === BLUE_PRINT: Condições de VENDA (Saída Institucional) ===
        # REGRA PRINCIPAL: Preço perdeu a média rápida (fraqueza imediata)
        # NÃO esperar cruzamento reverso das médias - isso é muito lento!
        institutional_exit = df['Close'] < df['EMA_fast']  # Preço < EMA21
        
        sell_condition = (
            institutional_exit |  # SAÍDA INSTITUCIONAL: Preço < EMA21
            (df['RSI'] > rsi_exit)  # RSI muito sobrecomprado
        )
        
        # Aplicar sinais
        df.loc[buy_condition, 'signal'] = 1
        df.loc[sell_condition, 'signal'] = -1
        
        # Calcular força do sinal (0 a 1)
        df['signal_strength'] = self._calculate_signal_strength(df)
        
        # Criar coluna de posição (para backtesting)
        df['position'] = df['signal'].replace(-1, 0)  # 0 = sem posição, 1 = comprado
        
        # Adicionar stop-loss dinâmico
        df['stop_loss'] = df['Close'] - (2 * df['ATR'])
        df['take_profit'] = df['Close'] + (3 * df['ATR'])
        
        return df
    
    def _calculate_signal_strength(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula a força do sinal baseado em múltiplos fatores
        Retorna valor entre 0 e 1
        """
        strength = pd.Series(0.0, index=df.index)
        
        # Força do ADX (quanto maior, mais forte a tendência)
        adx_strength = np.clip(df['ADX'] / 50, 0, 1)
        
        # Distância entre EMAs (quanto maior, mais forte a tendência)
        ema_distance = np.abs(df['EMA_cross']) / df['Close']
        ema_strength = np.clip(ema_distance * 100, 0, 1)
        
        # Volume relativo
        volume_ratio = df['Volume'] / df['Volume_SMA']
        volume_strength = np.clip((volume_ratio - 1) / 2, 0, 1)
        
        # Combinar com pesos
        strength = (
            0.4 * adx_strength +
            0.3 * ema_strength +
            0.3 * volume_strength
        )
        
        return strength
    
    def get_entry_conditions(self) -> list:
        """Retorna condições de entrada legíveis"""
        return [
            f"EMA {self.parameters['fast_ema']} > EMA {self.parameters['slow_ema']} (tendência de alta)",
            f"Volume > {self.parameters['volume_multiplier']}x média de {self.parameters['volume_sma']} períodos",
            f"RSI entre {self.parameters['rsi_lower']} e {self.parameters['rsi_upper']}",
            "ADX > 25 (tendência forte)"
        ]
    
    def get_exit_conditions(self) -> list:
        """Retorna condições de saída legíveis"""
        return [
            f"EMA {self.parameters['fast_ema']} < EMA {self.parameters['slow_ema']} (fim da tendência)",
            f"RSI > {self.parameters['rsi_exit']} (sobrecomprado extremo)",
            "Stop-loss: Preço - (2 × ATR)",
            "Take-profit: Preço + (3 × ATR)"
        ]
    
    def analyze_trend_strength(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analisa a força atual da tendência
        
        Returns:
            Dicionário com análise da tendência
        """
        if df.empty or 'ADX' not in df.columns:
            return {"error": "Dados insuficientes"}
        
        last_row = df.iloc[-1]
        
        trend_direction = "ALTA" if last_row['trend_bullish'] else "BAIXA"
        
        if last_row['ADX'] > 40:
            trend_strength = "MUITO FORTE"
        elif last_row['ADX'] > 25:
            trend_strength = "FORTE"
        elif last_row['ADX'] > 15:
            trend_strength = "MODERADA"
        else:
            trend_strength = "FRACA"
        
        return {
            "direction": trend_direction,
            "strength": trend_strength,
            "adx_value": float(last_row['ADX']),
            "ema_distance": float(last_row['EMA_cross']),
            "rsi_value": float(last_row['RSI']),
            "volume_confirmed": bool(last_row['volume_confirmed']),
            "current_signal": int(last_row['signal'])
        }


# Função auxiliar para criar instância da estratégia
def create_trend_following_strategy(params: Dict[str, Any] = None) -> TrendFollowingStrategy:
    """
    Factory function para criar instância da estratégia
    
    Args:
        params: Parâmetros customizados
        
    Returns:
        Instância configurada da TrendFollowingStrategy
    """
    return TrendFollowingStrategy(parameters=params)
