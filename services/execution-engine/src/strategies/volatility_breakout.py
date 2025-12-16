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
            'volume_multiplier': 1.5,
            'squeeze_lookback': 20,  # BLUE_PRINT: Períodos para detectar squeeze
            'squeeze_threshold': 1.1  # BLUE_PRINT: Bandas devem estar abaixo de 110% da mínima
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("Volatility Breakout", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        atr_period = self.parameters['atr_period']
        consolidation = self.parameters['consolidation_period']
        squeeze_lookback = self.parameters.get('squeeze_lookback', 20)
        
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=atr_period)
        df['ATR_pct'] = (df['ATR'] / df['Close']) * 100
        df['ATR_expanding'] = (df['ATR'] > df['ATR'].shift(5)).astype(int)
        
        df['high_channel'] = df['High'].rolling(window=consolidation).max()
        df['low_channel'] = df['Low'].rolling(window=consolidation).min()
        df['channel_width'] = df['high_channel'] - df['low_channel']
        
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        
        # === BLUE_PRINT: Bollinger Squeeze Detection ===
        # Bandas devem estar estreitas antes de explodir (evita fakeouts)
        bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2.0)
        df['BB_upper'] = bb.bollinger_hband()
        df['BB_lower'] = bb.bollinger_lband()
        df['BB_middle'] = bb.bollinger_mavg()
        df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle']
        df['BB_width_min'] = df['BB_width'].rolling(window=squeeze_lookback).min()
        df['is_squeezing'] = df['BB_width'] < (df['BB_width_min'] * self.parameters['squeeze_threshold'])
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de breakout com filtro de Squeeze
        
        BLUE_PRINT v1.0 - Refinamento Institucional:
        - Exige "Squeeze" prévio (bandas estreitas antes de explodir)
        - Confirmação de Volume obrigatória
        - Evita falsos rompimentos (fakeouts)
        """
        df['signal'] = 0
        
        # === BLUE_PRINT: Condições de COMPRA com Squeeze Filter ===
        # REGRA: Bollinger Squeeze + Breakout + Volume
        
        # OTIMIZAÇÃO #3: Ajuste para alta volatilidade
        # Em $20k+ ranges (ATR% > 5%), relaxar requisito de squeeze
        high_volatility = df['ATR_pct'] > 5.0  # ATR > 5% do preço
        
        # Se alta volatilidade, aceitar breakout mesmo sem squeeze prévio
        # Também reduzir volume multiplier (1.5x → 1.3x) para capturar movimentos
        volume_multiplier_adj = np.where(high_volatility, 1.3, self.parameters['volume_multiplier'])
        
        breakout_buy = (
            ((df['is_squeezing'].shift(1) == True) | high_volatility) &  # Squeeze OU alta volatilidade
            (df['Close'] > df['high_channel'].shift(1)) &  # Rompimento da máxima
            (df['ATR_expanding'] == 1) &  # ATR em expansão
            (df['Volume'] > df['Volume_SMA'] * volume_multiplier_adj)  # Volume confirma (ajustável)
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
            f"Bollinger Squeeze detectado (bandas < {self.parameters['squeeze_threshold']}x mínima)",
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
