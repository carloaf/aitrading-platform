"""Estratégia 6: Momentum"""
import pandas as pd
import ta
from typing import Dict, Any
from .base_strategy import BaseStrategy

class MomentumStrategy(BaseStrategy):
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {'roc_period': 10, 'threshold': 0}
        if parameters: default_params.update(parameters)
        super().__init__("Momentum Strategy", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df['ROC'] = ta.momentum.roc(df['Close'], window=self.parameters['roc_period'])
        df['ROC_sma'] = df['ROC'].rolling(window=10).mean()
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        df.loc[df['ROC'] > self.parameters['threshold'], 'signal'] = 1
        df.loc[df['ROC'] < self.parameters['threshold'], 'signal'] = -1
        df['position'] = df['signal'].replace(-1, 0)
        return df
    
    def get_entry_conditions(self) -> list:
        return [f"ROC > {self.parameters['threshold']} (momentum positivo)"]
    
    def get_exit_conditions(self) -> list:
        return [f"ROC < {self.parameters['threshold']} (momentum negativo)"]

def create_momentum_strategy(params: Dict[str, Any] = None):
    return MomentumStrategy(parameters=params)
