"""
Estratégia RSI Divergence - Detecção de Divergências com RSI

Esta estratégia detecta 4 padrões de divergência RSI:
1. Divergência de Alta (Bullish) - Preço faz mínimas mais baixas, RSI faz mínimas mais altas
2. Divergência de Baixa (Bearish) - Preço faz máximas mais altas, RSI faz máximas mais baixas
3. Reversão Positiva (Hidden Bullish) - Preço faz mínimas mais altas, RSI faz mínimas mais baixas
4. Reversão Negativa (Hidden Bearish) - Preço faz máximas mais baixas, RSI faz máximas mais altas

DISCLAIMER: Esta estratégia é para fins educacionais.
Past performance não garante resultados futuros.
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


@dataclass
class DivergencePattern:
    """Representa um padrão de divergência detectado"""
    pattern_type: str  # 'bullish', 'bearish', 'hidden_bullish', 'hidden_bearish'
    signal: int  # 1 para buy, -1 para sell
    strength: float  # 0.0 a 1.0
    price_point1: float
    price_point2: float
    rsi_point1: float
    rsi_point2: float
    index: int
    description: str


class RSIDivergenceStrategy(BaseStrategy):
    """
    Estratégia de detecção de divergências RSI
    
    Detecta divergências regulares e ocultas entre preço e RSI,
    gerando sinais de reversão ou continuação de tendência.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            # Parâmetros RSI
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            
            # Parâmetros de detecção de picos/vales
            'lookback_periods': 20,
            'min_peak_distance': 5,
            'divergence_threshold': 0.02,  # 2% de diferença mínima
            
            # Filtros de tendência
            'ma_trend_period': 50,
            'min_adx_trend': 20,
            
            # Confirmação de volume
            'volume_confirmation': True,
            'volume_multiplier': 1.2,
            
            # Gestão de risco
            'atr_period': 14,
            'stop_loss_atr_mult': 2.0,
            'take_profit_atr_mult': 4.0,
            
            # Qualidade mínima do sinal
            'min_signal_strength': 0.5
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("RSI Divergence Strategy", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula RSI, ATR, ADX e médias móveis para detecção de divergência
        """
        # Normalizar nomes das colunas (lowercase)
        df.columns = [c.lower() for c in df.columns]
        
        # RSI
        df['rsi'] = ta.momentum.rsi(df['close'], window=self.parameters['rsi_period'])
        
        # ATR para gestão de risco
        df['atr'] = ta.volatility.average_true_range(
            df['high'], df['low'], df['close'], 
            window=self.parameters['atr_period']
        )
        
        # ADX para filtro de tendência
        try:
            adx_indicator = ta.trend.ADXIndicator(
                df['high'], df['low'], df['close'], 
                window=self.parameters['min_adx_trend']
            )
            df['adx'] = adx_indicator.adx()
            df['di_plus'] = adx_indicator.adx_pos()
            df['di_minus'] = adx_indicator.adx_neg()
        except Exception:
            df['adx'] = 25  # Valor padrão se falhar
            df['di_plus'] = 25
            df['di_minus'] = 25
        
        # Médias móveis para contexto de tendência
        df['sma_trend'] = ta.trend.sma_indicator(df['close'], window=self.parameters['ma_trend_period'])
        df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=12)
        df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=26)
        
        # MACD para confirmação
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()
        
        # Médias de volume
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Detectar picos e vales no preço e RSI
        df = self._detect_peaks_and_valleys(df)
        
        return df
    
    def _detect_peaks_and_valleys(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta picos e vales no preço e no RSI
        """
        lookback = self.parameters['lookback_periods']
        
        df['price_peak'] = False
        df['price_valley'] = False
        df['rsi_peak'] = False
        df['rsi_valley'] = False
        
        for i in range(lookback, len(df) - lookback):
            # Picos de preço (máximas locais)
            window_high = df['high'].iloc[i-lookback:i+lookback+1]
            if df['high'].iloc[i] == window_high.max():
                df.iloc[i, df.columns.get_loc('price_peak')] = True
            
            # Vales de preço (mínimas locais)
            window_low = df['low'].iloc[i-lookback:i+lookback+1]
            if df['low'].iloc[i] == window_low.min():
                df.iloc[i, df.columns.get_loc('price_valley')] = True
            
            # Picos de RSI
            if pd.notna(df['rsi'].iloc[i]):
                window_rsi = df['rsi'].iloc[i-lookback:i+lookback+1].dropna()
                if len(window_rsi) > 0:
                    if df['rsi'].iloc[i] == window_rsi.max() and df['rsi'].iloc[i] > 50:
                        df.iloc[i, df.columns.get_loc('rsi_peak')] = True
                    
                    # Vales de RSI
                    if df['rsi'].iloc[i] == window_rsi.min() and df['rsi'].iloc[i] < 50:
                        df.iloc[i, df.columns.get_loc('rsi_valley')] = True
        
        return df
    
    def _find_divergence(self, df: pd.DataFrame, idx: int) -> Optional[DivergencePattern]:
        """
        Procura por divergências no ponto atual
        """
        if idx < self.parameters['lookback_periods'] * 2:
            return None
        
        lookback = self.parameters['lookback_periods']
        threshold = self.parameters['divergence_threshold']
        
        # Buscar últimos picos/vales de preço e RSI
        price_data = df.iloc[idx-lookback*2:idx+1]
        
        current_price = df['close'].iloc[idx]
        current_rsi = df['rsi'].iloc[idx]
        
        if pd.isna(current_rsi):
            return None
        
        # 1. DIVERGÊNCIA DE ALTA (Bullish Divergence)
        # Preço faz mínimas mais baixas, RSI faz mínimas mais altas
        price_valleys = price_data[price_data['price_valley']].tail(2)
        rsi_valleys = price_data[price_data['rsi_valley']].tail(2)
        
        if len(price_valleys) >= 2 and len(rsi_valleys) >= 2:
            # Verificar se preço faz lower lows
            price_ll = price_valleys['low'].iloc[-1] < price_valleys['low'].iloc[-2] * (1 - threshold)
            # Verificar se RSI faz higher lows
            rsi_hl = rsi_valleys['rsi'].iloc[-1] > rsi_valleys['rsi'].iloc[-2] * (1 + threshold/10)
            
            if price_ll and rsi_hl:
                strength = self._calculate_divergence_strength(
                    price_valleys['low'].iloc[-2], price_valleys['low'].iloc[-1],
                    rsi_valleys['rsi'].iloc[-2], rsi_valleys['rsi'].iloc[-1],
                    'bullish', df, idx
                )
                
                if strength >= self.parameters['min_signal_strength']:
                    return DivergencePattern(
                        pattern_type='bullish_divergence',
                        signal=1,
                        strength=strength,
                        price_point1=price_valleys['low'].iloc[-2],
                        price_point2=price_valleys['low'].iloc[-1],
                        rsi_point1=rsi_valleys['rsi'].iloc[-2],
                        rsi_point2=rsi_valleys['rsi'].iloc[-1],
                        index=idx,
                        description='Divergência de Alta: Preço ↓ RSI ↑'
                    )
        
        # 2. DIVERGÊNCIA DE BAIXA (Bearish Divergence)
        # Preço faz máximas mais altas, RSI faz máximas mais baixas
        price_peaks = price_data[price_data['price_peak']].tail(2)
        rsi_peaks = price_data[price_data['rsi_peak']].tail(2)
        
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            # Verificar se preço faz higher highs
            price_hh = price_peaks['high'].iloc[-1] > price_peaks['high'].iloc[-2] * (1 + threshold)
            # Verificar se RSI faz lower highs
            rsi_lh = rsi_peaks['rsi'].iloc[-1] < rsi_peaks['rsi'].iloc[-2] * (1 - threshold/10)
            
            if price_hh and rsi_lh:
                strength = self._calculate_divergence_strength(
                    price_peaks['high'].iloc[-2], price_peaks['high'].iloc[-1],
                    rsi_peaks['rsi'].iloc[-2], rsi_peaks['rsi'].iloc[-1],
                    'bearish', df, idx
                )
                
                if strength >= self.parameters['min_signal_strength']:
                    return DivergencePattern(
                        pattern_type='bearish_divergence',
                        signal=-1,
                        strength=strength,
                        price_point1=price_peaks['high'].iloc[-2],
                        price_point2=price_peaks['high'].iloc[-1],
                        rsi_point1=rsi_peaks['rsi'].iloc[-2],
                        rsi_point2=rsi_peaks['rsi'].iloc[-1],
                        index=idx,
                        description='Divergência de Baixa: Preço ↑ RSI ↓'
                    )
        
        # 3. DIVERGÊNCIA OCULTA DE ALTA (Hidden Bullish)
        if len(price_valleys) >= 2 and len(rsi_valleys) >= 2:
            price_hl = price_valleys['low'].iloc[-1] > price_valleys['low'].iloc[-2] * (1 + threshold)
            rsi_ll = rsi_valleys['rsi'].iloc[-1] < rsi_valleys['rsi'].iloc[-2] * (1 - threshold/10)
            
            # Confirmar tendência de alta (preço acima da MA)
            sma_val = df['sma_trend'].iloc[idx] if pd.notna(df['sma_trend'].iloc[idx]) else current_price
            trend_bullish = current_price > sma_val
            
            if price_hl and rsi_ll and trend_bullish:
                strength = self._calculate_divergence_strength(
                    price_valleys['low'].iloc[-2], price_valleys['low'].iloc[-1],
                    rsi_valleys['rsi'].iloc[-2], rsi_valleys['rsi'].iloc[-1],
                    'hidden_bullish', df, idx
                ) * 0.9
                
                if strength >= self.parameters['min_signal_strength']:
                    return DivergencePattern(
                        pattern_type='hidden_bullish',
                        signal=1,
                        strength=strength,
                        price_point1=price_valleys['low'].iloc[-2],
                        price_point2=price_valleys['low'].iloc[-1],
                        rsi_point1=rsi_valleys['rsi'].iloc[-2],
                        rsi_point2=rsi_valleys['rsi'].iloc[-1],
                        index=idx,
                        description='Reversão Positiva: Continuação de alta'
                    )
        
        # 4. DIVERGÊNCIA OCULTA DE BAIXA (Hidden Bearish)
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            price_lh = price_peaks['high'].iloc[-1] < price_peaks['high'].iloc[-2] * (1 - threshold)
            rsi_hh = rsi_peaks['rsi'].iloc[-1] > rsi_peaks['rsi'].iloc[-2] * (1 + threshold/10)
            
            # Confirmar tendência de baixa
            sma_val = df['sma_trend'].iloc[idx] if pd.notna(df['sma_trend'].iloc[idx]) else current_price
            trend_bearish = current_price < sma_val
            
            if price_lh and rsi_hh and trend_bearish:
                strength = self._calculate_divergence_strength(
                    price_peaks['high'].iloc[-2], price_peaks['high'].iloc[-1],
                    rsi_peaks['rsi'].iloc[-2], rsi_peaks['rsi'].iloc[-1],
                    'hidden_bearish', df, idx
                ) * 0.9
                
                if strength >= self.parameters['min_signal_strength']:
                    return DivergencePattern(
                        pattern_type='hidden_bearish',
                        signal=-1,
                        strength=strength,
                        price_point1=price_peaks['high'].iloc[-2],
                        price_point2=price_peaks['high'].iloc[-1],
                        rsi_point1=rsi_peaks['rsi'].iloc[-2],
                        rsi_point2=rsi_peaks['rsi'].iloc[-1],
                        index=idx,
                        description='Reversão Negativa: Continuação de baixa'
                    )
        
        return None
    
    def _calculate_divergence_strength(
        self, 
        price1: float, price2: float,
        rsi1: float, rsi2: float,
        div_type: str,
        df: pd.DataFrame,
        idx: int
    ) -> float:
        """
        Calcula a força da divergência baseada em múltiplos fatores
        
        Retorna valor entre 0.0 e 1.0
        """
        scores = []
        
        # 1. Magnitude da divergência de preço (25%)
        price_change = abs(price2 - price1) / price1
        price_score = min(price_change * 10, 1.0)
        scores.append(('price_magnitude', price_score, 0.25))
        
        # 2. Magnitude da divergência de RSI (25%)
        rsi_change = abs(rsi2 - rsi1) / 100
        rsi_score = min(rsi_change * 5, 1.0)
        scores.append(('rsi_magnitude', rsi_score, 0.25))
        
        # 3. Confirmação de volume (20%)
        if self.parameters['volume_confirmation'] and 'volume_ratio' in df.columns:
            vol_ratio = df['volume_ratio'].iloc[idx]
            if pd.notna(vol_ratio):
                volume_score = min(vol_ratio / self.parameters['volume_multiplier'], 1.0)
            else:
                volume_score = 0.5
        else:
            volume_score = 0.5
        scores.append(('volume', volume_score, 0.20))
        
        # 4. RSI em zona extrema (15%)
        current_rsi = df['rsi'].iloc[idx]
        if pd.notna(current_rsi):
            if div_type in ['bullish', 'hidden_bullish']:
                rsi_zone_score = max(0, (self.parameters['rsi_oversold'] - current_rsi + 20) / 40)
            else:
                rsi_zone_score = max(0, (current_rsi - self.parameters['rsi_overbought'] + 20) / 40)
            rsi_zone_score = min(rsi_zone_score, 1.0)
        else:
            rsi_zone_score = 0.5
        scores.append(('rsi_zone', rsi_zone_score, 0.15))
        
        # 5. Confirmação MACD (15%)
        if 'macd_hist' in df.columns:
            macd_hist = df['macd_hist'].iloc[idx]
            macd_hist_prev = df['macd_hist'].iloc[idx-1] if idx > 0 else macd_hist
            
            if pd.notna(macd_hist) and pd.notna(macd_hist_prev):
                if div_type in ['bullish', 'hidden_bullish']:
                    macd_score = 1.0 if macd_hist > macd_hist_prev else 0.3
                else:
                    macd_score = 1.0 if macd_hist < macd_hist_prev else 0.3
            else:
                macd_score = 0.5
        else:
            macd_score = 0.5
        scores.append(('macd', macd_score, 0.15))
        
        # Calcular score ponderado final
        final_score = sum(score * weight for name, score, weight in scores)
        
        return min(max(final_score, 0.0), 1.0)
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de compra/venda baseados em divergências RSI
        """
        df['signal'] = 0
        df['signal_type'] = ''
        df['signal_strength'] = 0.0
        df['divergence_description'] = ''
        df['stop_loss'] = 0.0
        df['take_profit'] = 0.0
        
        # Processar cada candle procurando divergências
        for i in range(self.parameters['lookback_periods'] * 2, len(df)):
            divergence = self._find_divergence(df, i)
            
            if divergence is not None:
                # Aplicar filtros adicionais
                if not self._apply_filters(df, i, divergence):
                    continue
                
                # Registrar sinal
                df.iloc[i, df.columns.get_loc('signal')] = divergence.signal
                df.iloc[i, df.columns.get_loc('signal_type')] = divergence.pattern_type
                df.iloc[i, df.columns.get_loc('signal_strength')] = divergence.strength
                df.iloc[i, df.columns.get_loc('divergence_description')] = divergence.description
                
                # Calcular Stop Loss e Take Profit
                atr = df['atr'].iloc[i]
                entry_price = df['close'].iloc[i]
                
                if pd.notna(atr):
                    if divergence.signal == 1:  # Compra
                        df.iloc[i, df.columns.get_loc('stop_loss')] = entry_price - (atr * self.parameters['stop_loss_atr_mult'])
                        df.iloc[i, df.columns.get_loc('take_profit')] = entry_price + (atr * self.parameters['take_profit_atr_mult'])
                    else:  # Venda
                        df.iloc[i, df.columns.get_loc('stop_loss')] = entry_price + (atr * self.parameters['stop_loss_atr_mult'])
                        df.iloc[i, df.columns.get_loc('take_profit')] = entry_price - (atr * self.parameters['take_profit_atr_mult'])
        
        # Posição baseada no sinal
        df['position'] = df['signal'].replace(-1, 0)
        
        return df
    
    def _apply_filters(self, df: pd.DataFrame, idx: int, divergence: DivergencePattern) -> bool:
        """
        Aplica filtros adicionais para validar o sinal
        """
        # 1. Filtro de tendência ADX
        adx_val = df['adx'].iloc[idx]
        if pd.notna(adx_val) and adx_val < self.parameters['min_adx_trend']:
            return False
        
        # 2. Filtro de volume (se habilitado)
        if self.parameters['volume_confirmation']:
            vol_ratio = df['volume_ratio'].iloc[idx]
            if pd.notna(vol_ratio) and vol_ratio < self.parameters['volume_multiplier']:
                # Permitir sinais com volume normal para divergências fortes
                if divergence.strength < 0.7:
                    return False
        
        # 3. Evitar sinais consecutivos muito próximos
        if idx >= 5:
            recent_signals = df['signal'].iloc[idx-5:idx]
            if (recent_signals != 0).any():
                return False
        
        # 4. Verificar RSI não está em zona neutra demais
        rsi = df['rsi'].iloc[idx]
        if pd.notna(rsi) and 45 < rsi < 55 and divergence.strength < 0.8:
            return False
        
        return True
    
    def get_entry_conditions(self) -> List[str]:
        return [
            "Divergência de Alta: Preço faz mínimas mais baixas, RSI faz mínimas mais altas",
            "Divergência de Baixa: Preço faz máximas mais altas, RSI faz máximas mais baixas",
            "Divergência Oculta de Alta: Continuação em tendência de alta",
            "Divergência Oculta de Baixa: Continuação em tendência de baixa",
            f"ADX > {self.parameters['min_adx_trend']} (tendência forte)",
            f"Volume > {self.parameters['volume_multiplier']}x média (confirmação)"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            f"Stop Loss: {self.parameters['stop_loss_atr_mult']}x ATR",
            f"Take Profit: {self.parameters['take_profit_atr_mult']}x ATR",
            "Divergência oposta detectada"
        ]
    
    def get_pattern_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Retorna estatísticas dos padrões detectados
        """
        signals_df = df[df['signal'] != 0]
        
        if len(signals_df) == 0:
            return {'total_patterns': 0}
        
        stats = {
            'total_patterns': len(signals_df),
            'buy_signals': len(signals_df[signals_df['signal'] == 1]),
            'sell_signals': len(signals_df[signals_df['signal'] == -1]),
            'avg_strength': float(signals_df['signal_strength'].mean()),
            'pattern_distribution': {}
        }
        
        for pattern_type in signals_df['signal_type'].unique():
            count = len(signals_df[signals_df['signal_type'] == pattern_type])
            stats['pattern_distribution'][pattern_type] = {
                'count': int(count),
                'percentage': float((count / len(signals_df)) * 100),
                'avg_strength': float(signals_df[signals_df['signal_type'] == pattern_type]['signal_strength'].mean())
            }
        
        return stats


def create_rsi_divergence_strategy(params: Dict[str, Any] = None):
    """Factory function para criar instância da estratégia"""
    return RSIDivergenceStrategy(parameters=params)
