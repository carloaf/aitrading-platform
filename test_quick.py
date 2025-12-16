#!/usr/bin/env python3
"""
Teste rápido - Apenas 1 mês para validar funcionamento
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:3008"

print("🚀 Teste Rápido - 1 Mês (Out 2022)")
print("=" * 60)

payload = {
    "symbol": "BTCUSDT",
    "start_date": "2022-10-01",
    "end_date": "2022-10-31",
    "initial_capital": 100000,
    "timeframe": "1h"
}

print(f"Enviando requisição para {BASE_URL}/api/meta-backtest/run...")
response = requests.post(f"{BASE_URL}/api/meta-backtest/run", json=payload, timeout=120)

if response.status_code == 200:
    result = response.json()
    
    print(f"\n📊 RESULTADOS:")
    print(f"   Total Return: {result.get('total_return_pct', 0):.2f}%")
    print(f"   Sharpe Ratio: {result.get('sharpe_ratio', 0):.2f}")
    print(f"   Max Drawdown: {result.get('max_drawdown_pct', 0):.2f}%")
    print(f"   Win Rate: {result.get('win_rate_pct', 0):.1f}%")
    print(f"   Total Trades: {result.get('total_trades', 0)}")
    print("\n✅ Sistema funcionando corretamente!")
else:
    print(f"❌ ERRO: {response.status_code}")
    print(response.text)
