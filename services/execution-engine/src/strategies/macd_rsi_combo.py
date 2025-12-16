"""
Estratégia 4: MACD + RSI Combo
Combina dois indicadores populares para filtrar sinais

Entrada: MACD cruza acima de 0 E RSI entre 40-70
Saída: MACD cruza abaixo de 0 OU RSI > 80
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Any
from .base_strategy import BaseStrategy


class MacdRsiComboStrategy(BaseStrategy):
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'rsi_period': 14,
            'rsi_lower': 40,
            'rsi_upper': 70,
            'rsi_exit': 80
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("MACD + RSI Combo", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        macd = ta.trend.MACD(
            df['Close'], 
            window_slow=self.parameters['macd_slow'],
            window_fast=self.parameters['macd_fast'],
            window_sign=self.parameters['macd_signal']
        )
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['MACD_hist'] = macd.macd_diff()
        
        df['RSI'] = ta.momentum.rsi(df['Close'], window=self.parameters['rsi_period'])
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        
        buy = (
            (df['MACD'] > df['MACD_signal']) &
            (df['RSI'] > self.parameters['rsi_lower']) &
            (df['RSI'] < self.parameters['rsi_upper'])
        )
        
        sell = (
            (df['MACD'] < df['MACD_signal']) |
            (df['RSI'] > self.parameters['rsi_exit'])
        )
        
        df.loc[buy, 'signal'] = 1
        df.loc[sell, 'signal'] = -1
        df['position'] = df['signal'].replace(-1, 0)
        
        return df
    
    def get_entry_conditions(self) -> list:
        return [
            "MACD cruza acima da linha de sinal",
            f"RSI entre {self.parameters['rsi_lower']} e {self.parameters['rsi_upper']}"
        ]
    
    def get_exit_conditions(self) -> list:
        return [
            "MACD cruza abaixo da linha de sinal",
            f"RSI > {self.parameters['rsi_exit']}"
        ]


def create_macd_rsi_combo_strategy(params: Dict[str, Any] = None):
    return MacdRsiComboStrategy(parameters=params)
