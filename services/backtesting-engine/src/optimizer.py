"""
Optimizer Module - Grid Search para Estratégias de Trading

Este módulo implementa otimização de parâmetros usando Grid Search
com validação Walk-Forward e métricas avançadas.

Author: CryptoDev Assistant
Date: 2025-12-09
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class OptimizationResult:
    """Resultado de uma otimização"""
    strategy_name: str
    parameters: Dict[str, Any]
    in_sample_return: float
    out_sample_return: float
    in_sample_sharpe: float
    out_sample_sharpe: float
    in_sample_trades: int
    out_sample_trades: int
    in_sample_win_rate: float
    out_sample_win_rate: float
    max_drawdown: float
    profit_factor: float
    robustness_score: float  # out_sample / in_sample ratio
    rank_score: float  # Score combinado para ranking
    
    def to_dict(self):
        return asdict(self)


class ParameterOptimizer:
    """
    Otimizador de parâmetros usando Grid Search com Walk-Forward Analysis
    """
    
    def __init__(self, 
                 strategy_class,
                 data_provider,
                 initial_capital: float = 10000.0,
                 commission: float = 0.001,
                 n_splits: int = 5,
                 train_ratio: float = 0.7):
        """
        Args:
            strategy_class: Classe da estratégia a otimizar
            data_provider: Provedor de dados de mercado
            initial_capital: Capital inicial
            commission: Taxa de comissão
            n_splits: Número de splits para walk-forward
            train_ratio: Proporção de dados para treino
        """
        self.strategy_class = strategy_class
        self.data_provider = data_provider
        self.initial_capital = initial_capital
        self.commission = commission
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        
    def generate_parameter_grid(self, param_ranges: Dict[str, List]) -> List[Dict]:
        """
        Gera grid de parâmetros a partir de ranges
        
        Args:
            param_ranges: Dict com ranges de valores para cada parâmetro
            
        Returns:
            Lista de dicionários com combinações de parâmetros
        """
        keys = param_ranges.keys()
        values = param_ranges.values()
        
        combinations = list(product(*values))
        
        return [dict(zip(keys, combo)) for combo in combinations]
    
    def split_data_walkforward(self, data: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Divide dados para walk-forward analysis
        
        Returns:
            Lista de tuplas (train, test)
        """
        total_len = len(data)
        train_size = int(total_len * self.train_ratio / self.n_splits)
        test_size = int(total_len * (1 - self.train_ratio) / self.n_splits)
        
        splits = []
        
        for i in range(self.n_splits):
            train_start = i * (train_size + test_size)
            train_end = train_start + train_size
            test_end = min(train_end + test_size, total_len)
            
            if test_end > total_len:
                break
                
            train = data.iloc[train_start:train_end]
            test = data.iloc[train_end:test_end]
            
            splits.append((train, test))
        
        return splits
    
    def calculate_metrics(self, trades: List[Dict], initial_capital: float) -> Dict:
        """Calcula métricas de performance"""
        if not trades:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'total_trades': 0
            }
        
        returns = [t['pnl'] / initial_capital for t in trades]
        
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        total_profit = sum([t['pnl'] for t in winning_trades])
        total_loss = abs(sum([t['pnl'] for t in losing_trades]))
        
        return {
            'total_return': (sum(returns) * 100),
            'sharpe_ratio': self._calculate_sharpe(returns),
            'max_drawdown': self._calculate_max_drawdown(trades, initial_capital),
            'win_rate': (len(winning_trades) / len(trades) * 100) if trades else 0,
            'profit_factor': (total_profit / total_loss) if total_loss > 0 else 0,
            'total_trades': len(trades)
        }
    
    def _calculate_sharpe(self, returns: List[float]) -> float:
        """Calcula Sharpe Ratio"""
        if len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        if returns_array.std() == 0:
            return 0.0
        
        # Assumindo 252 dias de trading por ano
        return (returns_array.mean() / returns_array.std()) * np.sqrt(252)
    
    def _calculate_max_drawdown(self, trades: List[Dict], initial_capital: float) -> float:
        """Calcula Maximum Drawdown"""
        if not trades:
            return 0.0
        
        equity = initial_capital
        peak = initial_capital
        max_dd = 0.0
        
        for trade in trades:
            equity += trade['pnl']
            if equity > peak:
                peak = equity
            
            drawdown = ((peak - equity) / peak) * 100
            max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def backtest_single(self, 
                       data: pd.DataFrame, 
                       parameters: Dict) -> Tuple[List[Dict], Dict]:
        """
        Executa backtest com parâmetros específicos
        
        Returns:
            (trades, metrics)
        """
        try:
            # Criar instância da estratégia com parâmetros
            strategy = self.strategy_class(parameters=parameters)
            
            # Executar estratégia (calcula indicadores e gera sinais)
            signals = strategy.run(data.copy())
            
            # Simular trades
            trades = self._simulate_trades(signals)
            
            # Calcular métricas
            metrics = self.calculate_metrics(trades, self.initial_capital)
            
            return trades, metrics
            
        except Exception as e:
            logger.error(f"Erro no backtest com parâmetros {parameters}: {e}")
            return [], {
                'total_return': -999,
                'sharpe_ratio': -999,
                'max_drawdown': 100,
                'win_rate': 0,
                'profit_factor': 0,
                'total_trades': 0
            }
    
    def _simulate_trades(self, signals: pd.DataFrame) -> List[Dict]:
        """Simula trades baseado em sinais"""
        trades = []
        position = None
        
        for i in range(len(signals)):
            row = signals.iloc[i]
            
            # Compra
            if row.get('signal') == 1 and position is None:
                position = {
                    'entry_date': row.name if hasattr(row, 'name') else i,
                    'entry_price': row['Close'],
                    'quantity': self.initial_capital / row['Close']
                }
            
            # Venda
            elif row.get('signal') == -1 and position is not None:
                exit_price = row['Close']
                pnl = (exit_price - position['entry_price']) * position['quantity']
                pnl -= (position['entry_price'] * position['quantity'] * self.commission)  # Comissão entrada
                pnl -= (exit_price * position['quantity'] * self.commission)  # Comissão saída
                
                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': row.name if hasattr(row, 'name') else i,
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'quantity': position['quantity'],
                    'pnl': pnl,
                    'return_pct': (pnl / self.initial_capital) * 100
                })
                
                position = None
        
        return trades
    
    def optimize_grid_search(self, 
                            symbol: str,
                            start_date: str,
                            end_date: str,
                            param_ranges: Dict[str, List],
                            max_workers: int = 4) -> List[OptimizationResult]:
        """
        Otimização usando Grid Search com Walk-Forward
        
        Args:
            symbol: Símbolo a testar
            start_date: Data inicial
            end_date: Data final
            param_ranges: Ranges de parâmetros
            max_workers: Número de workers paralelos
            
        Returns:
            Lista de OptimizationResult ordenada por rank_score
        """
        logger.info(f"🚀 Iniciando otimização Grid Search para {symbol}")
        logger.info(f"Período: {start_date} até {end_date}")
        
        # Carregar dados
        data = self.data_provider(symbol, start_date, end_date)
        
        if data is None or len(data) < 100:
            logger.error("Dados insuficientes para otimização")
            return []
        
        logger.info(f"Dados carregados: {len(data)} candles")
        
        # Gerar grid de parâmetros
        param_grid = self.generate_parameter_grid(param_ranges)
        logger.info(f"Grid de parâmetros: {len(param_grid)} combinações")
        
        # Dividir dados para walk-forward
        splits = self.split_data_walkforward(data)
        logger.info(f"Walk-Forward: {len(splits)} splits")
        
        results = []
        
        # Testar cada combinação de parâmetros
        for idx, params in enumerate(param_grid):
            logger.info(f"Testando combinação {idx+1}/{len(param_grid)}: {params}")
            
            in_sample_metrics_list = []
            out_sample_metrics_list = []
            
            # Walk-Forward Analysis
            for split_idx, (train_data, test_data) in enumerate(splits):
                # Backtest in-sample (treino)
                _, in_metrics = self.backtest_single(train_data, params)
                in_sample_metrics_list.append(in_metrics)
                
                # Backtest out-of-sample (teste)
                _, out_metrics = self.backtest_single(test_data, params)
                out_sample_metrics_list.append(out_metrics)
            
            # Agregar métricas
            avg_in_return = np.mean([m['total_return'] for m in in_sample_metrics_list])
            avg_out_return = np.mean([m['total_return'] for m in out_sample_metrics_list])
            avg_in_sharpe = np.mean([m['sharpe_ratio'] for m in in_sample_metrics_list])
            avg_out_sharpe = np.mean([m['sharpe_ratio'] for m in out_sample_metrics_list])
            avg_in_trades = np.mean([m['total_trades'] for m in in_sample_metrics_list])
            avg_out_trades = np.mean([m['total_trades'] for m in out_sample_metrics_list])
            avg_in_winrate = np.mean([m['win_rate'] for m in in_sample_metrics_list])
            avg_out_winrate = np.mean([m['win_rate'] for m in out_sample_metrics_list])
            avg_max_dd = np.mean([m['max_drawdown'] for m in in_sample_metrics_list + out_sample_metrics_list])
            avg_pf = np.mean([m['profit_factor'] for m in out_sample_metrics_list])
            
            # Calcular robustness score (quanto menor a diferença in/out, melhor)
            if avg_in_return > 0:
                robustness = avg_out_return / avg_in_return
            else:
                robustness = 0
            
            # Calcular rank score combinado
            # Peso maior para out-of-sample (validação real)
            rank_score = (
                avg_out_return * 0.4 +
                avg_out_sharpe * 10 * 0.3 +
                robustness * 50 * 0.2 +
                avg_out_winrate * 0.1
            )
            
            result = OptimizationResult(
                strategy_name=self.strategy_class.__name__,
                parameters=params,
                in_sample_return=avg_in_return,
                out_sample_return=avg_out_return,
                in_sample_sharpe=avg_in_sharpe,
                out_sample_sharpe=avg_out_sharpe,
                in_sample_trades=int(avg_in_trades),
                out_sample_trades=int(avg_out_trades),
                in_sample_win_rate=avg_in_winrate,
                out_sample_win_rate=avg_out_winrate,
                max_drawdown=avg_max_dd,
                profit_factor=avg_pf,
                robustness_score=robustness,
                rank_score=rank_score
            )
            
            results.append(result)
            
            logger.info(f"  Resultado: Return Out={avg_out_return:.2f}% | Sharpe Out={avg_out_sharpe:.2f} | Robustness={robustness:.2f}")
        
        # Ordenar por rank_score
        results.sort(key=lambda x: x.rank_score, reverse=True)
        
        logger.info(f"✅ Otimização concluída! Melhor resultado:")
        logger.info(f"  Parâmetros: {results[0].parameters}")
        logger.info(f"  Return Out-Sample: {results[0].out_sample_return:.2f}%")
        logger.info(f"  Sharpe Out-Sample: {results[0].out_sample_sharpe:.2f}")
        logger.info(f"  Robustness: {results[0].robustness_score:.2f}")
        
        return results
    
    def save_results(self, results: List[OptimizationResult], filename: str):
        """Salva resultados em JSON"""
        with open(filename, 'w') as f:
            json.dump([r.to_dict() for r in results], f, indent=2)
        
        logger.info(f"Resultados salvos em {filename}")


def create_optimizer_report(results: List[OptimizationResult]) -> str:
    """Cria relatório formatado de otimização"""
    report = []
    report.append("=" * 80)
    report.append("RELATÓRIO DE OTIMIZAÇÃO DE PARÂMETROS")
    report.append("=" * 80)
    report.append("")
    
    report.append(f"Estratégia: {results[0].strategy_name}")
    report.append(f"Total de combinações testadas: {len(results)}")
    report.append("")
    
    report.append("TOP 10 MELHORES CONFIGURAÇÕES:")
    report.append("-" * 80)
    
    for i, result in enumerate(results[:10], 1):
        report.append(f"\n#{i} - Rank Score: {result.rank_score:.2f}")
        report.append(f"  Parâmetros: {result.parameters}")
        report.append(f"  Retorno Out-Sample: {result.out_sample_return:.2f}%")
        report.append(f"  Retorno In-Sample: {result.in_sample_return:.2f}%")
        report.append(f"  Sharpe Out-Sample: {result.out_sample_sharpe:.2f}")
        report.append(f"  Win Rate Out-Sample: {result.out_sample_win_rate:.2f}%")
        report.append(f"  Robustness Score: {result.robustness_score:.2f}")
        report.append(f"  Max Drawdown: {result.max_drawdown:.2f}%")
        report.append(f"  Profit Factor: {result.profit_factor:.2f}")
    
    report.append("\n" + "=" * 80)
    
    return "\n".join(report)
