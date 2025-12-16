"""
Estratégia 8: Multi-Timeframe Confirmation
Analisa múltiplos timeframes para confirmar sinais

Timeframe maior (4h/diário): Define tendência principal
Timeframe médio (1h): Define entrada
Timeframe menor (15m): Define timing preciso
"""

import pandas as pd
import ta
from typing import Dict, Any, List
from .base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class MultiTimeframeStrategy(BaseStrategy):
    """
    Estratégia que confirma sinais em múltiplos timeframes
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'trend_ema': 50,  # EMA para tendência principal
            'entry_ema_fast': 20,
            'entry_ema_slow': 50,
            'rsi_period': 14
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("Multi-Timeframe Confirmation", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula indicadores para análise multi-timeframe
        """
        # EMAs para tendência
        df['EMA_trend'] = ta.trend.ema_indicator(df['Close'], window=self.parameters['trend_ema'])
        df['EMA_fast'] = ta.trend.ema_indicator(df['Close'], window=self.parameters['entry_ema_fast'])
        df['EMA_slow'] = ta.trend.ema_indicator(df['Close'], window=self.parameters['entry_ema_slow'])
        
        # Tendência principal (timeframe maior simulado)
        df['trend_direction'] = (df['Close'] > df['EMA_trend']).astype(int)
        
        # RSI para timing
        df['RSI'] = ta.momentum.rsi(df['Close'], window=self.parameters['rsi_period'])
        
        # MACD para confirmação
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais confirmados por múltiplos fatores
        """
        df['signal'] = 0
        
        # Condições de COMPRA (todos os timeframes alinhados)
        buy_condition = (
            (df['trend_direction'] == 1) &  # Tendência de alta (TF maior)
            (df['EMA_fast'] > df['EMA_slow']) &  # Cruzamento de EMAs (TF médio)
            (df['MACD'] > df['MACD_signal']) &  # MACD positivo (TF médio)
            (df['RSI'] > 40) & (df['RSI'] < 70)  # RSI neutro (TF menor)
        )
        
        # Condições de VENDA
        sell_condition = (
            (df['trend_direction'] == 0) |  # Tendência de baixa
            (df['EMA_fast'] < df['EMA_slow']) |  # Cruzamento negativo
            (df['RSI'] > 80)  # Sobrecomprado
        )
        
        df.loc[buy_condition, 'signal'] = 1
        df.loc[sell_condition, 'signal'] = -1
        df['position'] = df['signal'].replace(-1, 0)
        
        return df
    
    def get_entry_conditions(self) -> list:
        return [
            "Tendência de alta no timeframe maior (Preço > EMA50)",
            "Cruzamento de EMAs positivo no timeframe médio",
            "MACD acima da linha de sinal",
            "RSI entre 40-70 (não extremo)"
        ]
    
    def get_exit_conditions(self) -> list:
        return [
            "Tendência de baixa no timeframe maior",
            "Cruzamento de EMAs negativo",
            "RSI > 80 (sobrecomprado)"
        ]


def create_multi_timeframe_strategy(params: Dict[str, Any] = None):
    return MultiTimeframeStrategy(parameters=params)
