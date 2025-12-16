"""
Módulo de métricas avançadas para análise de performance de estratégias
Inclui: Sortino Ratio, Calmar Ratio, Omega Ratio, Win Rate avançado, etc.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class AdvancedMetrics:
    """
    Calculadora de métricas avançadas para backtesting
    """
    
    @staticmethod
    def calculate_all_metrics(
        equity_curve: List[Dict[str, Any]],
        trades: List[Any],
        initial_capital: float,
        risk_free_rate: float = 0.02
    ) -> Dict[str, Any]:
        """
        Calcula todas as métricas disponíveis
        
        Args:
            equity_curve: Lista com evolução do equity
            trades: Lista de trades realizados
            initial_capital: Capital inicial
            risk_free_rate: Taxa livre de risco anual (padrão 2%)
            
        Returns:
            Dicionário com todas as métricas
        """
        if not equity_curve or len(equity_curve) < 2:
            return {"error": "Dados insuficientes para cálculo de métricas"}
        
        # Converter para DataFrame
        df_equity = pd.DataFrame(equity_curve)
        df_equity['returns'] = df_equity['equity'].pct_change()
        
        # Extrair informações dos trades
        completed_trades = [t for t in trades if hasattr(t, 'pnl') and t.pnl is not None]
        
        metrics = {
            # Métricas básicas
            'initial_capital': initial_capital,
            'final_equity': df_equity['equity'].iloc[-1],
            'total_return_pct': ((df_equity['equity'].iloc[-1] - initial_capital) / initial_capital) * 100,
            
            # Métricas de trades
            'total_trades': len(completed_trades),
            'winning_trades': len([t for t in completed_trades if t.pnl > 0]),
            'losing_trades': len([t for t in completed_trades if t.pnl <= 0]),
            
            # Métricas avançadas de retorno
            'sharpe_ratio': AdvancedMetrics.sharpe_ratio(df_equity['returns'], risk_free_rate),
            'sortino_ratio': AdvancedMetrics.sortino_ratio(df_equity['returns'], risk_free_rate),
            'calmar_ratio': AdvancedMetrics.calmar_ratio(df_equity['equity'], risk_free_rate),
            'omega_ratio': AdvancedMetrics.omega_ratio(df_equity['returns']),
            
            # Métricas de risco
            'max_drawdown_pct': AdvancedMetrics.max_drawdown(df_equity['equity']),
            'max_drawdown_duration': AdvancedMetrics.max_drawdown_duration(df_equity),
            'volatility_annual': AdvancedMetrics.annual_volatility(df_equity['returns']),
            'downside_deviation': AdvancedMetrics.downside_deviation(df_equity['returns']),
            
            # Métricas de trades
            'win_rate_pct': (len([t for t in completed_trades if t.pnl > 0]) / len(completed_trades) * 100) if completed_trades else 0,
            'profit_factor': AdvancedMetrics.profit_factor(completed_trades),
            'avg_win': AdvancedMetrics.average_win(completed_trades),
            'avg_loss': AdvancedMetrics.average_loss(completed_trades),
            'largest_win': AdvancedMetrics.largest_win(completed_trades),
            'largest_loss': AdvancedMetrics.largest_loss(completed_trades),
            'avg_trade_duration': AdvancedMetrics.average_trade_duration(completed_trades),
            
            # Métricas de consistência
            'expectancy': AdvancedMetrics.expectancy(completed_trades),
            'recovery_factor': AdvancedMetrics.recovery_factor(df_equity['equity'], completed_trades),
            'risk_reward_ratio': AdvancedMetrics.risk_reward_ratio(completed_trades),
        }
        
        return metrics
    
    @staticmethod
    def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calcula Sharpe Ratio
        Sharpe Ratio = (Retorno Médio - Taxa Livre de Risco) / Desvio Padrão
        """
        if returns.empty or returns.std() == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std()
        
        return float(sharpe) if np.isfinite(sharpe) else 0.0
    
    @staticmethod
    def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02, target_return: float = 0) -> float:
        """
        Calcula Sortino Ratio (similar ao Sharpe mas usa apenas downside deviation)
        Sortino Ratio = (Retorno Médio - Target) / Downside Deviation
        
        Melhor que Sharpe pois penaliza apenas volatilidade negativa
        """
        if returns.empty:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 252)
        downside_returns = excess_returns[excess_returns < target_return]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        
        sortino = np.sqrt(252) * excess_returns.mean() / downside_returns.std()
        
        return float(sortino) if np.isfinite(sortino) else 0.0
    
    @staticmethod
    def calmar_ratio(equity: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calcula Calmar Ratio
        Calmar Ratio = Retorno Anualizado / Maximum Drawdown
        
        Mede retorno ajustado pelo pior drawdown
        """
        if equity.empty or len(equity) < 2:
            return 0.0
        
        # Retorno anualizado
        total_return = (equity.iloc[-1] - equity.iloc[0]) / equity.iloc[0]
        periods_per_year = 252
        num_periods = len(equity)
        annual_return = (1 + total_return) ** (periods_per_year / num_periods) - 1
        
        # Maximum Drawdown
        max_dd = AdvancedMetrics.max_drawdown(equity)
        
        if max_dd == 0:
            return 999.99  # Evitar divisão por zero
        
        calmar = annual_return / (max_dd / 100)
        
        return float(calmar) if np.isfinite(calmar) else 0.0
    
    @staticmethod
    def omega_ratio(returns: pd.Series, threshold: float = 0.0) -> float:
        """
        Calcula Omega Ratio
        Omega = (Prob. ganho acima do threshold) / (Prob. perda abaixo do threshold)
        
        Mede probabilidade de ganhos vs perdas
        """
        if returns.empty:
            return 0.0
        
        gains = returns[returns > threshold].sum()
        losses = abs(returns[returns < threshold].sum())
        
        if losses == 0:
            return 999.99
        
        omega = gains / losses
        
        return float(omega) if np.isfinite(omega) else 0.0
    
    @staticmethod
    def max_drawdown(equity: pd.Series) -> float:
        """
        Calcula Maximum Drawdown (em percentual)
        """
        if equity.empty:
            return 0.0
        
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max * 100
        
        return float(abs(drawdown.min()))
    
    @staticmethod
    def max_drawdown_duration(df_equity: pd.DataFrame) -> int:
        """
        Calcula duração máxima do drawdown (em períodos)
        """
        if df_equity.empty or 'equity' not in df_equity.columns:
            return 0
        
        equity = df_equity['equity']
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        
        # Encontrar períodos em drawdown
        in_drawdown = drawdown < 0
        
        # Calcular duração de cada drawdown
        drawdown_periods = []
        current_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    drawdown_periods.append(current_duration)
                current_duration = 0
        
        return max(drawdown_periods) if drawdown_periods else 0
    
    @staticmethod
    def annual_volatility(returns: pd.Series) -> float:
        """
        Calcula volatilidade anualizada
        """
        if returns.empty:
            return 0.0
        
        return float(returns.std() * np.sqrt(252) * 100)  # Em percentual
    
    @staticmethod
    def downside_deviation(returns: pd.Series, target: float = 0.0) -> float:
        """
        Calcula desvio padrão apenas dos retornos negativos
        """
        downside_returns = returns[returns < target]
        
        if downside_returns.empty:
            return 0.0
        
        return float(downside_returns.std() * np.sqrt(252) * 100)
    
    @staticmethod
    def profit_factor(trades: List[Any]) -> float:
        """
        Profit Factor = Gross Profit / Gross Loss
        """
        if not trades:
            return 0.0
        
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        
        if gross_loss == 0:
            return 999.99
        
        return gross_profit / gross_loss
    
    @staticmethod
    def average_win(trades: List[Any]) -> float:
        """Retorno médio dos trades vencedores"""
        winning_trades = [t.pnl for t in trades if t.pnl > 0]
        return sum(winning_trades) / len(winning_trades) if winning_trades else 0.0
    
    @staticmethod
    def average_loss(trades: List[Any]) -> float:
        """Perda média dos trades perdedores"""
        losing_trades = [t.pnl for t in trades if t.pnl < 0]
        return sum(losing_trades) / len(losing_trades) if losing_trades else 0.0
    
    @staticmethod
    def largest_win(trades: List[Any]) -> float:
        """Maior ganho em um único trade"""
        winning_trades = [t.pnl for t in trades if t.pnl > 0]
        return max(winning_trades) if winning_trades else 0.0
    
    @staticmethod
    def largest_loss(trades: List[Any]) -> float:
        """Maior perda em um único trade"""
        losing_trades = [t.pnl for t in trades if t.pnl < 0]
        return min(losing_trades) if losing_trades else 0.0
    
    @staticmethod
    def average_trade_duration(trades: List[Any]) -> float:
        """
        Duração média dos trades (em dias)
        """
        if not trades:
            return 0.0
        
        durations = []
        for trade in trades:
            if trade.exit_date:
                try:
                    entry = pd.to_datetime(trade.entry_date)
                    exit_dt = pd.to_datetime(trade.exit_date)
                    duration = (exit_dt - entry).days
                    durations.append(duration)
                except:
                    continue
        
        return sum(durations) / len(durations) if durations else 0.0
    
    @staticmethod
    def expectancy(trades: List[Any]) -> float:
        """
        Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        
        Valor esperado por trade
        """
        if not trades:
            return 0.0
        
        winning_trades = [t.pnl for t in trades if t.pnl > 0]
        losing_trades = [t.pnl for t in trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / len(trades)
        loss_rate = len(losing_trades) / len(trades)
        
        avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(losing_trades) / len(losing_trades)) if losing_trades else 0
        
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
        
        return float(expectancy)
    
    @staticmethod
    def recovery_factor(equity: pd.Series, trades: List[Any]) -> float:
        """
        Recovery Factor = Net Profit / Maximum Drawdown
        
        Mede capacidade de recuperação de perdas
        """
        if equity.empty or not trades:
            return 0.0
        
        net_profit = equity.iloc[-1] - equity.iloc[0]
        max_dd_value = equity.iloc[0] * (AdvancedMetrics.max_drawdown(equity) / 100)
        
        if max_dd_value == 0:
            return 999.99
        
        return net_profit / max_dd_value
    
    @staticmethod
    def risk_reward_ratio(trades: List[Any]) -> float:
        """
        Risk/Reward Ratio = Average Win / Average Loss
        """
        avg_win = AdvancedMetrics.average_win(trades)
        avg_loss = abs(AdvancedMetrics.average_loss(trades))
        
        if avg_loss == 0:
            return 999.99
        
        return avg_win / avg_loss


def format_metrics_report(metrics: Dict[str, Any]) -> str:
    """
    Formata métricas em relatório legível
    
    Args:
        metrics: Dicionário com métricas
        
    Returns:
        String formatada com relatório
    """
    report = """
╔══════════════════════════════════════════════════════════════╗
║         RELATÓRIO DE PERFORMANCE - BACKTESTING               ║
╚══════════════════════════════════════════════════════════════╝

📊 MÉTRICAS DE RETORNO:
   • Retorno Total: {total_return_pct:.2f}%
   • Capital Inicial: ${initial_capital:,.2f}
   • Capital Final: ${final_equity:,.2f}
   
📈 MÉTRICAS AJUSTADAS POR RISCO:
   • Sharpe Ratio: {sharpe_ratio:.3f}
   • Sortino Ratio: {sortino_ratio:.3f}
   • Calmar Ratio: {calmar_ratio:.3f}
   • Omega Ratio: {omega_ratio:.3f}

⚠️  MÉTRICAS DE RISCO:
   • Maximum Drawdown: {max_drawdown_pct:.2f}%
   • Duração Max DD: {max_drawdown_duration} períodos
   • Volatilidade Anual: {volatility_annual:.2f}%
   • Downside Deviation: {downside_deviation:.2f}%

💼 MÉTRICAS DE TRADING:
   • Total de Trades: {total_trades}
   • Win Rate: {win_rate_pct:.2f}%
   • Profit Factor: {profit_factor:.2f}
   • Expectancy: ${expectancy:.2f}
   • Risk/Reward Ratio: {risk_reward_ratio:.2f}
   
💰 ANÁLISE DE TRADES:
   • Ganho Médio: ${avg_win:.2f}
   • Perda Média: ${avg_loss:.2f}
   • Maior Ganho: ${largest_win:.2f}
   • Maior Perda: ${largest_loss:.2f}
   • Duração Média: {avg_trade_duration:.1f} dias
   
""".format(**metrics)
    
    return report
