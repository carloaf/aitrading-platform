"""
Classe base para todas as estratégias de trading
Define a interface comum que todas as estratégias devem implementar
"""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Representa um sinal de trading"""
    timestamp: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    price: float
    strength: float  # 0.0 to 1.0
    indicators: Dict[str, float]
    reason: str


class BaseStrategy(ABC):
    """
    Classe base abstrata para estratégias de trading
    
    Todas as estratégias devem herdar desta classe e implementar
    os métodos abstratos: calculate_indicators e generate_signals
    """
    
    def __init__(self, name: str, parameters: Dict[str, Any] = None):
        """
        Inicializa a estratégia
        
        Args:
            name: Nome da estratégia
            parameters: Dicionário com parâmetros configuráveis
        """
        self.name = name
        self.parameters = parameters or {}
        self.signals = []
        self.performance = {}
        
    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula os indicadores técnicos necessários para a estratégia
        
        Args:
            df: DataFrame com dados OHLCV
            
        Returns:
            DataFrame com indicadores adicionados
        """
        pass
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de compra/venda baseados nos indicadores
        
        Args:
            df: DataFrame com dados OHLCV e indicadores
            
        Returns:
            DataFrame com coluna 'signal' adicionada (1=BUY, -1=SELL, 0=HOLD)
        """
        pass
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Valida se o DataFrame contém as colunas necessárias
        
        Args:
            df: DataFrame para validar
            
        Returns:
            True se válido, False caso contrário
        """
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"Coluna necessária '{col}' não encontrada no DataFrame")
                return False
        
        if df.empty or len(df) < 50:
            logger.error(f"DataFrame com dados insuficientes: {len(df)} linhas")
            return False
            
        return True
    
    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Executa a estratégia completa: validação -> indicadores -> sinais
        
        Args:
            df: DataFrame com dados OHLCV
            
        Returns:
            DataFrame com indicadores e sinais
        """
        try:
            # Validar dados
            if not self.validate_data(df):
                raise ValueError("Dados inválidos para estratégia")
            
            # Criar cópia para não modificar original
            df_strategy = df.copy()
            
            # Calcular indicadores
            logger.info(f"{self.name}: Calculando indicadores...")
            df_strategy = self.calculate_indicators(df_strategy)
            
            # Gerar sinais
            logger.info(f"{self.name}: Gerando sinais de trading...")
            df_strategy = self.generate_signals(df_strategy)
            
            # Limpar NaN
            df_strategy = df_strategy.bfill().ffill()
            
            logger.info(f"{self.name}: Estratégia executada com sucesso")
            return df_strategy
            
        except Exception as e:
            logger.error(f"{self.name}: Erro ao executar estratégia - {e}")
            raise
    
    def get_entry_conditions(self) -> List[str]:
        """
        Retorna as condições de entrada em formato legível
        
        Returns:
            Lista de strings descrevendo condições de entrada
        """
        return []
    
    def get_exit_conditions(self) -> List[str]:
        """
        Retorna as condições de saída em formato legível
        
        Returns:
            Lista de strings descrevendo condições de saída
        """
        return []
    
    def optimize_parameters(
        self, 
        df: pd.DataFrame, 
        param_ranges: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """
        Otimiza os parâmetros da estratégia usando grid search
        
        Args:
            df: DataFrame com dados históricos
            param_ranges: Dicionário com ranges de parâmetros para testar
            
        Returns:
            Melhores parâmetros encontrados
        """
        from itertools import product
        
        best_params = {}
        best_sharpe = -999
        
        # Gerar todas as combinações de parâmetros
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        
        for values in product(*param_values):
            # Criar dicionário de parâmetros
            test_params = dict(zip(param_names, values))
            
            # Testar estratégia com esses parâmetros
            self.parameters = test_params
            
            try:
                df_result = self.run(df)
                sharpe = self.calculate_sharpe_ratio(df_result)
                
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = test_params.copy()
                    
            except Exception as e:
                logger.warning(f"Erro ao testar parâmetros {test_params}: {e}")
                continue
        
        logger.info(f"Melhores parâmetros encontrados: {best_params} (Sharpe: {best_sharpe:.2f})")
        return best_params
    
    def calculate_sharpe_ratio(self, df: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
        """
        Calcula o Sharpe Ratio da estratégia
        
        Args:
            df: DataFrame com coluna 'signal' e 'Close'
            risk_free_rate: Taxa livre de risco anual
            
        Returns:
            Sharpe Ratio
        """
        if 'signal' not in df.columns:
            return 0.0
        
        # Calcular retornos
        df['returns'] = df['Close'].pct_change()
        df['strategy_returns'] = df['returns'] * df['signal'].shift(1)
        
        # Remover NaN
        strategy_returns = df['strategy_returns'].dropna()
        
        if len(strategy_returns) == 0:
            return 0.0
        
        # Calcular Sharpe
        excess_returns = strategy_returns - risk_free_rate / 252  # Daily risk-free rate
        sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0
        
        return sharpe if np.isfinite(sharpe) else 0.0
    
    def __str__(self) -> str:
        return f"{self.name} - Parameters: {self.parameters}"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', params={self.parameters})>"
