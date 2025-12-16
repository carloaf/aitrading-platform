"""
Estratégia 9: Dynamic Position Sizing
Ajusta tamanho da posição baseado em volatilidade e risco

Usa Kelly Criterion modificado e ATR para dimensionar posições
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Any
from .base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class DynamicPositionSizing(BaseStrategy):
    """
    Estratégia que calcula tamanho de posição dinâmico baseado em risco
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'risk_per_trade': 0.02,  # 2% de risco por trade
            'atr_period': 14,
            'atr_multiplier': 2.0,
            'max_position_size': 0.25  # Máximo 25% do capital por posição
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("Dynamic Position Sizing", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula ATR e métricas de volatilidade
        """
        # ATR para medir volatilidade
        df['ATR'] = ta.volatility.average_true_range(
            df['High'], df['Low'], df['Close'], 
            window=self.parameters['atr_period']
        )
        
        # ATR percentual
        df['ATR_pct'] = (df['ATR'] / df['Close']) * 100
        
        # Bollinger Bands Width (outra medida de volatilidade)
        bb = ta.volatility.BollingerBands(df['Close'])
        df['BB_width'] = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
        
        # EMA para tendência
        df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
        df['EMA_50'] = ta.trend.ema_indicator(df['Close'], window=50)
        
        # RSI para timing
        df['RSI'] = ta.momentum.rsi(df['Close'])
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais E calcula tamanho da posição
        """
        df['signal'] = 0
        df['position_size'] = 0.0
        
        # Sinais básicos de entrada (EMA crossover)
        buy_condition = (
            (df['EMA_20'] > df['EMA_50']) &
            (df['RSI'] > 40) & (df['RSI'] < 70)
        )
        
        sell_condition = (
            (df['EMA_20'] < df['EMA_50']) |
            (df['RSI'] > 80)
        )
        
        df.loc[buy_condition, 'signal'] = 1
        df.loc[sell_condition, 'signal'] = -1
        
        # Calcular tamanho de posição dinâmico
        df['position_size'] = self._calculate_position_size(df)
        
        df['position'] = df['signal'].replace(-1, 0)
        
        # Stop-loss baseado em ATR
        df['stop_loss'] = df['Close'] - (self.parameters['atr_multiplier'] * df['ATR'])
        df['take_profit'] = df['Close'] + (self.parameters['atr_multiplier'] * df['ATR'] * 1.5)
        
        return df
    
    def _calculate_position_size(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula tamanho de posição usando Kelly Criterion simplificado
        
        Fórmula: Position Size = (Risk per Trade) / (ATR * Multiplier)
        """
        risk_per_trade = self.parameters['risk_per_trade']
        atr_multiplier = self.parameters['atr_multiplier']
        max_position = self.parameters['max_position_size']
        
        # Calcular risco por unidade (em percentual do preço)
        risk_per_unit = (df['ATR'] * atr_multiplier) / df['Close']
        
        # Tamanho da posição = risco desejado / risco por unidade
        position_size = risk_per_trade / risk_per_unit
        
        # Limitar ao máximo permitido
        position_size = np.minimum(position_size, max_position)
        
        # Ajustar pela volatilidade (reduzir posição em alta volatilidade)
        volatility_adjustment = 1 / (1 + df['ATR_pct'] / 5)
        position_size = position_size * volatility_adjustment
        
        # Garantir que está entre 0 e max_position
        position_size = np.clip(position_size, 0, max_position)
        
        return position_size
    
    def calculate_kelly_criterion(
        self, 
        win_rate: float, 
        avg_win: float, 
        avg_loss: float
    ) -> float:
        """
        Calcula Kelly Criterion para tamanho ótimo de posição
        
        Args:
            win_rate: Taxa de acerto (0 a 1)
            avg_win: Ganho médio por trade vencedor
            avg_loss: Perda média por trade perdedor
            
        Returns:
            Fração do capital a arriscar (0 a 1)
        """
        if avg_loss == 0:
            return 0
        
        # Kelly Criterion: f* = (bp - q) / b
        # onde: b = avg_win/avg_loss, p = win_rate, q = 1-p
        b = avg_win / abs(avg_loss)
        p = win_rate
        q = 1 - p
        
        kelly_pct = (b * p - q) / b
        
        # Usar metade do Kelly (mais conservador)
        kelly_pct = kelly_pct * 0.5
        
        # Limitar entre 0 e 25%
        kelly_pct = np.clip(kelly_pct, 0, 0.25)
        
        logger.info(f"Kelly Criterion: {kelly_pct:.2%} (Win Rate: {win_rate:.2%}, Avg Win: {avg_win:.2f}, Avg Loss: {avg_loss:.2f})")
        
        return kelly_pct
    
    def get_entry_conditions(self) -> list:
        return [
            "EMA20 > EMA50 (tendência de alta)",
            "RSI entre 40-70",
            f"Tamanho de posição ajustado por volatilidade (ATR)",
            f"Risco máximo: {self.parameters['risk_per_trade']*100}% por trade"
        ]
    
    def get_exit_conditions(self) -> list:
        return [
            "EMA20 < EMA50",
            "RSI > 80",
            f"Stop-loss: {self.parameters['atr_multiplier']}x ATR",
            f"Take-profit: {self.parameters['atr_multiplier']*1.5}x ATR"
        ]
    
    def analyze_risk(self, df: pd.DataFrame, account_balance: float = 10000) -> Dict[str, Any]:
        """
        Analisa o risco atual da estratégia
        
        Args:
            df: DataFrame com dados e sinais
            account_balance: Saldo da conta
            
        Returns:
            Análise de risco
        """
        if df.empty or 'position_size' not in df.columns:
            return {"error": "Dados insuficientes"}
        
        last_row = df.iloc[-1]
        
        position_value = account_balance * last_row['position_size']
        risk_amount = position_value * self.parameters['risk_per_trade']
        
        return {
            "current_price": float(last_row['Close']),
            "atr": float(last_row['ATR']),
            "atr_pct": float(last_row['ATR_pct']),
            "recommended_position_size_pct": float(last_row['position_size'] * 100),
            "position_value_usd": float(position_value),
            "risk_per_trade_usd": float(risk_amount),
            "stop_loss": float(last_row['stop_loss']),
            "take_profit": float(last_row['take_profit']),
            "risk_reward_ratio": float(
                (last_row['take_profit'] - last_row['Close']) / 
                (last_row['Close'] - last_row['stop_loss'])
            ) if (last_row['Close'] - last_row['stop_loss']) > 0 else 0
        }


def create_dynamic_position_sizing_strategy(params: Dict[str, Any] = None):
    return DynamicPositionSizing(parameters=params)
