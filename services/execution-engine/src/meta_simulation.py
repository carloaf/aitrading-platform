"""
BLUE_PRINT v1.0: Meta-Backtester - Simulador Adaptativo
========================================================

Sistema que testa a capacidade do sistema de trocar de estratégia
dinamicamente baseado no regime de mercado.

Características:
- Itera candle a candle
- Recalcula regime em tempo real
- Troca estratégia automaticamente
- Aplica slippage (0.1%) e taxas (0.1%)
- Registra equity curve completa

Cenários de Stress Test (Obrigatórios):
1. The Bull Run: Jan 2021 - Abr 2021 (Deve lucrar muito)
2. The Chop: Mai 2021 - Jul 2021 (Deve perder pouco)
3. The Crash: Nov 2021 - Jan 2022 (Deve virar para Short rápido)
4. The Recovery: Jan 2023 - Mar 2023 (Deve capturar o fundo)

Autor: "The Legend" (Wall St. & Faria Lima)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import ta
from collections import defaultdict

# Importar componentes do sistema
try:
    from market_regime_detector import MarketRegimeDetector, MarketRegime
    from risk_manager import RiskManager, MarketPhase, VolumeProfile, get_volume_profile, regime_to_phase
    from strategies.trend_following import TrendFollowingStrategy
    from strategies.mean_reversion import MeanReversionStrategy
    from strategies.volatility_breakout import VolatilityBreakoutStrategy
    from strategies.momentum import MomentumStrategy
    from strategies.bear_market_short import BearMarketShortStrategy
    from strategies.breakdown_momentum import BreakdownMomentumStrategy
    from strategies.liquidity_grab import LiquidityGrabStrategy
    from strategies.rsi_divergence import RSIDivergenceStrategy
except ImportError:
    # Para execução standalone
    pass

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Representa um trade executado"""
    entry_time: datetime
    entry_price: float
    direction: str  # 'LONG' ou 'SHORT'
    size: float
    strategy: str
    regime: str
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    status: str = 'OPEN'  # 'OPEN', 'CLOSED', 'STOPPED'
    highest_price: Optional[float] = None  # Para trailing stop em LONG
    lowest_price: Optional[float] = None   # Para trailing stop em SHORT
    exit_reason: str = ''  # STOP_LOSS, TAKE_PROFIT, REGIME_CHANGE, VOLATILITY_CRISIS


@dataclass 
class SimulationResult:
    """Resultado completo da simulação"""
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    regime_changes: int
    strategy_switches: int
    equity_curve: List[float]
    trades: List[Trade]
    regime_history: List[Dict]
    daily_returns: List[float]
    exit_reasons: Dict[str, int] = None  # Contagem de motivos de saída
    debug_stats: Optional[Dict[str, Any]] = None


class StrategySelector:
    """
    Mapeamento de Regime -> Estratégia conforme BLUE_PRINT
    """
    
    # Configuração do BLUE_PRINT (atualizado com RSI Divergence - PASSO 23)
    REGIME_STRATEGY_MAP = {
        MarketRegime.BULL: {
            'long': ['trend_following', 'momentum', 'rsi_divergence_bullish'],  # RSI Divergence bullish para LONG
            'short': ['rsi_divergence_bearish'],  # RSI Divergence bearish detecta topos
            'risk_factor': 1.0
        },
        MarketRegime.BEAR: {
            'long': ['rsi_divergence_bullish'],  # RSI Divergence bullish detecta fundos
            'short': ['breakdown_momentum', 'bear_market_short', 'rsi_divergence_bearish'],
            'risk_factor': 0.8
        },
        MarketRegime.SIDEWAYS: {
            'long': ['mean_reversion', 'liquidity_grab', 'rsi_divergence_bullish'],  # RSI Divergence para reversões
            'short': ['rsi_divergence_bearish'],  # RSI Divergence para topos em range
            'risk_factor': 0.6
        },
        MarketRegime.VOLATILE: {
            'long': ['volatility_breakout'],
            'short': [],  # Cash is King em crise
            'risk_factor': 0.4
        }
    }
    
    @classmethod
    def get_active_strategies(cls, regime: MarketRegime) -> Dict[str, List[str]]:
        """Retorna estratégias ativas para o regime"""
        return cls.REGIME_STRATEGY_MAP.get(regime, cls.REGIME_STRATEGY_MAP[MarketRegime.SIDEWAYS])
    
    @classmethod
    def get_risk_factor(cls, regime: MarketRegime) -> float:
        """Retorna fator de risco para o regime"""
        config = cls.REGIME_STRATEGY_MAP.get(regime, {})
        return config.get('risk_factor', 0.6)


class MetaBacktester:
    """
    Meta-Backtester Adaptativo
    
    Simula trading com troca dinâmica de estratégias baseado no regime.
    """
    
    def __init__(self,
                 initial_capital: float = 100000.0,
                 slippage: float = 0.001,      # 0.1%
                 commission: float = 0.001,     # 0.1%
                 risk_per_trade: float = 0.02,  # 2%
                 max_position_size: float = 0.25,
                 regime_lookback: int = 100,    # FIX: Reduzido de 250 para 100 (compatível com dados menores)
                 use_trailing_stop: bool = True,
                 regime_confirmation_threshold: int = 8,  # PASSO 24.3: Aumentado de 6→8 para reduzir oscillation (era 6 no PASSO 19.5)
                 volatility_crisis_threshold: float = 3.0,  # PASSO 19: 3x ATR normal = crise
                 cash_position_crisis: float = 0.5,  # PASSO 19: 50% em cash durante crise
                 # OPÇÃO B (cirúrgica): Chop-protection só para entradas de momentum em BULL recém-detectado
                 # DESABILITADO por padrão após testes (opt-in via API para tuning futuro)
                 bull_momentum_chop_protection: bool = False,
                 bull_momentum_min_regime_age_candles: int = 12,
                 bull_momentum_cooldown_hours: int = 12,
                 bull_momentum_min_adx: float = 18.0,
                 bull_momentum_adx_window_candles: int = 24,
                 bull_momentum_max_prev_sideways_candles: int = 1_000_000,
                 bull_momentum_min_ema_separation: float = 0.03,
                 # PASSO 25: Kelly Position Sizing
                 use_kelly_sizing: bool = False,
                 kelly_fraction: float = 0.25,
                 kelly_min_trades: int = 30,
                 # PASSO 28: Sentiment filter (opt-in)
                 use_sentiment_filter: bool = False,
                 sentiment_score: float = 0.0,
                 sentiment_min_score: float = -0.2):
        """
        Inicializa o Meta-Backtester
        
        Args:
            initial_capital: Capital inicial
            slippage: Slippage por trade (0.1%)
            commission: Comissão por trade (0.1%)
            risk_per_trade: Risco por trade (2%)
            max_position_size: Tamanho máximo de posição (25%)
            regime_lookback: Candles para detectar regime
            use_trailing_stop: Usar trailing stop (padrão: True)
        """
        self.initial_capital = initial_capital
        self.slippage = slippage
        self.commission = commission
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        self.regime_lookback = regime_lookback
        self.use_trailing_stop = use_trailing_stop
        self.regime_confirmation_threshold = regime_confirmation_threshold  # FIX: Armazenar threshold
        self.volatility_crisis_threshold = volatility_crisis_threshold  # PASSO 19
        self.cash_position_crisis = cash_position_crisis  # PASSO 19

        # Chop-protection (bull recém-detectado) - limitado ao strategy == 'momentum'
        self.bull_momentum_chop_protection = bull_momentum_chop_protection
        self.bull_momentum_min_regime_age_candles = max(0, int(bull_momentum_min_regime_age_candles))
        self.bull_momentum_cooldown_hours = max(0, int(bull_momentum_cooldown_hours))
        self.bull_momentum_min_adx = float(bull_momentum_min_adx)
        self.bull_momentum_adx_window_candles = max(0, int(bull_momentum_adx_window_candles))
        self.bull_momentum_max_prev_sideways_candles = max(0, int(bull_momentum_max_prev_sideways_candles))
        self.bull_momentum_min_ema_separation = max(0.0, float(bull_momentum_min_ema_separation))
        
        # PASSO 25: Kelly Position Sizing
        self.use_kelly_sizing = use_kelly_sizing
        self.kelly_fraction = kelly_fraction
        self.kelly_min_trades = kelly_min_trades

        # PASSO 28: Sentiment filter (opt-in)
        self.use_sentiment_filter = bool(use_sentiment_filter)
        self.sentiment_score = float(sentiment_score)
        self.sentiment_min_score = float(sentiment_min_score)
        
        # Componentes
        self.regime_detector = MarketRegimeDetector()
        self.risk_manager = RiskManager(
            base_risk_per_trade=risk_per_trade,
            max_position_size=max_position_size
        )
        # PASSO 25: Configurar Kelly no RiskManager
        self.risk_manager.kelly_enabled = use_kelly_sizing
        self.risk_manager.kelly_fraction = kelly_fraction
        self.risk_manager.min_trades_for_kelly = kelly_min_trades
        
        # Estado da simulação
        self.reset()
    
    def reset(self):
        """Reseta estado da simulação"""
        self.capital = self.initial_capital
        self.equity_curve = [self.initial_capital]
        self.trades: List[Trade] = []
        self.open_position: Optional[Trade] = None
        self.current_regime = MarketRegime.UNKNOWN
        self.current_strategy = None
        self.regime_history = []
        self.strategy_switches = 0
        self.peak_capital = self.initial_capital
        self.max_drawdown = 0.0
        self.daily_returns = []
        
        # OTIMIZAÇÃO #4: Re-entry tracking
        self.last_stop_time = None  # Timestamp do último stop
        self.last_stop_regime = None  # Regime onde ocorreu o último stop
        self.stops_in_current_regime = 0  # Contador de stops no regime atual
        
        # PASSO 19: Crisis detection
        self.in_crisis_mode = False  # Flag de modo crise
        self.atr_baseline = None  # ATR médio (baseline)
        self.crisis_start_time = None  # Início da crise
        
        # HISTERESE: Regime só muda com confirmação
        self.pending_regime = None  # Regime candidato
        self.pending_regime_count = 0  # Candles consecutivos no regime candidato
        # threshold definido no __init__, não sobrescrever aqui

        # OPÇÃO B: tracking de idade do regime (para bloquear momentum no BULL recém-confirmado)
        self.current_regime_age_candles = 0
        self.last_regime_change_time = None
        self.last_bull_regime_change_time = None
        self.last_bull_regime_change_from = None
        self.last_bull_prev_sideways_candles = None
        
        # OTIMIZAÇÃO #14: Position Sizing Dinâmico
        self.current_drawdown = 0.0  # Drawdown atual
        self.strategy_performance = {}  # Performance por estratégia (últimos trades)
        self.recent_trades_window = 20  # Últimos 20 trades para calcular Sharpe

        # DEBUG/DIAGNÓSTICO: contadores para validar execução de estratégias
        # Mantido simples (dict[str,int]) para serialização fácil no endpoint
        self.debug_stats = {
            'strategy_calls': defaultdict(int),
            'strategy_last_signal': defaultdict(int),
            'entry_accepted': defaultdict(int),
            'entry_rejected_quality': defaultdict(int),
            'entry_rejected_sentiment': defaultdict(int),
            'entry_rejected_chop_protection': defaultdict(int),
            'entry_rejected_exception': defaultdict(int),
            'entry_rejected_missing_signal_col': defaultdict(int),
            'entry_rejected_unknown_strategy': defaultdict(int),
        }
    
    def run_simulation(self,
                       df: pd.DataFrame,
                       strategy_funcs: Dict[str, Callable] = None) -> SimulationResult:
        """
        Executa simulação completa
        
        BLUE_PRINT v1.0 - Algoritmo:
        1. Loop principal (candle a candle)
        2. Detectar regime atual
        3. Selecionar estratégia recomendada
        4. Verificar sinais de entrada/saída
        5. Aplicar slippage e taxas
        6. Registrar equity curve
        
        Args:
            df: DataFrame com OHLCV
            strategy_funcs: Dicionário de funções de estratégia
            
        Returns:
            SimulationResult com todos os resultados
        """
        self.reset()
        
        # Preparar dados
        df = self._prepare_data(df)
        
        # Estratégias disponíveis (funções simplificadas para simulação)
        if strategy_funcs is None:
            strategy_funcs = self._get_default_strategies()
        
        logger.info(f"🚀 Iniciando Meta-Backtest: {len(df)} candles")
        logger.info(f"💰 Capital Inicial: ${self.initial_capital:,.2f}")
        
        prev_day = None
        daily_start_capital = self.capital
        
        # OTIMIZAÇÃO: Log progress a cada 10%
        total_candles = len(df) - self.regime_lookback
        log_interval = max(100, total_candles // 10)
        
        # === LOOP PRINCIPAL (Candle a Candle) ===
        for i in range(self.regime_lookback, len(df)):
            current_bar = df.iloc[i]
            
            # Lookback data para regime detection (precisa ser copy para evitar SettingWithCopyWarning)
            lookback_data = df.iloc[max(0, i-self.regime_lookback):i+1].copy()
            
            # Progress log otimizado
            if (i - self.regime_lookback) % log_interval == 0:
                progress = ((i - self.regime_lookback) / total_candles) * 100
                logger.info(f"   📊 Progresso: {progress:.0f}% ({i-self.regime_lookback}/{total_candles} candles)")
            
            # Tracking diário
            current_day = current_bar.name.date() if hasattr(current_bar.name, 'date') else None
            if prev_day is not None and current_day != prev_day:
                daily_return = (self.capital - daily_start_capital) / daily_start_capital
                self.daily_returns.append(daily_return)
                daily_start_capital = self.capital
            prev_day = current_day
            
            # === PASSO 1: Detectar Regime COM HISTERESE ===
            if i == self.regime_lookback:  # Log apenas no primeiro candle processado
                logger.info(f"🔍 Detectando regime (lookback={len(lookback_data)} candles)...")
            detected_regime = self._detect_regime(lookback_data)
            
            # DEBUG: Log detalhado no primeiro candle
            if i == self.regime_lookback:
                logger.info(f"📊 FIRST_CANDLE_DEBUG: detected={detected_regime.value}, current={self.current_regime.value}, lookback_len={len(lookback_data)}")
            
            # Aplicar histerese - regime só muda se ficar consistente
            if detected_regime != self.current_regime:
                if self.pending_regime == detected_regime:
                    # Mesmo regime candidato - incrementar contador
                    self.pending_regime_count += 1
                else:
                    # Novo regime candidato - resetar contador
                    self.pending_regime = detected_regime
                    self.pending_regime_count = 1
                
                # DEBUG: Log progresso da histerese (primeiro candle e a cada 100)
                if self.pending_regime_count == 1 or (i - self.regime_lookback) % 100 == 0:
                    logger.info(f"📍 Histerese: {detected_regime.value} ({self.pending_regime_count}/{self.regime_confirmation_threshold})")
                
                # Verificar se passou do threshold para confirmar mudança
                if self.pending_regime_count >= self.regime_confirmation_threshold:
                    # CRITICAL: Log mudança de regime (voltou para INFO)
                    logger.info(f"🔄 REGIME_CHANGE: {self.current_regime.value if self.current_regime else 'NONE'} → {detected_regime.value}")
                    old_regime = self.current_regime
                    old_regime_age_candles = self.current_regime_age_candles
                    self.regime_history.append({
                        'time': current_bar.name,
                        'old_regime': self.current_regime.value if self.current_regime else 'NONE',
                        'new_regime': detected_regime.value,
                        'capital': self.capital
                    })
                    self.current_regime = detected_regime

                    # OPÇÃO B: regime-age tracking
                    self.last_regime_change_time = current_bar.name
                    self.current_regime_age_candles = 0
                    if detected_regime == MarketRegime.BULL:
                        self.last_bull_regime_change_time = current_bar.name
                        self.last_bull_regime_change_from = old_regime
                        if old_regime == MarketRegime.SIDEWAYS:
                            self.last_bull_prev_sideways_candles = int(old_regime_age_candles)
                        else:
                            self.last_bull_prev_sideways_candles = None
                    
                    # Reset histerese e contador de stops
                    self.pending_regime = None
                    self.pending_regime_count = 0
                    self.stops_in_current_regime = 0
            else:
                # Regime confirmado - resetar candidato
                self.pending_regime = None
                self.pending_regime_count = 0

                # OPÇÃO B: incrementar idade do regime quando estável
                if self.current_regime is not None:
                    self.current_regime_age_candles += 1
            
            # === PASSO 2: Selecionar Estratégias Candidatas (LONG + SHORT) ===
            active_strategies = StrategySelector.get_active_strategies(self.current_regime)
            risk_factor = StrategySelector.get_risk_factor(self.current_regime)

            candidates: List[tuple[str, str]] = []
            for s in active_strategies.get('long', []):
                candidates.append((s, 'LONG'))
            for s in active_strategies.get('short', []):
                candidates.append((s, 'SHORT'))
            
            # === PASSO 3: Verificar Saídas de Posições Abertas ===
            if self.open_position:
                # PASSO 19: FECHAR POSIÇÃO se entrar em crise
                atr = current_bar.get('ATR', 0)
                atr_ratio = atr / self.atr_baseline if self.atr_baseline and self.atr_baseline > 0 else 1.0
                
                if atr_ratio > self.volatility_crisis_threshold and not self.in_crisis_mode:
                    self.in_crisis_mode = True
                    self.crisis_start_time = current_bar.name
                    logger.warning(f"🚨 CRISE DETECTADA em {current_bar.name}: ATR {atr_ratio:.2f}x normal!")
                    logger.warning(f"⚠️ Fechando posição aberta por segurança...")
                    self._close_position(current_bar, 'VOLATILITY_CRISIS')
                else:
                    exit_signal = self._check_exit_signal(
                        self.open_position, current_bar, lookback_data
                    )
                    
                    if exit_signal:
                        self._close_position(current_bar, exit_signal)
            
            # === PASSO 4: Verificar Entradas ===
            if not self.open_position and candidates:
                # DEBUG: Log candidatos (a cada 500 candles)
                if (i - self.regime_lookback) % 500 == 0:
                    cand_str = ', '.join([f"{s}:{d}" for s, d in candidates[:5]])
                    suffix = "" if len(candidates) <= 5 else f" (+{len(candidates)-5}...)"
                    logger.info(f"🎯 Regime: {self.current_regime.value} | Candidates: {cand_str}{suffix}")

                chosen_strategy = None
                chosen_direction = None
                for strategy_name, direction in candidates:
                    if self._check_entry_signal(strategy_name, direction, lookback_data, strategy_funcs):
                        chosen_strategy = strategy_name
                        chosen_direction = direction
                        break

                if chosen_strategy and chosen_direction:
                    if chosen_strategy != self.current_strategy:
                        self.strategy_switches += 1
                        self.current_strategy = chosen_strategy

                    logger.info(f"🟢 ENTRY SIGNAL: {chosen_strategy} {chosen_direction} @ ${current_bar['Close']:.2f}")
                    self._open_position(
                        current_bar, chosen_direction, chosen_strategy,
                        risk_factor, lookback_data
                    )
            
            # === PASSO 5: Atualizar Equity ===
            self._update_equity(current_bar)
        
        # Fechar posição aberta no final
        if self.open_position:
            self._close_position(df.iloc[-1], 'END_OF_DATA')
        
        # Calcular métricas finais
        return self._calculate_results()
    
    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepara dados com indicadores básicos"""
        df = df.copy()
        
        # Normalizar nomes de colunas
        df.columns = [c.capitalize() for c in df.columns]
        
        # Garantir que temos todas as colunas necessárias
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required:
            if col not in df.columns:
                # Tentar encontrar variação
                for c in df.columns:
                    if c.lower() == col.lower():
                        df[col] = df[c]
                        break
        
        # Adicionar indicadores básicos para estratégias
        df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['SMA200'] = ta.trend.sma_indicator(df['Close'], window=200)
        df['EMA21'] = ta.trend.ema_indicator(df['Close'], window=21)
        df['EMA55'] = ta.trend.ema_indicator(df['Close'], window=55)
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
        df['ADX'] = ta.trend.adx(df['High'], df['Low'], df['Close'], window=14)
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2.0)
        df['BB_upper'] = bb.bollinger_hband()
        df['BB_lower'] = bb.bollinger_lband()
        df['BB_middle'] = bb.bollinger_mavg()
        
        # Volume
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        
        # FIX: Só remover NaN das colunas essenciais de curto prazo (não SMA200!)
        # Isso permite processar mais candles quando não temos 200+ de histórico
        essential_cols = ['RSI', 'ATR', 'ADX', 'SMA20', 'BB_upper', 'BB_lower']
        df = df.dropna(subset=essential_cols)
        
        return df
    
    def _detect_regime(self, df: pd.DataFrame) -> MarketRegime:
        """Detecta regime de mercado atual - OTIMIZADO"""
        try:
            analysis = self.regime_detector.analyze(df)
            # OTIMIZAÇÃO: Removido log excessivo (estava em CADA iteração)
            return analysis.regime
        except Exception as e:
            # Log apenas erros reais
            if not hasattr(self, '_regime_error_logged'):
                logger.warning(f"Erro detectando regime: {e}")
                self._regime_error_logged = True
            return MarketRegime.UNKNOWN
    
    def _calculate_strategy_sharpe(self, strategy: str) -> float:
        """
        Calcula Sharpe Ratio da estratégia nos últimos N trades
        
        Args:
            strategy: Nome da estratégia
            
        Returns:
            Sharpe ratio (padrão 1.0 se sem dados)
        """
        # Filtrar últimos trades da estratégia
        strategy_trades = [t for t in self.trades 
                          if t.strategy == strategy and t.pnl is not None]
        
        if len(strategy_trades) < 5:  # Mínimo 5 trades para calcular
            return 1.0  # Sharpe neutro
        
        # Pegar últimos N trades
        recent = strategy_trades[-self.recent_trades_window:]
        
        # Calcular retornos percentuais
        returns = [t.pnl_pct / 100.0 for t in recent]
        
        if not returns:
            return 1.0
        
        # Sharpe = média / desvio padrão (anualizado)
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 1.0
        
        sharpe = (mean_return / std_return) * np.sqrt(252)  # Anualizado
        
        # Limitar entre 0.1 e 3.0
        return max(0.1, min(sharpe, 3.0))
    
    def _calculate_current_drawdown(self) -> float:
        """
        Calcula drawdown atual desde o pico
        
        Returns:
            Drawdown em percentual (0.0 a 1.0)
        """
        if self.capital >= self.peak_capital:
            return 0.0
        
        dd = (self.peak_capital - self.capital) / self.peak_capital
        return dd
    
    def _calculate_historical_stats(self) -> dict:
        """
        Calcula estatísticas históricas para Kelly Criterion
        
        PASSO 25: Usado para dimensionar posição via Kelly Position Sizing
        
        Returns:
            dict com win_rate, avg_win, avg_loss, num_trades
        """
        completed_trades = [t for t in self.trades if t.pnl is not None]
        
        if len(completed_trades) == 0:
            return {
                'win_rate': None,
                'avg_win': None,
                'avg_loss': None,
                'num_trades': 0
            }
        
        wins = [t.pnl for t in completed_trades if t.pnl > 0]
        losses = [abs(t.pnl) for t in completed_trades if t.pnl < 0]
        
        win_rate = len(wins) / len(completed_trades) if completed_trades else None
        avg_win = np.mean(wins) if wins else None
        avg_loss = np.mean(losses) if losses else None
        
        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'num_trades': len(completed_trades)
        }
    
    def _calculate_setup_quality(self, df: pd.DataFrame, strategy: str = None, regime: MarketRegime = None) -> float:
        """
        Calcula score de qualidade do setup (0-100)
        
        PASSO 23.6: Lógica adaptativa para mean-reversion vs trend-following
        
        Para estratégias de TENDÊNCIA (trend_following, momentum, breakdown_momentum):
        - Volume acima da média = bom
        - ADX alto = bom
        - EMAs separadas = bom
        
        Para estratégias de REVERSÃO em SIDEWAYS (rsi_divergence_*, mean_reversion, liquidity_grab):
        - Volume acima da média = bom (confirma interesse)
        - ADX BAIXO = bom (mercado lateralizado = ideal para reversão)
        - EMAs PRÓXIMAS = bom (sem tendência forte = espaço para reversão)
        
        Returns:
            Score 0-100
        """
        # Identificar se é estratégia mean-reversion
        mean_reversion_strategies = [
            'rsi_divergence_bullish', 'rsi_divergence_bearish',
            'mean_reversion', 'liquidity_grab'
        ]
        is_mean_reversion = strategy in mean_reversion_strategies if strategy else False
        is_sideways = regime == MarketRegime.SIDEWAYS if regime else False
        
        # Usar lógica invertida para mean-reversion em SIDEWAYS
        use_reversion_logic = is_mean_reversion and is_sideways
        
        try:
            score = 0
            
            # 1. VOLUME QUALITY (0-25 pontos) - Igual para ambos
            # Volume alto confirma interesse no movimento (reversão ou continuação)
            if 'Volume' in df.columns and 'Volume_SMA' in df.columns:
                volume_ratio = df['Volume'].iloc[-1] / df['Volume_SMA'].iloc[-1]
                if volume_ratio > 2.5:
                    score += 25
                elif volume_ratio > 2.0:
                    score += 18
                elif volume_ratio > 1.5:
                    score += 12
                elif volume_ratio > 1.2:
                    score += 6
                else:
                    score += 0
            
            # 2. VOLATILITY QUALITY (0-25 pontos) - Igual para ambos
            if 'ATR' in df.columns:
                atr = df['ATR'].iloc[-1]
                atr_ma = df['ATR'].rolling(20).mean().iloc[-1]
                atr_ratio = atr / atr_ma if atr_ma > 0 else 1.0
                
                if 0.8 <= atr_ratio <= 1.5:
                    score += 25
                elif 0.6 <= atr_ratio <= 2.0:
                    score += 15
                else:
                    score += 5
            
            # 3. TREND CLARITY (0-25 pontos) - LÓGICA INVERTIDA para reversion
            if 'EMA21' in df.columns and 'EMA55' in df.columns:
                ema21 = df['EMA21'].iloc[-1]
                ema55 = df['EMA55'].iloc[-1]
                price = df['Close'].iloc[-1]
                ema_separation = abs(ema21 - ema55) / price
                
                if use_reversion_logic:
                    # MEAN-REVERSION em SIDEWAYS: EMAs próximas = BOM (mercado sem tendência)
                    if ema_separation < 0.01:  # < 1% (muito próximas)
                        score += 25
                    elif ema_separation < 0.015:
                        score += 20
                    elif ema_separation < 0.02:
                        score += 15
                    elif ema_separation < 0.03:
                        score += 10
                    else:
                        score += 5  # EMAs muito separadas = tendência forte, ruim para reversão
                else:
                    # TREND-FOLLOWING: EMAs separadas = BOM (tendência clara)
                    if ema_separation > 0.05:
                        score += 25
                    elif ema_separation > 0.04:
                        score += 18
                    elif ema_separation > 0.03:
                        score += 12
                    elif ema_separation > 0.02:
                        score += 6
                    else:
                        score += 0
            
            # 4. TREND STRENGTH via ADX (0-25 pontos) - LÓGICA INVERTIDA para reversion
            if 'ADX' in df.columns:
                adx = df['ADX'].iloc[-1]
                
                if use_reversion_logic:
                    # MEAN-REVERSION em SIDEWAYS: ADX baixo = BOM (mercado lateralizado)
                    if adx < 15:  # Muito lateralizado = ideal para reversão
                        score += 25
                    elif adx < 20:
                        score += 20
                    elif adx < 25:
                        score += 15
                    elif adx < 30:
                        score += 10
                    else:
                        score += 5  # ADX alto = tendência forte, ruim para reversão
                else:
                    # TREND-FOLLOWING: ADX alto = BOM (tendência forte)
                    if adx > 35:
                        score += 25
                    elif adx > 30:
                        score += 18
                    elif adx > 25:
                        score += 12
                    elif adx > 20:
                        score += 6
                    else:
                        score += 0
            
            # Log para debug
            if use_reversion_logic:
                logger.debug(f"📊 Setup quality (REVERSION mode): {score} for {strategy} in {regime.value if regime else 'N/A'}")
            
            return score
            
        except Exception as e:
            logger.debug(f"Erro calculando qualidade setup: {e}")
            return 50  # Score neutro em caso de erro
    
    def _check_entry_signal(self,
                            strategy: str,
                            direction: str,
                            df: pd.DataFrame,
                            strategy_funcs: Dict) -> bool:
        """Verifica se há sinal de entrada"""
        
        if strategy not in strategy_funcs:
            self.debug_stats['entry_rejected_unknown_strategy'][strategy] += 1
            return False

        self.debug_stats['strategy_calls'][strategy] += 1
        
        # OTIMIZAÇÃO #4: Re-entry cooldown logic
        if self.last_stop_time is not None:
            current_time = df.index[-1]
            time_since_stop = current_time - self.last_stop_time
            
            # Determinar cooldown period baseado no regime
            if self.current_regime == MarketRegime.BULL:
                cooldown_hours = 4   # BULL: Cooldown curto para não perder momentum
            elif self.current_regime == MarketRegime.SIDEWAYS:
                cooldown_hours = 72  # FIX: SIDEWAYS: Cooldown longo (3 dias) para evitar whipsaw
            else:
                cooldown_hours = 24  # Outros regimes: Cooldown padrão 24h
            
            # Verificar se ainda está em cooldown
            if time_since_stop < timedelta(hours=cooldown_hours):
                logger.debug(f"⏸️ Cooldown ativo: {time_since_stop} < {cooldown_hours}h")
                return False
            
            # Máximo de stops por regime (proteção contra overtrading)
            max_stops = 1 if self.current_regime == MarketRegime.SIDEWAYS else 2
            if self.stops_in_current_regime >= max_stops:
                logger.debug(f"🚫 Max stops ({max_stops}) atingido no regime {self.current_regime.value}")
                return False
        
        try:
            # Executar função da estratégia
            result_df = strategy_funcs[strategy](df.copy())
            
            if 'signal' not in result_df.columns:
                self.debug_stats['entry_rejected_missing_signal_col'][strategy] += 1
                return False
            
            last_signal = result_df['signal'].iloc[-1]
            self.debug_stats['strategy_last_signal'][f"{strategy}:{last_signal}"] += 1

            # Só faz sentido avaliar qualidade do setup se existe um sinal de entrada.
            # Evita rejeições/overhead em candles com HOLD.
            if direction == 'LONG':
                is_entry_signal = last_signal in ['BUY', 1]
            elif direction == 'SHORT':
                is_entry_signal = last_signal in ['SHORT', 'SELL', -1]
            else:
                is_entry_signal = False

            if not is_entry_signal:
                return False

            # PASSO 28: Sentiment filter (opt-in)
            # Objetivo: bloquear LONG quando sentiment agregado está negativo (ex.: notícias ruins)
            if self.use_sentiment_filter and direction == 'LONG':
                if self.sentiment_score < self.sentiment_min_score:
                    self.debug_stats['entry_rejected_sentiment'][f"{strategy}:LONG:{self.current_regime.value}"] += 1
                    logger.debug(
                        f"📰 Sentiment filter: bloqueando LONG (score {self.sentiment_score:.3f} < {self.sentiment_min_score:.3f})"
                    )
                    return False
            
            # PASSO 17: FILTRO DE QUALIDADE DE SETUP
            # PASSO 23.6: Passar strategy e regime para lógica adaptativa
            setup_quality = self._calculate_setup_quality(df, strategy=strategy, regime=self.current_regime)
            
            # Reverted to original thresholds
            # PASSO 24.3: Ajustes Q3/2025 - Aumentado min_quality SIDEWAYS
            if self.current_regime == MarketRegime.BULL:
                min_quality = 45  # BULL: mais permissivo
            elif self.current_regime == MarketRegime.SIDEWAYS:
                min_quality = 70  # SIDEWAYS: mais rigoroso (AJUSTADO de 60→70)
            else:
                min_quality = 50  # BEAR: Padrão
            
            if setup_quality < min_quality:
                logger.debug(f"❌ Setup quality baixa: {setup_quality:.1f} < {min_quality} (regime: {self.current_regime.value})")
                self.debug_stats['entry_rejected_quality'][f"{strategy}:{self.current_regime.value}"] += 1
                return False

            # OPÇÃO B (cirúrgica): proteger whipsaw bull↔sideways
            # Só bloqueia entradas do strategy == 'momentum' durante o BULL recém-confirmado.
            if (
                self.bull_momentum_chop_protection
                and strategy == 'momentum'
                and self.current_regime == MarketRegime.BULL
                and self.last_bull_regime_change_time is not None
                and self.last_bull_regime_change_from == MarketRegime.SIDEWAYS
                and self.last_bull_prev_sideways_candles is not None
                and self.last_bull_prev_sideways_candles <= self.bull_momentum_max_prev_sideways_candles
            ):
                # Se o trend já está claramente estabelecido, não bloqueia (preserva entradas boas em BULL forte)
                trend_is_strong = False
                if self.bull_momentum_min_ema_separation > 0 and 'EMA21' in df.columns and 'EMA55' in df.columns and 'Close' in df.columns:
                    price = float(df['Close'].iloc[-1]) if len(df) > 0 else 0.0
                    if price > 0:
                        ema21 = float(df['EMA21'].iloc[-1])
                        ema55 = float(df['EMA55'].iloc[-1])
                        ema_separation = abs(ema21 - ema55) / price
                        if ema_separation >= self.bull_momentum_min_ema_separation:
                            trend_is_strong = True

                if not trend_is_strong:
                    current_time = df.index[-1]
                    time_since_bull = current_time - self.last_bull_regime_change_time

                    if self.bull_momentum_cooldown_hours > 0 and time_since_bull < timedelta(hours=self.bull_momentum_cooldown_hours):
                        self.debug_stats['entry_rejected_chop_protection'][f"{strategy}:cooldown:{self.current_regime.value}"] += 1
                        logger.debug(
                            f"⏸️ Chop-protection: cooldown BULL {time_since_bull} < {self.bull_momentum_cooldown_hours}h"
                        )
                        return False

                    if self.current_regime_age_candles < self.bull_momentum_min_regime_age_candles:
                        self.debug_stats['entry_rejected_chop_protection'][f"{strategy}:age:{self.current_regime.value}"] += 1
                        logger.debug(
                            f"⏸️ Chop-protection: idade BULL {self.current_regime_age_candles} < {self.bull_momentum_min_regime_age_candles} candles"
                        )
                        return False

                    # ADX mínimo somente na janela inicial do BULL
                    if self.bull_momentum_adx_window_candles > 0 and self.current_regime_age_candles <= self.bull_momentum_adx_window_candles:
                        adx = float(df['ADX'].iloc[-1]) if 'ADX' in df.columns and len(df) > 0 else 0.0
                        if adx < self.bull_momentum_min_adx:
                            self.debug_stats['entry_rejected_chop_protection'][f"{strategy}:adx:{self.current_regime.value}"] += 1
                            logger.debug(
                                f"⏸️ Chop-protection: ADX {adx:.1f} < {self.bull_momentum_min_adx:.1f} (janela {self.bull_momentum_adx_window_candles} candles)"
                            )
                            return False
            
            # Removido: OPÇÃO 3 - Filtro SMA200 não funcionou bem
            
            # PASSO 18: Removido RSI momentum filter - muito restritivo
            # A qualidade de setup já filtra entradas ruins
            
            # OTIMIZAÇÃO #4: Re-entry em BULL requer confirmação extra de momentum
            if self.last_stop_time is not None and self.current_regime == MarketRegime.BULL:
                # Exigir EMA crossover como confirmação de novo momentum
                if 'EMA21' in df.columns and 'EMA55' in df.columns:
                    ema21_current = df['EMA21'].iloc[-1]
                    ema55_current = df['EMA55'].iloc[-1]
                    ema21_prev = df['EMA21'].iloc[-2]
                    ema55_prev = df['EMA55'].iloc[-2]
                    
                    # Confirmar crossover bullish (EMA21 acabou de cruzar EMA55 pra cima)
                    bullish_crossover = (ema21_current > ema55_current) and (ema21_prev <= ema55_prev)
                    
                    if not bullish_crossover and (ema21_current <= ema55_current):
                        logger.debug(f"⏸️ Re-entry em BULL requer EMA crossover bullish")
                        return False
            
            # Se chegou aqui, há sinal de entrada e passou no filtro de qualidade
            if direction == 'LONG':
                logger.debug(f"✅ Sinal LONG detectado: {last_signal} | Quality: {setup_quality:.1f}")
                self.debug_stats['entry_accepted'][f"{strategy}:LONG:{self.current_regime.value}"] += 1
                return True
            elif direction == 'SHORT':
                logger.debug(f"✅ Sinal SHORT detectado: {last_signal} | Quality: {setup_quality:.1f}")
                self.debug_stats['entry_accepted'][f"{strategy}:SHORT:{self.current_regime.value}"] += 1
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Erro verificando entrada: {e}")
            self.debug_stats['entry_rejected_exception'][strategy] += 1
            return False
    
    def _check_exit_signal(self, 
                           position: Trade, 
                           current_bar: pd.Series,
                           df: pd.DataFrame) -> Optional[str]:
        """Verifica se deve sair da posição"""
        
        entry_price = position.entry_price
        current_price = current_bar['Close']
        current_high = current_bar['High']
        current_low = current_bar['Low']
        atr = current_bar.get('ATR', current_price * 0.02)
        
        # PASSO 20: Take-profit otimizado para stop 2.0x ATR
        # PASSO 24.3: Ajustes Q3/2025 - Aumentado TP SIDEWAYS para melhorar R/R
        if self.current_regime == MarketRegime.BULL:
            tp_multiplier = 4.0  # BULL: TP 4x / Stop 2x = R/R 2:1
        elif self.current_regime == MarketRegime.BEAR:
            tp_multiplier = 2.5  # BEAR: TP 2.5x / Stop 2x = R/R 1.25:1
        elif self.current_regime == MarketRegime.SIDEWAYS:
            tp_multiplier = 2.5  # SIDEWAYS: TP 2.5x / Stop 2x = R/R 1.25:1 (AJUSTADO de 2.0x → 2.5x)
        else:
            tp_multiplier = 2.5  # Outros: moderado
        
        tp_distance = tp_multiplier * atr
        
        # PASSO 19.5: Calcular P&L atual em ATRs para trailing dinâmico
        if position.direction == 'LONG':
            current_pnl_atr = (current_price - entry_price) / atr if atr > 0 else 0
        else:
            current_pnl_atr = (entry_price - current_price) / atr if atr > 0 else 0
        
        if position.direction == 'LONG':
            # PASSO 19.5: TRAILING STOP EM 3 FASES
            if self.use_trailing_stop:
                # Atualizar highest_price desde entry
                if position.highest_price is None:
                    position.highest_price = max(entry_price, current_high)
                else:
                    position.highest_price = max(position.highest_price, current_high)
                
                # PASSO 20: Stop MAIS LARGO para reduzir stop-outs
                # PASSO 24.3: Trailing stop otimizado (Ajuste 4) ✅
                # FASE 1: P&L < 0.5x ATR → Stop fixo 2.0x ATR (mais espaço)
                # FASE 2: P&L >= 0.5x ATR → Break-even (protege capital) ✅
                # FASE 3: P&L >= 1.5x ATR → Trailing 1.5x ATR (deixa winner correr)
                if current_pnl_atr >= 1.5:
                    stop_price = position.highest_price - (1.5 * atr)
                elif current_pnl_atr >= 0.5:
                    stop_price = entry_price  # Break-even protection ✅
                else:
                    stop_price = entry_price - (2.0 * atr)  # Otimizado: 2.0x ATR
            else:
                # Stop fixo original: entry - (2 × ATR)
                stop_price = entry_price - (2 * atr)
            
            tp_price = entry_price + tp_distance
            
            if current_low <= stop_price:
                return 'STOP_LOSS'
            if current_high >= tp_price:
                return 'TAKE_PROFIT'
            
            # DESABILITADO: Saída institucional estava impedindo TP
            # if current_price < current_bar.get('EMA21', entry_price):
            #     return 'INSTITUTIONAL_EXIT'
                
        else:  # SHORT
            # PASSO 19.5: TRAILING STOP EM 3 FASES para SHORT
            if self.use_trailing_stop:
                # Atualizar lowest_price desde entry
                if position.lowest_price is None:
                    position.lowest_price = min(entry_price, current_low)
                else:
                    position.lowest_price = min(position.lowest_price, current_low)
                
                # PASSO 20: Stop MAIS LARGO para reduzir stop-outs
                # PASSO 24.3: Trailing stop otimizado para SHORT (Ajuste 4)
                # FASE 1: P&L < 0.5x ATR → Stop fixo 2.0x ATR (mais espaço)
                # FASE 2: P&L >= 0.5x ATR → Break-even (protege capital) ✅
                # FASE 3: P&L >= 1.5x ATR → Trailing 1.5x ATR (deixa winner correr)
                if current_pnl_atr >= 1.5:
                    stop_price = position.lowest_price + (1.5 * atr)
                elif current_pnl_atr >= 0.5:
                    stop_price = entry_price
                else:
                    stop_price = entry_price + (2.0 * atr)  # Otimizado: 2.0x ATR
            else:
                # Stop fixo original: entry + (2 × ATR)
                stop_price = entry_price + (2 * atr)
            
            tp_price = entry_price - tp_distance
            
            if current_high >= stop_price:
                return 'STOP_LOSS'
            if current_low <= tp_price:
                return 'TAKE_PROFIT'
        
        # Verificar mudança de regime (pode forçar saída)
        # PASSO 18: Proteger trades vencedores - não sair por REGIME_CHANGE se P&L > 1.5x ATR
        active = StrategySelector.get_active_strategies(self.current_regime)
        
        # current_pnl_atr já calculado acima no PASSO 19.5
        
        # Se trade está vencendo > 1.5x ATR, deixar TP/SL trabalhar
        if current_pnl_atr > 1.5:
            return None  # Protege trade vencedor
        
        if position.direction == 'LONG' and not active['long']:
            return 'REGIME_CHANGE'
        if position.direction == 'SHORT' and not active['short']:
            return 'REGIME_CHANGE'
        
        return None
    
    def _open_position(self,
                       bar: pd.Series,
                       direction: str,
                       strategy: str,
                       risk_factor: float,
                       df: pd.DataFrame):
        """Abre nova posição"""
        
        # PASSO 19: Verificar se está em modo crise (volatilidade extrema)
        atr = bar.get('ATR', 0)
        if self.atr_baseline is None or len(df) >= 100:
            # Calcular ATR baseline (média dos últimos 100 candles)
            self.atr_baseline = df['ATR'].tail(100).mean() if len(df) >= 100 else df['ATR'].mean()
        
        atr_ratio = atr / self.atr_baseline if self.atr_baseline > 0 else 1.0
        
        # Detectar crise: ATR atual > 3x ATR normal
        if atr_ratio > self.volatility_crisis_threshold:
            if not self.in_crisis_mode:
                self.in_crisis_mode = True
                self.crisis_start_time = bar.name
                logger.warning(f"🚨 CRISE DETECTADA em {bar.name}: ATR {atr_ratio:.2f}x normal! Entrando em modo proteção...")
            
            # NÃO ABRIR NOVAS POSIÇÕES durante crise
            logger.info(f"⛔ Posição bloqueada: Sistema em modo crise (ATR {atr_ratio:.2f}x)")
            return
        elif self.in_crisis_mode:
            # Sair do modo crise quando volatilidade normalizar
            self.in_crisis_mode = False
            logger.info(f"✅ Fim da crise em {bar.name}: ATR normalizado ({atr_ratio:.2f}x). Retomando operações.")
        
        entry_price = bar['Close']
        
        # Aplicar slippage
        if direction == 'LONG':
            entry_price *= (1 + self.slippage)
        else:
            entry_price *= (1 - self.slippage)
        
        # Calcular stop-loss
        atr = bar.get('ATR', entry_price * 0.02)
        stop_distance = 2 * atr
        
        if direction == 'LONG':
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance
        
        # Calcular tamanho da posição
        regime_phase = regime_to_phase(self.current_regime.value)
        volume_profile = get_volume_profile(bar['Volume'], bar.get('Volume_SMA', bar['Volume']))
        atr_ratio = atr / df['ATR'].mean() if df['ATR'].mean() > 0 else 1.0
        
        # PASSO 14: Calcular performance da estratégia e drawdown atual
        strategy_sharpe = self._calculate_strategy_sharpe(strategy)
        current_dd = self._calculate_current_drawdown()
        
        # PASSO 25: Calcular estatísticas históricas para Kelly Criterion
        hist_stats = self._calculate_historical_stats()
        
        risk_params = self.risk_manager.calculate_position_size(
            capital=self.capital,
            entry_price=entry_price,
            stop_loss_price=stop_price,
            regime=regime_phase,
            regime_confidence=80.0,
            volume_profile=volume_profile,
            volatility_atr_ratio=atr_ratio,
            strategy_sharpe=strategy_sharpe,
            current_drawdown=current_dd,
            # PASSO 25: Estatísticas para Kelly
            win_rate=hist_stats['win_rate'],
            avg_win=hist_stats['avg_win'],
            avg_loss=hist_stats['avg_loss'],
            num_trades=hist_stats['num_trades']
        )
        
        # Tamanho em unidades de capital
        position_size = self.capital * risk_params.position_size
        
        # Aplicar comissão
        commission_cost = position_size * self.commission
        
        # Criar trade
        self.open_position = Trade(
            entry_time=bar.name,
            entry_price=entry_price,
            direction=direction,
            size=position_size,
            strategy=strategy,
            regime=self.current_regime.value
        )
        
        # Deduzir comissão
        self.capital -= commission_cost
        
        # OTIMIZAÇÃO: Log mudou para debug (não imprime por padrão)
    
    def _close_position(self, bar: pd.Series, reason: str):
        """Fecha posição atual"""
        
        if not self.open_position:
            return
        
        exit_price = bar['Close']
        
        # Aplicar slippage
        if self.open_position.direction == 'LONG':
            exit_price *= (1 - self.slippage)
        else:
            exit_price *= (1 + self.slippage)
        
        # Calcular PnL
        if self.open_position.direction == 'LONG':
            pnl_pct = (exit_price - self.open_position.entry_price) / self.open_position.entry_price
        else:
            pnl_pct = (self.open_position.entry_price - exit_price) / self.open_position.entry_price
        
        pnl = self.open_position.size * pnl_pct
        
        # Aplicar comissão de saída
        commission_cost = self.open_position.size * self.commission
        pnl -= commission_cost
        
        # Atualizar capital - apenas adiciona PnL (size não foi deduzido na abertura)
        self.capital += pnl
        
        # Atualizar trade
        self.open_position.exit_time = bar.name
        self.open_position.exit_price = exit_price
        self.open_position.pnl = pnl
        self.open_position.pnl_pct = pnl_pct * 100
        self.open_position.status = reason
        self.open_position.exit_reason = reason  # Registrar motivo de saída
        
        # DEBUG: Log fechamento
        emoji = "🟢" if pnl > 0 else "🔴"
        logger.info(f"{emoji} CLOSE: {self.open_position.strategy} | Reason: {reason} | PnL: ${pnl:.2f} ({pnl_pct*100:.2f}%)")
        
        # OTIMIZAÇÃO #4: Tracking de stops para re-entry logic
        if reason == 'STOP_LOSS':
            self.last_stop_time = bar.name
            self.last_stop_regime = self.current_regime
            
            # Incrementar contador de stops se ainda no mesmo regime
            if self.current_regime == self.last_stop_regime:
                self.stops_in_current_regime += 1
            else:
                # Novo regime, resetar contador
                self.stops_in_current_regime = 1
        
        # Adicionar à lista de trades
        self.trades.append(self.open_position)
        
        logger.debug(f"📉 CLOSE {reason}: PnL ${pnl:.2f} ({pnl_pct*100:.2f}%)")
        
        self.open_position = None
    
    def _update_equity(self, bar: pd.Series):
        """Atualiza equity curve e drawdown"""
        
        current_equity = self.capital
        
        # Se tem posição aberta, adicionar MTM
        if self.open_position:
            current_price = bar['Close']
            if self.open_position.direction == 'LONG':
                mtm_pnl = (current_price - self.open_position.entry_price) / self.open_position.entry_price
            else:
                mtm_pnl = (self.open_position.entry_price - current_price) / self.open_position.entry_price
            
            current_equity += self.open_position.size * mtm_pnl
        
        self.equity_curve.append(current_equity)
        
        # Atualizar drawdown
        if current_equity > self.peak_capital:
            self.peak_capital = current_equity
        
        drawdown = (self.peak_capital - current_equity) / self.peak_capital
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
    
    def _calculate_results(self) -> SimulationResult:
        """Calcula métricas finais"""
        
        total_return = self.capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        # Estatísticas de trades
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0
        
        # Profit Factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        # When no losses, use large but finite number for JSON serialization
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.99
        
        # Sharpe Ratio (anualizado)
        if self.daily_returns:
            returns_array = np.array(self.daily_returns)
            sharpe = np.sqrt(252) * (returns_array.mean() / returns_array.std()) if returns_array.std() > 0 else 0
            
            # Sortino Ratio (apenas downside volatility)
            negative_returns = returns_array[returns_array < 0]
            downside_std = negative_returns.std() if len(negative_returns) > 0 else returns_array.std()
            sortino = np.sqrt(252) * (returns_array.mean() / downside_std) if downside_std > 0 else 0
        else:
            sharpe = 0
            sortino = 0
        
        # Contar motivos de saída
        from collections import Counter
        exit_reasons = Counter()
        for trade in self.trades:
            if hasattr(trade, 'exit_reason') and trade.exit_reason:
                exit_reasons[trade.exit_reason] += 1
        
        debug_out = {
            k: dict(v) for k, v in self.debug_stats.items()
        }

        return SimulationResult(
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            max_drawdown=self.max_drawdown * 100,
            max_drawdown_pct=self.max_drawdown * 100,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate * 100,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            regime_changes=len(self.regime_history),
            strategy_switches=self.strategy_switches,
            equity_curve=self.equity_curve,
            trades=self.trades,
            regime_history=self.regime_history,
            daily_returns=self.daily_returns,
            exit_reasons=dict(exit_reasons),
            debug_stats=debug_out
        )
    
    def _get_default_strategies(self) -> Dict[str, Callable]:
        """Retorna estratégias padrão para simulação"""
        
        def trend_following_func(df):
            df = df.copy()
            df['signal'] = 'HOLD'
            
            # Trend Following - Condições balanceadas
            buy = (
                (df['EMA21'] > df['EMA55']) &
                (df['ADX'] > 22) &  # ADX moderado
                (df['RSI'] > 45) & (df['RSI'] < 72)  # RSI nem oversold nem overbought
            )
            sell = df['Close'] < df['EMA55']  # Sair quando perde tendência
            
            df.loc[buy, 'signal'] = 'BUY'
            df.loc[sell, 'signal'] = 'SELL'
            return df
        
        def momentum_func(df):
            df = df.copy()
            df['signal'] = 'HOLD'
            df['ROC'] = ta.momentum.roc(df['Close'], window=10)
            df['ROC_MA'] = df['ROC'].rolling(5).mean()  # Média de 5 períodos para suavizar
            
            # Momentum - só entra em momentum forte
            buy = (df['ROC_MA'] > 2) & (df['EMA21'] > df['EMA55'])  # ROC > 2% + tendência
            sell = df['ROC_MA'] < -1  # ROC < -1% para sair
            
            df.loc[buy, 'signal'] = 'BUY'
            df.loc[sell, 'signal'] = 'SELL'
            return df
        
        def mean_reversion_func(df):
            df = df.copy()
            df['signal'] = 'HOLD'
            
            # Mean Reversion - só em oversold extremo
            macro_bull = df['Close'] > df['SMA200']
            # Mean Reversion - só em oversold extremo com confirmação
            buy = (
                (df['Close'] <= df['BB_lower']) &
                (df['RSI'] < 30) &                         # RSI muito baixo
                (df['Close'] > df['Close'].shift(1))       # Confirmação de reversão
            )
            sell = (
                (df['Close'] >= df['BB_middle']) |
                (df['RSI'] > 60)
            )
            
            df.loc[buy, 'signal'] = 'BUY'
            df.loc[sell, 'signal'] = 'SELL'
            return df
        
        def volatility_breakout_func(df):
            df = df.copy()
            df['signal'] = 'HOLD'
            
            df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle']
            df['BB_width_min'] = df['BB_width'].rolling(20).min()
            df['is_squeezing'] = df['BB_width'] < (df['BB_width_min'] * 1.15)
            df['high_channel'] = df['High'].rolling(20).max()
            
            # Breakout - só com squeeze confirmado e volume
            buy = (
                (df['is_squeezing'].shift(1) == True) &
                (df['Close'] > df['high_channel'].shift(1)) &
                (df['Volume'] > df['Volume_SMA'] * 1.3) &
                (df['ADX'] > 20)                           # ADX subindo
            )
            
            df.loc[buy, 'signal'] = 'BUY'
            return df
        
        def breakdown_momentum_func(df):
            """Breakdown Momentum - SHORT em rompimentos de suporte"""
            df = df.copy()
            df['signal'] = 'HOLD'
            
            # Suporte recente
            df['support'] = df['Low'].rolling(20).min()
            df['volume_ratio'] = df['Volume'] / df['Volume_SMA']
            
            # Breakdown - só com rompimento claro e volume
            short_signal = (
                (df['Close'] < df['support'].shift(1)) &  # Rompe suporte
                (df['Close'] < df['Close'].shift(1)) &     # Continuação bearish
                (df['volume_ratio'] > 1.8) &               # Volume alto
                (df['RSI'] < 45) &                         # Momentum bearish
                (df['ADX'] > 20)                           # Tendência confirmada
            )
            
            # EXIT: RSI muito oversold
            exit_signal = (df['RSI'] < 22)
            
            df.loc[short_signal, 'signal'] = 'SHORT'
            df.loc[exit_signal, 'signal'] = 'CLOSE'
            return df
        
        def bear_market_short_func(df):
            """Bear Market Short - SHORT em tendência de baixa confirmada"""
            df = df.copy()
            df['signal'] = 'HOLD'
            
            # SMA para tendência
            df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
            
            # DI para direção
            adx_ind = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14)
            df['plus_di'] = adx_ind.adx_pos()
            df['minus_di'] = adx_ind.adx_neg()
            
            # Bear Market Short - só em bear market confirmado
            short_signal = (
                (df['Close'] < df['SMA50']) &              # Preço abaixo SMA50
                (df['SMA50'] < df['SMA50'].shift(5)) &     # SMA50 descendente
                (df['ADX'] > 22) &                         # Tendência moderada
                (df['minus_di'] > df['plus_di']) &         # Direção bearish
                (df['RSI'] < 50) &                         # RSI bearish
                (df['RSI'] > 30)                           # Mas não oversold
            )
            
            # EXIT: Reversão ou oversold extremo
            df['EMA20'] = ta.trend.ema_indicator(df['Close'], window=20)
            exit_signal = (
                (df['RSI'] < 22) |                          # RSI muito baixo
                (df['Close'] > df['SMA50'])                 # Preço recuperou SMA50
            )
            
            df.loc[short_signal, 'signal'] = 'SHORT'
            df.loc[exit_signal, 'signal'] = 'CLOSE'
            return df
        
        def liquidity_grab_func(df):
            df = df.copy()
            df['signal'] = 'HOLD'
            
            df['support'] = df['Low'].rolling(20).min().shift(1)
            df['lower_wick'] = df[['Open', 'Close']].min(axis=1) - df['Low']
            df['candle_range'] = df['High'] - df['Low']
            df['wick_ratio'] = np.where(df['candle_range'] > 0, df['lower_wick'] / df['candle_range'], 0)
            
            spring = (
                (df['Low'] < df['support']) &
                (df['Close'] > df['support']) &
                (df['wick_ratio'] >= 0.5) &
                (df['Volume'] > df['Volume_SMA'] * 1.5) &
                (df['Close'] > df['Open'])
            )
            
            df.loc[spring, 'signal'] = 'BUY'
            return df
        
        def rsi_divergence_bullish_func(df):
            """
            RSI Divergence Bullish - Detecta divergências de alta
            
            PASSO 23: Integração no MetaBacktester
            - Divergência de Alta: Preço faz mínimas mais baixas, RSI faz mínimas mais altas
            - Hidden Bullish: Preço faz mínimas mais altas, RSI faz mínimas mais baixas (continuação)
            
            Resultados validados:
            - BTC: +26.27%, WR 71.43%
            - ETH: +38.54%, WR 64.29%
            - SOL: +219.14%, WR 63.64%
            """
            df = df.copy()
            df['signal'] = 'HOLD'
            
            # PASSO 23.5: Parâmetros otimizados para MetaBacktester
            lookback = 6   # OTIMIZADO: 10 → 6 (mais agressivo)
            min_adx = 12   # OTIMIZADO: 15 → 12 (mais permissivo)
            min_strength = 0.12  # AJUSTE: strength anterior ficava alto demais em 1h
            
            # Calcular RSI se não existir
            if 'RSI' not in df.columns:
                df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            
            # Estratégia CAUSAL (sem lookahead): sinal só no candle atual.
            # Identifica swing lows usando apenas histórico (janela passada), adequado para loop candle-a-candle.
            if len(df) < (lookback + 5):
                return df

            idx = len(df) - 1
            low_window = df['Low'].iloc[max(0, idx - lookback + 1):idx + 1]
            is_swing_low = df['Low'].iloc[idx] == low_window.min()

            if not is_swing_low:
                return df

            # Encontrar swing low anterior
            swing_lows = []
            for j in range(lookback, idx + 1):
                w = df['Low'].iloc[j - lookback + 1:j + 1]
                if df['Low'].iloc[j] == w.min():
                    # evitar duplicatas (muitos lows iguais)
                    if not swing_lows or j - swing_lows[-1] >= max(2, lookback // 2):
                        swing_lows.append(j)
            if len(swing_lows) < 2:
                return df

            prev_idx = swing_lows[-2]
            curr_idx = swing_lows[-1]
            if curr_idx != idx:
                return df

            # Divergência de Alta: preço lower-low, RSI higher-low
            prev_low = float(df['Low'].iloc[prev_idx])
            curr_low = float(df['Low'].iloc[curr_idx])
            prev_rsi = float(df['RSI'].iloc[prev_idx]) if pd.notna(df['RSI'].iloc[prev_idx]) else None
            curr_rsi = float(df['RSI'].iloc[curr_idx]) if pd.notna(df['RSI'].iloc[curr_idx]) else None
            if prev_rsi is None or curr_rsi is None:
                return df

            # 1h tende a ter swings curtos: reduzir a exigência de deslocamento.
            price_ll = curr_low < prev_low * 0.995  # ~0.5% lower-low
            rsi_hl = (curr_rsi - prev_rsi) >= 0.5   # +0.5 ponto de RSI

            adx_ok = df['ADX'].iloc[idx] >= min_adx if 'ADX' in df.columns and pd.notna(df['ADX'].iloc[idx]) else True

            price_diff = abs(curr_low - prev_low) / prev_low if prev_low > 0 else 0
            rsi_diff = abs(curr_rsi - prev_rsi) / 100
            strength = (price_diff * 5 + rsi_diff * 5) / 2

            if price_ll and rsi_hl and adx_ok and strength >= min_strength:
                # Confirmação simples: RSI em zona baixa
                if df['RSI'].iloc[idx] < 45:
                    df.iloc[idx, df.columns.get_loc('signal')] = 'BUY'
            
            return df
        
        def rsi_divergence_bearish_func(df):
            """
            RSI Divergence Bearish - Detecta divergências de baixa
            
            PASSO 23: Integração no MetaBacktester
            - Divergência de Baixa: Preço faz máximas mais altas, RSI faz máximas mais baixas
            - Hidden Bearish: Preço faz máximas mais baixas, RSI faz máximas mais altas (continuação)
            """
            df = df.copy()
            df['signal'] = 'HOLD'
            
            # PASSO 23.5: Parâmetros otimizados para MetaBacktester
            lookback = 6   # OTIMIZADO: 10 → 6 (mais agressivo)
            min_adx = 12   # OTIMIZADO: 15 → 12 (mais permissivo)
            min_strength = 0.12  # AJUSTE: strength anterior ficava alto demais em 1h
            
            if 'RSI' not in df.columns:
                df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            
            # Estratégia CAUSAL (sem lookahead): sinal só no candle atual.
            if len(df) < (lookback + 5):
                return df

            idx = len(df) - 1
            high_window = df['High'].iloc[max(0, idx - lookback + 1):idx + 1]
            is_swing_high = df['High'].iloc[idx] == high_window.max()

            if not is_swing_high:
                return df

            swing_highs = []
            for j in range(lookback, idx + 1):
                w = df['High'].iloc[j - lookback + 1:j + 1]
                if df['High'].iloc[j] == w.max():
                    if not swing_highs or j - swing_highs[-1] >= max(2, lookback // 2):
                        swing_highs.append(j)
            if len(swing_highs) < 2:
                return df

            prev_idx = swing_highs[-2]
            curr_idx = swing_highs[-1]
            if curr_idx != idx:
                return df

            prev_high = float(df['High'].iloc[prev_idx])
            curr_high = float(df['High'].iloc[curr_idx])
            prev_rsi = float(df['RSI'].iloc[prev_idx]) if pd.notna(df['RSI'].iloc[prev_idx]) else None
            curr_rsi = float(df['RSI'].iloc[curr_idx]) if pd.notna(df['RSI'].iloc[curr_idx]) else None
            if prev_rsi is None or curr_rsi is None:
                return df

            # Divergência de Baixa: preço higher-high, RSI lower-high
            price_hh = curr_high > prev_high * 1.005  # ~0.5% higher-high
            rsi_lh = (prev_rsi - curr_rsi) >= 0.5     # -0.5 ponto de RSI

            adx_ok = df['ADX'].iloc[idx] >= min_adx if 'ADX' in df.columns and pd.notna(df['ADX'].iloc[idx]) else True

            price_diff = abs(curr_high - prev_high) / prev_high if prev_high > 0 else 0
            rsi_diff = abs(curr_rsi - prev_rsi) / 100
            strength = (price_diff * 5 + rsi_diff * 5) / 2

            if price_hh and rsi_lh and adx_ok and strength >= min_strength:
                if df['RSI'].iloc[idx] > 55:
                    df.iloc[idx, df.columns.get_loc('signal')] = 'SHORT'
            
            return df
        
        return {
            'trend_following': trend_following_func,
            'momentum': momentum_func,
            'mean_reversion': mean_reversion_func,
            'volatility_breakout': volatility_breakout_func,
            'breakdown_momentum': breakdown_momentum_func,
            'liquidity_grab': liquidity_grab_func,
            'bear_market_short': bear_market_short_func,
            'bollinger_bear': mean_reversion_func,  # Alias para mean reversion SHORT
            'rsi_divergence_bullish': rsi_divergence_bullish_func,  # PASSO 23: RSI Divergence para LONG
            'rsi_divergence_bearish': rsi_divergence_bearish_func   # PASSO 23: RSI Divergence para SHORT
        }


def print_results(result: SimulationResult):
    """Imprime resultados formatados"""
    
    print("\n" + "=" * 60)
    print("📊 RESULTADOS DO META-BACKTEST")
    print("=" * 60)
    
    print(f"\n💰 PERFORMANCE:")
    print(f"   Capital Inicial: ${result.initial_capital:,.2f}")
    print(f"   Capital Final:   ${result.final_capital:,.2f}")
    print(f"   Retorno Total:   ${result.total_return:,.2f} ({result.total_return_pct:+.2f}%)")
    print(f"   Max Drawdown:    {result.max_drawdown_pct:.2f}%")
    
    print(f"\n📈 MÉTRICAS DE RISCO:")
    print(f"   Sharpe Ratio:    {result.sharpe_ratio:.2f}")
    print(f"   Sortino Ratio:   {result.sortino_ratio:.2f}")
    print(f"   Profit Factor:   {result.profit_factor:.2f}")
    
    print(f"\n🎯 ESTATÍSTICAS DE TRADES:")
    print(f"   Total Trades:    {result.total_trades}")
    print(f"   Vencedores:      {result.winning_trades} ({result.win_rate:.1f}%)")
    print(f"   Perdedores:      {result.losing_trades}")
    print(f"   Ganho Médio:     ${result.avg_win:,.2f}")
    print(f"   Perda Média:     ${result.avg_loss:,.2f}")
    
    print(f"\n🔄 ADAPTABILIDADE:")
    print(f"   Mudanças de Regime:    {result.regime_changes}")
    print(f"   Trocas de Estratégia:  {result.strategy_switches}")
    
    # Validação BLUE_PRINT
    print("\n" + "-" * 60)
    print("✅ VALIDAÇÃO BLUE_PRINT (Metas):")
    
    if result.sharpe_ratio >= 1.5:
        print(f"   ✅ Sharpe Ratio >= 1.5: PASSOU ({result.sharpe_ratio:.2f})")
    else:
        print(f"   ❌ Sharpe Ratio >= 1.5: FALHOU ({result.sharpe_ratio:.2f})")
    
    if result.max_drawdown_pct <= 20:
        print(f"   ✅ Max Drawdown <= 20%: PASSOU ({result.max_drawdown_pct:.2f}%)")
    else:
        print(f"   ❌ Max Drawdown <= 20%: FALHOU ({result.max_drawdown_pct:.2f}%)")
    
    print("=" * 60)


# Stress Tests conforme BLUE_PRINT
STRESS_TEST_PERIODS = {
    'bull_run': {
        'name': 'The Bull Run',
        'start': '2024-01-01',  # FIX: Atualizado para 2024 Q1 (ATH Run)
        'end': '2024-03-31',
        'expected': 'LUCRO ALTO'
    },
    'chop': {
        'name': 'The Chop (Whipsaw)',
        'start': '2022-06-01',  # FIX: Consolidação pós-crash 2022
        'end': '2022-09-30',
        'expected': 'PERDA PEQUENA ou LATERAL'
    },
    'crash': {
        'name': 'The Crash',
        'start': '2022-03-01',  # FIX: Crash LUNA/3AC de 2022
        'end': '2022-06-30',
        'expected': 'VIRAR PARA SHORT RÁPIDO'
    },
    'recovery': {
        'name': 'The Recovery',
        'start': '2023-01-01',  # OK: Recovery de 2023
        'end': '2023-03-31',
        'expected': 'CAPTURAR O FUNDO'
    }
}


async def run_stress_tests(df: pd.DataFrame) -> Dict[str, SimulationResult]:
    """Executa todos os stress tests do BLUE_PRINT"""
    
    results = {}
    backtester = MetaBacktester()
    
    for period_key, period_config in STRESS_TEST_PERIODS.items():
        print(f"\n🔬 Executando: {period_config['name']}")
        print(f"   Período: {period_config['start']} a {period_config['end']}")
        print(f"   Expectativa: {period_config['expected']}")
        
        # Filtrar dados do período
        mask = (df.index >= period_config['start']) & (df.index <= period_config['end'])
        period_df = df.loc[mask].copy()
        
        if len(period_df) < 100:
            print(f"   ⚠️ Dados insuficientes: {len(period_df)} candles")
            continue
        
        # Executar simulação
        result = backtester.run_simulation(period_df)
        results[period_key] = result
        
        print(f"   Resultado: {result.total_return_pct:+.2f}% | DD: {result.max_drawdown_pct:.2f}%")
    
    return results


# Exemplo de uso
if __name__ == "__main__":
    import asyncio
    
    # Criar dados de exemplo
    np.random.seed(42)
    dates = pd.date_range(start='2021-01-01', end='2023-12-31', freq='1h')
    
    # Simular preços com tendência
    n = len(dates)
    returns = np.random.normal(0.0001, 0.02, n)
    prices = 40000 * np.cumprod(1 + returns)
    
    df = pd.DataFrame({
        'Open': prices * (1 + np.random.uniform(-0.01, 0.01, n)),
        'High': prices * (1 + np.random.uniform(0, 0.02, n)),
        'Low': prices * (1 - np.random.uniform(0, 0.02, n)),
        'Close': prices,
        'Volume': np.random.uniform(100, 1000, n) * 1e6
    }, index=dates)
    
    # Executar backtest
    backtester = MetaBacktester(initial_capital=100000)
    result = backtester.run_simulation(df)
    
    # Mostrar resultados
    print_results(result)
