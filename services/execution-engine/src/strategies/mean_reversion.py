"""
Estratégia 2: Mean Reversion com Bollinger Bands
Para mercados laterais (ranging)

Regras de Entrada (BUY):
1. Preço toca ou ultrapassa banda inferior (oversold)
2. RSI < 30 (confirma sobrevenda)
3. Volume acima da média

Regras de Saída (SELL):
1. Preço toca banda superior (overbought)
2. RSI > 70
3. Preço retorna à média móvel central
"""

import pandas as pd
import numpy as np
import ta
from typing import Dict, Any
from .base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """
    Estratégia de reversão à média usando Bollinger Bands
    Ideal para mercados laterais com alta volatilidade
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'bb_period': 20,
            'bb_std': 2.5,  # PLANO_DE_MELHORAMENTO: 2.5 (mais conservador)
            'rsi_period': 14,
            'rsi_oversold': 28,  # PLANO_DE_MELHORAMENTO: 28 (mais conservador)
            'rsi_overbought': 70,
            'volume_sma': 20,
            'volume_multiplier': 1.3,  # PLANO_DE_MELHORAMENTO: 1.3 (institucional)
            'sma_macro_period': 200,  # BLUE_PRINT: Filtro Macro para evitar facas caindo
            'min_adx': 15,  # PLANO: Mínimo ADX para evitar lateralidade extrema
            'max_adx': 25   # PLANO: Máximo ADX (não opera em tendência forte)
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__("Mean Reversion (Bollinger Bands)", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula Bollinger Bands, RSI e Volume
        """
        bb_period = self.parameters['bb_period']
        bb_std = self.parameters['bb_std']
        rsi_period = self.parameters['rsi_period']
        volume_sma = self.parameters['volume_sma']
        
        # Bollinger Bands
        bollinger = ta.volatility.BollingerBands(
            df['Close'], 
            window=bb_period, 
            window_dev=bb_std
        )
        
        df['BB_upper'] = bollinger.bollinger_hband()
        df['BB_middle'] = bollinger.bollinger_mavg()
        df['BB_lower'] = bollinger.bollinger_lband()
        
        # Largura das bandas (volatilidade)
        df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle']
        
        # Posição do preço em relação às bandas
        df['BB_position'] = (df['Close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
        
        # RSI
        df['RSI'] = ta.momentum.rsi(df['Close'], window=rsi_period)
        
        # Volume
        df['Volume_SMA'] = df['Volume'].rolling(window=volume_sma).mean()
        df['volume_confirmed'] = (
            df['Volume'] > df['Volume_SMA'] * self.parameters['volume_multiplier']
        ).astype(int)
        
        # Stochastic para confirmar reversão
        stoch = ta.momentum.StochasticOscillator(
            df['High'], df['Low'], df['Close'], 
            window=14, smooth_window=3
        )
        df['Stoch'] = stoch.stoch()
        
        # ATR para stop-loss
        df['ATR'] = ta.volatility.average_true_range(
            df['High'], df['Low'], df['Close'], window=14
        )
        
        # === BLUE_PRINT: Filtro Macro SMA200 ===
        # Só compra reversão se preço estiver ACIMA da SMA200 (Bull Macro)
        # Evita tentar pegar "facas caindo" em tendências de baixa
        sma_period = self.parameters.get('sma_macro_period', 200)
        df['SMA200'] = ta.trend.sma_indicator(df['Close'], window=sma_period)
        df['macro_bull'] = df['Close'] > df['SMA200']
        
        # PLANO_DE_MELHORAMENTO: ADX para filtrar lateralidade
        # Mean Reversion funciona melhor em ADX baixo (15-25)
        adx_indicator = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14)
        df['ADX'] = adx_indicator.adx()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de compra/venda para reversão à média
        
        BLUE_PRINT v1.0 - Refinamento Institucional:
        - Filtro Macro: Só compra reversão se preço > SMA200
        - Evita tentar pegar facas caindo em bear markets
        """
        rsi_oversold = self.parameters['rsi_oversold']
        rsi_overbought = self.parameters['rsi_overbought']
        
        # Inicializar sinais
        df['signal'] = 0
        df['signal_strength'] = 0.0
        
        # === BLUE_PRINT: Condições de COMPRA com Filtro Macro ===
        # REGRA: Só compra se preço > SMA200 (Bull Macro)
        
        # OTIMIZAÇÃO #3: Ajuste para alta volatilidade
        # Calcular ATR% para detectar ambientes de alta volatilidade
        df['ATR_pct'] = (df['ATR'] / df['Close']) * 100
        high_volatility = df['ATR_pct'] > 5.0  # ATR > 5% do preço
        
        # Em alta volatilidade, relaxar RSI (28 → 32) e BB position (20% → 25%)
        rsi_oversold_adj = np.where(high_volatility, 32, rsi_oversold)
        bb_position_threshold = np.where(high_volatility, 0.25, 0.2)
        
        # PLANO_DE_MELHORAMENTO: ADX range para mean reversion (15-25)
        min_adx = self.parameters.get('min_adx', 15)
        max_adx = self.parameters.get('max_adx', 25)
        adx_in_range = (df['ADX'] > min_adx) & (df['ADX'] < max_adx)
        
        buy_condition = (
            (df['macro_bull'] == True) &  # FILTRO MACRO: Preço > SMA200
            adx_in_range &  # PLANO: ADX entre 15-25 (lateralidade moderada)
            (df['Close'] <= df['BB_lower'] * 1.01) &  # Toca banda inferior
            (df['RSI'] < rsi_oversold_adj) &  # RSI confirma sobrevenda (ajustável)
            (df['BB_position'] < bb_position_threshold) &  # Preço nos X% inferiores (ajustável)
            (df['Stoch'] < 20)  # Stochastic sobrevenda
        )
        
        # Condições de VENDA (preço na banda superior ou retorno à média)
        sell_condition = (
            (df['Close'] >= df['BB_upper'] * 0.99) |  # Toca banda superior
            (df['RSI'] > rsi_overbought) |  # RSI sobrecomprado
            (df['BB_position'] > 0.8) |  # Preço nos 80% superiores
            (df['Stoch'] > 80)  # Stochastic sobrecomprado
        )
        
        # Aplicar sinais
        df.loc[buy_condition, 'signal'] = 1
        df.loc[sell_condition, 'signal'] = -1
        
        # Calcular força do sinal
        df['signal_strength'] = self._calculate_signal_strength(df)
        
        # Posição para backtesting
        df['position'] = df['signal'].replace(-1, 0)
        
        # Stop-loss e take-profit
        df['stop_loss'] = df['BB_lower'] - df['ATR']
        df['take_profit'] = df['BB_middle']  # Target é a média
        
        return df
    
    def _calculate_signal_strength(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula força do sinal baseado em distância das bandas e RSI
        """
        strength = pd.Series(0.0, index=df.index)
        
        # Quanto mais perto da banda, mais forte o sinal
        # BB_position: 0 = banda inferior, 1 = banda superior
        distance_strength = np.where(
            df['BB_position'] < 0.5,
            1 - (df['BB_position'] * 2),  # Compra: mais forte perto da banda inferior
            (df['BB_position'] - 0.5) * 2  # Venda: mais forte perto da banda superior
        )
        
        # RSI extremo aumenta força
        rsi_normalized = np.abs(df['RSI'] - 50) / 50  # 0 a 1
        
        # Volume confirma força
        volume_ratio = df['Volume'] / df['Volume_SMA']
        volume_strength = np.clip((volume_ratio - 1) / 2, 0, 1)
        
        # Combinar
        strength = (
            0.5 * distance_strength +
            0.3 * rsi_normalized +
            0.2 * volume_strength
        )
        
        return np.clip(strength, 0, 1)
    
    def get_entry_conditions(self) -> list:
        """Retorna condições de entrada legíveis"""
        return [
            "Preço toca ou ultrapassa banda inferior de Bollinger",
            f"RSI < {self.parameters['rsi_oversold']} (sobrevenda)",
            "Posição nas bandas < 20% (área inferior)",
            "Stochastic < 20 (confirma sobrevenda)"
        ]
    
    def get_exit_conditions(self) -> list:
        """Retorna condições de saída legíveis"""
        return [
            "Preço toca banda superior de Bollinger",
            f"RSI > {self.parameters['rsi_overbought']} (sobrecompra)",
            "Posição nas bandas > 80% (área superior)",
            "Take-profit: Retorno à média (banda central)",
            "Stop-loss: Banda inferior - ATR"
        ]
    
    def is_ranging_market(self, df: pd.DataFrame, periods: int = 50) -> bool:
        """
        Detecta se o mercado está lateral (ranging)
        Útil para decidir quando usar esta estratégia
        
        Args:
            df: DataFrame com dados
            periods: Número de períodos para análise
            
        Returns:
            True se mercado está lateral
        """
        if len(df) < periods:
            return False
        
        recent_data = df.tail(periods)
        
        # Calcular volatilidade relativa
        price_std = recent_data['Close'].std()
        price_mean = recent_data['Close'].mean()
        cv = price_std / price_mean  # Coeficiente de variação
        
        # Calcular tendência (slope da regressão linear)
        x = np.arange(len(recent_data))
        y = recent_data['Close'].values
        slope = np.polyfit(x, y, 1)[0]
        slope_pct = (slope / price_mean) * 100
        
        # Mercado lateral: baixa tendência e volatilidade moderada
        is_ranging = abs(slope_pct) < 0.1 and cv < 0.05
        
        logger.info(f"Market analysis - Slope: {slope_pct:.3f}%, CV: {cv:.3f}, Ranging: {is_ranging}")
        
        return is_ranging
    
    def analyze_bands(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analisa estado atual das Bollinger Bands
        
        Returns:
            Dicionário com análise das bandas
        """
        if df.empty or 'BB_position' not in df.columns:
            return {"error": "Dados insuficientes"}
        
        last_row = df.iloc[-1]
        
        # Determinar região
        if last_row['BB_position'] < 0.2:
            region = "BANDA INFERIOR (Sobrevenda)"
        elif last_row['BB_position'] > 0.8:
            region = "BANDA SUPERIOR (Sobrecompra)"
        elif 0.4 < last_row['BB_position'] < 0.6:
            region = "MÉDIA (Neutro)"
        else:
            region = "INTERMEDIÁRIO"
        
        # Volatilidade
        if last_row['BB_width'] > 0.1:
            volatility = "ALTA"
        elif last_row['BB_width'] > 0.05:
            volatility = "MÉDIA"
        else:
            volatility = "BAIXA"
        
        return {
            "current_price": float(last_row['Close']),
            "bb_upper": float(last_row['BB_upper']),
            "bb_middle": float(last_row['BB_middle']),
            "bb_lower": float(last_row['BB_lower']),
            "position": float(last_row['BB_position']),
            "region": region,
            "width": float(last_row['BB_width']),
            "volatility": volatility,
            "rsi": float(last_row['RSI']),
            "current_signal": int(last_row['signal'])
        }


def create_mean_reversion_strategy(params: Dict[str, Any] = None) -> MeanReversionStrategy:
    """Factory function para criar instância da estratégia"""
    return MeanReversionStrategy(parameters=params)
