"""
Módulo de estratégias de trading para criptomoedas
Baseado nas especificações do INSTRUCOES.md

BLUE_PRINT v1.0: Estratégias Institucionais com filtros avançados
"""

from .base_strategy import BaseStrategy
from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .volatility_breakout import VolatilityBreakoutStrategy
from .macd_rsi_combo import MacdRsiComboStrategy
from .bollinger_bands import BollingerBandsStrategy
from .momentum import MomentumStrategy
from .volume_profile import VolumeProfileStrategy
from .multi_timeframe import MultiTimeframeStrategy
from .dynamic_position_sizing import DynamicPositionSizing
from .liquidity_grab import LiquidityGrabStrategy  # BLUE_PRINT: Nova estratégia
from .rsi_divergence import RSIDivergenceStrategy  # RSI Divergence Strategy

__all__ = [
    'BaseStrategy',
    'TrendFollowingStrategy',
    'MeanReversionStrategy',
    'VolatilityBreakoutStrategy',
    'MacdRsiComboStrategy',
    'BollingerBandsStrategy',
    'MomentumStrategy',
    'VolumeProfileStrategy',
    'MultiTimeframeStrategy',
    'DynamicPositionSizing',
    'LiquidityGrabStrategy',  # BLUE_PRINT
    'RSIDivergenceStrategy'   # RSI Divergence
]
