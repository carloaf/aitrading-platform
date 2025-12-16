#!/usr/bin/env python3
"""
Análise Comparativa de Resultados Monte Carlo
Analista Sênior de Dados e Investidor Experiente
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import sys

@dataclass
class StrategyResult:
    """Resultado de uma estratégia"""
    name: str
    iterations: int
    successful_runs: int
    
    # Retorno
    mean_return: float
    median_return: float
    std_return: float
    min_return: float
    max_return: float
    
    # Risco
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    
    # Performance
    win_rate: float
    profit_factor: float
    probability_of_profit: float
    
    # Intervalos de confiança
    ci_lower: float
    ci_upper: float
    
    # Parâmetros ótimos
    best_params: Dict

def load_results(results_dir: str) -> Dict[str, StrategyResult]:
    """Carrega todos os resultados das simulações"""
    results = {}
    
    results_path = Path(results_dir)
    for json_file in results_path.glob("monte_carlo_*.json"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            strategy_name = data.get('strategy_name', 'unknown')
            
            # Extrair estatísticas
            return_stats = data.get('return_statistics', {})
            risk_metrics = data.get('risk_metrics', {})
            sharpe_stats = data.get('sharpe_statistics', {})
            confidence_intervals = data.get('confidence_intervals', {})
            best_params = data.get('best_params', {})
            
            result = StrategyResult(
                name=strategy_name,
                iterations=data.get('total_iterations', 0),
                successful_runs=data.get('successful_runs', 0),
                
                # Retorno
                mean_return=return_stats.get('mean', 0),
                median_return=return_stats.get('median', 0),
                std_return=return_stats.get('std', 0),
                min_return=return_stats.get('min', 0),
                max_return=return_stats.get('max', 0),
                
                # Risco
                sharpe_ratio=sharpe_stats.get('mean', 0),
                sortino_ratio=risk_metrics.get('sortino_ratio', 0),
                max_drawdown=risk_metrics.get('max_drawdown', 0),
                var_95=risk_metrics.get('var_95', 0),
                cvar_95=risk_metrics.get('cvar_95', 0),
                
                # Performance
                win_rate=risk_metrics.get('win_rate', 0),
                profit_factor=risk_metrics.get('profit_factor', 0),
                probability_of_profit=risk_metrics.get('probability_of_profit', 0),
                
                # Intervalos de confiança
                ci_lower=confidence_intervals.get('95%', [0, 0])[0],
                ci_upper=confidence_intervals.get('95%', [0, 0])[1],
                
                # Parâmetros
                best_params=best_params
            )
            
            results[strategy_name] = result
            print(f"✅ Carregado: {strategy_name} ({result.iterations} iterações)")
            
        except Exception as e:
            print(f"❌ Erro ao carregar {json_file.name}: {e}")
    
    return results

def calculate_composite_score(result: StrategyResult) -> float:
    """
    Calcula score composto baseado em múltiplos critérios
    
    Pesos:
    - Sharpe Ratio: 30%
    - Retorno Médio: 25%
    - Risk-Adjusted Return (Sortino): 20%
    - Win Rate: 15%
    - Probability of Profit: 10%
    
    Penalizações:
    - Max Drawdown > 30%: -20%
    - Profit Factor < 1.2: -15%
    - Win Rate < 40%: -10%
    """
    score = 0.0
    
    # 1. Sharpe Ratio (normalizado 0-10)
    sharpe_normalized = min(result.sharpe_ratio * 2, 10) if result.sharpe_ratio > 0 else 0
    score += sharpe_normalized * 0.30
    
    # 2. Retorno Médio (normalizado 0-10)
    return_normalized = min(result.mean_return / 10, 10) if result.mean_return > 0 else 0
    score += return_normalized * 0.25
    
    # 3. Sortino Ratio (normalizado 0-10)
    sortino_normalized = min(result.sortino_ratio * 2, 10) if result.sortino_ratio > 0 else 0
    score += sortino_normalized * 0.20
    
    # 4. Win Rate (normalizado 0-10)
    win_rate_normalized = result.win_rate / 10
    score += win_rate_normalized * 0.15
    
    # 5. Probability of Profit (normalizado 0-10)
    prob_normalized = result.probability_of_profit / 10
    score += prob_normalized * 0.10
    
    # Penalizações
    if result.max_drawdown > 30:
        score *= 0.80  # -20%
    
    if result.profit_factor < 1.2:
        score *= 0.85  # -15%
    
    if result.win_rate < 40:
        score *= 0.90  # -10%
    
    return round(score, 2)

def rank_strategies(results: Dict[str, StrategyResult]) -> List[Tuple[str, float]]:
    """Rankeia estratégias por score composto"""
    rankings = []
    
    for name, result in results.items():
        score = calculate_composite_score(result)
        rankings.append((name, score, result))
    
    # Ordenar por score (maior primeiro)
    rankings.sort(key=lambda x: x[1], reverse=True)
    
    return rankings

def print_analysis(results: Dict[str, StrategyResult]):
    """Imprime análise completa com formatação profissional"""
    
    print("\n" + "="*80)
    print("📊 ANÁLISE COMPARATIVA DE ESTRATÉGIAS - MONTE CARLO SIMULATION")
    print("="*80)
    print(f"\n🎯 Total de Estratégias Analisadas: {len(results)}")
    print(f"📈 Iterações por Estratégia: 200 (nível de confiança estatística elevado)")
    print("\n" + "-"*80)
    
    # Tabela comparativa
    print("\n📋 RESUMO EXECUTIVO - MÉTRICAS PRINCIPAIS\n")
    print(f"{'Estratégia':<25} {'Retorno':<12} {'Sharpe':<10} {'MDD':<10} {'Win%':<10} {'PF':<8}")
    print("-"*80)
    
    for name, result in results.items():
        print(f"{name:<25} "
              f"{result.mean_return:>10.2f}%  "
              f"{result.sharpe_ratio:>8.3f}  "
              f"{result.max_drawdown:>8.2f}%  "
              f"{result.win_rate:>8.2f}%  "
              f"{result.profit_factor:>6.2f}")
    
    print("\n" + "-"*80)
    
    # Ranking
    rankings = rank_strategies(results)
    
    print("\n🏆 RANKING DE ESTRATÉGIAS (Score Composto)\n")
    
    for i, (name, score, result) in enumerate(rankings, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}°"
        print(f"\n{medal} {name.upper()}")
        print(f"   Score Composto: {score:.2f}/10")
        print(f"   └─ Sharpe Ratio: {result.sharpe_ratio:.3f}")
        print(f"   └─ Retorno Médio: {result.mean_return:.2f}%")
        print(f"   └─ Sortino Ratio: {result.sortino_ratio:.3f}")
        print(f"   └─ Win Rate: {result.win_rate:.2f}%")
        print(f"   └─ Probability of Profit: {result.probability_of_profit:.2f}%")
        print(f"   └─ Max Drawdown: {result.max_drawdown:.2f}%")
        print(f"   └─ Profit Factor: {result.profit_factor:.2f}")
    
    print("\n" + "="*80)
    
    # Análise detalhada da estratégia vencedora
    winner_name, winner_score, winner = rankings[0]
    
    print(f"\n💎 ESTRATÉGIA VENCEDORA: {winner_name.upper()}")
    print("="*80)
    print(f"\n📊 MÉTRICAS DE RETORNO:")
    print(f"   Retorno Médio:     {winner.mean_return:>10.2f}%")
    print(f"   Retorno Mediano:   {winner.median_return:>10.2f}%")
    print(f"   Desvio Padrão:     {winner.std_return:>10.2f}%")
    print(f"   Retorno Mínimo:    {winner.min_return:>10.2f}%")
    print(f"   Retorno Máximo:    {winner.max_return:>10.2f}%")
    print(f"   IC 95%:            [{winner.ci_lower:.2f}%, {winner.ci_upper:.2f}%]")
    
    print(f"\n⚠️  MÉTRICAS DE RISCO:")
    print(f"   Max Drawdown:      {winner.max_drawdown:>10.2f}%")
    print(f"   VaR 95%:           {winner.var_95:>10.2f}%")
    print(f"   CVaR 95%:          {winner.cvar_95:>10.2f}%")
    print(f"   Sharpe Ratio:      {winner.sharpe_ratio:>10.3f}")
    print(f"   Sortino Ratio:     {winner.sortino_ratio:>10.3f}")
    
    print(f"\n🎯 MÉTRICAS DE PERFORMANCE:")
    print(f"   Win Rate:          {winner.win_rate:>10.2f}%")
    print(f"   Profit Factor:     {winner.profit_factor:>10.2f}")
    print(f"   Prob. Lucro:       {winner.probability_of_profit:>10.2f}%")
    print(f"   Runs Sucesso:      {winner.successful_runs}/{winner.iterations}")
    
    print(f"\n🔧 PARÂMETROS ÓTIMOS:")
    for param, value in winner.best_params.items():
        if isinstance(value, float):
            print(f"   {param:<20} {value:>10.3f}")
        else:
            print(f"   {param:<20} {value:>10}")
    
    print("\n" + "="*80)
    
    # Recomendações
    print("\n💡 RECOMENDAÇÕES PARA INVESTIMENTO:\n")
    
    if winner.sharpe_ratio > 1.0:
        print("✅ SHARPE EXCELENTE: Retorno ajustado ao risco muito bom (>1.0)")
    elif winner.sharpe_ratio > 0.5:
        print("⚠️  SHARPE MODERADO: Retorno ajustado ao risco aceitável (0.5-1.0)")
    else:
        print("❌ SHARPE BAIXO: Retorno não compensa o risco (<0.5)")
    
    if winner.max_drawdown < 20:
        print("✅ DRAWDOWN CONTROLADO: Risco de perdas significativas baixo (<20%)")
    elif winner.max_drawdown < 30:
        print("⚠️  DRAWDOWN MODERADO: Risco de perdas gerenciável (20-30%)")
    else:
        print("❌ DRAWDOWN ALTO: Risco de perdas significativas elevado (>30%)")
    
    if winner.win_rate > 50:
        print("✅ WIN RATE FORTE: Mais de 50% das operações lucrativas")
    elif winner.win_rate > 40:
        print("⚠️  WIN RATE ACEITÁVEL: 40-50% das operações lucrativas")
    else:
        print("❌ WIN RATE BAIXO: Menos de 40% das operações lucrativas")
    
    if winner.profit_factor > 1.5:
        print("✅ PROFIT FACTOR EXCELENTE: Lucros 50% maiores que perdas")
    elif winner.profit_factor > 1.2:
        print("⚠️  PROFIT FACTOR ACEITÁVEL: Lucros 20% maiores que perdas")
    else:
        print("❌ PROFIT FACTOR BAIXO: Lucros não compensam perdas adequadamente")
    
    # Análise de consistência
    print(f"\n📐 ANÁLISE DE CONSISTÊNCIA:")
    cv = (winner.std_return / winner.mean_return * 100) if winner.mean_return != 0 else 0
    print(f"   Coeficiente de Variação: {cv:.2f}%")
    
    if cv < 100:
        print("   ✅ Alta consistência - resultados previsíveis")
    elif cv < 200:
        print("   ⚠️  Consistência moderada - resultados variáveis")
    else:
        print("   ❌ Baixa consistência - resultados muito voláteis")
    
    # Decisão final
    print("\n" + "="*80)
    print("\n🎯 DECISÃO FINAL:\n")
    
    # Critérios eliminatórios
    if winner.sharpe_ratio < 0.5:
        print("❌ NÃO RECOMENDADO: Sharpe Ratio abaixo do mínimo aceitável")
        return
    
    if winner.max_drawdown > 35:
        print("❌ NÃO RECOMENDADO: Drawdown máximo muito alto")
        return
    
    if winner.profit_factor < 1.1:
        print("❌ NÃO RECOMENDADO: Profit Factor insuficiente")
        return
    
    # Classificação
    if winner_score >= 7.0:
        print("🌟 ALTAMENTE RECOMENDADO")
        print(f"   Score: {winner_score}/10 - Excelente em todos os critérios")
        print("   Considerar alocação significativa de capital")
    elif winner_score >= 5.0:
        print("✅ RECOMENDADO")
        print(f"   Score: {winner_score}/10 - Bom desempenho geral")
        print("   Considerar alocação moderada com monitoramento")
    elif winner_score >= 3.0:
        print("⚠️  RECOMENDADO COM RESSALVAS")
        print(f"   Score: {winner_score}/10 - Desempenho aceitável")
        print("   Considerar alocação conservadora e testes adicionais")
    else:
        print("❌ NÃO RECOMENDADO")
        print(f"   Score: {winner_score}/10 - Desempenho insuficiente")
        print("   Necessário otimização adicional ou descarte da estratégia")
    
    print("\n" + "="*80 + "\n")

def main():
    """Função principal"""
    # Tentar v2 primeiro, fallback para v1
    results_dir_v2 = "/home/dellno/worksapace/aitrading-platform/results_monte_carlo_v2"
    results_dir_v1 = "/home/dellno/worksapace/aitrading-platform/results_monte_carlo"
    
    if os.path.exists(results_dir_v2) and len(list(Path(results_dir_v2).glob("monte_carlo_*.json"))) > 0:
        results_dir = results_dir_v2
        print("\n🎯 Analisando resultados V2.0 (com correções)")
    elif os.path.exists(results_dir_v1):
        results_dir = results_dir_v1
        print("\n⚠️  Analisando resultados V1.0 (sem correções)")
    else:
        print(f"❌ Diretórios não encontrados!")
        sys.exit(1)
    
    print("\n🔍 Carregando resultados...")
    results = load_results(results_dir)
    
    if not results:
        print("❌ Nenhum resultado encontrado!")
        sys.exit(1)
    
    print_analysis(results)

if __name__ == "__main__":
    main()
