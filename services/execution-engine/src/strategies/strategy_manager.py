"""
Gerenciador de estratégias - facilita uso de todas as estratégias disponíveis
"""

from typing import Dict, Any, List, Type
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
import logging

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Gerenciador central de todas as estratégias disponíveis
    """
    
    # Registro de todas as estratégias disponíveis
    STRATEGIES: Dict[str, Type[BaseStrategy]] = {
        'trend_following': TrendFollowingStrategy,
        'mean_reversion': MeanReversionStrategy,
        'volatility_breakout': VolatilityBreakoutStrategy,
        'macd_rsi_combo': MacdRsiComboStrategy,
        'bollinger_bands': BollingerBandsStrategy,
        'momentum': MomentumStrategy,
        'volume_profile': VolumeProfileStrategy,
        'multi_timeframe': MultiTimeframeStrategy,
        'dynamic_position_sizing': DynamicPositionSizing
    }
    
    @classmethod
    def get_strategy(cls, strategy_name: str, parameters: Dict[str, Any] = None) -> BaseStrategy:
        """
        Cria instância de uma estratégia pelo nome
        
        Args:
            strategy_name: Nome da estratégia
            parameters: Parâmetros customizados
            
        Returns:
            Instância da estratégia
            
        Raises:
            ValueError: Se estratégia não existe
        """
        strategy_key = strategy_name.lower().replace(' ', '_').replace('-', '_')
        
        if strategy_key not in cls.STRATEGIES:
            available = ', '.join(cls.STRATEGIES.keys())
            raise ValueError(f"Estratégia '{strategy_name}' não encontrada. Disponíveis: {available}")
        
        strategy_class = cls.STRATEGIES[strategy_key]
        return strategy_class(parameters=parameters)
    
    @classmethod
    def list_strategies(cls) -> List[Dict[str, Any]]:
        """
        Lista todas as estratégias disponíveis com suas descrições
        
        Returns:
            Lista de dicionários com info das estratégias
        """
        strategies_info = []
        
        for key, strategy_class in cls.STRATEGIES.items():
            # Criar instância temporária para obter informações
            temp_instance = strategy_class()
            
            strategies_info.append({
                'id': key,
                'name': temp_instance.name,
                'class': strategy_class.__name__,
                'default_parameters': temp_instance.parameters,
                'entry_conditions': temp_instance.get_entry_conditions(),
                'exit_conditions': temp_instance.get_exit_conditions()
            })
        
        return strategies_info
    
    @classmethod
    def get_strategy_class(cls, strategy_name: str) -> Type[BaseStrategy]:
        """
        Retorna a classe da estratégia (não instancia)
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            Classe da estratégia
            
        Raises:
            ValueError: Se estratégia não existe
        """
        strategy_key = strategy_name.lower().replace(' ', '_').replace('-', '_')
        
        if strategy_key not in cls.STRATEGIES:
            available = ', '.join(cls.STRATEGIES.keys())
            raise ValueError(f"Estratégia '{strategy_name}' não encontrada. Disponíveis: {available}")
        
        return cls.STRATEGIES[strategy_key]
    
    @classmethod
    def get_strategy_description(cls, strategy_name: str) -> Dict[str, Any]:
        """
        Obtém descrição detalhada de uma estratégia específica
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            Dicionário com descrição detalhada
        """
        strategy = cls.get_strategy(strategy_name)
        
        return {
            'name': strategy.name,
            'parameters': strategy.parameters,
            'entry_conditions': strategy.get_entry_conditions(),
            'exit_conditions': strategy.get_exit_conditions(),
            'description': strategy.__class__.__doc__
        }
    
    @classmethod
    def compare_strategies(cls, strategies: List[str], df, initial_capital: float = 10000) -> Dict[str, Any]:
        """
        Compara performance de múltiplas estratégias
        
        Args:
            strategies: Lista de nomes de estratégias
            df: DataFrame com dados
            initial_capital: Capital inicial
            
        Returns:
            Comparação de performances
        """
        results = {}
        
        for strategy_name in strategies:
            try:
                strategy = cls.get_strategy(strategy_name)
                df_result = strategy.run(df.copy())
                
                # Calcular métricas
                sharpe = strategy.calculate_sharpe_ratio(df_result)
                
                # Calcular retorno total
                df_result['returns'] = df_result['Close'].pct_change()
                df_result['strategy_returns'] = df_result['returns'] * df_result['signal'].shift(1)
                total_return = (1 + df_result['strategy_returns'].fillna(0)).prod() - 1
                
                results[strategy_name] = {
                    'sharpe_ratio': float(sharpe),
                    'total_return': float(total_return * 100),  # em percentual
                    'total_trades': int(df_result['signal'].abs().sum()),
                    'win_rate': 0.0  # Calculado no backtesting completo
                }
                
            except Exception as e:
                logger.error(f"Erro ao comparar estratégia {strategy_name}: {e}")
                results[strategy_name] = {'error': str(e)}
        
        return results


# Descrições das estratégias para documentação
STRATEGY_DESCRIPTIONS = {
    'trend_following': """
        Estratégia de seguimento de tendência usando EMAs, volume e RSI.
        Melhor para: Mercados em tendência forte
        Timeframe recomendado: 1h, 4h, diário
        Risk/Reward: Médio/Alto
    """,
    'mean_reversion': """
        Estratégia de reversão à média usando Bollinger Bands.
        Melhor para: Mercados laterais, alta volatilidade
        Timeframe recomendado: 15m, 1h
        Risk/Reward: Alto/Médio
    """,
    'volatility_breakout': """
        Estratégia de rompimento de faixas de consolidação.
        Melhor para: Início de tendências, após consolidações
        Timeframe recomendado: 1h, 4h
        Risk/Reward: Médio/Alto
    """,
    'macd_rsi_combo': """
        Combinação de MACD e RSI para sinais confirmados.
        Melhor para: Qualquer mercado, uso geral
        Timeframe recomendado: 1h, 4h
        Risk/Reward: Médio/Médio
    """,
    'bollinger_bands': """
        Estratégia simples de Bollinger Bands.
        Melhor para: Iniciantes, mercados laterais
        Timeframe recomendado: 1h
        Risk/Reward: Médio/Médio
    """,
    'momentum': """
        Estratégia baseada em momentum (Rate of Change).
        Melhor para: Tendências fortes, breakouts
        Timeframe recomendado: 4h, diário
        Risk/Reward: Alto/Alto
    """,
    'volume_profile': """
        Análise de volume usando On-Balance Volume.
        Melhor para: Confirmação de tendências
        Timeframe recomendado: 1h, 4h
        Risk/Reward: Médio/Médio
    """,
    'multi_timeframe': """
        Confirmação de sinais em múltiplos timeframes.
        Melhor para: Traders experientes, alta precisão
        Timeframe recomendado: 15m com análise em 1h e 4h
        Risk/Reward: Baixo/Alto
    """,
    'dynamic_position_sizing': """
        Gestão de risco com tamanho de posição dinâmico.
        Melhor para: Proteção de capital, gestão de risco
        Timeframe recomendado: Qualquer
        Risk/Reward: Baixo/Médio (foco em preservação)
    """
}


def get_recommended_strategy(market_condition: str) -> List[str]:
    """
    Recomenda estratégias baseado nas condições de mercado
    
    Args:
        market_condition: 'trending_up', 'trending_down', 'ranging', 'volatile'
        
    Returns:
        Lista de estratégias recomendadas
    """
    recommendations = {
        'trending_up': ['trend_following', 'momentum', 'multi_timeframe'],
        'trending_down': ['mean_reversion', 'dynamic_position_sizing'],
        'ranging': ['mean_reversion', 'bollinger_bands', 'volatility_breakout'],
        'volatile': ['volatility_breakout', 'dynamic_position_sizing', 'bollinger_bands']
    }
    
    return recommendations.get(market_condition.lower(), ['macd_rsi_combo'])
