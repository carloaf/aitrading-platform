"""
Multi-Symbol RSI Divergence Scanner

Escaneia múltiplas criptomoedas em tempo real procurando divergências RSI,
gerando alertas e sinais para Paper Trading.

Autor: AI Trading Platform
Data: 17 de Dezembro de 2025
"""

import asyncio
import os
import ccxt
import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
import ta

# ML Signal Filter
try:
    from ml_signal_filter import MLSignalFilter
    ML_FILTER_AVAILABLE = True
except ImportError:
    ML_FILTER_AVAILABLE = False
    logging.warning("ML Signal Filter not available. Install: pip install lightgbm")

logger = logging.getLogger(__name__)


class SignalType(Enum):
    BULLISH_DIVERGENCE = "bullish_divergence"
    BEARISH_DIVERGENCE = "bearish_divergence"
    HIDDEN_BULLISH = "hidden_bullish"
    HIDDEN_BEARISH = "hidden_bearish"


class SignalStrength(Enum):
    WEAK = "weak"       # 0.3 - 0.5
    MODERATE = "moderate"  # 0.5 - 0.7
    STRONG = "strong"   # 0.7 - 0.9
    VERY_STRONG = "very_strong"  # > 0.9


@dataclass
class DivergenceSignal:
    """Representa um sinal de divergência detectado"""
    symbol: str
    signal_type: SignalType
    strength: float
    strength_level: SignalStrength
    direction: int  # 1 = BUY, -1 = SELL
    current_price: float
    rsi_value: float
    timestamp: datetime
    timeframe: str
    
    # Pontos da divergência
    price_point1: float
    price_point2: float
    rsi_point1: float
    rsi_point2: float
    
    # Níveis de entrada sugeridos
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    
    # Confirmações
    volume_confirmed: bool = False
    macd_confirmed: bool = False
    trend_aligned: bool = False
    
    # Metadados
    scan_id: str = ""
    notes: str = ""


@dataclass
class ScannerConfig:
    """Configuração do scanner multi-symbol"""
    # Símbolos para escanear
    symbols: List[str] = field(default_factory=lambda: [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
        "ADA/USDT", "AVAX/USDT", "DOT/USDT", "MATIC/USDT", "LINK/USDT"
    ])
    
    # Timeframes para análise
    timeframes: List[str] = field(default_factory=lambda: ["1h", "4h"])
    
    # Parâmetros RSI
    rsi_period: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    
    # Parâmetros de detecção (alinhados com Backtest Visual v2.1)
    lookback_periods: int = 15  # Atualizado: 10 → 15 para coincidir com Backtest Visual
    min_signal_strength: float = 0.35  # Atualizado: 0.3 → 0.35 (mais qualidade)
    min_adx_trend: int = 15
    divergence_threshold: float = 0.02
    
    # Gestão de risco (alinhados com Backtest Visual)
    atr_period: int = 14
    stop_loss_atr_mult: float = 2.0
    take_profit_atr_mult: float = 3.5  # Atualizado: 4.0 → 3.5 (mais realista)
    
    # Filtros (NOVO: alinhados com Backtest Visual v2.1)
    min_volume_ratio: float = 1.3  # Atualizado: 1.0 → 1.3 (volume 30% acima da média)
    require_volume_confirmation: bool = True
    require_macd_confirmation: bool = False
    use_ema_filter: bool = True  # NOVO: Filtro EMA 50/200 para alinhamento com tendência
    
    # Intervalo de scan (segundos)
    scan_interval: int = 60


class MultiSymbolScanner:
    """
    Scanner de múltiplos símbolos para detecção de divergências RSI
    
    Funcionalidades:
    - Escaneia 10+ criptos simultaneamente
    - Detecta 4 tipos de divergência RSI
    - Calcula força do sinal e níveis de entrada
    - Gera alertas em tempo real
    - Integra com Paper Trading
    """
    
    def __init__(self, config: ScannerConfig = None, db_pool=None, auto_trade_enabled: bool = False):
        self.config = config or ScannerConfig()
        self.use_local_cache_only = os.getenv("USE_LOCAL_MARKET_DATA", "true").lower() == "true"

        # Quando USE_LOCAL_MARKET_DATA=true não criamos client da Binance
        self.exchange = None if self.use_local_cache_only else ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        # Cache de dados
        self.ohlcv_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.last_update: Dict[str, datetime] = {}
        
        # Sinais detectados
        self.active_signals: List[DivergenceSignal] = []
        self.signal_history: List[DivergenceSignal] = []
        
        # Estado do scanner
        self.is_running = False
        self.scan_count = 0
        self.last_scan_time: Optional[datetime] = None
        
        # Callbacks
        self.on_signal_detected: Optional[callable] = None
        
        # Database connection
        self.db_pool = db_pool
        
        # Auto-trade configuration
        self.auto_trade_enabled = auto_trade_enabled
        self.auto_trade_session_id: Optional[str] = None
        self.min_signal_strength_for_trade = 0.4  # Mínimo 40% de força
        
        # ML Filter configuration
        self.ml_filter_enabled = False
        self.ml_filter: Optional['MLSignalFilter'] = None
        self.min_ml_score = 0.60  # 60% confiança mínima
        self.ml_training_metrics: Dict[str, Any] = {}
        self.ml_stats = {
            'total_signals': 0,
            'approved': 0,
            'rejected': 0,
            'avg_score': 0.0
        }
        
        logger.info(f"MultiSymbolScanner initialized with {len(self.config.symbols)} symbols | Auto-trade: {auto_trade_enabled} | ML: {ML_FILTER_AVAILABLE}")
    
    async def start(self):
        """Inicia o scanner em modo contínuo"""
        self.is_running = True
        logger.info("Starting MultiSymbolScanner...")
        
        while self.is_running:
            try:
                signals = await self.scan_all_symbols()
                
                if signals:
                    self.active_signals = signals
                    logger.info(f"Scan #{self.scan_count}: Found {len(signals)} signals")
                    
                    # Callback para cada sinal
                    if self.on_signal_detected:
                        for signal in signals:
                            await self.on_signal_detected(signal)
                
                self.scan_count += 1
                self.last_scan_time = datetime.utcnow()
                
                await asyncio.sleep(self.config.scan_interval)
                
            except Exception as e:
                logger.error(f"Scanner error: {e}")
                await asyncio.sleep(5)
    
    def stop(self):
        """Para o scanner"""
        self.is_running = False
        logger.info("MultiSymbolScanner stopped")
    
    async def scan_all_symbols(self) -> List[DivergenceSignal]:
        """
        Escaneia todos os símbolos configurados
        Retorna lista de sinais detectados
        """
        all_signals = []
        
        # Processar símbolos em paralelo
        tasks = []
        for symbol in self.config.symbols:
            for timeframe in self.config.timeframes:
                tasks.append(self.scan_symbol(symbol, timeframe))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Scan error: {result}")
            elif result:
                all_signals.extend(result)
        
        # Ordenar por força do sinal
        all_signals.sort(key=lambda x: x.strength, reverse=True)
        
        # 💾 Salvar novos sinais no banco de dados
        if all_signals and self.db_pool:
            logger.info(f"💾 Saving {len(all_signals)} signals to database...")
            for signal in all_signals:
                await self._save_signal_to_db(signal)
        
        return all_signals
    
    async def scan_symbol(self, symbol: str, timeframe: str) -> List[DivergenceSignal]:
        """
        Escaneia um único símbolo em um timeframe específico
        """
        try:
            # Buscar dados OHLCV
            df = await self._fetch_ohlcv(symbol, timeframe)
            
            # ✅ VALIDAÇÃO: Dados insuficientes (mínimo 100 candles)
            if df is None or len(df) < 100:
                if df is not None and len(df) < 100:
                    logger.warning(f"⚠️  {symbol} tem apenas {len(df)} candles (mínimo: 100). Pulando scan.")
                return []
            
            # Calcular indicadores
            df = self._calculate_indicators(df)
            
            # Detectar divergências
            signals = self._detect_divergences(df, symbol, timeframe)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error scanning {symbol} {timeframe}: {e}")
            return []
    
    async def _fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """
        Busca dados OHLCV do banco (Timescale) quando USE_LOCAL_MARKET_DATA=true.
        Não faz chamadas externas para a Binance neste modo.
        """
        cache_key = f"{symbol}_{timeframe}"
        
        # Verificar cache (máximo 1 minuto)
        if cache_key in self.ohlcv_cache:
            last_update = self.last_update.get(cache_key)
            if last_update and (datetime.utcnow() - last_update).seconds < 60:
                return self.ohlcv_cache[cache_key]
        
        # Sempre priorizar dados locais
        if self.use_local_cache_only:
            if not self.db_pool:
                logger.warning("[Scanner] db_pool não disponível para fetch OHLCV local")
                return None

            db_symbol = symbol.replace('/', '')  # Binance usa formato BTCUSDT no banco
            source = f"binance_{timeframe}"

            try:
                async with self.db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT timestamp, open, high, low, close, volume
                        FROM market_data
                        WHERE symbol = $1 AND source = $2
                        ORDER BY timestamp DESC
                        LIMIT $3
                        """,
                        db_symbol,
                        source,
                        limit
                    )

                if not rows:
                    logger.warning(f"[Scanner] Sem dados locais para {db_symbol} {timeframe}")
                    return None

                df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                df = df.sort_index()

                self.ohlcv_cache[cache_key] = df
                self.last_update[cache_key] = datetime.utcnow()
                return df

            except Exception as e:
                logger.error(f"[Scanner] Erro ao ler OHLCV local {db_symbol} {timeframe}: {e}")
                return None

        # Se explicitamente permitido, pode usar Binance (modo antigo)
        if not self.exchange:
            logger.warning("[Scanner] Exchange não inicializado (USE_LOCAL_MARKET_DATA=true). Retornando vazio.")
            return None

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            self.ohlcv_cache[cache_key] = df
            self.last_update[cache_key] = datetime.utcnow()

            return df

        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return None
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula indicadores técnicos necessários
        """
        # RSI
        df['rsi'] = ta.momentum.rsi(df['close'], window=self.config.rsi_period)
        
        # ATR para gestão de risco
        df['atr'] = ta.volatility.average_true_range(
            df['high'], df['low'], df['close'], 
            window=self.config.atr_period
        )
        
        # ADX para filtro de tendência
        try:
            adx_indicator = ta.trend.ADXIndicator(
                df['high'], df['low'], df['close'], 
                window=self.config.min_adx_trend
            )
            df['adx'] = adx_indicator.adx()
            df['di_plus'] = adx_indicator.adx_pos()
            df['di_minus'] = adx_indicator.adx_neg()
        except:
            df['adx'] = 25
            df['di_plus'] = 25
            df['di_minus'] = 25
        
        # MACD para confirmação
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()
        
        # Volume SMA
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # EMAs para tendência (incluindo EMA 200 para filtro v2.1)
        df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
        df['ema_26'] = ta.trend.ema_indicator(df['close'], window=26)
        df['ema_50'] = ta.trend.ema_indicator(df['close'], window=50)
        df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)  # NOVO: Para filtro EMA v2.1
        
        # Detectar picos e vales
        df = self._detect_peaks_valleys(df)
        
        return df
    
    def _detect_peaks_valleys(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta picos e vales no preço e RSI
        """
        lookback = self.config.lookback_periods
        
        df['price_peak'] = False
        df['price_valley'] = False
        df['rsi_peak'] = False
        df['rsi_valley'] = False
        
        for i in range(lookback, len(df) - lookback):
            # Picos de preço
            window_high = df['high'].iloc[i-lookback:i+lookback+1]
            if df['high'].iloc[i] == window_high.max():
                df.iloc[i, df.columns.get_loc('price_peak')] = True
            
            # Vales de preço
            window_low = df['low'].iloc[i-lookback:i+lookback+1]
            if df['low'].iloc[i] == window_low.min():
                df.iloc[i, df.columns.get_loc('price_valley')] = True
            
            # Picos e vales de RSI
            if pd.notna(df['rsi'].iloc[i]):
                window_rsi = df['rsi'].iloc[i-lookback:i+lookback+1].dropna()
                if len(window_rsi) > 0:
                    if df['rsi'].iloc[i] == window_rsi.max() and df['rsi'].iloc[i] > 50:
                        df.iloc[i, df.columns.get_loc('rsi_peak')] = True
                    if df['rsi'].iloc[i] == window_rsi.min() and df['rsi'].iloc[i] < 50:
                        df.iloc[i, df.columns.get_loc('rsi_valley')] = True
        
        return df
    
    def _detect_divergences(self, df: pd.DataFrame, symbol: str, timeframe: str) -> List[DivergenceSignal]:
        """
        Detecta divergências RSI nos últimos candles
        """
        signals = []
        lookback = self.config.lookback_periods * 3
        
        # Analisar apenas os últimos N candles
        recent_df = df.iloc[-lookback:]
        
        current_idx = len(df) - 1
        current_price = df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        current_atr = df['atr'].iloc[-1]
        
        if pd.isna(current_rsi) or pd.isna(current_atr):
            return []
        
        # 1. Divergência de Alta (Bullish)
        bullish_signal = self._check_bullish_divergence(recent_df, symbol, timeframe, current_price, current_rsi, current_atr)
        if bullish_signal:
            signals.append(bullish_signal)
        
        # 2. Divergência de Baixa (Bearish)
        bearish_signal = self._check_bearish_divergence(recent_df, symbol, timeframe, current_price, current_rsi, current_atr)
        if bearish_signal:
            signals.append(bearish_signal)
        
        # 3. Hidden Bullish
        hidden_bullish = self._check_hidden_bullish(recent_df, symbol, timeframe, current_price, current_rsi, current_atr)
        if hidden_bullish:
            signals.append(hidden_bullish)
        
        # 4. Hidden Bearish
        hidden_bearish = self._check_hidden_bearish(recent_df, symbol, timeframe, current_price, current_rsi, current_atr)
        if hidden_bearish:
            signals.append(hidden_bearish)
        
        return signals
    
    def _check_bullish_divergence(self, df: pd.DataFrame, symbol: str, timeframe: str, 
                                   price: float, rsi: float, atr: float) -> Optional[DivergenceSignal]:
        """
        Divergência de Alta: Preço faz lower lows, RSI faz higher lows
        Filtro EMA v2.1: Só aceita se EMA 50 > EMA 200 (tendência de alta macro)
        """
        price_valleys = df[df['price_valley']].tail(3)
        rsi_valleys = df[df['rsi_valley']].tail(3)
        
        if len(price_valleys) < 2 or len(rsi_valleys) < 2:
            return None
        
        # NOVO v2.1: Filtro EMA 50/200 para alinhamento com tendência macro
        if self.config.use_ema_filter and 'ema_200' in df.columns:
            ema_50 = df['ema_50'].iloc[-1]
            ema_200 = df['ema_200'].iloc[-1]
            # Bullish divergence funciona melhor quando tendência macro é de alta ou lateral
            # Aceita se EMA 50 > EMA 200 OU se preço está próximo das EMAs (±5%)
            ema_bullish_aligned = ema_50 >= ema_200 * 0.95  # Aceita até 5% abaixo
            if not ema_bullish_aligned:
                return None
        
        # Preço: lower lows
        price_ll = price_valleys['low'].iloc[-1] < price_valleys['low'].iloc[-2]
        # RSI: higher lows
        rsi_hl = rsi_valleys['rsi'].iloc[-1] > rsi_valleys['rsi'].iloc[-2]
        
        # RSI deve estar em zona de sobrevenda ou próximo
        rsi_oversold = rsi < self.config.rsi_oversold + 10
        
        if price_ll and rsi_hl and rsi_oversold:
            strength = self._calculate_strength(
                price_valleys['low'].iloc[-2], price_valleys['low'].iloc[-1],
                rsi_valleys['rsi'].iloc[-2], rsi_valleys['rsi'].iloc[-1],
                df
            )
            
            if strength >= self.config.min_signal_strength:
                return self._create_signal(
                    symbol, timeframe, SignalType.BULLISH_DIVERGENCE, 1, strength,
                    price, rsi, atr,
                    price_valleys['low'].iloc[-2], price_valleys['low'].iloc[-1],
                    rsi_valleys['rsi'].iloc[-2], rsi_valleys['rsi'].iloc[-1],
                    df
                )
        
        return None
    
    def _check_bearish_divergence(self, df: pd.DataFrame, symbol: str, timeframe: str,
                                   price: float, rsi: float, atr: float) -> Optional[DivergenceSignal]:
        """
        Divergência de Baixa: Preço faz higher highs, RSI faz lower highs
        Filtro EMA v2.1: Só aceita se EMA 50 < EMA 200 (tendência de baixa macro)
        """
        price_peaks = df[df['price_peak']].tail(3)
        rsi_peaks = df[df['rsi_peak']].tail(3)
        
        if len(price_peaks) < 2 or len(rsi_peaks) < 2:
            return None
        
        # NOVO v2.1: Filtro EMA 50/200 para alinhamento com tendência macro
        if self.config.use_ema_filter and 'ema_200' in df.columns:
            ema_50 = df['ema_50'].iloc[-1]
            ema_200 = df['ema_200'].iloc[-1]
            # Bearish divergence funciona melhor quando tendência macro é de baixa ou lateral
            # Aceita se EMA 50 < EMA 200 OU se preço está próximo das EMAs (±5%)
            ema_bearish_aligned = ema_50 <= ema_200 * 1.05  # Aceita até 5% acima
            if not ema_bearish_aligned:
                return None
        
        # Preço: higher highs
        price_hh = price_peaks['high'].iloc[-1] > price_peaks['high'].iloc[-2]
        # RSI: lower highs
        rsi_lh = rsi_peaks['rsi'].iloc[-1] < rsi_peaks['rsi'].iloc[-2]
        
        # RSI deve estar em zona de sobrecompra ou próximo
        rsi_overbought = rsi > self.config.rsi_overbought - 10
        
        if price_hh and rsi_lh and rsi_overbought:
            strength = self._calculate_strength(
                price_peaks['high'].iloc[-2], price_peaks['high'].iloc[-1],
                rsi_peaks['rsi'].iloc[-2], rsi_peaks['rsi'].iloc[-1],
                df
            )
            
            if strength >= self.config.min_signal_strength:
                return self._create_signal(
                    symbol, timeframe, SignalType.BEARISH_DIVERGENCE, -1, strength,
                    price, rsi, atr,
                    price_peaks['high'].iloc[-2], price_peaks['high'].iloc[-1],
                    rsi_peaks['rsi'].iloc[-2], rsi_peaks['rsi'].iloc[-1],
                    df
                )
        
        return None
    
    def _check_hidden_bullish(self, df: pd.DataFrame, symbol: str, timeframe: str,
                               price: float, rsi: float, atr: float) -> Optional[DivergenceSignal]:
        """
        Hidden Bullish: Preço faz higher lows, RSI faz lower lows (continuação de alta)
        """
        price_valleys = df[df['price_valley']].tail(3)
        rsi_valleys = df[df['rsi_valley']].tail(3)
        
        if len(price_valleys) < 2 or len(rsi_valleys) < 2:
            return None
        
        # Preço: higher lows (tendência de alta)
        price_hl = price_valleys['low'].iloc[-1] > price_valleys['low'].iloc[-2]
        # RSI: lower lows
        rsi_ll = rsi_valleys['rsi'].iloc[-1] < rsi_valleys['rsi'].iloc[-2]
        
        # Tendência de alta confirmada
        ema_bullish = df['ema_12'].iloc[-1] > df['ema_26'].iloc[-1]
        
        if price_hl and rsi_ll and ema_bullish:
            strength = self._calculate_strength(
                price_valleys['low'].iloc[-2], price_valleys['low'].iloc[-1],
                rsi_valleys['rsi'].iloc[-2], rsi_valleys['rsi'].iloc[-1],
                df
            ) * 0.9  # Hidden patterns têm força ligeiramente menor
            
            if strength >= self.config.min_signal_strength:
                return self._create_signal(
                    symbol, timeframe, SignalType.HIDDEN_BULLISH, 1, strength,
                    price, rsi, atr,
                    price_valleys['low'].iloc[-2], price_valleys['low'].iloc[-1],
                    rsi_valleys['rsi'].iloc[-2], rsi_valleys['rsi'].iloc[-1],
                    df
                )
        
        return None
    
    def _check_hidden_bearish(self, df: pd.DataFrame, symbol: str, timeframe: str,
                               price: float, rsi: float, atr: float) -> Optional[DivergenceSignal]:
        """
        Hidden Bearish: Preço faz lower highs, RSI faz higher highs (continuação de baixa)
        """
        price_peaks = df[df['price_peak']].tail(3)
        rsi_peaks = df[df['rsi_peak']].tail(3)
        
        if len(price_peaks) < 2 or len(rsi_peaks) < 2:
            return None
        
        # Preço: lower highs (tendência de baixa)
        price_lh = price_peaks['high'].iloc[-1] < price_peaks['high'].iloc[-2]
        # RSI: higher highs
        rsi_hh = rsi_peaks['rsi'].iloc[-1] > rsi_peaks['rsi'].iloc[-2]
        
        # Tendência de baixa confirmada
        ema_bearish = df['ema_12'].iloc[-1] < df['ema_26'].iloc[-1]
        
        if price_lh and rsi_hh and ema_bearish:
            strength = self._calculate_strength(
                price_peaks['high'].iloc[-2], price_peaks['high'].iloc[-1],
                rsi_peaks['rsi'].iloc[-2], rsi_peaks['rsi'].iloc[-1],
                df
            ) * 0.9
            
            if strength >= self.config.min_signal_strength:
                return self._create_signal(
                    symbol, timeframe, SignalType.HIDDEN_BEARISH, -1, strength,
                    price, rsi, atr,
                    price_peaks['high'].iloc[-2], price_peaks['high'].iloc[-1],
                    rsi_peaks['rsi'].iloc[-2], rsi_peaks['rsi'].iloc[-1],
                    df
                )
        
        return None
    
    def _calculate_strength(self, price1: float, price2: float, 
                            rsi1: float, rsi2: float, df: pd.DataFrame) -> float:
        """
        Calcula a força da divergência (0.0 a 1.0)
        """
        # Diferença percentual no preço
        price_diff = abs(price2 - price1) / price1
        
        # Diferença no RSI (normalizada)
        rsi_diff = abs(rsi2 - rsi1) / 100
        
        # Componente base (média das diferenças)
        base_strength = (price_diff * 100 + rsi_diff * 100) / 2
        base_strength = min(base_strength / 10, 1.0)  # Normalizar para 0-1
        
        # Bonus por volume
        volume_ratio = df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns else 1.0
        volume_bonus = min(volume_ratio / 2, 0.2) if volume_ratio > 1.5 else 0
        
        # Bonus por ADX baixo (ideal para reversão)
        adx = df['adx'].iloc[-1] if 'adx' in df.columns else 25
        adx_bonus = 0.1 if adx < 25 else 0
        
        # Bonus por MACD alinhado
        macd_hist = df['macd_hist'].iloc[-1] if 'macd_hist' in df.columns else 0
        macd_bonus = 0.1 if abs(macd_hist) < df['close'].iloc[-1] * 0.001 else 0
        
        total_strength = base_strength + volume_bonus + adx_bonus + macd_bonus
        
        return min(max(total_strength, 0.0), 1.0)
    
    def _create_signal(self, symbol: str, timeframe: str, signal_type: SignalType,
                       direction: int, strength: float, current_price: float,
                       current_rsi: float, atr: float,
                       price1: float, price2: float, rsi1: float, rsi2: float,
                       df: pd.DataFrame) -> DivergenceSignal:
        """
        Cria um objeto DivergenceSignal completo
        """
        # Determinar nível de força
        if strength >= 0.9:
            strength_level = SignalStrength.VERY_STRONG
        elif strength >= 0.7:
            strength_level = SignalStrength.STRONG
        elif strength >= 0.5:
            strength_level = SignalStrength.MODERATE
        else:
            strength_level = SignalStrength.WEAK
        
        # Calcular níveis de entrada
        if direction == 1:  # BUY
            entry_price = current_price
            stop_loss = current_price - (atr * self.config.stop_loss_atr_mult)
            take_profit = current_price + (atr * self.config.take_profit_atr_mult)
        else:  # SELL
            entry_price = current_price
            stop_loss = current_price + (atr * self.config.stop_loss_atr_mult)
            take_profit = current_price - (atr * self.config.take_profit_atr_mult)
        
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        risk_reward = reward / risk if risk > 0 else 0
        
        # Verificar confirmações
        volume_confirmed = df['volume_ratio'].iloc[-1] > self.config.min_volume_ratio if 'volume_ratio' in df.columns else False
        
        macd_hist = df['macd_hist'].iloc[-1] if 'macd_hist' in df.columns else 0
        macd_confirmed = (direction == 1 and macd_hist > 0) or (direction == -1 and macd_hist < 0)
        
        ema_trend = df['ema_12'].iloc[-1] > df['ema_50'].iloc[-1] if 'ema_50' in df.columns else True
        trend_aligned = (direction == 1 and ema_trend) or (direction == -1 and not ema_trend)
        
        return DivergenceSignal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            strength_level=strength_level,
            direction=direction,
            current_price=current_price,
            rsi_value=current_rsi,
            timestamp=datetime.utcnow(),
            timeframe=timeframe,
            price_point1=price1,
            price_point2=price2,
            rsi_point1=rsi1,
            rsi_point2=rsi2,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            volume_confirmed=volume_confirmed,
            macd_confirmed=macd_confirmed,
            trend_aligned=trend_aligned,
            scan_id=f"{symbol}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            notes=f"RSI: {current_rsi:.1f}, ATR: {atr:.2f}"
        )
    
    def get_scan_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo do último scan
        """
        return {
            "is_running": self.is_running,
            "scan_count": self.scan_count,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "symbols_monitored": len(self.config.symbols),
            "timeframes": self.config.timeframes,
            "active_signals": len(self.active_signals),
            "signals": [
                {
                    "symbol": s.symbol,
                    "type": s.signal_type.value,
                    "direction": "BUY" if s.direction == 1 else "SELL",
                    "strength": round(float(s.strength), 3),
                    "strength_level": s.strength_level.value,
                    "price": float(s.current_price),
                    "rsi": round(float(s.rsi_value), 1),
                    "timeframe": s.timeframe,
                    "entry": float(s.entry_price),
                    "stop_loss": round(float(s.stop_loss), 2),
                    "take_profit": round(float(s.take_profit), 2),
                    "risk_reward": round(float(s.risk_reward), 2),
                    "confirmations": {
                        "volume": bool(s.volume_confirmed),
                        "macd": bool(s.macd_confirmed),
                        "trend": bool(s.trend_aligned)
                    },
                    "timestamp": s.timestamp.isoformat()
                }
                for s in self.active_signals
            ],
            "config": {
                "symbols": self.config.symbols,
                "timeframes": self.config.timeframes,
                "rsi_period": self.config.rsi_period,
                "min_signal_strength": self.config.min_signal_strength,
                "stop_loss_atr_mult": self.config.stop_loss_atr_mult,
                "take_profit_atr_mult": self.config.take_profit_atr_mult
            }
        }
    
    async def scan_once(self) -> Dict[str, Any]:
        """
        Executa um único scan e retorna resultados
        """
        signals = await self.scan_all_symbols()
        self.active_signals = signals
        self.scan_count += 1
        self.last_scan_time = datetime.utcnow()
        
        return self.get_scan_summary()
    
    async def _save_signal_to_db(self, signal: DivergenceSignal):
        """
        Salva sinal detectado no banco de dados (autotrade_signals)
        """
        if not self.db_pool:
            logger.warning("Database pool not configured, signal not saved")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                signal_id = f"scan_{uuid.uuid4().hex[:12]}"
                session_id = f"scanner_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                
                query = """
                INSERT INTO autotrade_signals (
                    signal_id, session_id, symbol, timeframe, signal_type, direction,
                    strength, entry_price, stop_loss, take_profit, current_price,
                    rsi, adx, volume, volatility, market_regime, reason, timestamp
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                """
                
                await conn.execute(
                    query,
                    signal_id,
                    session_id,
                    signal.symbol,
                    signal.timeframe,
                    signal.type.value,  # 'bullish_divergence', 'bearish_divergence', etc
                    'BUY' if 'bullish' in signal.type.value else 'SELL',
                    signal.strength,
                    signal.entry,
                    signal.stop_loss,
                    signal.take_profit,
                    signal.price,
                    signal.rsi,
                    signal.confirmations.get('adx', 0.0) if isinstance(signal.confirmations, dict) else 0.0,
                    signal.confirmations.get('volume', 0.0) if isinstance(signal.confirmations, dict) else 0.0,
                    0.0,  # volatility placeholder
                    None,  # market_regime placeholder
                    f"RSI Divergence: {signal.type.value} | Strength: {signal.strength:.2f}",
                    datetime.utcnow()
                )
                
                logger.info(f"💾 Signal saved to DB: {signal_id} - {signal.symbol} {signal.type.value}")
                
                # 🤖 ML FILTER: Avaliar sinal antes de executar
                ml_score = 0.5  # Default (sem filtro)
                ml_approved = True
                
                if self.ml_filter_enabled and self.ml_filter:
                    try:
                        # Extrair features do sinal
                        candle_data = {
                            'close': signal.price,
                            'open': signal.price * 0.999,  # Aproximação
                            'rsi': signal.rsi,
                            'adx': signal.confirmations.get('adx', 20.0) if isinstance(signal.confirmations, dict) else 20.0,
                            'volume': signal.confirmations.get('volume', 1000.0) if isinstance(signal.confirmations, dict) else 1000.0,
                            'atr': abs(signal.entry - signal.stop_loss),
                            'volume_ma_20': 1000.0,  # Placeholder
                            'ema_50': signal.price,
                            'ema_200': signal.price
                        }
                        
                        # Predizer qualidade do sinal
                        ml_score = self.ml_filter.predict(
                            candle_data=candle_data,
                            strategy='rsi_divergence',
                            signal_strength=signal.strength,
                            setup_quality=70.0,  # Placeholder
                            regime='SIDEWAYS'  # RSI Divergence é mean-reversion
                        )
                        
                        ml_approved = ml_score >= self.min_ml_score
                        
                        # Atualizar estatísticas
                        self.ml_stats['total_signals'] += 1
                        if ml_approved:
                            self.ml_stats['approved'] += 1
                        else:
                            self.ml_stats['rejected'] += 1
                        # Média móvel do score
                        n = self.ml_stats['total_signals']
                        self.ml_stats['avg_score'] = ((n-1) * self.ml_stats['avg_score'] + ml_score) / n
                        
                        logger.info(f"🤖 ML Score: {ml_score:.2%} | Approved: {ml_approved} | Min: {self.min_ml_score:.2%}")
                        
                        # Salvar ML score no banco
                        await conn.execute("""
                            UPDATE autotrade_signals
                            SET ml_score = $1
                            WHERE signal_id = $2
                        """, ml_score, signal_id)
                        
                    except Exception as e:
                        logger.warning(f"🤖 ML Filter error (using default): {e}")
                
                # 🚀 AUTO-EXECUTE: Se auto-trade estiver habilitado E ML aprovar
                if self.auto_trade_enabled and signal.strength >= self.min_signal_strength_for_trade:
                    if ml_approved:
                        trade_id = await self._create_paper_trade_from_signal(signal, signal_id, ml_score)
                        if trade_id:
                            logger.info(f"🤖 Auto-executed paper trade: {trade_id} from signal {signal_id} (ML: {ml_score:.2%})")
                    else:
                        logger.info(f"🚫 ML Filter rejected signal: {signal_id} | Score: {ml_score:.2%} < {self.min_ml_score:.2%}")
                        # Marcar sinal como rejeitado pelo ML
                        await conn.execute("""
                            UPDATE autotrade_signals
                            SET executed = false, execution_reason = $1
                            WHERE signal_id = $2
                        """, f"ML Filter rejected: {ml_score:.2%} < {self.min_ml_score:.2%}", signal_id)
                
                return signal_id
                
        except Exception as e:
            logger.error(f"Error saving signal to DB: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def initialize_ml_filter(self, min_trades: int = 50) -> Dict[str, Any]:
        """
        🤖 Inicializa e treina o ML Filter com histórico de trades
        
        Args:
            min_trades: Mínimo de trades necessários para treinar
            
        Returns:
            Dict com métricas de treinamento ou erro
        """
        if not ML_FILTER_AVAILABLE:
            return {'success': False, 'error': 'LightGBM not installed. Run: pip install lightgbm'}
        
        if not self.db_pool:
            return {'success': False, 'error': 'Database not connected'}
        
        try:
            self.ml_filter = MLSignalFilter()
            
            # Buscar histórico de trades do banco
            # Usa autotrade_signals que tem todas as informações necessárias
            async with self.db_pool.acquire() as conn:
                trades = await conn.fetch("""
                    SELECT 
                        s.signal_id, s.symbol, s.signal_type, s.direction,
                        s.strength, s.entry_price, s.stop_loss, s.take_profit,
                        s.rsi, s.adx, s.current_price, s.market_regime,
                        s.executed, s.timestamp,
                        t.pnl, t.pnl_percent, t.trade_type
                    FROM autotrade_signals s
                    LEFT JOIN paper_trading_trades t ON t.signal_id = s.signal_id
                    WHERE s.executed = true
                        AND t.pnl IS NOT NULL
                        AND s.timestamp >= NOW() - INTERVAL '60 days'
                    ORDER BY s.timestamp DESC
                    LIMIT 500
                """)
            
            if len(trades) < min_trades:
                return {
                    'success': False, 
                    'error': f'Not enough trades for training: {len(trades)} (need {min_trades}+)',
                    'trades_found': len(trades)
                }
            
            # Preparar dados para treino
            training_data = []
            for trade in trades:
                # Determinar label (0=bad, 1=good)
                pnl = float(trade['pnl']) if trade['pnl'] else 0
                label = 1 if pnl > 0 else 0
                
                entry_price = float(trade['entry_price']) if trade['entry_price'] else 40000.0
                stop_loss = float(trade['stop_loss']) if trade['stop_loss'] else entry_price * 0.98
                
                training_data.append({
                    'entry_state': {
                        'close': entry_price,
                        'open': entry_price * 0.999,
                        'rsi': float(trade['rsi']) if trade['rsi'] else 50.0,
                        'adx': float(trade['adx']) if trade['adx'] else 25.0,
                        'volume': 1000.0,
                        'atr': abs(entry_price - stop_loss),
                        'volume_ma_20': 1000.0,
                        'ema_50': entry_price,
                        'ema_200': entry_price
                    },
                    'strategy': 'rsi_divergence',
                    'signal_strength': float(trade['strength']) if trade['strength'] else 0.5,
                    'setup_quality': 70.0,
                    'regime': trade['market_regime'] or 'SIDEWAYS',
                    'exit_reason': 'TAKE_PROFIT' if label == 1 else 'STOP_LOSS'
                })
            
            # Treinar modelo
            metrics = self.ml_filter.train(training_data, test_size=0.2, num_rounds=100)
            
            self.ml_filter_enabled = True
            self.ml_training_metrics = metrics
            
            logger.info(f"🤖 ML Filter trained successfully!")
            logger.info(f"   Samples: {len(training_data)}")
            logger.info(f"   Accuracy: {metrics['accuracy']:.2%}")
            logger.info(f"   Precision: {metrics['precision']:.2%}")
            logger.info(f"   Recall: {metrics['recall']:.2%}")
            logger.info(f"   AUC: {metrics['auc']:.2f}")
            
            return {
                'success': True,
                'message': 'ML Filter trained successfully',
                'samples': len(training_data),
                'metrics': metrics
            }
            
        except Exception as e:
            logger.error(f"🤖 Error initializing ML Filter: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def disable_ml_filter(self):
        """Desabilita o ML Filter"""
        self.ml_filter_enabled = False
        logger.info("🤖 ML Filter disabled")
    
    def get_ml_filter_stats(self) -> Dict[str, Any]:
        """
        📊 Retorna estatísticas do ML Filter
        """
        return {
            'enabled': self.ml_filter_enabled,
            'available': ML_FILTER_AVAILABLE,
            'min_score': self.min_ml_score,
            'stats': self.ml_stats,
            'training_metrics': self.ml_training_metrics
        }
    
    async def get_recent_signals_from_db(self, limit: int = 50, hours: int = 24):
        """
        Busca sinais recentes do banco de dados
        """
        if not self.db_pool:
            return []
        
        try:
            async with self.db_pool.acquire() as conn:
                query = """
                SELECT 
                    signal_id, timestamp, symbol, timeframe, signal_type, direction,
                    strength, entry_price, stop_loss, take_profit, current_price,
                    rsi, adx, reason, executed, execution_reason
                FROM autotrade_signals
                WHERE timestamp >= NOW() - INTERVAL '%s hours'
                  AND signal_type LIKE '%%divergence%%'
                ORDER BY timestamp DESC
                LIMIT $1
                """
                
                rows = await conn.fetch(query % hours, limit)
                
                signals = []
                for row in rows:
                    signals.append({
                        'signal_id': row['signal_id'],
                        'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None,
                        'symbol': row['symbol'],
                        'timeframe': row['timeframe'],
                        'type': row['signal_type'],
                        'direction': row['direction'],
                        'strength': float(row['strength']) if row['strength'] else 0.0,
                        'entry': float(row['entry_price']) if row['entry_price'] else 0.0,
                        'stop_loss': float(row['stop_loss']) if row['stop_loss'] else 0.0,
                        'take_profit': float(row['take_profit']) if row['take_profit'] else 0.0,
                        'price': float(row['current_price']) if row['current_price'] else 0.0,
                        'rsi': float(row['rsi']) if row['rsi'] else 0.0,
                        'adx': float(row['adx']) if row['adx'] else 0.0,
                        'reason': row['reason'],
                        'executed': row['executed'],
                        'execution_reason': row['execution_reason']
                    })
                
                return signals
                
        except Exception as e:
            logger.error(f"Error fetching signals from DB: {e}")
            return []
    
    async def _create_paper_trade_from_signal(self, signal: DivergenceSignal, signal_id: str, ml_score: float = 0.5) -> Optional[int]:
        """
        🤖 Cria automaticamente um paper trade a partir de um sinal detectado
        
        Position sizing ajustado por ML score:
        - ML >= 80%: 3% risk (high confidence)
        - ML >= 60%: 2% risk (medium confidence)
        - ML < 60%: 1% risk (low confidence)
        """
        if not self.db_pool:
            return None
        
        try:
            # Criar session_id se não existir
            if not self.auto_trade_session_id:
                self.auto_trade_session_id = f"auto_scanner_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                
                # Criar sessão de paper trading
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO paper_trading_sessions (
                            session_id, initial_capital, current_capital, strategy, 
                            status, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (session_id) DO NOTHING
                    """, 
                    self.auto_trade_session_id,
                    10000.0,  # Capital inicial
                    10000.0,
                    'rsi_divergence_auto',
                    'active',
                    datetime.utcnow())
            
            async with self.db_pool.acquire() as conn:
                # Calcular posição baseada em risco ajustado pelo ML
                capital = 10000.0
                
                # 🤖 ML POSITION SIZING ADJUSTMENT
                if ml_score >= 0.8:
                    risk_pct = 0.03  # High confidence: 3% risk
                    logger.info(f"🤖 High ML confidence ({ml_score:.2%}) -> 3% risk")
                elif ml_score >= 0.6:
                    risk_pct = 0.02  # Medium confidence: 2% risk (padrão)
                    logger.info(f"🤖 Medium ML confidence ({ml_score:.2%}) -> 2% risk")
                else:
                    risk_pct = 0.01  # Low confidence: 1% risk (conservador)
                    logger.info(f"🤖 Low ML confidence ({ml_score:.2%}) -> 1% risk")
                
                risk_amount = capital * risk_pct
                entry_price = signal.entry
                stop_loss = signal.stop_loss
                stop_distance = abs(entry_price - stop_loss)
                
                if stop_distance > 0:
                    position_size = risk_amount / stop_distance
                else:
                    position_size = 0.001  # Posição mínima
                
                # Inserir paper trade
                trade_id = await conn.fetchval("""
                    INSERT INTO paper_trading_trades (
                        session_id, symbol, side, entry_price, quantity,
                        stop_loss, take_profit, status, entry_time,
                        signal_source, signal_strength, timeframe
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    RETURNING id
                """,
                self.auto_trade_session_id,
                signal.symbol.replace('/', ''),  # BTCUSDT format
                'BUY' if 'bullish' in signal.type.value else 'SELL',
                entry_price,
                position_size,
                stop_loss,
                signal.take_profit,
                'open',
                datetime.utcnow(),
                f"scanner_{signal.type.value}",
                signal.strength,
                signal.timeframe)
                
                # Vincular sinal ao trade
                await conn.execute("""
                    UPDATE autotrade_signals
                    SET paper_trading_trade_id = $1, executed = true, execution_reason = $2
                    WHERE signal_id = $3
                """,
                trade_id,
                f"Auto-executed by scanner | Strength: {signal.strength:.2%}",
                signal_id)
                
                logger.info(f"🤖 Auto paper trade created: ID={trade_id} | {signal.symbol} {signal.type.value} | Strength: {signal.strength:.2%}")
                return trade_id
                
        except Exception as e:
            logger.error(f"Error creating auto paper trade: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def get_auto_trade_performance(self) -> Dict[str, Any]:
        """
        📊 Retorna estatísticas de performance dos trades auto-executados
        """
        if not self.db_pool or not self.auto_trade_session_id:
            return {
                'enabled': False,
                'message': 'Auto-trade not enabled'
            }
        
        try:
            async with self.db_pool.acquire() as conn:
                # Buscar trades da sessão
                trades = await conn.fetch("""
                    SELECT 
                        id, symbol, side, entry_price, exit_price, quantity,
                        stop_loss, take_profit, status, pnl, pnl_percent,
                        entry_time, exit_time, signal_source, signal_strength, timeframe
                    FROM paper_trading_trades
                    WHERE session_id = $1
                    ORDER BY entry_time DESC
                """, self.auto_trade_session_id)
                
                # Calcular estatísticas
                total_trades = len(trades)
                closed_trades = [t for t in trades if t['status'] == 'closed']
                open_trades = [t for t in trades if t['status'] == 'open']
                
                wins = [t for t in closed_trades if t['pnl'] and t['pnl'] > 0]
                losses = [t for t in closed_trades if t['pnl'] and t['pnl'] < 0]
                
                win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0.0
                total_pnl = sum(t['pnl'] or 0 for t in closed_trades)
                avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0.0
                avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0.0
                
                # Buscar informações da sessão
                session = await conn.fetchrow("""
                    SELECT initial_capital, current_capital, total_trades, 
                           total_pnl, win_rate, created_at
                    FROM paper_trading_sessions
                    WHERE session_id = $1
                """, self.auto_trade_session_id)
                
                return {
                    'enabled': True,
                    'session_id': self.auto_trade_session_id,
                    'created_at': session['created_at'].isoformat() if session else None,
                    'total_trades': total_trades,
                    'open_trades': len(open_trades),
                    'closed_trades': len(closed_trades),
                    'wins': len(wins),
                    'losses': len(losses),
                    'win_rate': round(win_rate, 2),
                    'total_pnl': round(total_pnl, 2),
                    'avg_win': round(avg_win, 2),
                    'avg_loss': round(avg_loss, 2),
                    'profit_factor': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0.0,
                    'initial_capital': float(session['initial_capital']) if session else 10000.0,
                    'current_capital': float(session['current_capital']) if session else 10000.0,
                    'return_pct': round((float(session['current_capital']) / float(session['initial_capital']) - 1) * 100, 2) if session else 0.0,
                    'recent_trades': [
                        {
                            'id': t['id'],
                            'symbol': t['symbol'],
                            'side': t['side'],
                            'entry_price': float(t['entry_price']) if t['entry_price'] else 0.0,
                            'exit_price': float(t['exit_price']) if t['exit_price'] else 0.0,
                            'quantity': float(t['quantity']) if t['quantity'] else 0.0,
                            'pnl': float(t['pnl']) if t['pnl'] else 0.0,
                            'pnl_percent': float(t['pnl_percent']) if t['pnl_percent'] else 0.0,
                            'status': t['status'],
                            'signal_source': t['signal_source'],
                            'signal_strength': float(t['signal_strength']) if t['signal_strength'] else 0.0,
                            'entry_time': t['entry_time'].isoformat() if t['entry_time'] else None,
                            'exit_time': t['exit_time'].isoformat() if t['exit_time'] else None
                        }
                        for t in trades[:10]  # Últimos 10 trades
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error fetching auto-trade performance: {e}")
            return {
                'enabled': True,
                'error': str(e)
            }


# Adicionar import no topo do arquivo
import uuid


# Instância global do scanner
_scanner_instance: Optional[MultiSymbolScanner] = None


def get_scanner(config: ScannerConfig = None) -> MultiSymbolScanner:
    """
    Retorna instância singleton do scanner
    """
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = MultiSymbolScanner(config)
    return _scanner_instance


async def quick_scan(symbols: List[str] = None, timeframes: List[str] = None) -> Dict[str, Any]:
    """
    Função utilitária para scan rápido
    
    Exemplo:
        result = await quick_scan(["BTC/USDT", "ETH/USDT"], ["1h"])
    """
    config = ScannerConfig()
    if symbols:
        config.symbols = symbols
    if timeframes:
        config.timeframes = timeframes
    
    scanner = MultiSymbolScanner(config)
    return await scanner.scan_once()
