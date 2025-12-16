#!/usr/bin/env python3
"""
Walk-Forward Optimization Multi-Par - 2025
Testa BTCUSDT, ETHUSDT e SOLUSDT no ano de 2025
"""

import requests
import json
import sys
from typing import Dict

API_URL = "http://localhost:8001/api/meta-backtest/run"
INITIAL_CAPITAL = 100000
RISK_PER_TRADE = 0.02

# Apenas Q3/2025 para comparação rápida
WINDOWS = [
    {
        "name": "Q3 2025",
        "test": ("2025-07-01", "2025-09-30")
    }
]

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def run_backtest(symbol: str, start_date: str, end_date: str) -> Dict:
    """Executa backtest via API"""
    payload = {
        "symbol": symbol,
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
        print(f" ❌ Erro: {e}")
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
        'profit_factor': rm.get('profit_factor', 0),
        'trades': ts.get('total_trades', 0),
        'win_rate': ts.get('win_rate', 0),
        'avg_win': ts.get('avg_win', 0),
        'avg_loss': ts.get('avg_loss', 0)
    }


def main():
    """Executa comparação multi-par"""
    print("="*80)
    print("🔄 COMPARAÇÃO MULTI-PAR 2025 - Q3 (Jul-Set)")
    print("="*80)
    print(f"\n💰 Pares: {', '.join(SYMBOLS)}")
    print("⏱️  Tempo estimado: ~3-5 minutos (3 backtests)")
    print("="*80)
    
    results = {}
    
    for symbol in SYMBOLS:
        print(f"\n\n{'='*80}")
        print(f"📊 Testando {symbol}")
        print(f"{'='*80}")
        
        window = WINDOWS[0]
        print(f"\n✅ TEST: {window['test'][0]} → {window['test'][1]}")
        print(f"   ⏳ Executando backtest {symbol}...", end="", flush=True)
        
        result = run_backtest(symbol, window['test'][0], window['test'][1])
        metrics = extract_metrics(result)
        
        if metrics:
            print(" ✅ Concluído!")
            print(f"\n📊 RESULTADOS {symbol}:")
            print(f"   Return: {metrics['return_pct']:+.2f}%")
            print(f"   Sharpe: {metrics['sharpe']:.2f}")
            print(f"   Win Rate: {metrics['win_rate']:.1f}%")
            print(f"   Max DD: {metrics['max_dd']:.2f}%")
            print(f"   Trades: {metrics['trades']}")
            print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
            
            results[symbol] = metrics
        else:
            print(" ❌ Falha!")
            results[symbol] = None
    
    # Resumo comparativo
    print(f"\n\n{'='*80}")
    print("📊 COMPARAÇÃO Q3/2025 - MULTI-PAR")
    print(f"{'='*80}")
    
    print("\n| Par | Return | Sharpe | Win Rate | Trades | Max DD | P.Factor |")
    print("|-----|--------|--------|----------|--------|--------|----------|")
    
    for symbol in SYMBOLS:
        m = results.get(symbol)
        if m:
            print(f"| {symbol:7} | {m['return_pct']:+6.2f}% | {m['sharpe']:6.2f} | {m['win_rate']:5.1f}% | {m['trades']:6} | {m['max_dd']:5.2f}% | {m['profit_factor']:8.2f} |")
        else:
            print(f"| {symbol:7} | ERRO | - | - | - | - | - |")
    
    # Análise
    valid_results = {k: v for k, v in results.items() if v}
    
    if len(valid_results) >= 2:
        print(f"\n{'='*80}")
        print("🏆 RANKINGS Q3/2025:")
        print(f"{'='*80}")
        
        # Por retorno
        sorted_return = sorted(valid_results.items(), key=lambda x: x[1]['return_pct'], reverse=True)
        print("\n📈 Por Retorno:")
        for i, (symbol, m) in enumerate(sorted_return, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            print(f"   {emoji} {i}. {symbol}: {m['return_pct']:+.2f}%")
        
        # Por Sharpe
        sorted_sharpe = sorted(valid_results.items(), key=lambda x: x[1]['sharpe'], reverse=True)
        print("\n💎 Por Qualidade (Sharpe):")
        for i, (symbol, m) in enumerate(sorted_sharpe, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            print(f"   {emoji} {i}. {symbol}: {m['sharpe']:.2f}")
        
        # Por segurança (menor DD)
        sorted_dd = sorted(valid_results.items(), key=lambda x: x[1]['max_dd'])
        print("\n🛡️  Por Segurança (menor DD):")
        for i, (symbol, m) in enumerate(sorted_dd, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            print(f"   {emoji} {i}. {symbol}: {m['max_dd']:.2f}%")
        
        # Análise consolidada
        print(f"\n{'='*80}")
        print("💡 ANÁLISE CONSOLIDADA:")
        print(f"{'='*80}")
        
        avg_return = sum(m['return_pct'] for m in valid_results.values()) / len(valid_results)
        avg_sharpe = sum(m['sharpe'] for m in valid_results.values()) / len(valid_results)
        positive_count = sum(1 for m in valid_results.values() if m['return_pct'] > 0)
        
        print(f"\n📊 Métricas Médias:")
        print(f"   Return médio: {avg_return:+.2f}%")
        print(f"   Sharpe médio: {avg_sharpe:.2f}")
        print(f"   Pares positivos: {positive_count}/{len(valid_results)}")
        
        if positive_count == 0:
            print("\n🔴 ALERTA: Nenhum par teve retorno positivo em Q3/2025")
            print("   → Problema provavelmente é do mercado geral, não do sistema")
        elif positive_count < len(valid_results):
            print(f"\n🟡 ATENÇÃO: Apenas {positive_count}/{len(valid_results)} pares positivos")
            print("   → Q3/2025 foi período desafiador para a maioria")
        else:
            print(f"\n✅ SUCESSO: Todos os pares positivos em Q3/2025")
    
    print("\n✅ Comparação multi-par concluída!")


if __name__ == "__main__":
    main()
