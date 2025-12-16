"""
BREAKDOWN MOMENTUM STRATEGY - SHORT
Versão: 1.0 | Implementado conforme PLANO_DE_MELHORAMENTO.md

Estratégia SHORT para rompimentos de suporte com momentum:
1. Rompe suporte chave (mínima de 20 períodos)
2. Volume explosivo (>2x média)
3. RSI < 45 (momentum bearish)
4. ATR expandindo (volatilidade aumentando)

Ideal para: Capturas de movimentos de pânico e capitulações
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Tuple, Optional
from .base_strategy import BaseStrategy


class BreakdownMomentumStrategy(BaseStrategy):
    """
    Estratégia SHORT para rompimentos de suporte com momentum bearish
    
    Sinais de ENTRADA (SHORT):
    - Preço rompe abaixo da mínima de N períodos
    - Volume > 2x média (pânico/capitulação)
    - RSI < 45 (momentum bearish)
    - ATR expandindo (>1.3x média)
    - Confirmação: Fecha abaixo do suporte
    
    Sinais de SAÍDA:
    - Stop Loss: Resistência anterior (máxima recente)
    - Take Profit: 4x ATR abaixo do breakdown (R:R 2:1)
    - Exit: RSI < 30 (oversold extremo - potencial reversão)
    """
    
    def __init__(self,
                 lookback_period: int = 20,
                 volume_multiplier: float = 2.0,
                 rsi_threshold: int = 45,
                 atr_expansion: float = 1.3):
        """
        Args:
            lookback_period: Períodos para identificar suporte (padrão: 20)
            volume_multiplier: Multiplicador de volume (padrão: 2.0)
            rsi_threshold: RSI máximo para entrada (padrão: 45)
            atr_expansion: Expansão mínima do ATR (padrão: 1.3)
        """
        super().__init__(name="Breakdown Momentum")
        
        self.lookback_period = lookback_period
        self.volume_multiplier = volume_multiplier
        self.rsi_threshold = rsi_threshold
        self.atr_expansion = atr_expansion
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula todos os indicadores necessários"""
        df = df.copy()
        
        # 1. SUPORTE E RESISTÊNCIA
        df['Support_Level'] = df['Low'].rolling(window=self.lookback_period).min()
        df['Resistance_Level'] = df['High'].rolling(window=self.lookback_period).max()
        
        # 2. RSI
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        
        # 3. ATR E EXPANSÃO
        df['ATR'] = ta.volatility.average_true_range(
            df['High'], df['Low'], df['Close'], window=14
        )
        df['ATR_MA'] = ta.trend.sma_indicator(df['ATR'], window=20)
        df['ATR_Expansion'] = df['ATR'] / df['ATR_MA']
        
        # 4. VOLUME
        df['Volume_SMA'] = ta.trend.sma_indicator(df['Volume'], window=20)
        df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
        
        # 5. MACD PARA MOMENTUM
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais SHORT para breakdowns de suporte
        
        Returns:
            DataFrame com colunas signal, stop_loss, take_profit
        """
        df = self.calculate_indicators(df)
        
        # === CONDIÇÕES DE ENTRADA SHORT ===
        
        # 1. BREAKDOWN: Preço rompe abaixo do suporte
        support_break = df['Close'] < df['Support_Level'].shift(1)
        
        # Confirmação: LOW também rompeu (não é apenas wick)
        confirmed_break = df['Low'] < df['Support_Level'].shift(1)
        
        # 2. VOLUME EXPLOSIVO (pânico)
        panic_volume = df['Volume_Ratio'] > self.volume_multiplier
        
        # 3. RSI BEARISH
        rsi_bearish = df['RSI'] < self.rsi_threshold
        
        # 4. ATR EXPANDINDO
        volatility_expanding = df['ATR_Expansion'] > self.atr_expansion
        
        # 5. MACD NEGATIVO (momentum bearish)
        macd_bearish = df['MACD_Hist'] < 0
        
        # === SINAL COMBINADO ===
        df['signal'] = 0
        breakdown_signal = (
            support_break &
            confirmed_break &
            panic_volume &
            rsi_bearish &
            volatility_expanding &
            macd_bearish
        )
        df.loc[breakdown_signal, 'signal'] = -1  # -1 = SHORT
        
        # === GESTÃO DE RISCO ===
        
        # STOP LOSS: Resistência recente (máxima)
        df['stop_loss'] = df['Resistance_Level']
        
        # TAKE PROFIT: 4x ATR abaixo do breakdown
        df['take_profit'] = df['Close'] - (4 * df['ATR'])
        
        # === EXIT SIGNALS ===
        df['exit_signal'] = 0
        
        # Exit 1: RSI oversold extremo (< 30) - potencial reversão
        oversold_extreme = df['RSI'] < 30
        df.loc[oversold_extreme, 'exit_signal'] = 1
        
        # Exit 2: MACD cruzando para cima
        macd_crossover = (df['MACD'] > df['MACD_Signal']) & \
                        (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))
        df.loc[macd_crossover, 'exit_signal'] = 1
        
        # Exit 3: Volume seca (< 0.7x média) - movimento perdendo força
        volume_drying = df['Volume_Ratio'] < 0.7
        df.loc[volume_drying, 'exit_signal'] = 1
        
        return df
    
    def get_position_size(self,
                         capital: float,
                         entry_price: float,
                         stop_loss: float,
                         risk_per_trade: float = 0.02) -> float:
        """
        Calcula tamanho da posição SHORT com risk management
        
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
        
        # Limitar posição a 12% do capital (breakdown pode ser volátil)
        max_position = capital * 0.12
        return min(position_size, max_position)
    
    def identify_support_quality(self, df: pd.DataFrame, idx: int) -> str:
        """
        Classifica qualidade do suporte rompido
        
        Returns:
            'STRONG', 'MODERATE', 'WEAK'
        """
        if idx < self.lookback_period:
            return 'UNKNOWN'
        
        support_level = df['Support_Level'].iloc[idx]
        
        # Contar quantas vezes testou o suporte
        touches = 0
        for i in range(idx - self.lookback_period, idx):
            if abs(df['Low'].iloc[i] - support_level) < (support_level * 0.005):  # 0.5%
                touches += 1
        
        if touches >= 3:
            return 'STRONG'
        elif touches == 2:
            return 'MODERATE'
        else:
            return 'WEAK'
    
    def get_strategy_info(self) -> Dict:
        """Retorna informações sobre a estratégia"""
        return {
            'name': 'Breakdown Momentum',
            'type': 'SHORT',
            'timeframe': ['15m', '1h', '4h'],
            'best_regime': 'BEAR',
            'risk_level': 'HIGH',
            'parameters': {
                'lookback_period': self.lookback_period,
                'volume_multiplier': self.volume_multiplier,
                'rsi_threshold': self.rsi_threshold,
                'atr_expansion': self.atr_expansion
            },
            'description': 'Estratégia SHORT para rompimentos de suporte com volume explosivo',
            'typical_holding_time': '2-12 horas',
            'ideal_market': 'Alta volatilidade com momentum bearish'
        }


if __name__ == "__main__":
    # TESTE BÁSICO
    print("📉 Breakdown Momentum Strategy - Teste Unitário")
    
    # Criar dados sintéticos com breakdown
    dates = pd.date_range(start='2022-06-01', periods=200, freq='1h')
    
    np.random.seed(42)
    
    # Simular consolidação seguida de breakdown
    prices = []
    for i in range(200):
        if i < 100:
            # Consolidação (range trading)
            prices.append(30000 + np.random.randn() * 500)
        else:
            # Breakdown (queda acentuada)
            prices.append(30000 - (i - 100) * 50 + np.random.randn() * 300)
    
    prices = np.array(prices)
    
    df = pd.DataFrame({
        'Open': prices,
        'High': prices + np.random.rand(200) * 200,
        'Low': prices - np.random.rand(200) * 200,
        'Close': prices + np.random.randn(200) * 100,
        'Volume': np.random.randint(100, 1000, 200)
    }, index=dates)
    
    # Simular volume explosivo no breakdown (candle 100-110)
    df.loc[df.index[100:110], 'Volume'] = df['Volume'].iloc[100:110] * 3
    
    # Testar estratégia
    strategy = BreakdownMomentumStrategy()
    df_with_signals = strategy.generate_signals(df)
    
    # Contar sinais
    short_signals = (df_with_signals['signal'] == -1).sum()
    
    print(f"\n📊 RESULTADOS:")
    print(f"Total de candles: {len(df)}")
    print(f"Sinais SHORT gerados: {short_signals}")
    print(f"Taxa de sinal: {(short_signals/len(df))*100:.2f}%")
    
    # Verificar se detectou o breakdown esperado
    breakdown_detected = df_with_signals.iloc[100:110]['signal'].sum()
    if breakdown_detected < 0:
        print(f"✅ Breakdown detectado corretamente no período esperado!")
    else:
        print(f"⚠️ Breakdown não detectado - ajustar parâmetros")
    
    print(f"\n✅ Teste concluído!")
