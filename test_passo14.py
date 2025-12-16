#!/usr/bin/env python3
"""
Script para testar PASSO 14 - Position Sizing Dinâmico
Testa Bear Market 2022 e Ciclo 4 Anos
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:3008"

def test_bear_market_2022():
    """Testa Bear Market 2022"""
    print("=" * 80)
    print("🐻 TESTE: Bear Market 2022 (Jan-Dez)")
    print("=" * 80)
    
    payload = {
        "symbol": "BTCUSDT",
        "start_date": "2022-01-01",
        "end_date": "2022-12-31",
        "initial_capital": 100000,
        "timeframe": "1h"
    }
    
    response = requests.post(f"{BASE_URL}/api/meta-backtest/run", json=payload, timeout=300)
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"\n📊 RESULTADOS:")
        print(f"   Total Return: {result.get('total_return_pct', 0):.2f}%")
        print(f"   Sharpe Ratio: {result.get('sharpe_ratio', 0):.2f}")
        print(f"   Max Drawdown: {result.get('max_drawdown_pct', 0):.2f}%")
        print(f"   Win Rate: {result.get('win_rate_pct', 0):.1f}%")
        print(f"   Profit Factor: {result.get('profit_factor', 0):.2f}")
        print(f"   Total Trades: {result.get('total_trades', 0)}")
        
        # Regime breakdown
        if 'regime_breakdown' in result:
            print(f"\n🔍 REGIME BREAKDOWN:")
            for regime, stats in result['regime_breakdown'].items():
                print(f"   {regime}: {stats.get('trades', 0)} trades, "
                      f"{stats.get('return_pct', 0):.2f}% return")
        
        return result
    else:
        print(f"❌ ERRO: {response.status_code}")
        print(response.text)
        return None

def test_4year_cycle():
    """Testa ciclo de 4 anos"""
    print("\n" + "=" * 80)
    print("📈 TESTE: Ciclo 4 Anos (2021-2024)")
    print("=" * 80)
    
    payload = {
        "symbol": "BTCUSDT",
        "start_date": "2021-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000,
        "timeframe": "1h"
    }
    
    response = requests.post(f"{BASE_URL}/api/meta-backtest/run", json=payload, timeout=600)
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"\n📊 RESULTADOS:")
        print(f"   Total Return: {result.get('total_return_pct', 0):.2f}%")
        print(f"   Sharpe Ratio: {result.get('sharpe_ratio', 0):.2f}")
        print(f"   Max Drawdown: {result.get('max_drawdown_pct', 0):.2f}%")
        print(f"   Win Rate: {result.get('win_rate_pct', 0):.1f}%")
        print(f"   Profit Factor: {result.get('profit_factor', 0):.2f}")
        print(f"   Total Trades: {result.get('total_trades', 0)}")
        
        # Regime breakdown
        if 'regime_breakdown' in result:
            print(f"\n🔍 REGIME BREAKDOWN:")
            for regime, stats in result['regime_breakdown'].items():
                print(f"   {regime}: {stats.get('trades', 0)} trades, "
                      f"{stats.get('return_pct', 0):.2f}% return")
        
        return result
    else:
        print(f"❌ ERRO: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    print(f"\n🚀 Testing PASSO 14 - Position Sizing Dinâmico")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Test Bear Market 2022
    bear_result = test_bear_market_2022()
    
    # Test 4-Year Cycle
    cycle_result = test_4year_cycle()
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 COMPARAÇÃO DE RESULTADOS")
    print("=" * 80)
    
    if bear_result and cycle_result:
        print(f"\n🐻 Bear Market 2022:")
        print(f"   Return: {bear_result.get('total_return_pct', 0):.2f}% (Expectativa: +6.38%)")
        print(f"   Win Rate: {bear_result.get('win_rate_pct', 0):.1f}%")
        print(f"   Max DD: {bear_result.get('max_drawdown_pct', 0):.2f}%")
        
        print(f"\n📈 Ciclo 4 Anos:")
        print(f"   Return: {cycle_result.get('total_return_pct', 0):.2f}% (Antes: -28.69%)")
        print(f"   Win Rate: {cycle_result.get('win_rate_pct', 0):.1f}% (Meta: >45%)")
        print(f"   Max DD: {cycle_result.get('max_drawdown_pct', 0):.2f}% (Meta: <25%)")
        
        # Check if improvements met targets
        print(f"\n🎯 VALIDAÇÃO DAS METAS:")
        
        # Win Rate
        win_rate = cycle_result.get('win_rate_pct', 0)
        if win_rate >= 45:
            print(f"   ✅ Win Rate: {win_rate:.1f}% (META ATINGIDA: >45%)")
        else:
            print(f"   ⚠️  Win Rate: {win_rate:.1f}% (Ainda abaixo da meta de 45%)")
        
        # Max DD
        max_dd = cycle_result.get('max_drawdown_pct', 0)
        if max_dd <= 25:
            print(f"   ✅ Max Drawdown: {max_dd:.2f}% (META ATINGIDA: <25%)")
        else:
            print(f"   ⚠️  Max Drawdown: {max_dd:.2f}% (Ainda acima da meta de 25%)")
        
        # Positive Return
        total_return = cycle_result.get('total_return_pct', 0)
        if total_return > 0:
            print(f"   ✅ Return Positivo: {total_return:.2f}% (MELHORIA CONFIRMADA)")
        else:
            print(f"   ⚠️  Return: {total_return:.2f}% (Ainda negativo)")
    
    print("\n" + "=" * 80)
    print("✅ Teste concluído")
    print("=" * 80 + "\n")
