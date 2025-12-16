"""
Estratégia 3: Volatility Breakout
Explora rompimentos de faixas de volatilidade usando ATR

Regras de Entrada (BUY):
1. Preço rompe máxima de consolidação (período de 20 candles)
2. ATR em expansão (aumento de volatilidade)
3. Volume acima de 1.5x a média

Regras de Saída (SELL):
1. Preço volta para dentro da faixa de consolidação
2. Stop-loss: 2x ATR abaixo do preço de entrada
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Any
from .base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class VolatilityBreakoutStrategy(BaseStrategy):
    """Estratégia de breakout baseada em volatilidade"""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'atr_period': 14,
            'consolidation_period': 20,
            'breakout_multiplier': 1.5,
            'volume_multiplier': 1.5
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("Volatility Breakout", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        atr_period = self.parameters['atr_period']
        consolidation = self.parameters['consolidation_period']
        
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=atr_period)
        df['ATR_pct'] = (df['ATR'] / df['Close']) * 100
        df['ATR_expanding'] = (df['ATR'] > df['ATR'].shift(5)).astype(int)
        
        df['high_channel'] = df['High'].rolling(window=consolidation).max()
        df['low_channel'] = df['Low'].rolling(window=consolidation).min()
        df['channel_width'] = df['high_channel'] - df['low_channel']
        
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        
        breakout_buy = (
            (df['Close'] > df['high_channel'].shift(1)) &
            (df['ATR_expanding'] == 1) &
            (df['Volume'] > df['Volume_SMA'] * self.parameters['volume_multiplier'])
        )
        
        breakout_sell = (
            (df['Close'] < df['low_channel'].shift(1))
        )
        
        df.loc[breakout_buy, 'signal'] = 1
        df.loc[breakout_sell, 'signal'] = -1
        df['position'] = df['signal'].replace(-1, 0)
        df['stop_loss'] = df['Close'] - (2 * df['ATR'])
        
        return df
    
    def get_entry_conditions(self) -> list:
        return [
            f"Preço rompe máxima dos últimos {self.parameters['consolidation_period']} períodos",
            "ATR em expansão (volatilidade crescente)",
            f"Volume > {self.parameters['volume_multiplier']}x média"
        ]
    
    def get_exit_conditions(self) -> list:
        return [
            "Preço rompe mínima do canal de consolidação",
            "Stop-loss: 2x ATR abaixo da entrada"
        ]


def create_volatility_breakout_strategy(params: Dict[str, Any] = None):
    return VolatilityBreakoutStrategy(parameters=params)
