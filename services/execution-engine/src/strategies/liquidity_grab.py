"""
BLUE_PRINT v1.0: Liquidity Grab Strategy (Wyckoff Spring)
=========================================================

Conceito: Comprar quando o "Smart Money" estopa o varejo e devolve o preço rapidamente.

Lógica Institucional:
1. Identificar suporte recente (mínima de 20 candles)
2. Preço viola a mínima (fura suporte - stop hunt)
3. Preço fecha ACIMA do suporte no mesmo candle (Rejeição/Martelo)
4. Volume > 1.5x Média (Smart Money absorvendo liquidez)

Este padrão indica que grandes players estão acumulando posições
ao "varrer" stop-losses do varejo em níveis óbvios de suporte.

Autor: "The Legend" (Wall St. & Faria Lima)
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Any, List
from .base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class LiquidityGrabStrategy(BaseStrategy):
    """
    Estratégia de Liquidity Grab / Wyckoff Spring
    
    Captura movimentos onde o Smart Money estopa o varejo
    e rapidamente reverte o preço.
    
    Ideal para: Mercados laterais (SIDEWAYS) com níveis claros de S/R
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'support_period': 20,      # Períodos para identificar suporte
            'volume_multiplier': 2.0,   # PLANO_DE_MELHORAMENTO: 2.0x (era 1.5)
            'rejection_tolerance': 0.001,  # 0.1% de tolerância para rejeição
            'min_wick_ratio': 0.5,      # Mínimo de sombra inferior (martelo)
            'rsi_period': 14,
            'atr_period': 14,
            'spring_depth_pct': 0.02,   # PLANO: 2% abaixo do suporte
            'atr_target_multiplier': 2.0,  # PLANO: Target 2x ATR
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__("Liquidity Grab (Wyckoff Spring)", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula indicadores para detecção de liquidity grab
        """
        support_period = self.parameters['support_period']
        
        # Suporte recente: mínima dos últimos N candles
        df['support'] = df['Low'].rolling(window=support_period).min()
        df['support_shifted'] = df['support'].shift(1)  # Suporte do período anterior
        
        # Resistência recente (para shorts, se implementado)
        df['resistance'] = df['High'].rolling(window=support_period).max()
        
        # Volume
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        df['volume_spike'] = df['Volume'] > (df['Volume_SMA'] * self.parameters['volume_multiplier'])
        
        # RSI para confirmação
        df['RSI'] = ta.momentum.rsi(df['Close'], window=self.parameters['rsi_period'])
        
        # ATR para stops
        df['ATR'] = ta.volatility.average_true_range(
            df['High'], df['Low'], df['Close'], 
            window=self.parameters['atr_period']
        )
        
        # Cálculo do corpo e sombras do candle
        df['body'] = abs(df['Close'] - df['Open'])
        df['lower_wick'] = df[['Open', 'Close']].min(axis=1) - df['Low']
        df['upper_wick'] = df['High'] - df[['Open', 'Close']].max(axis=1)
        df['candle_range'] = df['High'] - df['Low']
        
        # Ratio da sombra inferior (para martelos)
        df['lower_wick_ratio'] = np.where(
            df['candle_range'] > 0,
            df['lower_wick'] / df['candle_range'],
            0
        )
        
        # Identificar candle de rejeição (martelo/hammer)
        df['is_hammer'] = (
            (df['lower_wick_ratio'] >= self.parameters['min_wick_ratio']) &
            (df['Close'] > df['Open'])  # Candle de alta
        )
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de Liquidity Grab (Wyckoff Spring)
        
        BLUE_PRINT v1.0 - Lógica Institucional:
        1. Preço viola suporte (fura mínima - stop hunt)
        2. Preço fecha ACIMA do suporte (rejeição/martelo)
        3. Volume alto (Smart Money absorvendo liquidez)
        """
        tolerance = self.parameters['rejection_tolerance']
        
        # Inicializar
        df['signal'] = 0
        df['signal_strength'] = 0.0
        df['spring_detected'] = False
        
        # === CONDIÇÃO 1: Violação do Suporte ===
        # A mínima do candle deve furar o suporte (stop hunt)
        support_violated = df['Low'] < df['support_shifted']
        
        # === CONDIÇÃO 2: Rejeição (Fecha acima do suporte) ===
        # O preço de fechamento deve estar acima do suporte (rejeição)
        support_level = df['support_shifted']
        rejection = df['Close'] > (support_level * (1 + tolerance))
        
        # === CONDIÇÃO 3: Candle de Reversão (Martelo) ===
        reversal_candle = df['is_hammer']
        
        # === CONDIÇÃO 4: Volume Confirma (Smart Money) ===
        volume_confirmed = df['volume_spike']
        
        # === CONDIÇÃO 5: RSI não muito overbought ===
        rsi_ok = df['RSI'] < 70
        
        # === LIQUIDITY GRAB / WYCKOFF SPRING ===
        spring_condition = (
            support_violated &     # 1. Violou suporte (stop hunt)
            rejection &            # 2. Fechou acima do suporte (rejeição)
            reversal_candle &      # 3. Candle de reversão (martelo)
            volume_confirmed &     # 4. Volume alto (smart money)
            rsi_ok                 # 5. RSI não extremo
        )
        
        # Marcar springs detectados
        df.loc[spring_condition, 'spring_detected'] = True
        
        # Sinal de COMPRA no candle seguinte (confirmação)
        df.loc[spring_condition, 'signal'] = 1
        
        # Condições de VENDA (saída)
        # Alvo: Resistência recente ou 2x ATR de lucro
        sell_condition = (
            (df['Close'] >= df['resistance'].shift(1)) |  # Atingiu resistência
            (df['RSI'] > 75)  # Overbought
        )
        df.loc[sell_condition, 'signal'] = -1
        
        # Calcular força do sinal
        df['signal_strength'] = self._calculate_signal_strength(df)
        
        # Posição para backtesting
        df['position'] = df['signal'].replace(-1, 0)
        
        # Stop-loss e take-profit
        df['stop_loss'] = df['Low'] - df['ATR']  # Abaixo da mínima do spring
        df['take_profit'] = df['resistance']  # Alvo na resistência
        
        return df
    
    def _calculate_signal_strength(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula força do sinal baseado na qualidade do spring
        """
        strength = pd.Series(0.0, index=df.index)
        
        # Quanto maior a sombra inferior, mais forte a rejeição
        wick_strength = np.clip(df['lower_wick_ratio'] * 2, 0, 1)
        
        # Volume acima da média aumenta força
        volume_ratio = df['Volume'] / df['Volume_SMA']
        volume_strength = np.clip((volume_ratio - 1) / 2, 0, 1)
        
        # RSI oversold aumenta força
        rsi_strength = np.clip((50 - df['RSI']) / 50, 0, 1)
        
        # Combinar
        strength = (
            0.4 * wick_strength +
            0.3 * volume_strength +
            0.3 * rsi_strength
        )
        
        return strength
    
    def get_entry_conditions(self) -> list:
        """Retorna condições de entrada legíveis"""
        return [
            f"Preço viola suporte dos últimos {self.parameters['support_period']} candles (stop hunt)",
            "Preço fecha ACIMA do suporte no mesmo candle (rejeição)",
            f"Candle de reversão: sombra inferior > {self.parameters['min_wick_ratio']*100}% do candle",
            f"Volume > {self.parameters['volume_multiplier']}x média (Smart Money)",
            "RSI < 70 (não overbought)"
        ]
    
    def get_exit_conditions(self) -> list:
        """Retorna condições de saída legíveis"""
        return [
            "Preço atinge resistência recente",
            "RSI > 75 (overbought)",
            "Stop-loss: Mínima do spring - ATR"
        ]
    
    def analyze_spring_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analisa a qualidade de um spring detectado
        
        Returns:
            Dicionário com análise do spring
        """
        if df.empty:
            return {"error": "Dados insuficientes"}
        
        last_row = df.iloc[-1]
        
        # Verificar se há spring
        if not last_row.get('spring_detected', False):
            return {
                "spring_detected": False,
                "message": "Nenhum spring no candle atual"
            }
        
        return {
            "spring_detected": True,
            "support_level": float(last_row.get('support_shifted', 0)),
            "low_price": float(last_row['Low']),
            "close_price": float(last_row['Close']),
            "penetration": float(last_row['support_shifted'] - last_row['Low']),
            "rejection_strength": float(last_row['Close'] - last_row['support_shifted']),
            "lower_wick_ratio": float(last_row['lower_wick_ratio']),
            "volume_ratio": float(last_row['Volume'] / last_row['Volume_SMA']),
            "rsi": float(last_row['RSI']),
            "signal_strength": float(last_row['signal_strength']),
            "stop_loss": float(last_row['stop_loss']),
            "take_profit": float(last_row['take_profit']),
            "risk_reward": float(
                (last_row['take_profit'] - last_row['Close']) / 
                (last_row['Close'] - last_row['stop_loss'])
            ) if last_row['Close'] > last_row['stop_loss'] else 0
        }


# Função para Monte Carlo adapter
def liquidity_grab_strategy_func(df: pd.DataFrame,
                                  support_period: int = 20,
                                  volume_multiplier: float = 1.5,
                                  min_wick_ratio: float = 0.5) -> pd.DataFrame:
    """
    Função adaptadora para Monte Carlo simulations
    
    Detecta Liquidity Grabs (Wyckoff Springs) em dados OHLCV
    """
    df = df.copy()
    df.columns = df.columns.str.lower()
    
    # Suporte recente
    df['support'] = df['low'].rolling(window=int(support_period)).min().shift(1)
    
    # Volume
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    
    # Corpo e sombras
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    df['candle_range'] = df['high'] - df['low']
    df['lower_wick_ratio'] = np.where(
        df['candle_range'] > 0,
        df['lower_wick'] / df['candle_range'],
        0
    )
    
    # RSI
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    
    df['signal'] = 'HOLD'
    
    # Liquidity Grab / Wyckoff Spring
    spring = (
        (df['low'] < df['support']) &  # Violou suporte
        (df['close'] > df['support']) &  # Fechou acima
        (df['lower_wick_ratio'] >= min_wick_ratio) &  # Martelo
        (df['volume'] > df['volume_ma'] * volume_multiplier) &  # Volume
        (df['close'] > df['open']) &  # Candle de alta
        (df['rsi'] < 70)  # RSI ok
    )
    df.loc[spring, 'signal'] = 'BUY'
    
    # Saída
    df['resistance'] = df['high'].rolling(window=int(support_period)).max().shift(1)
    sell = (
        (df['close'] >= df['resistance']) |
        (df['rsi'] > 75)
    )
    df.loc[sell, 'signal'] = 'SELL'
    
    return df


def create_liquidity_grab_strategy(params: Dict[str, Any] = None) -> LiquidityGrabStrategy:
    """Factory function para criar instância da estratégia"""
    return LiquidityGrabStrategy(parameters=params)
