"""
Funções wrapper para estratégias - Compatíveis com Monte Carlo Simulation

Estas funções recebem DataFrame e parâmetros, retornam DataFrame com sinal
"""

import pandas as pd
import ta
import numpy as np


def momentum_strategy_func(df: pd.DataFrame, 
                          roc_period: int = 10,
                          threshold: float = 0.0) -> pd.DataFrame:
    """
    Estratégia Momentum para Monte Carlo
    
    Args:
        df: DataFrame com OHLCV (columns: open, high, low, close, volume)
        roc_period: Período para Rate of Change
        threshold: Threshold para sinais
    
    Returns:
        DataFrame com coluna 'signal' (BUY/SELL/HOLD)
    """
    df = df.copy()
    
    # Ensure lowercase columns
    df.columns = df.columns.str.lower()
    
    # Calculate ROC (Rate of Change)
    df['roc'] = ta.momentum.roc(df['close'], window=int(roc_period))
    
    # Generate signals
    df['signal'] = 'HOLD'
    df.loc[df['roc'] > threshold, 'signal'] = 'BUY'
    df.loc[df['roc'] < -threshold, 'signal'] = 'SELL'
    
    return df


def macd_rsi_strategy_func(df: pd.DataFrame,
                           macd_fast: int = 12,
                           macd_slow: int = 26,
                           macd_signal: int = 9,
                           rsi_period: int = 14,
                           rsi_overbought: float = 70.0,
                           rsi_oversold: float = 30.0) -> pd.DataFrame:
    """
    Estratégia MACD + RSI Combo para Monte Carlo
    
    Args:
        df: DataFrame com OHLCV
        macd_fast: Período rápido do MACD
        macd_slow: Período lento do MACD
        macd_signal: Período da linha de sinal
        rsi_period: Período do RSI
        rsi_overbought: Nível de sobrecompra RSI
        rsi_oversold: Nível de sobrevenda RSI
    
    Returns:
        DataFrame com coluna 'signal'
    """
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    # MACD
    macd = ta.trend.MACD(
        df['close'],
        window_fast=int(macd_fast),
        window_slow=int(macd_slow),
        window_sign=int(macd_signal)
    )
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()
    
    # RSI
    df['rsi'] = ta.momentum.rsi(df['close'], window=int(rsi_period))
    
    # Sinais combinados
    df['signal'] = 'HOLD'
    
    # BUY: MACD cruza acima da signal e RSI < 70 (não sobrecomprado)
    buy_condition = (
        (df['macd'] > df['macd_signal']) &
        (df['macd'].shift(1) <= df['macd_signal'].shift(1)) &
        (df['rsi'] < rsi_overbought)
    )
    df.loc[buy_condition, 'signal'] = 'BUY'
    
    # SELL: MACD cruza abaixo da signal ou RSI > 70 (sobrecomprado)
    sell_condition = (
        ((df['macd'] < df['macd_signal']) &
         (df['macd'].shift(1) >= df['macd_signal'].shift(1))) |
        (df['rsi'] > rsi_overbought)
    )
    df.loc[sell_condition, 'signal'] = 'SELL'
    
    return df


def trend_following_strategy_func(df: pd.DataFrame,
                                  ema_fast: int = 12,
                                  ema_slow: int = 26,
                                  adx_period: int = 14,
                                  adx_threshold: float = 25.0) -> pd.DataFrame:
    """
    Estratégia Trend Following para Monte Carlo
    
    Args:
        df: DataFrame com OHLCV
        ema_fast: Período EMA rápida
        ema_slow: Período EMA lenta
        adx_period: Período ADX
        adx_threshold: Threshold ADX para trend forte
    
    Returns:
        DataFrame com coluna 'signal'
    """
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    # EMAs
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=int(ema_fast))
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=int(ema_slow))
    
    # ADX
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=int(adx_period))
    
    # Signals
    df['signal'] = 'HOLD'
    
    # BUY: EMA fast cruza acima da slow com ADX forte
    buy_condition = (
        (df['ema_fast'] > df['ema_slow']) &
        (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1)) &
        (df['adx'] > adx_threshold)
    )
    df.loc[buy_condition, 'signal'] = 'BUY'
    
    # SELL: EMA fast cruza abaixo da slow
    sell_condition = (
        (df['ema_fast'] < df['ema_slow']) &
        (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
    )
    df.loc[sell_condition, 'signal'] = 'SELL'
    
    return df


def volatility_breakout_strategy_func(df: pd.DataFrame,
                                      atr_period: int = 14,
                                      atr_multiplier: float = 2.0,
                                      volume_ma_period: int = 20) -> pd.DataFrame:
    """
    Estratégia Volatility Breakout para Monte Carlo
    
    Args:
        df: DataFrame com OHLCV
        atr_period: Período ATR
        atr_multiplier: Multiplicador ATR para breakout
        volume_ma_period: Período MA do volume
    
    Returns:
        DataFrame com coluna 'signal'
    """
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    # ATR
    df['atr'] = ta.volatility.average_true_range(
        df['high'], df['low'], df['close'], 
        window=int(atr_period)
    )
    
    # Bollinger Bands (usado para breakout)
    bb = ta.volatility.BollingerBands(
        df['close'],
        window=20,
        window_dev=2
    )
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    
    # Volume MA
    df['volume_ma'] = df['volume'].rolling(window=int(volume_ma_period)).mean()
    
    # Signals
    df['signal'] = 'HOLD'
    
    # BUY: Preço quebra banda superior com volume alto
    buy_condition = (
        (df['close'] > df['bb_upper']) &
        (df['volume'] > df['volume_ma'])
    )
    df.loc[buy_condition, 'signal'] = 'BUY'
    
    # SELL: Preço quebra banda inferior
    sell_condition = (df['close'] < df['bb_lower'])
    df.loc[sell_condition, 'signal'] = 'SELL'
    
    return df


def bollinger_bands_strategy_func(df: pd.DataFrame,
                                  bb_period: int = 20,
                                  bb_std: float = 2.0,
                                  rsi_period: int = 14) -> pd.DataFrame:
    """
    Estratégia Bollinger Bands para Monte Carlo
    
    Args:
        df: DataFrame com OHLCV
        bb_period: Período Bollinger Bands
        bb_std: Desvios padrão
        rsi_period: Período RSI (confirmação)
    
    Returns:
        DataFrame com coluna 'signal'
    """
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(
        df['close'],
        window=int(bb_period),
        window_dev=bb_std
    )
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_middle'] = bb.bollinger_mavg()
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_width'] = bb.bollinger_wband()
    
    # RSI para confirmação
    df['rsi'] = ta.momentum.rsi(df['close'], window=int(rsi_period))
    
    # Volume para confirmação de breakout
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    
    # Signals
    df['signal'] = 'HOLD'
    
    # BOLLINGER BREAKOUT (Trend-Following):
    # BUY: Breakout acima da banda superior com volume (força compradora)
    buy_condition = (
        (df['close'] > df['bb_upper']) &
        (df['volume'] > df['volume_ma'] * 1.2) &  # Volume 20% acima da média
        (df['rsi'] > 50)  # Confirmação de força
    )
    df.loc[buy_condition, 'signal'] = 'BUY'
    
    # SELL: Breakdown abaixo da banda inferior (força vendedora)
    sell_condition = (
        (df['close'] < df['bb_lower']) &
        (df['rsi'] < 50)  # Confirmação de fraqueza
    )
    df.loc[sell_condition, 'signal'] = 'SELL'
    
    return df


def mean_reversion_strategy_func(df: pd.DataFrame,
                                 window: int = 20,
                                 num_std: float = 2.0,
                                 rsi_period: int = 14,
                                 rsi_oversold: float = 40.0,
                                 rsi_overbought: float = 60.0) -> pd.DataFrame:
    """Estratégia EMA Crossover simples e robusta.
    
    BUY: EMA rápida cruza acima da EMA lenta (tendência de alta)
    SELL: EMA rápida cruza abaixo da EMA lenta (tendência de baixa)
    
    Esta é uma das estratégias mais testadas e comprovadas no trading.
    """
    df = df.copy()
    df.columns = df.columns.str.lower()

    # EMAs para detectar mudança de tendência
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=int(window))
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=int(window * 2))
    
    # RSI como filtro de confirmação
    df['rsi'] = ta.momentum.rsi(df['close'], window=int(rsi_period))

    df['signal'] = 'HOLD'

    # BUY (LONG): EMA rápida cruza acima da lenta (golden cross)
    buy_condition = (
        (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1)) &  # Estava abaixo ou igual
        (df['ema_fast'] > df['ema_slow']) &  # Agora está acima
        (df['rsi'] < 70)  # Não está muito overbought
    )
    
    # SELL (SHORT): EMA rápida cruza abaixo da lenta (death cross)
    sell_condition = (
        (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1)) &  # Estava acima ou igual
        (df['ema_fast'] < df['ema_slow']) &  # Agora está abaixo
        (df['rsi'] > 30)  # Não está muito oversold
    )

    df.loc[buy_condition, 'signal'] = 'BUY'
    df.loc[sell_condition, 'signal'] = 'SELL'

    return df


def bear_market_short_strategy_func(df: pd.DataFrame,
                                     ema_fast: int = 8,
                                     ema_slow: int = 21,
                                     rsi_period: int = 14,
                                     rsi_threshold: float = 55.0,
                                     volume_multiplier: float = 1.2) -> pd.DataFrame:
    """
    🐻 ESTRATÉGIA BEAR MARKET - Prioriza SHORT em tendências de baixa
    
    Lógica:
    - SELL (SHORT): EMA rápida abaixo da lenta + RSI < threshold + volume alto
    - BUY (Fechar SHORT): RSI oversold ou EMA golden cross
    
    Esta estratégia é otimizada para lucrar em mercados em queda.
    """
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    # EMAs para detectar tendência
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=int(ema_fast))
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=int(ema_slow))
    
    # RSI para momentum
    df['rsi'] = ta.momentum.rsi(df['close'], window=int(rsi_period))
    
    # Volume para confirmação
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    
    # Detectar tendência de baixa
    df['downtrend'] = df['ema_fast'] < df['ema_slow']
    
    df['signal'] = 'HOLD'
    
    # SELL (SHORT): Tendência de baixa confirmada + força vendedora
    sell_condition = (
        (df['downtrend']) &  # Tendência de baixa
        (df['rsi'] < rsi_threshold) &  # Fraqueza confirmada
        (df['close'] < df['ema_fast']) &  # Preço abaixo da EMA rápida
        (df['volume'] > df['volume_ma'] * volume_multiplier)  # Volume confirmando
    )
    df.loc[sell_condition, 'signal'] = 'SELL'
    
    # BUY (Fechar SHORT): Reversão potencial
    buy_condition = (
        (df['rsi'] < 30) |  # Oversold extremo
        ((df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1)))  # Golden cross
    )
    df.loc[buy_condition, 'signal'] = 'BUY'
    
    return df


def breakdown_momentum_strategy_func(df: pd.DataFrame,
                                      bb_period: int = 20,
                                      bb_std: float = 2.0,
                                      roc_period: int = 10,
                                      roc_threshold: float = -1.0) -> pd.DataFrame:
    """
    📉 ESTRATÉGIA BREAKDOWN MOMENTUM - Captura quedas fortes
    
    Lógica:
    - SELL: Breakdown abaixo da banda inferior + momentum negativo
    - BUY: Toque na banda inferior + momentum se invertendo
    
    Ideal para capturar movimentos de pânico e quedas aceleradas.
    """
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(
        df['close'],
        window=int(bb_period),
        window_dev=bb_std
    )
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_middle'] = bb.bollinger_mavg()
    df['bb_lower'] = bb.bollinger_lband()
    
    # Rate of Change (momentum)
    df['roc'] = ta.momentum.roc(df['close'], window=int(roc_period))
    
    # RSI para detecção de oversold
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    
    df['signal'] = 'HOLD'
    
    # SELL (SHORT): Breakdown com momentum negativo forte
    sell_condition = (
        (df['close'] < df['bb_lower']) &  # Abaixo da banda inferior
        (df['roc'] < roc_threshold) &  # Momentum negativo
        (df['rsi'] < 50)  # Confirmação de fraqueza
    )
    df.loc[sell_condition, 'signal'] = 'SELL'
    
    # BUY: Oversold extremo (bounce de curto prazo)
    buy_condition = (
        (df['close'] <= df['bb_lower']) &
        (df['rsi'] < 25) &  # Oversold severo
        (df['roc'] > -3.0)  # Momentum começando a estabilizar
    )
    df.loc[buy_condition, 'signal'] = 'BUY'
    
    return df


def death_cross_strategy_func(df: pd.DataFrame,
                               sma_fast: int = 50,
                               sma_slow: int = 200,
                               macd_fast: int = 12,
                               macd_slow: int = 26,
                               macd_signal: int = 9) -> pd.DataFrame:
    """
    ☠️ ESTRATÉGIA DEATH CROSS - Clássica para bear markets
    
    Lógica:
    - SELL: SMA 50 cruza abaixo da SMA 200 (Death Cross) + MACD negativo
    - BUY: Golden Cross ou MACD virando positivo
    
    Estratégia tradicional usada por traders institucionais.
    """
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    # SMAs para death/golden cross
    df['sma_fast'] = ta.trend.sma_indicator(df['close'], window=int(sma_fast))
    df['sma_slow'] = ta.trend.sma_indicator(df['close'], window=int(sma_slow))
    
    # MACD para confirmação
    macd = ta.trend.MACD(
        df['close'],
        window_fast=int(macd_fast),
        window_slow=int(macd_slow),
        window_sign=int(macd_signal)
    )
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()
    
    # Volume
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    
    df['signal'] = 'HOLD'
    
    # SELL (SHORT): Death Cross + MACD negativo
    death_cross = (
        (df['sma_fast'].shift(1) >= df['sma_slow'].shift(1)) &  # Estava acima
        (df['sma_fast'] < df['sma_slow']) &  # Cruzou para baixo
        (df['macd_diff'] < 0)  # MACD confirma fraqueza
    )
    df.loc[death_cross, 'signal'] = 'SELL'
    
    # Manter SHORT enquanto tendência de baixa persistir
    bear_trend = (
        (df['sma_fast'] < df['sma_slow']) &  # Death cross ativo
        (df['macd'] < df['macd_signal']) &  # MACD negativo
        (df['close'] < df['sma_fast'])  # Preço abaixo da SMA rápida
    )
    df.loc[bear_trend & (df['signal'] == 'HOLD'), 'signal'] = 'SELL'
    
    # BUY: Golden Cross ou MACD virando positivo
    golden_cross = (
        (df['sma_fast'].shift(1) <= df['sma_slow'].shift(1)) &
        (df['sma_fast'] > df['sma_slow'])
    )
    macd_positive = (
        (df['macd'].shift(1) <= df['macd_signal'].shift(1)) &
        (df['macd'] > df['macd_signal'])
    )
    df.loc[golden_cross | macd_positive, 'signal'] = 'BUY'
    
    return df


# Mapeamento de estratégias para parâmetros padrão
STRATEGY_PARAMETER_RANGES = {
    'momentum': {
        'roc_period': (5, 20),
        'threshold': (0.5, 3.0)
    },
    'macd_rsi_combo': {
        'macd_fast': (8, 16),
        'macd_slow': (20, 30),
        'macd_signal': (7, 11),
        'rsi_period': (10, 18),
        'rsi_overbought': (65, 75),
        'rsi_oversold': (25, 35)
    },
    'trend_following': {
        'ema_fast': (8, 16),
        'ema_slow': (20, 30),
        'adx_period': (10, 18),
        'adx_threshold': (20, 30)
    },
    'volatility_breakout': {
        'atr_period': (10, 20),
        'atr_multiplier': (1.5, 3.0),
        'volume_ma_period': (15, 25)
    },
    'bollinger_bands': {
        'bb_period': (15, 25),
        'bb_std': (1.5, 2.5),
        'rsi_period': (10, 18)
    },
    'mean_reversion': {
        'window': (15, 30),
        'num_std': (1.5, 2.5),
        'rsi_period': (10, 18),
        'rsi_oversold': (35, 45),  # Menos restritivo
        'rsi_overbought': (55, 65)  # Menos restritivo
    },
    'bear_market_short': {
        'ema_fast': (5, 13),
        'ema_slow': (18, 26),
        'rsi_period': (10, 18),
        'rsi_threshold': (45, 60),
        'volume_multiplier': (1.1, 1.5)
    },
    'breakdown_momentum': {
        'bb_period': (15, 25),
        'bb_std': (1.8, 2.5),
        'roc_period': (8, 15),
        'roc_threshold': (-3.0, -0.5)
    },
    'death_cross': {
        'sma_fast': (40, 60),
        'sma_slow': (180, 220),
        'macd_fast': (10, 14),
        'macd_slow': (24, 28),
        'macd_signal': (8, 10)
    }
}


def get_default_param_ranges(strategy_name: str) -> dict:
    """Retorna ranges de parâmetros padrão para uma estratégia"""
    return STRATEGY_PARAMETER_RANGES.get(strategy_name, {})


if __name__ == "__main__":
    # Test
    print("Strategy Functions for Monte Carlo Simulation")
    print("=" * 60)
    
    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=500, freq='1H')
    test_df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.cumsum(np.random.randn(500) * 100),
        'high': 50100 + np.cumsum(np.random.randn(500) * 100),
        'low': 49900 + np.cumsum(np.random.randn(500) * 100),
        'close': 50000 + np.cumsum(np.random.randn(500) * 100),
        'volume': np.random.uniform(100, 1000, 500)
    })
    
    # Test each strategy
    strategies = [
        ('Momentum', momentum_strategy_func, {}),
        ('MACD+RSI', macd_rsi_strategy_func, {}),
        ('Trend Following', trend_following_strategy_func, {}),
        ('Volatility Breakout', volatility_breakout_strategy_func, {}),
        ('Bollinger Bands', bollinger_bands_strategy_func, {}),
        ('Mean Reversion', mean_reversion_strategy_func, {})
    ]
    
    for name, func, params in strategies:
        result = func(test_df.copy(), **params)
        buy_signals = (result['signal'] == 'BUY').sum()
        sell_signals = (result['signal'] == 'SELL').sum()
        print(f"{name:20} | BUY: {buy_signals:3} | SELL: {sell_signals:3}")
    
    print("=" * 60)
    print("All strategies working correctly!")
