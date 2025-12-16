"""
Walk-Forward Analysis (WFA) Module
===================================
Validação estatística rigorosa de estratégias de trading.

O Walk-Forward Analysis é uma técnica de validação que:
1. Divide os dados em múltiplas janelas temporais
2. Para cada janela: otimiza em dados "in-sample" e testa em dados "out-of-sample"
3. Agrega os resultados para avaliar robustez e evitar overfitting

DISCLAIMER: Esta ferramenta é para fins educacionais.
Past performance não garante resultados futuros.
Teste extensivamente com paper trading antes de usar capital real.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime, timedelta
from scipy import stats
from enum import Enum
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WFAMode(Enum):
    """Modos de Walk-Forward Analysis"""
    ANCHORED = "anchored"      # Janela inicial fixa, expande
    ROLLING = "rolling"        # Janela deslizante de tamanho fixo
    EXPANDING = "expanding"    # Janela que expande continuamente


@dataclass
class WFAWindow:
    """Representa uma janela de análise Walk-Forward"""
    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    optimal_params: Dict[str, Any] = field(default_factory=dict)
    train_metrics: Dict[str, float] = field(default_factory=dict)
    test_metrics: Dict[str, float] = field(default_factory=dict)
    trades: List[Dict] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)


@dataclass
class StatisticalMetrics:
    """Métricas estatísticas para avaliação de estratégia"""
    # Retorno
    total_return: float = 0.0
    annualized_return: float = 0.0
    monthly_returns: List[float] = field(default_factory=list)
    
    # Risco
    volatility: float = 0.0
    annualized_volatility: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    drawdown_duration_days: float = 0.0
    
    # Risk-Adjusted Returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    
    # Trade Statistics
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_trade_duration: float = 0.0
    
    # Statistical Significance
    t_statistic: float = 0.0
    p_value: float = 1.0
    confidence_interval_95: Tuple[float, float] = (0.0, 0.0)
    is_statistically_significant: bool = False


@dataclass
class WFAResult:
    """Resultado completo do Walk-Forward Analysis"""
    strategy_name: str
    symbol: str
    timeframe: str
    mode: WFAMode
    
    # Configuração
    total_windows: int = 0
    train_ratio: float = 0.7
    test_ratio: float = 0.3
    
    # Resultados por janela
    windows: List[WFAWindow] = field(default_factory=list)
    
    # Métricas agregadas Out-of-Sample
    oos_metrics: StatisticalMetrics = field(default_factory=StatisticalMetrics)
    
    # Métricas In-Sample (para comparação)
    is_metrics: StatisticalMetrics = field(default_factory=StatisticalMetrics)
    
    # Análise de Robustez
    parameter_stability: Dict[str, float] = field(default_factory=dict)
    degradation_ratio: float = 0.0  # IS vs OOS performance degradation
    consistency_score: float = 0.0  # % de janelas lucrativas OOS
    
    # Resumo
    passed_validation: bool = False
    validation_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class WalkForwardAnalyzer:
    """
    Analisador Walk-Forward para validação estatística de estratégias.
    
    Implementa três modos de análise:
    - ANCHORED: Treino começa sempre no início, teste desliza
    - ROLLING: Janelas fixas que deslizam no tempo
    - EXPANDING: Treino expande, teste desliza
    """
    
    def __init__(
        self,
        strategy_func: Callable,
        param_grid: Dict[str, List[Any]],
        optimize_metric: str = "sharpe_ratio",
        risk_free_rate: float = 0.02,
        min_trades_required: int = 30,
        significance_level: float = 0.05
    ):
        """
        Inicializa o analisador Walk-Forward.
        
        Args:
            strategy_func: Função que executa backtest com parâmetros dados
            param_grid: Grid de parâmetros para otimização
            optimize_metric: Métrica a otimizar (sharpe_ratio, sortino_ratio, etc)
            risk_free_rate: Taxa livre de risco anual
            min_trades_required: Mínimo de trades para validação estatística
            significance_level: Nível de significância para testes estatísticos
        """
        self.strategy_func = strategy_func
        self.param_grid = param_grid
        self.optimize_metric = optimize_metric
        self.risk_free_rate = risk_free_rate
        self.min_trades_required = min_trades_required
        self.significance_level = significance_level
        
    def run_analysis(
        self,
        data: pd.DataFrame,
        n_windows: int = 5,
        train_ratio: float = 0.7,
        mode: WFAMode = WFAMode.ROLLING,
        strategy_name: str = "Strategy",
        symbol: str = "BTCUSDT",
        timeframe: str = "1h"
    ) -> WFAResult:
        """
        Executa Walk-Forward Analysis completo.
        
        Args:
            data: DataFrame com dados OHLCV (index=datetime)
            n_windows: Número de janelas Walk-Forward
            train_ratio: Proporção de dados para treinamento
            mode: Modo de análise (ANCHORED, ROLLING, EXPANDING)
            strategy_name: Nome da estratégia
            symbol: Par de trading
            timeframe: Timeframe dos dados
            
        Returns:
            WFAResult com análise completa
        """
        logger.info(f"Iniciando Walk-Forward Analysis: {strategy_name}")
        logger.info(f"Dados: {len(data)} candles, {data.index[0]} a {data.index[-1]}")
        logger.info(f"Modo: {mode.value}, Janelas: {n_windows}, Train/Test: {train_ratio:.0%}/{1-train_ratio:.0%}")
        
        # Criar janelas
        windows = self._create_windows(data, n_windows, train_ratio, mode)
        
        result = WFAResult(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            mode=mode,
            total_windows=n_windows,
            train_ratio=train_ratio,
            test_ratio=1 - train_ratio
        )
        
        # Processar cada janela
        all_oos_returns = []
        all_is_returns = []
        all_oos_trades = []
        all_optimal_params = []
        
        for window in windows:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processando Janela {window.window_id + 1}/{n_windows}")
            logger.info(f"Train: {window.train_start} -> {window.train_end}")
            logger.info(f"Test:  {window.test_start} -> {window.test_end}")
            
            # Dados de treino e teste
            train_data = data[window.train_start:window.train_end].copy()
            test_data = data[window.test_start:window.test_end].copy()
            
            if len(train_data) < 50 or len(test_data) < 10:
                logger.warning(f"Janela {window.window_id + 1} com dados insuficientes, pulando...")
                continue
            
            # 1. Otimização In-Sample
            best_params, train_metrics, train_returns = self._optimize_in_sample(train_data)
            window.optimal_params = best_params
            window.train_metrics = train_metrics
            all_optimal_params.append(best_params)
            all_is_returns.extend(train_returns)
            
            logger.info(f"Melhores parâmetros: {best_params}")
            logger.info(f"Sharpe IS: {train_metrics.get('sharpe_ratio', 0):.2f}")
            
            # 2. Teste Out-of-Sample
            test_metrics, test_returns, trades = self._test_out_of_sample(test_data, best_params)
            window.test_metrics = test_metrics
            window.trades = trades
            all_oos_returns.extend(test_returns)
            all_oos_trades.extend(trades)
            
            logger.info(f"Sharpe OOS: {test_metrics.get('sharpe_ratio', 0):.2f}")
            logger.info(f"Trades OOS: {len(trades)}")
            
            result.windows.append(window)
        
        # 3. Calcular métricas agregadas
        result.oos_metrics = self._calculate_aggregate_metrics(all_oos_returns, all_oos_trades)
        result.is_metrics = self._calculate_aggregate_metrics(all_is_returns, [])
        
        # 4. Análise de robustez
        result.parameter_stability = self._analyze_parameter_stability(all_optimal_params)
        result.degradation_ratio = self._calculate_degradation_ratio(result.is_metrics, result.oos_metrics)
        result.consistency_score = self._calculate_consistency_score(result.windows)
        
        # 5. Validação estatística
        result.passed_validation, result.validation_score, result.recommendations = \
            self._validate_strategy(result)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"RESULTADO FINAL")
        logger.info(f"Validação: {'PASSOU ✓' if result.passed_validation else 'FALHOU ✗'}")
        logger.info(f"Score: {result.validation_score:.1f}/100")
        
        return result
    
    def _create_windows(
        self,
        data: pd.DataFrame,
        n_windows: int,
        train_ratio: float,
        mode: WFAMode
    ) -> List[WFAWindow]:
        """Cria janelas de análise baseado no modo selecionado."""
        windows = []
        total_len = len(data)
        
        if mode == WFAMode.ROLLING:
            # Janela deslizante de tamanho fixo
            window_size = total_len // n_windows
            train_size = int(window_size * train_ratio)
            test_size = window_size - train_size
            
            for i in range(n_windows):
                start_idx = i * test_size  # Overlap apenas no teste
                train_start_idx = start_idx
                train_end_idx = start_idx + train_size
                test_start_idx = train_end_idx
                test_end_idx = min(test_start_idx + test_size, total_len)
                
                if test_end_idx > total_len:
                    break
                    
                windows.append(WFAWindow(
                    window_id=i,
                    train_start=data.index[train_start_idx],
                    train_end=data.index[train_end_idx - 1],
                    test_start=data.index[test_start_idx],
                    test_end=data.index[test_end_idx - 1]
                ))
                
        elif mode == WFAMode.ANCHORED:
            # Treino começa sempre do início
            test_size = total_len // (n_windows + 1)
            
            for i in range(n_windows):
                train_end_idx = (i + 1) * test_size + int(total_len * train_ratio / n_windows)
                test_start_idx = train_end_idx
                test_end_idx = min(test_start_idx + test_size, total_len)
                
                if test_end_idx > total_len:
                    break
                    
                windows.append(WFAWindow(
                    window_id=i,
                    train_start=data.index[0],
                    train_end=data.index[train_end_idx - 1],
                    test_start=data.index[test_start_idx],
                    test_end=data.index[test_end_idx - 1]
                ))
                
        elif mode == WFAMode.EXPANDING:
            # Treino expande continuamente
            min_train_size = int(total_len * 0.3)
            remaining = total_len - min_train_size
            step = remaining // n_windows
            
            for i in range(n_windows):
                train_end_idx = min_train_size + i * step
                test_start_idx = train_end_idx
                test_end_idx = min(test_start_idx + step, total_len)
                
                if test_end_idx > total_len:
                    break
                    
                windows.append(WFAWindow(
                    window_id=i,
                    train_start=data.index[0],
                    train_end=data.index[train_end_idx - 1],
                    test_start=data.index[test_start_idx],
                    test_end=data.index[test_end_idx - 1]
                ))
        
        return windows
    
    def _optimize_in_sample(
        self,
        data: pd.DataFrame
    ) -> Tuple[Dict[str, Any], Dict[str, float], List[float]]:
        """
        Otimiza parâmetros usando dados in-sample.
        Retorna melhores parâmetros, métricas e retornos.
        """
        best_params = {}
        best_metric = float('-inf')
        best_metrics = {}
        best_returns = []
        
        # Grid search simples
        param_combinations = self._generate_param_combinations()
        logger.info(f"Testando {len(param_combinations)} combinações de parâmetros")
        
        for params in param_combinations:
            try:
                # Executa backtest com parâmetros
                result = self.strategy_func(data, params)
                
                if result is None:
                    continue
                    
                metrics = result.get('metrics', {})
                returns = result.get('returns', [])
                
                current_metric = metrics.get(self.optimize_metric, float('-inf'))
                
                logger.debug(f"Params {params} -> {self.optimize_metric}={current_metric:.2f}")
                
                if current_metric > best_metric:
                    best_metric = current_metric
                    best_params = params
                    best_metrics = metrics
                    best_returns = returns
                    
            except Exception as e:
                logger.warning(f"Erro ao otimizar com params {params}: {e}")
                continue
        
        logger.info(f"Melhor resultado: {self.optimize_metric}={best_metric:.2f}, params={best_params}")
        return best_params, best_metrics, best_returns
    
    def _test_out_of_sample(
        self,
        data: pd.DataFrame,
        params: Dict[str, Any]
    ) -> Tuple[Dict[str, float], List[float], List[Dict]]:
        """
        Testa estratégia com parâmetros fixos em dados out-of-sample.
        """
        try:
            result = self.strategy_func(data, params)
            
            if result is None:
                return {}, [], []
                
            metrics = result.get('metrics', {})
            returns = result.get('returns', [])
            trades = result.get('trades', [])
            
            return metrics, returns, trades
            
        except Exception as e:
            logger.warning(f"Erro no teste OOS: {e}")
            return {}, [], []
    
    def _generate_param_combinations(self) -> List[Dict[str, Any]]:
        """Gera todas as combinações de parâmetros do grid."""
        if not self.param_grid:
            return [{}]
            
        import itertools
        
        keys = self.param_grid.keys()
        values = self.param_grid.values()
        combinations = list(itertools.product(*values))
        
        return [dict(zip(keys, combo)) for combo in combinations]
    
    def _calculate_aggregate_metrics(
        self,
        returns: List[float],
        trades: List[Dict]
    ) -> StatisticalMetrics:
        """Calcula métricas estatísticas agregadas."""
        metrics = StatisticalMetrics()
        
        if not returns:
            return metrics
        
        returns_arr = np.array(returns)
        
        # Retorno
        metrics.total_return = (np.prod(1 + returns_arr) - 1) * 100
        periods_per_year = 252 * 24  # Assumindo dados horários
        metrics.annualized_return = ((1 + metrics.total_return/100) ** (periods_per_year / len(returns_arr)) - 1) * 100
        
        # Volatilidade
        metrics.volatility = np.std(returns_arr) * 100
        metrics.annualized_volatility = metrics.volatility * np.sqrt(periods_per_year)
        
        # Drawdown
        cumulative = np.cumprod(1 + returns_arr)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        metrics.max_drawdown = abs(np.min(drawdown)) * 100
        metrics.avg_drawdown = abs(np.mean(drawdown[drawdown < 0])) * 100 if np.any(drawdown < 0) else 0
        
        # Risk-Adjusted Returns
        rf_period = self.risk_free_rate / periods_per_year
        excess_returns = returns_arr - rf_period
        
        # Sharpe Ratio
        if metrics.volatility > 0:
            metrics.sharpe_ratio = (np.mean(excess_returns) / np.std(returns_arr)) * np.sqrt(periods_per_year)
        
        # Sortino Ratio (downside deviation)
        downside_returns = returns_arr[returns_arr < 0]
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                metrics.sortino_ratio = (np.mean(excess_returns) / downside_std) * np.sqrt(periods_per_year)
        
        # Calmar Ratio
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.annualized_return / metrics.max_drawdown
        
        # Omega Ratio
        threshold = rf_period
        gains = returns_arr[returns_arr > threshold] - threshold
        losses = threshold - returns_arr[returns_arr <= threshold]
        if np.sum(losses) > 0:
            metrics.omega_ratio = np.sum(gains) / np.sum(losses)
        
        # Trade Statistics
        if trades:
            metrics.total_trades = len(trades)
            pnls = [t.get('pnl', 0) for t in trades]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]
            
            metrics.win_rate = len(wins) / len(pnls) * 100 if pnls else 0
            metrics.avg_win = np.mean(wins) if wins else 0
            metrics.avg_loss = abs(np.mean(losses)) if losses else 0
            metrics.largest_win = max(pnls) if pnls else 0
            metrics.largest_loss = abs(min(pnls)) if pnls else 0
            
            if metrics.avg_loss > 0:
                metrics.profit_factor = (metrics.avg_win * len(wins)) / (metrics.avg_loss * len(losses)) if losses else float('inf')
        
        # Statistical Significance
        if len(returns_arr) >= 30:
            t_stat, p_val = stats.ttest_1samp(excess_returns, 0)
            metrics.t_statistic = t_stat
            metrics.p_value = p_val
            metrics.is_statistically_significant = p_val < self.significance_level
            
            # Intervalo de confiança 95%
            ci = stats.t.interval(0.95, len(excess_returns)-1, loc=np.mean(excess_returns), scale=stats.sem(excess_returns))
            metrics.confidence_interval_95 = (ci[0] * 100, ci[1] * 100)
        
        return metrics
    
    def _analyze_parameter_stability(
        self,
        params_list: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Analisa estabilidade dos parâmetros otimizados entre janelas.
        Coeficiente de variação baixo = parâmetros estáveis.
        """
        if not params_list or len(params_list) < 2:
            return {}
        
        stability = {}
        
        # Agrupar valores por parâmetro
        param_values = {}
        for params in params_list:
            for key, value in params.items():
                if isinstance(value, (int, float)):
                    if key not in param_values:
                        param_values[key] = []
                    param_values[key].append(value)
        
        # Calcular coeficiente de variação para cada parâmetro
        for key, values in param_values.items():
            if len(values) > 1:
                mean_val = np.mean(values)
                if mean_val != 0:
                    cv = np.std(values) / abs(mean_val) * 100
                    stability[key] = 100 - min(cv, 100)  # 100 = perfeitamente estável
                else:
                    stability[key] = 100.0
            else:
                stability[key] = 100.0
        
        return stability
    
    def _calculate_degradation_ratio(
        self,
        is_metrics: StatisticalMetrics,
        oos_metrics: StatisticalMetrics
    ) -> float:
        """
        Calcula razão de degradação entre IS e OOS.
        0% = sem degradação, 100% = degradação completa.
        """
        if is_metrics.sharpe_ratio <= 0:
            return 100.0
            
        if oos_metrics.sharpe_ratio <= 0:
            return 100.0
            
        degradation = (is_metrics.sharpe_ratio - oos_metrics.sharpe_ratio) / is_metrics.sharpe_ratio * 100
        return max(0, min(100, degradation))
    
    def _calculate_consistency_score(
        self,
        windows: List[WFAWindow]
    ) -> float:
        """
        Calcula percentual de janelas OOS lucrativas.
        """
        if not windows:
            return 0.0
            
        profitable_windows = sum(
            1 for w in windows 
            if w.test_metrics.get('total_return', 0) > 0
        )
        
        return profitable_windows / len(windows) * 100
    
    def _validate_strategy(
        self,
        result: WFAResult
    ) -> Tuple[bool, float, List[str]]:
        """
        Valida estratégia com base em múltiplos critérios.
        Retorna: (passou, score, recomendações)
        """
        score = 0
        max_score = 100
        recommendations = []
        
        # 1. Sharpe Ratio OOS (25 pontos)
        if result.oos_metrics.sharpe_ratio >= 2.0:
            score += 25
        elif result.oos_metrics.sharpe_ratio >= 1.5:
            score += 20
        elif result.oos_metrics.sharpe_ratio >= 1.0:
            score += 15
        elif result.oos_metrics.sharpe_ratio >= 0.5:
            score += 10
        else:
            recommendations.append("⚠️ Sharpe Ratio OOS baixo. Considere ajustar parâmetros ou estratégia.")
        
        # 2. Consistência entre janelas (20 pontos)
        if result.consistency_score >= 80:
            score += 20
        elif result.consistency_score >= 60:
            score += 15
        elif result.consistency_score >= 40:
            score += 10
        else:
            recommendations.append(f"⚠️ Consistência baixa ({result.consistency_score:.0f}%). Estratégia instável.")
        
        # 3. Degradação IS vs OOS (20 pontos)
        if result.degradation_ratio <= 20:
            score += 20
        elif result.degradation_ratio <= 40:
            score += 15
        elif result.degradation_ratio <= 60:
            score += 10
        else:
            recommendations.append(f"⚠️ Alta degradação ({result.degradation_ratio:.0f}%). Possível overfitting.")
        
        # 4. Significância estatística (15 pontos)
        if result.oos_metrics.is_statistically_significant:
            score += 15
        else:
            recommendations.append(f"⚠️ Retornos não são estatisticamente significativos (p={result.oos_metrics.p_value:.3f}).")
        
        # 5. Max Drawdown (10 pontos)
        if result.oos_metrics.max_drawdown <= 15:
            score += 10
        elif result.oos_metrics.max_drawdown <= 25:
            score += 7
        elif result.oos_metrics.max_drawdown <= 35:
            score += 4
        else:
            recommendations.append(f"⚠️ Drawdown alto ({result.oos_metrics.max_drawdown:.1f}%). Considere stop-loss mais apertado.")
        
        # 6. Número de trades (5 pontos)
        if result.oos_metrics.total_trades >= self.min_trades_required:
            score += 5
        else:
            recommendations.append(f"⚠️ Poucos trades ({result.oos_metrics.total_trades}). Aumentar período ou ajustar filtros.")
        
        # 7. Profit Factor (5 pontos)
        if result.oos_metrics.profit_factor >= 2.0:
            score += 5
        elif result.oos_metrics.profit_factor >= 1.5:
            score += 3
        elif result.oos_metrics.profit_factor >= 1.2:
            score += 1
        
        # Determinar se passou
        passed = score >= 60 and result.consistency_score >= 50 and result.degradation_ratio <= 50
        
        if passed:
            recommendations.insert(0, "✅ Estratégia APROVADA para paper trading estendido.")
        else:
            recommendations.insert(0, "❌ Estratégia REPROVADA. Revisar antes de usar.")
        
        return passed, score, recommendations


def generate_wfa_report(result: WFAResult) -> str:
    """Gera relatório detalhado em texto."""
    
    report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              WALK-FORWARD ANALYSIS REPORT                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Strategy: {result.strategy_name:<63} ║
║  Symbol: {result.symbol:<65} ║
║  Timeframe: {result.timeframe:<62} ║
║  Analysis Mode: {result.mode.value:<58} ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────────┐
│                        VALIDATION RESULT                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  Status: {'✅ PASSED' if result.passed_validation else '❌ FAILED':<65} │
│  Score: {result.validation_score:.1f}/100{' '*60} │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                    OUT-OF-SAMPLE METRICS (OOS)                               │
├──────────────────────────────────────────────────────────────────────────────┤
│  RETURNS                                                                     │
│  ├─ Total Return:      {result.oos_metrics.total_return:>10.2f}%                                      │
│  ├─ Annualized Return: {result.oos_metrics.annualized_return:>10.2f}%                                      │
│  └─ Volatility (Ann):  {result.oos_metrics.annualized_volatility:>10.2f}%                                      │
│                                                                              │
│  RISK-ADJUSTED                                                               │
│  ├─ Sharpe Ratio:      {result.oos_metrics.sharpe_ratio:>10.2f}                                        │
│  ├─ Sortino Ratio:     {result.oos_metrics.sortino_ratio:>10.2f}                                        │
│  ├─ Calmar Ratio:      {result.oos_metrics.calmar_ratio:>10.2f}                                        │
│  └─ Omega Ratio:       {result.oos_metrics.omega_ratio:>10.2f}                                        │
│                                                                              │
│  DRAWDOWN                                                                    │
│  ├─ Max Drawdown:      {result.oos_metrics.max_drawdown:>10.2f}%                                      │
│  └─ Avg Drawdown:      {result.oos_metrics.avg_drawdown:>10.2f}%                                      │
│                                                                              │
│  TRADE STATISTICS                                                            │
│  ├─ Total Trades:      {result.oos_metrics.total_trades:>10}                                        │
│  ├─ Win Rate:          {result.oos_metrics.win_rate:>10.1f}%                                      │
│  ├─ Profit Factor:     {result.oos_metrics.profit_factor:>10.2f}                                        │
│  ├─ Avg Win:           {result.oos_metrics.avg_win:>10.2f}%                                      │
│  └─ Avg Loss:          {result.oos_metrics.avg_loss:>10.2f}%                                      │
│                                                                              │
│  STATISTICAL SIGNIFICANCE                                                    │
│  ├─ t-Statistic:       {result.oos_metrics.t_statistic:>10.2f}                                        │
│  ├─ p-Value:           {result.oos_metrics.p_value:>10.4f}                                        │
│  ├─ 95% CI:            [{result.oos_metrics.confidence_interval_95[0]:>6.3f}%, {result.oos_metrics.confidence_interval_95[1]:>6.3f}%]                           │
│  └─ Significant:       {'Yes ✓' if result.oos_metrics.is_statistically_significant else 'No ✗':>10}                                        │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                      IN-SAMPLE METRICS (IS)                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│  ├─ Total Return:      {result.is_metrics.total_return:>10.2f}%                                      │
│  ├─ Sharpe Ratio:      {result.is_metrics.sharpe_ratio:>10.2f}                                        │
│  └─ Max Drawdown:      {result.is_metrics.max_drawdown:>10.2f}%                                      │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                      ROBUSTNESS ANALYSIS                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  ├─ Consistency Score: {result.consistency_score:>10.1f}% (% profitable windows)                  │
│  ├─ Degradation Ratio: {result.degradation_ratio:>10.1f}% (IS vs OOS performance loss)            │
│  └─ Parameter Stability:                                                     │
"""
    
    for param, stability in result.parameter_stability.items():
        report += f"│     └─ {param}: {stability:.1f}%                                                     │\n"
    
    report += """└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                      WINDOW-BY-WINDOW RESULTS                                │
├──────────────────────────────────────────────────────────────────────────────┤
"""
    
    for i, window in enumerate(result.windows):
        is_sharpe = window.train_metrics.get('sharpe_ratio', 0)
        oos_sharpe = window.test_metrics.get('sharpe_ratio', 0)
        oos_return = window.test_metrics.get('total_return', 0)
        
        report += f"│  Window {i+1}: IS Sharpe={is_sharpe:>5.2f} | OOS Sharpe={oos_sharpe:>5.2f} | OOS Return={oos_return:>6.2f}%     │\n"
    
    report += """└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                      RECOMMENDATIONS                                         │
├──────────────────────────────────────────────────────────────────────────────┤
"""
    
    for rec in result.recommendations:
        # Truncate long recommendations
        rec_truncated = rec[:70] if len(rec) > 70 else rec
        report += f"│  {rec_truncated:<72} │\n"
    
    report += """└──────────────────────────────────────────────────────────────────────────────┘

DISCLAIMER: Esta análise é para fins educacionais apenas.
Resultados passados não garantem performance futura.
Sempre use gerenciamento de risco adequado.

Report generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return report


def wfa_result_to_dict(result: WFAResult) -> Dict:
    """Converte WFAResult para dicionário serializável."""
    return {
        "strategy_name": result.strategy_name,
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "mode": result.mode.value,
        "total_windows": result.total_windows,
        "passed_validation": result.passed_validation,
        "validation_score": result.validation_score,
        "consistency_score": result.consistency_score,
        "degradation_ratio": result.degradation_ratio,
        "oos_metrics": {
            "total_return": result.oos_metrics.total_return,
            "annualized_return": result.oos_metrics.annualized_return,
            "sharpe_ratio": result.oos_metrics.sharpe_ratio,
            "sortino_ratio": result.oos_metrics.sortino_ratio,
            "calmar_ratio": result.oos_metrics.calmar_ratio,
            "max_drawdown": result.oos_metrics.max_drawdown,
            "total_trades": result.oos_metrics.total_trades,
            "win_rate": result.oos_metrics.win_rate,
            "profit_factor": result.oos_metrics.profit_factor,
            "t_statistic": result.oos_metrics.t_statistic,
            "p_value": result.oos_metrics.p_value,
            "is_statistically_significant": result.oos_metrics.is_statistically_significant
        },
        "is_metrics": {
            "total_return": result.is_metrics.total_return,
            "sharpe_ratio": result.is_metrics.sharpe_ratio,
            "max_drawdown": result.is_metrics.max_drawdown
        },
        "parameter_stability": result.parameter_stability,
        "windows": [
            {
                "window_id": w.window_id,
                "train_period": f"{w.train_start} to {w.train_end}",
                "test_period": f"{w.test_start} to {w.test_end}",
                "optimal_params": w.optimal_params,
                "is_sharpe": w.train_metrics.get('sharpe_ratio', 0),
                "oos_sharpe": w.test_metrics.get('sharpe_ratio', 0),
                "oos_return": w.test_metrics.get('total_return', 0)
            }
            for w in result.windows
        ],
        "recommendations": result.recommendations
    }
