"""Estratégia 5: Bollinger Bands básica"""
import pandas as pd
import ta
from typing import Dict, Any
from .base_strategy import BaseStrategy

class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {'bb_period': 20, 'bb_std': 2.0}
        if parameters: default_params.update(parameters)
        super().__init__("Bollinger Bands", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        bb = ta.volatility.BollingerBands(df['Close'], window=self.parameters['bb_period'], window_dev=self.parameters['bb_std'])
        df['BB_upper'] = bb.bollinger_hband()
        df['BB_lower'] = bb.bollinger_lband()
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        df.loc[df['Close'] <= df['BB_lower'], 'signal'] = 1
        df.loc[df['Close'] >= df['BB_upper'], 'signal'] = -1
        df['position'] = df['signal'].replace(-1, 0)
        return df
    
    def get_entry_conditions(self) -> list:
        return ["Preço toca banda inferior"]
    
    def get_exit_conditions(self) -> list:
        return ["Preço toca banda superior"]

def create_bollinger_bands_strategy(params: Dict[str, Any] = None):
    return BollingerBandsStrategy(parameters=params)
