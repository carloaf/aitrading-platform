"""Estratégia 7: Volume Profile / On-Balance Volume"""
import pandas as pd
import ta
import numpy as np
from typing import Dict, Any
from .base_strategy import BaseStrategy

class VolumeProfileStrategy(BaseStrategy):
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {'obv_period': 20}
        if parameters: default_params.update(parameters)
        super().__init__("Volume Profile (OBV)", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df['OBV'] = ta.volume.on_balance_volume(df['Close'], df['Volume'])
        df['OBV_sma'] = df['OBV'].rolling(window=self.parameters['obv_period']).mean()
        df['volume_trend'] = (df['OBV'] > df['OBV_sma']).astype(int)
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        df.loc[df['volume_trend'] == 1, 'signal'] = 1
        df.loc[df['volume_trend'] == 0, 'signal'] = -1
        df['position'] = df['signal'].replace(-1, 0)
        return df
    
    def get_entry_conditions(self) -> list:
        return ["OBV acima da média móvel (volume comprando)"]
    
    def get_exit_conditions(self) -> list:
        return ["OBV abaixo da média móvel (volume vendendo)"]

def create_volume_profile_strategy(params: Dict[str, Any] = None):
    return VolumeProfileStrategy(parameters=params)
