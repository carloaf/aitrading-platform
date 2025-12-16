"""
Monte Carlo Simulation Module for Trading Strategy Validation

This module implements stochastic simulation to assess risk and return
distributions of trading strategies through parameter variation.

Features:
- Random parameter variation within defined ranges
- 10,000+ simulation iterations
- Confidence intervals (5th, 50th, 95th percentiles)
- Risk metrics: VaR, CVaR, worst-case scenarios
- Distribution analysis: returns, drawdowns, Sharpe ratios
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Trading Configuration Constants
MAKER_FEE = 0.001  # 0.1% - Binance spot maker fee
TAKER_FEE = 0.001  # 0.1% - Binance spot taker fee
STOP_LOSS_PCT = 0.02  # 2% stop loss
TAKE_PROFIT_PCT = 0.04  # 4% take profit


@dataclass
class SimulationResult:
    """Container for a single simulation result"""
    iteration: int
    parameters: Dict
    final_balance: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    profit_factor: float
    avg_trade_return: float
    std_returns: float
    
    def to_dict(self) -> Dict:
        return {
            'iteration': self.iteration,
            'parameters': self.parameters,
            'final_balance': self.final_balance,
            'total_return': self.total_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'total_trades': self.total_trades,
            'profit_factor': self.profit_factor,
            'avg_trade_return': self.avg_trade_return,
            'std_returns': self.std_returns
        }


@dataclass
class MonteCarloReport:
    """Complete Monte Carlo simulation report"""
    strategy_name: str
    total_iterations: int
    successful_runs: int
    failed_runs: int
    execution_time: float
    
    # Return statistics
    mean_return: float
    median_return: float
    std_return: float
    percentile_5: float
    percentile_95: float
    
    # Risk metrics
    probability_of_profit: float
    probability_of_loss: float
    value_at_risk_95: float  # VaR at 95% confidence
    conditional_var_95: float  # CVaR (Expected Shortfall)
    
    # Sharpe statistics
    mean_sharpe: float
    median_sharpe: float
    
    # Drawdown statistics
    mean_max_dd: float
    worst_drawdown: float
    percentile_dd_95: float
    
    # Trade statistics
    mean_trades: float
    mean_win_rate: float
    
    # Scenarios
    best_case: SimulationResult
    worst_case: SimulationResult
    median_case: SimulationResult
    
    # All results for distribution plotting
    all_results: List[SimulationResult]
    
    def to_dict(self) -> Dict:
        return {
            'strategy_name': self.strategy_name,
            'total_iterations': self.total_iterations,
            'successful_runs': self.successful_runs,
            'failed_runs': self.failed_runs,
            'execution_time': self.execution_time,
            'return_statistics': {
                'mean': self.mean_return,
                'median': self.median_return,
                'std': self.std_return,
                'percentile_5': self.percentile_5,
                'percentile_95': self.percentile_95
            },
            'risk_metrics': {
                'probability_of_profit': self.probability_of_profit,
                'probability_of_loss': self.probability_of_loss,
                'value_at_risk_95': self.value_at_risk_95,
                'conditional_var_95': self.conditional_var_95
            },
            'sharpe_statistics': {
                'mean': self.mean_sharpe,
                'median': self.median_sharpe
            },
            'drawdown_statistics': {
                'mean': self.mean_max_dd,
                'worst': self.worst_drawdown,
                'percentile_95': self.percentile_dd_95
            },
            'trade_statistics': {
                'mean_trades': self.mean_trades,
                'mean_win_rate': self.mean_win_rate
            },
            'scenarios': {
                'best_case': self.best_case.to_dict(),
                'worst_case': self.worst_case.to_dict(),
                'median_case': self.median_case.to_dict()
            },
            'distributions': {
                'returns': [r.total_return for r in self.all_results],
                'sharpe_ratios': [r.sharpe_ratio for r in self.all_results],
                'max_drawdowns': [r.max_drawdown for r in self.all_results],
                'win_rates': [r.win_rate for r in self.all_results]
            }
        }


class MonteCarloSimulator:
    """
    Monte Carlo Simulator for trading strategy validation
    
    Performs thousands of simulations with randomized parameters to assess
    the robustness and risk profile of trading strategies.
    """
    
    def __init__(self, 
                 initial_balance: float = 10000.0,
                 iterations: int = 10000,
                 random_seed: Optional[int] = None):
        """
        Initialize Monte Carlo Simulator
        
        Args:
            initial_balance: Starting capital for each simulation
            iterations: Number of Monte Carlo iterations
            random_seed: Seed for reproducibility (optional)
        """
        self.initial_balance = initial_balance
        self.iterations = iterations
        
        if random_seed:
            np.random.seed(random_seed)
        
        logger.info(f"MonteCarloSimulator initialized: {iterations} iterations, ${initial_balance} capital")
    
    def generate_parameter_set(self, 
                               param_ranges: Dict[str, Tuple[float, float]],
                               distribution: str = 'uniform') -> Dict[str, float]:
        """
        Generate random parameter values within specified ranges
        
        Args:
            param_ranges: Dict of parameter names and (min, max) tuples
            distribution: 'uniform' or 'normal'
        
        Returns:
            Dict of parameter names and random values
        """
        params = {}
        
        for param_name, (min_val, max_val) in param_ranges.items():
            if distribution == 'uniform':
                value = np.random.uniform(min_val, max_val)
            elif distribution == 'normal':
                # Use mean as midpoint, std as 1/6 of range (99.7% within range)
                mean = (min_val + max_val) / 2
                std = (max_val - min_val) / 6
                value = np.random.normal(mean, std)
                value = np.clip(value, min_val, max_val)  # Ensure within bounds
            else:
                raise ValueError(f"Unknown distribution: {distribution}")
            
            # Round integers
            if isinstance(min_val, int) and isinstance(max_val, int):
                value = int(round(value))
            
            params[param_name] = value
        
        return params
    
    def simulate_trades(self,
                       historical_data: pd.DataFrame,
                       strategy_func: callable,
                       parameters: Dict) -> SimulationResult:
        """
        Run a single simulation with given parameters
        
        Args:
            historical_data: DataFrame with OHLCV data
            strategy_func: Function that generates signals
            parameters: Strategy parameters for this simulation
        
        Returns:
            SimulationResult object
        """
        try:
            # Apply strategy with given parameters
            signals = strategy_func(historical_data.copy(), **parameters)
            
            # Simulate trading with LONG and SHORT support
            balance = self.initial_balance
            position = 0.0  # Positive = LONG, Negative = SHORT
            trades = []
            entry_price = 0.0
            entry_balance = 0.0  # Balance when position was opened
            position_type = None  # 'LONG' or 'SHORT'
            
            for i, row in signals.iterrows():
                signal = row.get('signal', 'HOLD')
                price = row['close']
                
                # Check Stop Loss / Take Profit for open positions
                if position != 0 and entry_price > 0:
                    if position_type == 'LONG':
                        pnl_pct_current = (price / entry_price - 1) * 100
                        
                        # Stop Loss hit
                        if pnl_pct_current <= -STOP_LOSS_PCT * 100:
                            exit_value = position * price * (1 - TAKER_FEE)
                            pnl = exit_value - entry_balance
                            pnl_pct = (exit_value / entry_balance - 1) * 100
                            
                            trades.append({
                                'entry': entry_price,
                                'exit': price,
                                'pnl': pnl,
                                'pnl_pct': pnl_pct,
                                'exit_reason': 'STOP_LOSS'
                            })
                            
                            balance = exit_value
                            position = 0.0
                            position_type = None
                            continue
                        
                        # Take Profit hit
                        elif pnl_pct_current >= TAKE_PROFIT_PCT * 100:
                            exit_value = position * price * (1 - TAKER_FEE)
                            pnl = exit_value - entry_balance
                            pnl_pct = (exit_value / entry_balance - 1) * 100
                            
                            trades.append({
                                'entry': entry_price,
                                'exit': price,
                                'pnl': pnl,
                                'pnl_pct': pnl_pct,
                                'exit_reason': 'TAKE_PROFIT'
                            })
                            
                            balance = exit_value
                            position = 0.0
                            position_type = None
                            continue
                    
                    elif position_type == 'SHORT':
                        pnl_pct_current = (entry_price / price - 1) * 100
                        
                        # Stop Loss hit
                        if pnl_pct_current <= -STOP_LOSS_PCT * 100:
                            cost = abs(position) * price * (1 + TAKER_FEE)
                            pnl = entry_balance - cost
                            pnl_pct = (pnl / entry_balance) * 100
                            
                            trades.append({
                                'entry': entry_price,
                                'exit': price,
                                'pnl': pnl,
                                'pnl_pct': pnl_pct,
                                'exit_reason': 'STOP_LOSS'
                            })
                            
                            balance = entry_balance + pnl
                            position = 0.0
                            position_type = None
                            continue
                        
                        # Take Profit hit
                        elif pnl_pct_current >= TAKE_PROFIT_PCT * 100:
                            cost = abs(position) * price * (1 + TAKER_FEE)
                            pnl = entry_balance - cost
                            pnl_pct = (pnl / entry_balance) * 100
                            
                            trades.append({
                                'entry': entry_price,
                                'exit': price,
                                'pnl': pnl,
                                'pnl_pct': pnl_pct,
                                'exit_reason': 'TAKE_PROFIT'
                            })
                            
                            balance = entry_balance + pnl
                            position = 0.0
                            position_type = None
                            continue
                
                # Process trading signals
                if signal == 'BUY':
                    if position == 0:
                        # Open LONG position
                        entry_balance = balance
                        position = balance / price * (1 - MAKER_FEE)
                        entry_price = price
                        position_type = 'LONG'
                        balance = 0
                        
                    elif position_type == 'SHORT':
                        # Close SHORT position
                        cost = abs(position) * price * (1 + TAKER_FEE)
                        pnl = entry_balance - cost
                        pnl_pct = (pnl / entry_balance) * 100 if entry_balance > 0 else 0
                        
                        trades.append({
                            'entry': entry_price,
                            'exit': price,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'exit_reason': 'SIGNAL'
                        })
                        
                        # Open LONG position with remaining balance
                        balance = entry_balance + pnl
                        if balance > 0:
                            entry_balance = balance
                            position = balance / price * (1 - MAKER_FEE)
                            entry_price = price
                            position_type = 'LONG'
                            balance = 0
                        else:
                            position = 0.0
                            position_type = None
                    
                elif signal == 'SELL':
                    if position == 0:
                        # Open SHORT position
                        entry_balance = balance
                        position = -(balance / price * (1 - MAKER_FEE))
                        entry_price = price
                        position_type = 'SHORT'
                        # balance stays the same for SHORT
                        
                    elif position_type == 'LONG':
                        # Close LONG position
                        exit_value = position * price * (1 - TAKER_FEE)
                        pnl = exit_value - entry_balance
                        pnl_pct = (exit_value / entry_balance - 1) * 100 if entry_balance > 0 else 0
                        
                        trades.append({
                            'entry': entry_price,
                            'exit': price,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'exit_reason': 'SIGNAL'
                        })
                        
                        # Open SHORT position with remaining balance
                        balance = exit_value
                        if balance > 0:
                            entry_balance = balance
                            position = -(balance / price * (1 - MAKER_FEE))
                            entry_price = price
                            position_type = 'SHORT'
                        else:
                            position = 0.0
                            position_type = None
            
            # Close any open position at end
            if position != 0:
                final_price = signals.iloc[-1]['close']
                
                if position_type == 'LONG':
                    exit_value = position * final_price * (1 - TAKER_FEE)
                    pnl = exit_value - entry_balance
                    pnl_pct = (exit_value / entry_balance - 1) * 100 if entry_balance > 0 else 0
                    balance = exit_value
                    
                elif position_type == 'SHORT':
                    cost = abs(position) * final_price * (1 + TAKER_FEE)
                    pnl = entry_balance - cost
                    pnl_pct = (pnl / entry_balance) * 100 if entry_balance > 0 else 0
                    balance = entry_balance + pnl
                
                trades.append({
                    'entry': entry_price,
                    'exit': final_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'exit_reason': 'END_OF_DATA'
                })
            
            # Calculate metrics
            final_balance = balance if position == 0 else balance
            total_return = ((final_balance / self.initial_balance) - 1) * 100
            
            if len(trades) > 0:
                returns = [t['pnl_pct'] for t in trades]
                winning_trades = [t for t in trades if t['pnl'] > 0]
                losing_trades = [t for t in trades if t['pnl'] < 0]
                
                win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0
                avg_return = np.mean(returns) if returns else 0
                std_returns = np.std(returns) if len(returns) > 1 else 0
                
                # Sharpe Ratio (annualized, assuming 252 trading days)
                if std_returns > 0:
                    sharpe = (avg_return / std_returns) * np.sqrt(252)
                else:
                    sharpe = 0
                
                # Max Drawdown
                balance_curve = [self.initial_balance]
                running_balance = self.initial_balance
                for trade in trades:
                    running_balance += trade['pnl']
                    balance_curve.append(running_balance)
                
                peak = balance_curve[0]
                max_dd = 0
                for balance in balance_curve:
                    if balance > peak:
                        peak = balance
                    dd = ((balance - peak) / peak) * 100
                    if dd < max_dd:
                        max_dd = dd
                
                # Profit Factor
                total_profit = sum([t['pnl'] for t in winning_trades]) if winning_trades else 0
                total_loss = abs(sum([t['pnl'] for t in losing_trades])) if losing_trades else 1
                profit_factor = total_profit / total_loss if total_loss > 0 else 0
                
            else:
                win_rate = 0
                avg_return = 0
                std_returns = 0
                sharpe = 0
                max_dd = 0
                profit_factor = 0
            
            return SimulationResult(
                iteration=0,  # Will be set by caller
                parameters=parameters,
                final_balance=final_balance,
                total_return=total_return,
                sharpe_ratio=sharpe,
                max_drawdown=max_dd,
                win_rate=win_rate,
                total_trades=len(trades),
                profit_factor=profit_factor,
                avg_trade_return=avg_return,
                std_returns=std_returns
            )
            
        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            # Return failed result
            return SimulationResult(
                iteration=0,
                parameters=parameters,
                final_balance=0,
                total_return=-100,
                sharpe_ratio=-999,
                max_drawdown=-100,
                win_rate=0,
                total_trades=0,
                profit_factor=0,
                avg_trade_return=0,
                std_returns=0
            )
    
    def run_simulation(self,
                      strategy_name: str,
                      historical_data: pd.DataFrame,
                      strategy_func: callable,
                      param_ranges: Dict[str, Tuple[float, float]],
                      parallel: bool = True,
                      progress_callback: callable = None) -> MonteCarloReport:
        """
        Run full Monte Carlo simulation
        
        Args:
            strategy_name: Name of the strategy
            historical_data: Historical OHLCV data
            strategy_func: Strategy function to test
            param_ranges: Parameter ranges for variation
            parallel: Use multiprocessing (default True)
            progress_callback: Optional callback for progress updates (current, total)
        
        Returns:
            MonteCarloReport with complete analysis
        """
        logger.info(f"Starting Monte Carlo simulation: {strategy_name}")
        logger.info(f"Iterations: {self.iterations}, Parameters: {list(param_ranges.keys())}")
        
        start_time = datetime.now()
        results = []
        
        if parallel:
            # Parallel execution
            with ProcessPoolExecutor() as executor:
                futures = []
                for i in range(self.iterations):
                    params = self.generate_parameter_set(param_ranges)
                    future = executor.submit(
                        self.simulate_trades,
                        historical_data,
                        strategy_func,
                        params
                    )
                    futures.append((i, future))
                
                # Collect results with progress logging
                for idx, (i, future) in enumerate(futures):
                    result = future.result()
                    result.iteration = i
                    results.append(result)
                    
                    # Call progress callback frequently for real-time updates
                    if progress_callback:
                        progress_callback(idx + 1, self.iterations)
                    
                    if (idx + 1) % 1000 == 0:
                        logger.info(f"Progress: {idx + 1}/{self.iterations} simulations completed")
        else:
            # Sequential execution (for debugging)
            for i in range(self.iterations):
                params = self.generate_parameter_set(param_ranges)
                result = self.simulate_trades(historical_data, strategy_func, params)
                result.iteration = i
                results.append(result)
                
                # Call progress callback for real-time updates
                if progress_callback:
                    progress_callback(i + 1, self.iterations)
                
                if (i + 1) % 1000 == 0:
                    logger.info(f"Progress: {i + 1}/{self.iterations} simulations completed")
        
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Simulation completed in {execution_time:.2f} seconds")
        
        # Filter out failed runs
        valid_results = [r for r in results if r.sharpe_ratio > -900]
        failed_runs = len(results) - len(valid_results)
        
        if len(valid_results) == 0:
            raise ValueError("All simulations failed. Check strategy function and data.")
        
        # Calculate statistics
        returns = [r.total_return for r in valid_results]
        sharpes = [r.sharpe_ratio for r in valid_results]
        drawdowns = [r.max_drawdown for r in valid_results]
        win_rates = [r.win_rate for r in valid_results]
        trades_counts = [r.total_trades for r in valid_results]
        
        # Return statistics
        mean_return = np.mean(returns)
        median_return = np.median(returns)
        std_return = np.std(returns)
        percentile_5 = np.percentile(returns, 5)
        percentile_95 = np.percentile(returns, 95)
        
        # Risk metrics
        probability_of_profit = (np.sum(np.array(returns) > 0) / len(returns)) * 100
        probability_of_loss = 100 - probability_of_profit
        value_at_risk_95 = np.percentile(returns, 5)  # 95% VaR
        losses = [r for r in returns if r < 0]
        conditional_var_95 = np.mean(losses) if losses else 0  # CVaR
        
        # Sharpe statistics
        mean_sharpe = np.mean(sharpes)
        median_sharpe = np.median(sharpes)
        
        # Drawdown statistics
        mean_max_dd = np.mean(drawdowns)
        worst_drawdown = min(drawdowns)
        percentile_dd_95 = np.percentile(drawdowns, 95)
        
        # Trade statistics
        mean_trades = np.mean(trades_counts)
        mean_win_rate = np.mean(win_rates)
        
        # Scenarios
        best_case = max(valid_results, key=lambda r: r.total_return)
        worst_case = min(valid_results, key=lambda r: r.total_return)
        median_idx = np.argsort(returns)[len(returns) // 2]
        median_case = valid_results[median_idx]
        
        report = MonteCarloReport(
            strategy_name=strategy_name,
            total_iterations=self.iterations,
            successful_runs=len(valid_results),
            failed_runs=failed_runs,
            execution_time=execution_time,
            mean_return=mean_return,
            median_return=median_return,
            std_return=std_return,
            percentile_5=percentile_5,
            percentile_95=percentile_95,
            probability_of_profit=probability_of_profit,
            probability_of_loss=probability_of_loss,
            value_at_risk_95=value_at_risk_95,
            conditional_var_95=conditional_var_95,
            mean_sharpe=mean_sharpe,
            median_sharpe=median_sharpe,
            mean_max_dd=mean_max_dd,
            worst_drawdown=worst_drawdown,
            percentile_dd_95=percentile_dd_95,
            mean_trades=mean_trades,
            mean_win_rate=mean_win_rate,
            best_case=best_case,
            worst_case=worst_case,
            median_case=median_case,
            all_results=valid_results
        )
        
        logger.info(f"Monte Carlo Report Summary:")
        logger.info(f"  Mean Return: {mean_return:.2f}%")
        logger.info(f"  Probability of Profit: {probability_of_profit:.1f}%")
        logger.info(f"  95% VaR: {value_at_risk_95:.2f}%")
        logger.info(f"  Mean Sharpe: {mean_sharpe:.2f}")
        
        return report
    
    def save_report(self, report: MonteCarloReport, filepath: str):
        """Save Monte Carlo report to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        logger.info(f"Report saved to {filepath}")


# Example strategy function for testing
def example_momentum_strategy(df: pd.DataFrame, 
                             period: int = 20,
                             threshold: float = 2.0) -> pd.DataFrame:
    """
    Example momentum strategy for Monte Carlo testing
    
    Args:
        df: DataFrame with OHLCV data
        period: Lookback period for momentum
        threshold: Threshold for signal generation
    
    Returns:
        DataFrame with 'signal' column
    """
    df = df.copy()
    
    # Calculate momentum
    df['momentum'] = df['close'].pct_change(period) * 100
    
    # Generate signals
    df['signal'] = 'HOLD'
    df.loc[df['momentum'] > threshold, 'signal'] = 'BUY'
    df.loc[df['momentum'] < -threshold, 'signal'] = 'SELL'
    
    return df


if __name__ == "__main__":
    # Test with sample data
    print("Monte Carlo Simulator - Test Mode")
    print("=" * 60)
    
    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=1000, freq='1H')
    sample_data = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.random.randn(1000) * 100,
        'high': 50100 + np.random.randn(1000) * 100,
        'low': 49900 + np.random.randn(1000) * 100,
        'close': 50000 + np.random.randn(1000) * 100,
        'volume': np.random.uniform(100, 1000, 1000)
    })
    
    # Define parameter ranges
    param_ranges = {
        'period': (10, 30),      # Momentum period: 10-30 candles
        'threshold': (1.0, 3.0)  # Signal threshold: 1-3%
    }
    
    # Run simulation
    simulator = MonteCarloSimulator(
        initial_balance=10000,
        iterations=1000,  # Reduced for testing
        random_seed=42
    )
    
    report = simulator.run_simulation(
        strategy_name="Momentum_Test",
        historical_data=sample_data,
        strategy_func=example_momentum_strategy,
        param_ranges=param_ranges,
        parallel=False  # Sequential for testing
    )
    
    print("\n" + "=" * 60)
    print("SIMULATION RESULTS")
    print("=" * 60)
    print(f"Mean Return: {report.mean_return:.2f}%")
    print(f"Median Return: {report.median_return:.2f}%")
    print(f"95% Confidence Interval: [{report.percentile_5:.2f}%, {report.percentile_95:.2f}%]")
    print(f"Probability of Profit: {report.probability_of_profit:.1f}%")
    print(f"95% Value at Risk: {report.value_at_risk_95:.2f}%")
    print(f"Mean Sharpe Ratio: {report.mean_sharpe:.2f}")
    print(f"Worst Drawdown: {report.worst_drawdown:.2f}%")
    print("\nBest Case: +{:.2f}% return".format(report.best_case.total_return))
    print("Worst Case: {:.2f}% return".format(report.worst_case.total_return))
    print("=" * 60)
