#!/usr/bin/env python3
"""
Teste de debug - verifica se estratégias estão sendo chamadas
"""

import requests
import json

BASE_URL = "http://localhost:3008"

print("=" * 80)
print("🐛 DEBUG TEST - Meta-Backtest")
print("=" * 80)

# Teste com período menor para debug rápido
payload = {
    "symbol": "BTCUSDT",
    "start_date": "2022-07-01",
    "end_date": "2022-07-15",  # Apenas 2 semanas
    "initial_capital": 100000,
    "timeframe": "1h"
}

print(f"\n📊 Testando 2 semanas (Jul 2022)")
print(f"   URL: {BASE_URL}/api/meta-backtest/run")

try:
    response = requests.post(f"{BASE_URL}/api/meta-backtest/run", json=payload, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"\n✅ Response OK")
        print(f"   Total Trades: {result.get('total_trades', 0)}")
        print(f"   Total Return: {result.get('total_return_pct', 0):.2f}%")
        
        # Verificar regimes detectados
        if 'regime_history' in result:
            print(f"\n🔄 Regimes detectados: {len(result['regime_history'])}")
            for r in result['regime_history'][:5]:
                print(f"      {r}")
        
        # Verificar trades
        if result.get('total_trades', 0) > 0:
            print(f"\n💰 Trades gerados!")
        else:
            print(f"\n⚠️  Nenhum trade - verificar condições de entrada")
            
    else:
        print(f"❌ Erro: {response.status_code}")
        print(response.text[:500])
        
except Exception as e:
    print(f"❌ Exceção: {e}")

print("\n" + "=" * 80)
