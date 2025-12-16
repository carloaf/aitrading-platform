"""
Market Regime Detector - Identifica automaticamente Bull/Bear/Lateral Market

Este módulo analisa múltiplos indicadores técnicos para classificar o regime
de mercado atual e recomendar estratégias apropriadas.

DISCLAIMER: Esta ferramenta é para fins educacionais e de análise.
Não constitui aconselhamento financeiro.
"""

import pandas as pd
import numpy as np
import ta
from enum import Enum
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Tipos de regime de mercado"""
    BULL = "bull"           # Mercado em alta
    BEAR = "bear"           # Mercado em baixa
    SIDEWAYS = "sideways"   # Mercado lateral/consolidação
    VOLATILE = "volatile"   # Mercado altamente volátil
    UNKNOWN = "unknown"     # Dados insuficientes


@dataclass
class RegimeAnalysis:
    """Resultado da análise de regime de mercado"""
    regime: MarketRegime
    confidence: float  # 0-100%
    trend_strength: float  # -100 a +100 (negativo = bear, positivo = bull)
    volatility: float  # 0-100%
    signals: Dict[str, str]  # Sinais individuais de cada indicador
    recommended_strategies: List[str]
    description: str
    
    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 2),
            "trend_strength": round(self.trend_strength, 2),
            "volatility": round(self.volatility, 2),
            "signals": self.signals,
            "recommended_strategies": self.recommended_strategies,
            "description": self.description
        }


class MarketRegimeDetector:
    """
    Detector de Regime de Mercado usando múltiplos indicadores técnicos
    
    Indicadores utilizados:
    - Moving Averages (SMA 50, 200) para tendência de longo prazo
    - ADX (Average Directional Index) para força da tendência
    - ATR (Average True Range) para volatilidade
    - RSI (Relative Strength Index) para momentum
    - Bollinger Bands Width para volatilidade
    - Volume Analysis para confirmação
    """
    
    def __init__(self,
                 sma_fast: int = 50,
                 sma_slow: int = 200,
                 adx_period: int = 14,
                 atr_period: int = 14,
                 rsi_period: int = 14,
                 bb_period: int = 20,
                 bb_std: float = 2.0):
        """
        Inicializa o detector com parâmetros configuráveis
        
        Args:
            sma_fast: Período da SMA rápida (padrão: 50)
            sma_slow: Período da SMA lenta (padrão: 200)
            adx_period: Período do ADX (padrão: 14)
            atr_period: Período do ATR (padrão: 14)
            rsi_period: Período do RSI (padrão: 14)
            bb_period: Período das Bollinger Bands (padrão: 20)
            bb_std: Desvios padrão das Bollinger Bands (padrão: 2.0)
        """
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        
    def analyze(self, df: pd.DataFrame) -> RegimeAnalysis:
        """
        Analisa o DataFrame e retorna o regime de mercado detectado
        
        Args:
            df: DataFrame com OHLCV (open, high, low, close, volume)
            
        Returns:
            RegimeAnalysis com classificação e métricas
        """
        df = df.copy()
        df.columns = df.columns.str.lower()
        
        # Converter Decimal para float (dados do PostgreSQL)
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Validar dados mínimos - FIX: Reduzido de 200 para 50
        # 50 candles é suficiente para ADX(14), RSI(14), BB(20), ATR(14)
        # SMA200 é opcional - usamos SMA50 como fallback quando não disponível
        min_periods = 50
        if len(df) < min_periods:
            logger.warning(f"Dados insuficientes: {len(df)} candles (mínimo: {min_periods})")
            return RegimeAnalysis(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                trend_strength=0.0,
                volatility=0.0,
                signals={},
                recommended_strategies=[],
                description=f"Dados insuficientes para análise (mínimo {min_periods} candles)"
            )
        
        # Calcular todos os indicadores
        signals = {}
        
        # 1. MOVING AVERAGES - Tendência de longo prazo
        df['sma_fast'] = ta.trend.sma_indicator(df['close'], window=self.sma_fast)
        df['sma_slow'] = ta.trend.sma_indicator(df['close'], window=self.sma_slow)
        
        current_price = df['close'].iloc[-1]
        sma_fast_val = df['sma_fast'].iloc[-1]
        sma_slow_val = df['sma_slow'].iloc[-1]
        
        # FIX: Tratar NaN em sma_slow (quando não temos 200 candles)
        # Usar SMA50 como fallback se SMA200 não disponível
        if pd.isna(sma_slow_val):
            df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
            sma_slow_val = df['sma_50'].iloc[-1]
            if pd.isna(sma_slow_val):
                sma_slow_val = current_price  # Último fallback
        
        if current_price > sma_fast_val > sma_slow_val:
            signals['ma_trend'] = 'BULL'
        elif current_price < sma_fast_val < sma_slow_val:
            signals['ma_trend'] = 'BEAR'
        else:
            signals['ma_trend'] = 'SIDEWAYS'
        
        # 2. ADX - Força da tendência
        adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=self.adx_period)
        df['adx'] = adx.adx()
        df['di_plus'] = adx.adx_pos()
        df['di_minus'] = adx.adx_neg()
        
        adx_val = df['adx'].iloc[-1]
        di_plus = df['di_plus'].iloc[-1]
        di_minus = df['di_minus'].iloc[-1]
        
        # ADX thresholds normais (estáveis)
        if adx_val > 25:
            if di_plus > di_minus:
                signals['adx'] = 'STRONG_BULL'
            else:
                signals['adx'] = 'STRONG_BEAR'
        elif adx_val > 20:
            signals['adx'] = 'MODERATE_TREND'
        else:
            signals['adx'] = 'WEAK_TREND'
        
        # 3. ATR - Volatilidade
        df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], 
                                                      window=self.atr_period)
        atr_val = df['atr'].iloc[-1]
        atr_pct = (atr_val / current_price) * 100
        
        if atr_pct > 5:
            signals['volatility'] = 'HIGH'
        elif atr_pct > 2:
            signals['volatility'] = 'MODERATE'
        else:
            signals['volatility'] = 'LOW'
        
        # 4. RSI - Momentum
        df['rsi'] = ta.momentum.rsi(df['close'], window=self.rsi_period)
        rsi_val = df['rsi'].iloc[-1]
        
        if rsi_val > 70:
            signals['rsi'] = 'OVERBOUGHT'
        elif rsi_val > 55:
            signals['rsi'] = 'BULLISH'
        elif rsi_val < 30:
            signals['rsi'] = 'OVERSOLD'
        elif rsi_val < 45:
            signals['rsi'] = 'BEARISH'
        else:
            signals['rsi'] = 'NEUTRAL'
        
        # 5. BOLLINGER BANDS - Volatilidade e breakouts
        bb = ta.volatility.BollingerBands(df['close'], window=self.bb_period, window_dev=self.bb_std)
        df['bb_width'] = bb.bollinger_wband() * 100
        
        bb_width = df['bb_width'].iloc[-1]
        if bb_width > 10:
            signals['bb'] = 'EXPANDING'
        elif bb_width < 3:
            signals['bb'] = 'SQUEEZING'
        else:
            signals['bb'] = 'NORMAL'
        
        # 5.1. PRICE RANGE ANALYSIS - Detecção de consolidação
        lookback = 168  # 7 days @ 1h candles
        if len(df) >= lookback:
            recent_high = df['high'].iloc[-lookback:].max()
            recent_low = df['low'].iloc[-lookback:].min()
            price_range = recent_high - recent_low
            range_pct = (price_range / current_price) * 100
            
            # Para BTC, range > $15k indica sideways de alta volatilidade
            if price_range > 15000 and bb_width < 8:
                signals['consolidation'] = 'HIGH_RANGE_SIDEWAYS'
            elif range_pct < 10 and adx_val < 20:
                signals['consolidation'] = 'LOW_RANGE_SIDEWAYS'
            else:
                signals['consolidation'] = 'NO_CONSOLIDATION'
        else:
            signals['consolidation'] = 'INSUFFICIENT_DATA'
        
        # 6. VOLUME ANALYSIS
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        volume_ratio = df['volume'].iloc[-1] / df['volume_sma'].iloc[-1]
        
        if volume_ratio > 1.5:
            signals['volume'] = 'HIGH'
        elif volume_ratio > 1.0:
            signals['volume'] = 'NORMAL'
        else:
            signals['volume'] = 'LOW'
        
        # 7. PRICE MOMENTUM (últimos 7 e 30 dias)
        returns_7d = ((df['close'].iloc[-1] / df['close'].iloc[-7]) - 1) * 100 if len(df) >= 7 else 0
        returns_30d = ((df['close'].iloc[-1] / df['close'].iloc[-30]) - 1) * 100 if len(df) >= 30 else 0
        
        signals['momentum_7d'] = f"{returns_7d:+.2f}%"
        signals['momentum_30d'] = f"{returns_30d:+.2f}%"
        
        # CLASSIFICAR REGIME baseado em todos os sinais
        regime, confidence, trend_strength = self._classify_regime(
            signals, adx_val, atr_pct, rsi_val, returns_7d, returns_30d, bb_width
        )
        
        # RECOMENDAR ESTRATÉGIAS
        recommended_strategies = self._recommend_strategies(regime, signals)
        
        # GERAR DESCRIÇÃO
        description = self._generate_description(regime, signals, confidence)
        
        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility=atr_pct,
            signals=signals,
            recommended_strategies=recommended_strategies,
            description=description
        )
    
    def _classify_regime(self, signals: Dict, adx: float, atr_pct: float, 
                        rsi: float, ret_7d: float, ret_30d: float, bb_width: float) -> Tuple[MarketRegime, float, float]:
        """Classifica o regime de mercado baseado em múltiplos sinais"""
        
        bull_score = 0
        bear_score = 0
        sideways_score = 0
        volatile_score = 0
        
        # DEBUG: Log de entrada
        logger.debug(f"REGIME_CLASSIFY: ADX={adx:.2f}, ATR%={atr_pct:.2f}, RSI={rsi:.2f}, ret7d={ret_7d:.2f}%, ret30d={ret_30d:.2f}%, BB_width={bb_width:.2f}")
        
        # DETECÇÃO PRIORITÁRIA DE CONSOLIDAÇÃO
        # Se consolidação detectada, priorizar SIDEWAYS independente de outros sinais
        consolidation_signal = signals.get('consolidation', 'INSUFFICIENT_DATA')
        logger.debug(f"CONSOLIDATION_SIGNAL: {consolidation_signal}")
        
        if consolidation_signal in ['HIGH_RANGE_SIDEWAYS', 'LOW_RANGE_SIDEWAYS']:
            sideways_score += 4
            logger.info(f"🔄 CONSOLIDATION DETECTED: {consolidation_signal} - sideways_score +4")
        
        # PONTUAÇÃO BASEADA EM SINAIS (ORIGINAL - STABLE)
        
        # Moving Averages (peso: 3)
        if signals['ma_trend'] == 'BULL':
            bull_score += 3
        elif signals['ma_trend'] == 'BEAR':
            bear_score += 3
        else:
            sideways_score += 3
        
        # ADX (peso: 2)
        if signals['adx'] == 'STRONG_BULL':
            bull_score += 2
        elif signals['adx'] == 'STRONG_BEAR':
            bear_score += 2
        elif signals['adx'] == 'WEAK_TREND':
            sideways_score += 2
        
        # RSI (peso: 1)
        if signals['rsi'] in ['BULLISH', 'OVERBOUGHT']:
            bull_score += 1
        elif signals['rsi'] in ['BEARISH', 'OVERSOLD']:
            bear_score += 1
        else:
            sideways_score += 1
        
        # Momentum (peso: 2)
        if ret_7d > 3 and ret_30d > 5:
            bull_score += 2
        elif ret_7d < -3 and ret_30d < -5:
            bear_score += 2
        else:
            sideways_score += 1
        
        # Volatilidade (peso: 1)
        if atr_pct > 5:
            volatile_score += 2
        
        # DETERMINAR REGIME
        total_score = bull_score + bear_score + sideways_score
        if total_score == 0:
            total_score = 1  # Evitar divisão por zero
        
        # DEBUG: Scores
        logger.debug(f"REGIME_SCORES: bull={bull_score}, bear={bear_score}, sideways={sideways_score}, volatile={volatile_score}")
        
        # Determinar regime (configuração original estável)
        if volatile_score >= 2 and adx < 20:
            regime = MarketRegime.VOLATILE
            confidence = min(volatile_score / total_score * 100, 100)
            trend_strength = 0
        elif bull_score > bear_score and bull_score > sideways_score:
            regime = MarketRegime.BULL
            confidence = (bull_score / total_score) * 100
            trend_strength = min((bull_score / total_score) * 100, 100)
        elif bear_score > bull_score and bear_score > sideways_score:
            regime = MarketRegime.BEAR
            confidence = (bear_score / total_score) * 100
            trend_strength = -min((bear_score / total_score) * 100, 100)
        else:
            regime = MarketRegime.SIDEWAYS
            confidence = (sideways_score / total_score) * 100
            trend_strength = ((bull_score - bear_score) / total_score) * 50
        
        # DEBUG: Resultado final
        logger.info(f"📊 REGIME_RESULT: {regime.value} (conf={confidence:.1f}%, trend_str={trend_strength:.1f})")
        
        return regime, confidence, trend_strength
    
    def _recommend_strategies(self, regime: MarketRegime, signals: Dict) -> List[str]:
        """Recomenda estratégias apropriadas para o regime detectado"""
        
        strategies = []
        
        if regime == MarketRegime.BULL:
            strategies = [
                "momentum",
                "trend_following",
                "macd_rsi_combo"
            ]
        elif regime == MarketRegime.BEAR:
            strategies = [
                "breakdown_momentum",
                "bear_market_short",
                "death_cross"
            ]
        elif regime == MarketRegime.SIDEWAYS:
            strategies = [
                "mean_reversion",
                "bollinger_bands"
            ]
        elif regime == MarketRegime.VOLATILE:
            strategies = [
                "volatility_breakout",
                "bollinger_bands"
            ]
        
        return strategies
    
    def _generate_description(self, regime: MarketRegime, signals: Dict, confidence: float) -> str:
        """Gera descrição textual da análise"""
        
        descriptions = {
            MarketRegime.BULL: f"Mercado em tendência de ALTA ({confidence:.0f}% confiança). "
                              f"Tendência confirmada por MA: {signals['ma_trend']}, ADX: {signals['adx']}, "
                              f"RSI: {signals['rsi']}. Momento favorável para estratégias long.",
            
            MarketRegime.BEAR: f"Mercado em tendência de BAIXA ({confidence:.0f}% confiança). "
                              f"Tendência confirmada por MA: {signals['ma_trend']}, ADX: {signals['adx']}, "
                              f"RSI: {signals['rsi']}. Momento favorável para estratégias short.",
            
            MarketRegime.SIDEWAYS: f"Mercado em CONSOLIDAÇÃO/LATERAL ({confidence:.0f}% confiança). "
                                  f"Sem tendência clara. ADX: {signals['adx']}, "
                                  f"Volatilidade: {signals['volatility']}. Favorável para mean reversion.",
            
            MarketRegime.VOLATILE: f"Mercado ALTAMENTE VOLÁTIL ({confidence:.0f}% confiança). "
                                  f"Alta volatilidade sem direção clara. "
                                  f"Volatilidade: {signals['volatility']}, Volume: {signals['volume']}. "
                                  f"Cuidado: alto risco!",
            
            MarketRegime.UNKNOWN: "Dados insuficientes para determinar regime de mercado."
        }
        
        return descriptions.get(regime, "Regime desconhecido")


def analyze_market_regime(df: pd.DataFrame, **kwargs) -> Dict:
    """
    Função helper para análise rápida de regime de mercado
    
    Args:
        df: DataFrame com OHLCV
        **kwargs: Parâmetros opcionais para o detector
        
    Returns:
        Dict com análise completa
    """
    detector = MarketRegimeDetector(**kwargs)
    analysis = detector.analyze(df)
    return analysis.to_dict()


if __name__ == "__main__":
    # Teste com dados sintéticos
    print("=" * 80)
    print("MARKET REGIME DETECTOR - Teste")
    print("=" * 80)
    
    # Gerar dados de teste (mercado de alta)
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=300, freq='1D')
    
    # Simular bull market
    trend = np.linspace(50000, 70000, 300)
    noise = np.random.normal(0, 500, 300)
    close_prices = trend + noise
    
    test_df = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices - 200,
        'high': close_prices + 300,
        'low': close_prices - 300,
        'close': close_prices,
        'volume': np.random.uniform(1000, 5000, 300)
    })
    
    detector = MarketRegimeDetector()
    analysis = detector.analyze(test_df)
    
    print(f"\n🎯 REGIME DETECTADO: {analysis.regime.value.upper()}")
    print(f"📊 Confiança: {analysis.confidence:.1f}%")
    print(f"📈 Força da Tendência: {analysis.trend_strength:.1f}")
    print(f"📉 Volatilidade: {analysis.volatility:.2f}%")
    print(f"\n💡 Descrição: {analysis.description}")
    print(f"\n🚀 Estratégias Recomendadas:")
    for strategy in analysis.recommended_strategies:
        print(f"   • {strategy}")
    print(f"\n📋 Sinais Individuais:")
    for key, value in analysis.signals.items():
        print(f"   • {key}: {value}")
    
    print("\n" + "=" * 80)
    print("✅ Teste concluído com sucesso!")
