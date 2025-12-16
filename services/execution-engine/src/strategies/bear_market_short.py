"""
BEAR MARKET SHORT STRATEGY - Institutional Grade
Versão: 1.0 | Implementado conforme PLANO_DE_MELHORAMENTO.md

Estratégia para mercados BEAR com confirmação tripla:
1. Death Cross (SMA50 < SMA200)
2. ADX forte (>25) com DI- > DI+
3. RSI < 50 e caindo
4. Volume acima da média

DISCLAIMER: Esta estratégia é para fins educacionais.
Past performance não garante resultados futuros.
Teste extensivamente com paper trading antes de usar capital real.
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Tuple, Optional
from .base_strategy import BaseStrategy


class BearMarketShortStrategy(BaseStrategy):
    """
    Estratégia SHORT para mercados BEAR confirmados
    
    Sinais de ENTRADA (SHORT):
    - SMA50 < SMA200 (Death Cross)
    - ADX > 25 com DI- > DI+
    - RSI < 50 e abaixo da sua média móvel
    - Preço abaixo de ambas SMAs
    - Volume > 1.5x média
    
    Sinais de SAÍDA:
    - Stop Loss: 2x ATR acima da entrada
    - Take Profit: 3x ATR abaixo da entrada (R:R 1.5:1)
    - Trailing Stop: EMA rápida virada para cima
    """
    
    def __init__(self, 
                 sma_fast: int = 50,
                 sma_slow: int = 200,
                 adx_threshold: int = 25,
                 rsi_threshold: int = 50,
                 volume_multiplier: float = 1.5):
        """
        Args:
            sma_fast: Período SMA rápida (padrão: 50)
            sma_slow: Período SMA lenta (padrão: 200)
            adx_threshold: ADX mínimo para força de tendência (padrão: 25)
            rsi_threshold: RSI máximo para entrada SHORT (padrão: 50)
            volume_multiplier: Multiplicador de volume (padrão: 1.5)
        """
        super().__init__(name="Bear Market Short")
        
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.adx_threshold = adx_threshold
        self.rsi_threshold = rsi_threshold
        self.volume_multiplier = volume_multiplier
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula todos os indicadores necessários"""
        df = df.copy()
        
        # 1. MOVING AVERAGES
        df['SMA_Fast'] = ta.trend.sma_indicator(df['Close'], window=self.sma_fast)
        df['SMA_Slow'] = ta.trend.sma_indicator(df['Close'], window=self.sma_slow)
        df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
        
        # 2. ADX COM DIRECIONAIS
        adx_indicator = ta.trend.ADXIndicator(
            df['High'], df['Low'], df['Close'], window=14
        )
        df['ADX'] = adx_indicator.adx()
        df['plus_di'] = adx_indicator.adx_pos()
        df['minus_di'] = adx_indicator.adx_neg()
        
        # 3. RSI COM MÉDIA MÓVEL
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        df['RSI_MA'] = ta.trend.sma_indicator(df['RSI'], window=10)
        
        # 4. ATR PARA STOPS
        df['ATR'] = ta.volatility.average_true_range(
            df['High'], df['Low'], df['Close'], window=14
        )
        
        # 5. VOLUME
        df['Volume_SMA'] = ta.trend.sma_indicator(df['Volume'], window=20)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de trading SHORT para mercado BEAR
        
        Returns:
            DataFrame com colunas:
            - signal: 1 = SHORT, 0 = nenhum sinal
            - stop_loss: Nível de stop loss
            - take_profit: Nível de take profit
            - trailing_stop: Stop dinâmico
        """
        df = self.calculate_indicators(df)
        
        # === CONDIÇÕES DE ENTRADA SHORT ===
        
        # 1. DEATH CROSS: SMA50 < SMA200
        death_cross = df['SMA_Fast'] < df['SMA_Slow']
        
        # 2. PREÇO ABAIXO DAS MÉDIAS
        price_below_mas = (df['Close'] < df['SMA_Fast']) & (df['Close'] < df['SMA_Slow'])
        
        # 3. ADX FORTE COM DIREÇÃO BEARISH
        strong_bear_trend = (
            (df['ADX'] > self.adx_threshold) &
            (df['minus_di'] > df['plus_di'])  # DI- dominante
        )
        
        # 4. RSI BEARISH
        rsi_bearish = (
            (df['RSI'] < self.rsi_threshold) &
            (df['RSI'] < df['RSI_MA'])  # RSI abaixo da sua média
        )
        
        # 5. VOLUME ACIMA DA MÉDIA
        volume_confirmation = df['Volume'] > (self.volume_multiplier * df['Volume_SMA'])
        
        # === SINAL COMBINADO ===
        df['signal'] = 0
        short_condition = (
            death_cross &
            price_below_mas &
            strong_bear_trend &
            rsi_bearish &
            volume_confirmation
        )
        df.loc[short_condition, 'signal'] = -1  # -1 = SHORT
        
        # === GESTÃO DE RISCO ===
        
        # STOP LOSS: 2x ATR acima da entrada
        df['stop_loss'] = df['Close'] + (2 * df['ATR'])
        
        # TAKE PROFIT: 3x ATR abaixo da entrada (R:R 1.5:1)
        df['take_profit'] = df['Close'] - (3 * df['ATR'])
        
        # TRAILING STOP: EMA20 (sai se preço fechar acima)
        df['trailing_stop'] = df['EMA_20']
        
        # EXIT SIGNAL: Quando EMA20 vira para cima
        df['exit_signal'] = 0
        ema_turning_up = df['EMA_20'] > df['EMA_20'].shift(1)
        df.loc[ema_turning_up, 'exit_signal'] = 1
        
        return df
    
    def get_position_size(self, 
                         capital: float,
                         entry_price: float,
                         stop_loss: float,
                         risk_per_trade: float = 0.02) -> float:
        """
        Calcula tamanho da posição SHORT baseado no risco
        
        Args:
            capital: Capital disponível
            entry_price: Preço de entrada
            stop_loss: Preço de stop loss
            risk_per_trade: % de risco por trade (padrão: 2%)
        
        Returns:
            Tamanho da posição em unidades monetárias
        """
        risk_amount = capital * risk_per_trade
        stop_distance = abs(stop_loss - entry_price)
        
        if stop_distance == 0:
            return 0
        
        position_size = risk_amount / stop_distance
        
        # Limitar posição a 15% do capital (estratégia SHORT mais conservadora)
        max_position = capital * 0.15
        return min(position_size, max_position)
    
    def get_strategy_info(self) -> Dict:
        """Retorna informações sobre a estratégia"""
        return {
            'name': 'Bear Market Short',
            'type': 'SHORT',
            'timeframe': ['1h', '4h', '1d'],
            'best_regime': 'BEAR',
            'risk_level': 'MEDIUM-HIGH',
            'parameters': {
                'sma_fast': self.sma_fast,
                'sma_slow': self.sma_slow,
                'adx_threshold': self.adx_threshold,
                'rsi_threshold': self.rsi_threshold,
                'volume_multiplier': self.volume_multiplier
            },
            'description': 'Estratégia SHORT para mercados BEAR com Death Cross e confirmação ADX'
        }


if __name__ == "__main__":
    # TESTE BÁSICO
    print("🐻 Bear Market Short Strategy - Teste Unitário")
    
    # Criar dados sintéticos de BEAR MARKET
    dates = pd.date_range(start='2022-01-01', periods=300, freq='1h')
    
    # Simular preço caindo (BEAR)
    np.random.seed(42)
    prices = 50000 - np.cumsum(np.random.randn(300) * 100)  # Tendência de queda
    
    df = pd.DataFrame({
        'Open': prices,
        'High': prices + np.random.rand(300) * 200,
        'Low': prices - np.random.rand(300) * 200,
        'Close': prices + np.random.randn(300) * 50,
        'Volume': np.random.randint(100, 1000, 300)
    }, index=dates)
    
    # Testar estratégia
    strategy = BearMarketShortStrategy()
    df_with_signals = strategy.generate_signals(df)
    
    # Contar sinais
    short_signals = (df_with_signals['signal'] == -1).sum()
    
    print(f"\n📊 RESULTADOS:")
    print(f"Total de candles: {len(df)}")
    print(f"Sinais SHORT gerados: {short_signals}")
    print(f"Taxa de sinal: {(short_signals/len(df))*100:.2f}%")
    print(f"\n✅ Teste concluído com sucesso!")
