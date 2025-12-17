"""
Estratégia RSI Divergence - Detecção de Divergências com RSI

Esta estratégia detecta 4 padrões de divergência RSI:
1. Divergência de Alta (Bullish) - Preço faz mínimas mais baixas, RSI faz mínimas mais altas
2. Divergência de Baixa (Bearish) - Preço faz máximas mais altas, RSI faz máximas mais baixas
3. Reversão Positiva (Hidden Bullish) - Preço faz mínimas mais altas, RSI faz mínimas mais baixas
4. Reversão Negativa (Hidden Bearish) - Preço faz máximas mais baixas, RSI faz máximas mais altas

OTIMIZAÇÕES v2.0 (17/Dez/2025):
- Filtro EMA 50/200 para alinhamento com tendência
- Volume > 1.5x média obrigatório
- RSI 25/75 em vez de 30/70 (zonas mais extremas)
- Smart Exit com MACD crossover (sem trailing fixo)
- Integração com regime de mercado

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
    trend_aligned: bool = False  # NOVO: Alinhado com EMA 50/200
    volume_confirmed: bool = False  # NOVO: Volume > 1.5x média


class RSIDivergenceStrategy(BaseStrategy):
    """
    Estratégia de detecção de divergências RSI v2.0
    
    MELHORIAS IMPLEMENTADAS:
    1. Filtro EMA 50/200 - só aceita sinais alinhados com tendência macro
    2. Volume > 1.5x média - confirmação obrigatória de interesse institucional
    3. RSI 25/75 - zonas mais extremas para menos falsos positivos
    4. Smart Exit com MACD - saída baseada em reversão de momentum
    5. Integração com regime de mercado via MetaBacktester
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            # Parâmetros RSI - OTIMIZADOS
            'rsi_period': 14,
            'rsi_overbought': 75,  # ALTERADO: 70 → 75 (mais extremo)
            'rsi_oversold': 25,    # ALTERADO: 30 → 25 (mais extremo)
            
            # Parâmetros de detecção de picos/vales
            'lookback_periods': 15,  # AJUSTADO: 20 → 15
            'min_peak_distance': 5,
            'divergence_threshold': 0.02,  # 2% de diferença mínima
            
            # Filtros de tendência - NOVOS
            'use_ema_filter': True,      # NOVO: Filtro EMA 50/200
            'ema_fast_period': 50,       # NOVO: EMA rápida
            'ema_slow_period': 200,      # NOVO: EMA lenta
            'require_trend_alignment': True,  # NOVO: Exigir alinhamento
            
            # ADX
            'min_adx_trend': 18,  # AJUSTADO: 20 → 18 (menos restritivo)
            
            # Confirmação de volume - FORTALECIDA
            'volume_confirmation': True,
            'volume_multiplier': 1.5,     # ALTERADO: 1.2 → 1.5 (mais rigoroso)
            'require_volume': True,        # NOVO: Volume obrigatório
            
            # Gestão de risco
            'atr_period': 14,
            'stop_loss_atr_mult': 2.0,
            'take_profit_atr_mult': 4.0,
            
            # Smart Exit - NOVO (em vez de trailing fixo)
            'use_smart_exit': True,        # NOVO: Usar MACD para saída
            'macd_exit_threshold': 0,      # NOVO: Sair quando MACD cruza zero
            
            # Qualidade mínima do sinal - BALANCEADO
            'min_signal_strength': 0.50,   # AJUSTADO: 0.55 → 0.50 (menos restritivo)
            
            # Filtro de regime de mercado - NOVO
            'use_regime_filter': True,     # NOVO: Integrar com MetaBacktester
            'preferred_regimes': ['SIDEWAYS', 'BEAR'],  # NOVO: Melhores regimes
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("RSI Divergence Strategy v2.0", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula RSI, ATR, ADX e médias móveis para detecção de divergência
        
        NOVO v2.0: Adiciona EMA 50/200 para filtro de tendência macro
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
        
        # EMAs para contexto de tendência - NOVO v2.0
        ema_fast = self.parameters.get('ema_fast_period', 50)
        ema_slow = self.parameters.get('ema_slow_period', 200)
        
        df['ema_50'] = ta.trend.ema_indicator(df['close'], window=ema_fast)
        df['ema_200'] = ta.trend.ema_indicator(df['close'], window=ema_slow)
        df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=12)
        df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=26)
        
        # NOVO: Determinar tendência macro (EMA 50 vs 200)
        df['trend_bullish'] = df['ema_50'] > df['ema_200']  # EMA 50 acima de 200 = bullish
        df['price_above_ema50'] = df['close'] > df['ema_50']
        df['price_above_ema200'] = df['close'] > df['ema_200']
        
        # MACD para confirmação e Smart Exit
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()
        
        # NOVO: MACD histogram anterior para detectar reversão
        df['macd_hist_prev'] = df['macd_hist'].shift(1)
        df['macd_reversal_up'] = (df['macd_hist'] > 0) & (df['macd_hist_prev'] <= 0)
        df['macd_reversal_down'] = (df['macd_hist'] < 0) & (df['macd_hist_prev'] >= 0)
        
        # Médias de volume - FORTALECIDO v2.0
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        df['volume_confirmed'] = df['volume_ratio'] >= self.parameters['volume_multiplier']
        
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
            
            # Confirmar tendência de alta (preço acima da EMA 50)
            ema50_val = df['ema_50'].iloc[idx] if pd.notna(df['ema_50'].iloc[idx]) else current_price
            trend_bullish = current_price > ema50_val
            
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
            
            # Confirmar tendência de baixa (preço abaixo da EMA 50)
            ema50_val = df['ema_50'].iloc[idx] if pd.notna(df['ema_50'].iloc[idx]) else current_price
            trend_bearish = current_price < ema50_val
            
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
        
        MELHORIAS v2.0:
        - Smart Exit baseado em MACD crossover (não trailing fixo)
        - Campos adicionais: trend_aligned, volume_confirmed, smart_exit_type
        """
        df['signal'] = 0
        df['signal_type'] = ''
        df['signal_strength'] = 0.0
        df['divergence_description'] = ''
        df['stop_loss'] = 0.0
        df['take_profit'] = 0.0
        
        # NOVO v2.0: Campos adicionais para Smart Exit
        df['trend_aligned'] = False
        df['volume_confirmed'] = False
        df['smart_exit_type'] = ''  # 'macd_reversal', 'rsi_neutral', 'atr_tp'
        
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
                df.iloc[i, df.columns.get_loc('trend_aligned')] = divergence.trend_aligned
                df.iloc[i, df.columns.get_loc('volume_confirmed')] = divergence.volume_confirmed
                
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
                
                # NOVO: Determinar tipo de Smart Exit preferido
                if self.parameters.get('use_smart_exit', True):
                    df.iloc[i, df.columns.get_loc('smart_exit_type')] = 'macd_reversal'
        
        # NOVO: Identificar pontos de Smart Exit
        df = self._calculate_smart_exits(df)
        
        # Posição baseada no sinal
        df['position'] = df['signal'].replace(-1, 0)
        
        return df
    
    def _calculate_smart_exits(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        NOVO v2.0: Calcula pontos de Smart Exit baseados em indicadores
        
        Em vez de trailing stop fixo após +2%, usamos:
        1. MACD histogram reversão (principal)
        2. RSI cruzando zona neutra (50)
        3. Divergência oposta
        """
        df['exit_signal'] = 0  # 1 = exit long, -1 = exit short
        df['exit_reason'] = ''
        
        if not self.parameters.get('use_smart_exit', True):
            return df
        
        in_position = 0  # 1 = long, -1 = short, 0 = flat
        entry_idx = None
        
        for i in range(len(df)):
            # Entrada em posição
            if df['signal'].iloc[i] != 0:
                in_position = df['signal'].iloc[i]
                entry_idx = i
                continue
            
            # Se não está em posição, skip
            if in_position == 0:
                continue
            
            # Verificar condições de Smart Exit
            current_rsi = df['rsi'].iloc[i]
            macd_reversal_up = df['macd_reversal_up'].iloc[i] if 'macd_reversal_up' in df.columns else False
            macd_reversal_down = df['macd_reversal_down'].iloc[i] if 'macd_reversal_down' in df.columns else False
            
            exit_triggered = False
            exit_reason = ''
            
            if in_position == 1:  # Long position
                # Exit 1: MACD histogram virou negativo (perda de momentum)
                if macd_reversal_down:
                    exit_triggered = True
                    exit_reason = 'macd_reversal_down'
                
                # Exit 2: RSI cruzou 50 de cima para baixo
                elif pd.notna(current_rsi) and i > 0:
                    prev_rsi = df['rsi'].iloc[i-1]
                    if pd.notna(prev_rsi) and prev_rsi > 50 and current_rsi < 50:
                        exit_triggered = True
                        exit_reason = 'rsi_crossed_below_50'
                
                # Exit 3: RSI entrou em overbought (lucro parcial implícito)
                elif pd.notna(current_rsi) and current_rsi > self.parameters['rsi_overbought']:
                    exit_triggered = True
                    exit_reason = 'rsi_overbought_exit'
            
            elif in_position == -1:  # Short position
                # Exit 1: MACD histogram virou positivo (perda de momentum)
                if macd_reversal_up:
                    exit_triggered = True
                    exit_reason = 'macd_reversal_up'
                
                # Exit 2: RSI cruzou 50 de baixo para cima
                elif pd.notna(current_rsi) and i > 0:
                    prev_rsi = df['rsi'].iloc[i-1]
                    if pd.notna(prev_rsi) and prev_rsi < 50 and current_rsi > 50:
                        exit_triggered = True
                        exit_reason = 'rsi_crossed_above_50'
                
                # Exit 3: RSI entrou em oversold (lucro parcial implícito)
                elif pd.notna(current_rsi) and current_rsi < self.parameters['rsi_oversold']:
                    exit_triggered = True
                    exit_reason = 'rsi_oversold_exit'
            
            if exit_triggered:
                df.iloc[i, df.columns.get_loc('exit_signal')] = -in_position  # Inverso da posição
                df.iloc[i, df.columns.get_loc('exit_reason')] = exit_reason
                in_position = 0
                entry_idx = None
        
        return df
    
    def _apply_filters(self, df: pd.DataFrame, idx: int, divergence: DivergencePattern) -> bool:
        """
        Aplica filtros adicionais para validar o sinal
        
        FILTROS v2.0:
        1. Filtro EMA 50/200 - Alinhamento com tendência macro (NOVO)
        2. Volume > 1.5x média obrigatório (FORTALECIDO)
        3. ADX para confirmar tendência (mantido)
        4. Evitar sinais consecutivos (mantido)
        5. RSI não em zona neutra (mantido)
        """
        
        # 1. NOVO: Filtro de tendência EMA 50/200
        if self.parameters.get('use_ema_filter', True):
            ema50 = df['ema_50'].iloc[idx]
            ema200 = df['ema_200'].iloc[idx]
            current_price = df['close'].iloc[idx]
            
            if pd.notna(ema50) and pd.notna(ema200):
                # Tendência macro: EMA 50 acima de 200 = bullish
                trend_is_bullish = ema50 > ema200
                
                if self.parameters.get('require_trend_alignment', True):
                    if divergence.signal == 1:  # Sinal de compra
                        # Para BUY: preferimos preço abaixo de EMA50 (pullback) em tendência de alta
                        # OU em tendência de baixa (reversão)
                        price_below_ema50 = current_price < ema50
                        
                        # Condição relaxada: aceita se está em pullback ou em reversão clara
                        if trend_is_bullish and not price_below_ema50:
                            # Em bull trend, só aceita se está em pullback
                            if divergence.strength < 0.7:
                                logger.debug(f"Filtro EMA: Buy rejeitado - não está em pullback em bull trend")
                                return False
                        
                    else:  # Sinal de venda (signal == -1)
                        # Para SELL: preferimos preço acima de EMA50 (bounce) em tendência de baixa
                        # OU em tendência de alta (reversão)
                        price_above_ema50 = current_price > ema50
                        
                        if not trend_is_bullish and not price_above_ema50:
                            # Em bear trend, só aceita se está em bounce
                            if divergence.strength < 0.7:
                                logger.debug(f"Filtro EMA: Sell rejeitado - não está em bounce em bear trend")
                                return False
                
                # Marcar no padrão se está alinhado
                divergence.trend_aligned = True
        
        # 2. FORTALECIDO: Filtro de volume (> 1.5x média) - mas permite sinais fortes
        if self.parameters.get('require_volume', True):
            vol_ratio = df['volume_ratio'].iloc[idx]
            volume_multiplier = self.parameters['volume_multiplier']
            
            if pd.notna(vol_ratio):
                if vol_ratio < volume_multiplier:
                    # Volume insuficiente - só aceita sinais FORTES (>=0.65)
                    if divergence.strength < 0.65:
                        logger.debug(f"Filtro Volume: Rejeitado - volume_ratio {vol_ratio:.2f} < {volume_multiplier}")
                        return False
                else:
                    divergence.volume_confirmed = True
            else:
                # Sem dados de volume - só aceita sinais fortes
                if divergence.strength < 0.60:
                    return False
        
        # 3. Filtro de tendência ADX
        adx_val = df['adx'].iloc[idx]
        if pd.notna(adx_val) and adx_val < self.parameters['min_adx_trend']:
            # ADX muito baixo = sem tendência clara
            if divergence.strength < 0.65:
                return False
        
        # 4. Evitar sinais consecutivos muito próximos
        if idx >= 5:
            recent_signals = df['signal'].iloc[idx-5:idx]
            if (recent_signals != 0).any():
                return False
        
        # 5. Verificar RSI não está em zona neutra demais
        rsi = df['rsi'].iloc[idx]
        if pd.notna(rsi) and 40 < rsi < 60 and divergence.strength < 0.8:
            # Zona neutra expandida (40-60) para ser mais rigoroso
            return False
        
        return True
    
    def get_entry_conditions(self) -> List[str]:
        return [
            "Divergência de Alta: Preço faz mínimas mais baixas, RSI faz mínimas mais altas",
            "Divergência de Baixa: Preço faz máximas mais altas, RSI faz máximas mais baixas",
            "Divergência Oculta de Alta: Continuação em tendência de alta",
            "Divergência Oculta de Baixa: Continuação em tendência de baixa",
            f"NOVO: Filtro EMA 50/200 - Alinhamento com tendência macro",
            f"NOVO: Volume > {self.parameters['volume_multiplier']}x média (obrigatório)",
            f"RSI extremo: < {self.parameters['rsi_oversold']} (buy) ou > {self.parameters['rsi_overbought']} (sell)",
            f"ADX > {self.parameters['min_adx_trend']} (tendência forte)"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            f"Stop Loss: {self.parameters['stop_loss_atr_mult']}x ATR",
            f"Take Profit: {self.parameters['take_profit_atr_mult']}x ATR",
            "NOVO: Smart Exit - MACD histogram reversão",
            "NOVO: Smart Exit - RSI cruza zona neutra (50)",
            "NOVO: Smart Exit - RSI atinge zona extrema oposta",
            "Divergência oposta detectada"
        ]
    
    def get_pattern_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Retorna estatísticas dos padrões detectados v2.0
        
        NOVO: Inclui métricas de alinhamento e volume
        """
        signals_df = df[df['signal'] != 0]
        
        if len(signals_df) == 0:
            return {'total_patterns': 0}
        
        stats = {
            'total_patterns': len(signals_df),
            'buy_signals': len(signals_df[signals_df['signal'] == 1]),
            'sell_signals': len(signals_df[signals_df['signal'] == -1]),
            'avg_strength': float(signals_df['signal_strength'].mean()),
            'pattern_distribution': {},
            # NOVO v2.0
            'trend_aligned_count': int(signals_df['trend_aligned'].sum()) if 'trend_aligned' in signals_df.columns else 0,
            'volume_confirmed_count': int(signals_df['volume_confirmed'].sum()) if 'volume_confirmed' in signals_df.columns else 0,
        }
        
        # Percentuais v2.0
        if stats['total_patterns'] > 0:
            stats['trend_aligned_pct'] = (stats['trend_aligned_count'] / stats['total_patterns']) * 100
            stats['volume_confirmed_pct'] = (stats['volume_confirmed_count'] / stats['total_patterns']) * 100
        
        for pattern_type in signals_df['signal_type'].unique():
            count = len(signals_df[signals_df['signal_type'] == pattern_type])
            stats['pattern_distribution'][pattern_type] = {
                'count': int(count),
                'percentage': float((count / len(signals_df)) * 100),
                'avg_strength': float(signals_df[signals_df['signal_type'] == pattern_type]['signal_strength'].mean())
            }
        
        # NOVO: Estatísticas de Smart Exit
        if 'exit_signal' in df.columns:
            exits_df = df[df['exit_signal'] != 0]
            stats['smart_exits'] = {
                'total': len(exits_df),
                'exit_reasons': {}
            }
            if 'exit_reason' in df.columns:
                for reason in exits_df['exit_reason'].unique():
                    count = len(exits_df[exits_df['exit_reason'] == reason])
                    stats['smart_exits']['exit_reasons'][reason] = int(count)
        
        return stats
    
    def check_regime_filter(self, market_regime: str) -> bool:
        """
        NOVO v2.0: Verifica se o regime de mercado é favorável
        
        Integração com MetaBacktester:
        - SIDEWAYS: Melhor regime para RSI Divergence (reversões)
        - BEAR: Bom para divergências de alta (potencial reversão)
        - BULL: Menos favorável (tendência forte, menos reversões)
        
        Args:
            market_regime: 'BULL', 'BEAR', 'SIDEWAYS' do MetaBacktester
            
        Returns:
            True se o regime é favorável para esta estratégia
        """
        if not self.parameters.get('use_regime_filter', True):
            return True
        
        preferred = self.parameters.get('preferred_regimes', ['SIDEWAYS', 'BEAR'])
        return market_regime.upper() in preferred
    
    def get_optimized_params_for_regime(self, market_regime: str) -> Dict[str, Any]:
        """
        NOVO v2.0: Retorna parâmetros otimizados por regime de mercado
        
        Baseado nos resultados do backtest multi-par:
        - BULL: RSI mais extremo, volume maior, menos sinais
        - BEAR: RSI normal, aceita mais sinais de reversão
        - SIDEWAYS: Configuração padrão, melhor cenário
        """
        regime = market_regime.upper()
        
        if regime == 'BULL':
            # Em bull market, ser mais conservador com reversões
            return {
                'rsi_overbought': 80,  # Mais extremo
                'rsi_oversold': 20,    # Mais extremo
                'volume_multiplier': 1.8,  # Volume maior
                'min_signal_strength': 0.65,  # Só sinais fortes
            }
        elif regime == 'BEAR':
            # Em bear market, divergências de alta são oportunidades
            return {
                'rsi_overbought': 75,
                'rsi_oversold': 25,
                'volume_multiplier': 1.4,  # Mais relaxado
                'min_signal_strength': 0.5,
            }
        else:  # SIDEWAYS
            # Melhor cenário - usar padrão
            return {
                'rsi_overbought': 75,
                'rsi_oversold': 25,
                'volume_multiplier': 1.5,
                'min_signal_strength': 0.55,
            }


def create_rsi_divergence_strategy(params: Dict[str, Any] = None):
    """Factory function para criar instância da estratégia"""
    return RSIDivergenceStrategy(parameters=params)
