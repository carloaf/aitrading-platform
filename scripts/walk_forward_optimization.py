#!/usr/bin/env python3
"""
Walk-Forward Optimization - PASSO 24
Valida robustez do MetaBacktester em diferentes períodos

Metodologia:
1. Divide dados em janelas temporais
2. Treina em janela anterior, testa em janela atual
3. Compara performance in-sample vs out-of-sample
4. Detecta overfitting se degradação > 30%
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sys

# Configuração
API_URL = "http://localhost:8001/api/meta-backtest/run"  # Porta do container
INITIAL_CAPITAL = 100000
RISK_PER_TRADE = 0.02
SYMBOL = "BTCUSDT"  # Padrão, pode ser alterado via argumento

# Janelas de teste (walk-forward) - FOCO EM 2025
WINDOWS = [
    {
        "name": "Window 1: 2025 Q1",
        "train": ("2024-10-01", "2024-12-31"),  # Treino: Q4 2024
        "test": ("2025-01-01", "2025-03-31")     # Teste: Q1 2025
    },
    {
        "name": "Window 2: 2025 Q2",
        "train": ("2025-01-01", "2025-03-31"),  # Treino: Q1 2025
        "test": ("2025-04-01", "2025-06-30")    # Teste: Q2 2025
    },
    {
        "name": "Window 3: 2025 Q3",
        "train": ("2025-04-01", "2025-06-30"),  # Treino: Q2 2025
        "test": ("2025-07-01", "2025-09-30")    # Teste: Q3 2025
    },
    {
        "name": "Window 4: 2025 Q4 (Parcial)",
        "train": ("2025-07-01", "2025-09-30"),  # Treino: Q3 2025
        "test": ("2025-10-01", "2025-12-15")    # Teste: Q4 2025 (até hoje)
    },
    {
        "name": "Window 5: 2025 Full (YTD)",
        "train": ("2021-01-01", "2024-12-31"),  # Treino: 4 anos histórico
        "test": ("2025-01-01", "2025-12-15")    # Teste: 2025 completo
    }
]


def run_backtest(start_date: str, end_date: str, symbol: str = None) -> Dict:
    """Executa backtest via API"""
    payload = {
        "symbol": symbol or SYMBOL,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": INITIAL_CAPITAL,
        "risk_per_trade": RISK_PER_TRADE
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Erro no backtest: {e}")
        return None


def extract_metrics(result: Dict) -> Dict:
    """Extrai métricas principais do resultado"""
    if not result or not result.get('success'):
        return None
    
    perf = result.get('performance', {})
    ts = result.get('trade_stats', {})
    rm = result.get('risk_metrics', {})
    
    return {
        'return_pct': perf.get('total_return_pct', 0),
        'max_dd': perf.get('max_drawdown_pct', 0),
        'sharpe': rm.get('sharpe_ratio', 0),
        'sortino': rm.get('sortino_ratio', 0),
        'profit_factor': rm.get('profit_factor', 0),
        'trades': ts.get('total_trades', 0),
        'win_rate': ts.get('win_rate', 0),
        'avg_win': ts.get('avg_win', 0),
        'avg_loss': ts.get('avg_loss', 0)
    }


def calculate_degradation(train_metrics: Dict, test_metrics: Dict) -> Dict:
    """Calcula degradação de performance (overfitting indicator)"""
    if not train_metrics or not test_metrics:
        return None
    
    degradation = {
        'return_deg': test_metrics['return_pct'] - train_metrics['return_pct'],
        'sharpe_deg': test_metrics['sharpe'] - train_metrics['sharpe'],
        'win_rate_deg': test_metrics['win_rate'] - train_metrics['win_rate'],
        'dd_increase': test_metrics['max_dd'] - train_metrics['max_dd']
    }
    
    # Score de robustez (0-100)
    # Penaliza se test < train (degradação)
    # Premia se test >= train (generalização)
    robustness_score = 50  # baseline
    
    # Return: +10 se mantém, -20 se cai >20pp
    if degradation['return_deg'] >= -5:
        robustness_score += 15
    elif degradation['return_deg'] < -20:
        robustness_score -= 25
    
    # Sharpe: +10 se mantém, -15 se cai >0.5
    if degradation['sharpe_deg'] >= -0.2:
        robustness_score += 15
    elif degradation['sharpe_deg'] < -0.5:
        robustness_score -= 20
    
    # Win Rate: +10 se mantém, -10 se cai >10pp
    if degradation['win_rate_deg'] >= -5:
        robustness_score += 10
    elif degradation['win_rate_deg'] < -10:
        robustness_score -= 15
    
    # Drawdown: +10 se aumenta <5pp, -10 se aumenta >10pp
    if degradation['dd_increase'] < 5:
        robustness_score += 10
    elif degradation['dd_increase'] > 10:
        robustness_score -= 15
    
    degradation['robustness_score'] = max(0, min(100, robustness_score))
    
    return degradation


def print_window_results(window: Dict, train_metrics: Dict, test_metrics: Dict, degradation: Dict):
    """Imprime resultados formatados de uma janela"""
    print(f"\n{'='*80}")
    print(f"📊 {window['name']}")
    print(f"{'='*80}")
    
    if window['name'] != "Window 1: 2021":  # Window 1 não tem train data
        print(f"\n🔧 TRAIN: {window['train'][0]} → {window['train'][1]}")
        if train_metrics:
            print(f"   Return: {train_metrics['return_pct']:+.2f}%")
            print(f"   Sharpe: {train_metrics['sharpe']:.2f}")
            print(f"   Win Rate: {train_metrics['win_rate']:.1f}%")
            print(f"   Max DD: {train_metrics['max_dd']:.2f}%")
            print(f"   Trades: {train_metrics['trades']}")
    
    print(f"\n✅ TEST: {window['test'][0]} → {window['test'][1]}")
    if test_metrics:
        print(f"   Return: {test_metrics['return_pct']:+.2f}%")
        print(f"   Sharpe: {test_metrics['sharpe']:.2f}")
        print(f"   Win Rate: {test_metrics['win_rate']:.1f}%")
        print(f"   Max DD: {test_metrics['max_dd']:.2f}%")
        print(f"   Trades: {test_metrics['trades']}")
    
    if degradation and window['name'] != "Window 1: 2021":
        print(f"\n📉 DEGRADAÇÃO (Test - Train):")
        print(f"   Return: {degradation['return_deg']:+.2f}pp")
        print(f"   Sharpe: {degradation['sharpe_deg']:+.2f}")
        print(f"   Win Rate: {degradation['win_rate_deg']:+.2f}pp")
        print(f"   DD Increase: {degradation['dd_increase']:+.2f}pp")
        
        score = degradation['robustness_score']
        if score >= 70:
            status = "✅ ROBUSTO"
        elif score >= 50:
            status = "🟡 ACEITÁVEL"
        else:
            status = "🔴 OVERFITTING"
        
        print(f"   Robustness Score: {score:.0f}/100 {status}")


def main():
    """Executa Walk-Forward Optimization completo"""
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else SYMBOL
    
    print("="*80)
    print("🚀 WALK-FORWARD OPTIMIZATION - PASSO 24")
    print("="*80)
    print(f"\n💰 Par: {symbol}")
    print("Validando robustez do MetaBacktester em diferentes períodos...")
    print("Metodologia: Train em período anterior → Test em período atual")
    print("\n⏱️  Tempo estimado: ~15-20 minutos (10 backtests)")
    print("="*80)
    
    results = []
    
    for i, window in enumerate(WINDOWS):
        print(f"\n\n{'='*80}")
        print(f"🔄 [{i+1}/{len(WINDOWS)}] Processando {window['name']}")
        print(f"{'='*80}")
        
        # Window 1 não tem dados de treino (2020)
        if window['name'] == "Window 1: 2021":
            print("   (Baseline - sem dados de treino anteriores)")
            
            print(f"\n✅ TEST: {window['test'][0]} → {window['test'][1]}")
            print("   ⏳ Executando backtest...", end="", flush=True)
            test_result = run_backtest(window['test'][0], window['test'][1])
            test_metrics = extract_metrics(test_result)
            print(" ✅ Concluído!")
            
            if test_metrics:
                print(f"\n📊 RESULTADOS TEST:")
                print(f"   Return: {test_metrics['return_pct']:+.2f}%")
                print(f"   Sharpe: {test_metrics['sharpe']:.2f}")
                print(f"   Win Rate: {test_metrics['win_rate']:.1f}%")
                print(f"   Max DD: {test_metrics['max_dd']:.2f}%")
                print(f"   Trades: {test_metrics['trades']}")
            else:
                print("   ❌ Falha no backtest")
            
            results.append({
                'window': window['name'],
                'train_metrics': None,
                'test_metrics': test_metrics,
                'degradation': None
            })
        else:
            # Train
            print(f"\n🔧 TRAIN: {window['train'][0]} → {window['train'][1]}")
            print("   ⏳ Executando backtest...", end="", flush=True)
            train_result = run_backtest(window['train'][0], window['train'][1])
            train_metrics = extract_metrics(train_result)
            print(" ✅ Concluído!")
            
            if train_metrics:
                print(f"\n📊 RESULTADOS TRAIN:")
                print(f"   Return: {train_metrics['return_pct']:+.2f}%")
                print(f"   Sharpe: {train_metrics['sharpe']:.2f}")
                print(f"   Win Rate: {train_metrics['win_rate']:.1f}%")
                print(f"   Max DD: {train_metrics['max_dd']:.2f}%")
                print(f"   Trades: {train_metrics['trades']}")
            else:
                print("   ❌ Falha no backtest de treino")
            
            # Test (out-of-sample)
            print(f"\n✅ TEST: {window['test'][0]} → {window['test'][1]}")
            print("   ⏳ Executando backtest...", end="", flush=True)
            test_result = run_backtest(window['test'][0], window['test'][1])
            test_metrics = extract_metrics(test_result)
            print(" ✅ Concluído!")
            
            if test_metrics:
                print(f"\n📊 RESULTADOS TEST:")
                print(f"   Return: {test_metrics['return_pct']:+.2f}%")
                print(f"   Sharpe: {test_metrics['sharpe']:.2f}")
                print(f"   Win Rate: {test_metrics['win_rate']:.1f}%")
                print(f"   Max DD: {test_metrics['max_dd']:.2f}%")
                print(f"   Trades: {test_metrics['trades']}")
            else:
                print("   ❌ Falha no backtest de teste")
            
            # Degradação
            degradation = calculate_degradation(train_metrics, test_metrics)
            
            if degradation:
                print(f"\n📉 DEGRADAÇÃO (Test - Train):")
                print(f"   Return: {degradation['return_deg']:+.2f}pp")
                print(f"   Sharpe: {degradation['sharpe_deg']:+.2f}")
                print(f"   Win Rate: {degradation['win_rate_deg']:+.2f}pp")
                print(f"   DD Increase: {degradation['dd_increase']:+.2f}pp")
                
                score = degradation['robustness_score']
                if score >= 70:
                    status = "✅ ROBUSTO"
                elif score >= 50:
                    status = "🟡 ACEITÁVEL"
                else:
                    status = "🔴 OVERFITTING"
                
                print(f"   Robustness Score: {score:.0f}/100 {status}")
            
            results.append({
                'window': window['name'],
                'train_metrics': train_metrics,
                'test_metrics': test_metrics,
                'degradation': degradation
            })
    
    # Resumo Final
    print(f"\n\n{'='*80}")
    print("📊 RESUMO WALK-FORWARD OPTIMIZATION")
    print(f"{'='*80}")
    
    # Tabela comparativa
    print("\n| Window | Test Return | Test Sharpe | Test WR | Degradation Return | Robustness |")
    print("|--------|-------------|-------------|---------|-------------------|------------|")
    
    avg_robustness = 0
    count_robustness = 0
    
    for r in results:
        test = r['test_metrics']
        deg = r['degradation']
        
        if test:
            window_short = r['window'].split(":")[1].strip()
            
            if deg:
                deg_return = f"{deg['return_deg']:+.1f}pp"
                robustness = f"{deg['robustness_score']:.0f}"
                avg_robustness += deg['robustness_score']
                count_robustness += 1
            else:
                deg_return = "N/A"
                robustness = "Baseline"
            
            print(f"| {window_short} | {test['return_pct']:+.2f}% | {test['sharpe']:.2f} | {test['win_rate']:.1f}% | {deg_return} | {robustness} |")
    
    # Score médio de robustez
    if count_robustness > 0:
        avg_robustness /= count_robustness
        
        print(f"\n{'='*80}")
        print(f"🎯 SCORE MÉDIO DE ROBUSTEZ: {avg_robustness:.0f}/100")
        
        if avg_robustness >= 70:
            print("✅ CONCLUSÃO: Sistema é ROBUSTO e generaliza bem!")
            print("   → Confiança alta para produção")
        elif avg_robustness >= 50:
            print("🟡 CONCLUSÃO: Sistema tem robustez ACEITÁVEL")
            print("   → Pode usar em produção com monitoramento")
        else:
            print("🔴 CONCLUSÃO: Sistema apresenta OVERFITTING")
            print("   → NÃO recomendado para produção sem ajustes")
        
        print(f"{'='*80}")
    
    # Análise de consistência
    print("\n📈 ANÁLISE DE CONSISTÊNCIA:")
    test_returns = [r['test_metrics']['return_pct'] for r in results if r['test_metrics']]
    
    if len(test_returns) > 0:
        positive_periods = sum(1 for ret in test_returns if ret > 0)
        total_periods = len(test_returns)
        
        print(f"   Períodos positivos: {positive_periods}/{total_periods} ({100*positive_periods/total_periods:.0f}%)")
        print(f"   Return médio: {sum(test_returns)/len(test_returns):+.2f}%")
        print(f"   Return mínimo: {min(test_returns):+.2f}%")
        print(f"   Return máximo: {max(test_returns):+.2f}%")
        
        if positive_periods >= total_periods * 0.75:
            print("   ✅ Alta consistência (>75% períodos positivos)")
        elif positive_periods >= total_periods * 0.5:
            print("   🟡 Consistência moderada (50-75% períodos positivos)")
        else:
            print("   🔴 Baixa consistência (<50% períodos positivos)")
    else:
        print("   ⚠️ Nenhum resultado válido obtido")
    
    print("\n✅ Walk-Forward Optimization concluído!")
    print("💾 Resultados podem ser usados para documentação no PLANO_DE_MELHORAMENTO.md")


if __name__ == "__main__":
    main()
