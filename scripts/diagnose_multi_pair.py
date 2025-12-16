#!/usr/bin/env python3
"""
Teste diagnóstico multi-par
Verifica se cada símbolo retorna candles diferentes
"""
import requests
import json
from datetime import datetime

API_URL = "http://localhost:8001/api/meta-backtest/run"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
START = "2025-07-01"
END = "2025-07-03"  # Apenas 3 dias para diagnóstico

print("="*80)
print("🔬 TESTE DIAGNÓSTICO MULTI-PAR")
print("="*80)
print(f"\nPeríodo: {START} → {END} (3 dias)")
print(f"Símbolos: {', '.join(SYMBOLS)}\n")

for symbol in SYMBOLS:
    print(f"\n{'='*80}")
    print(f"📊 Testando {symbol}")
    print(f"{'='*80}")
    
    payload = {
        "symbol": symbol,
        "start_date": START,
        "end_date": END,
        "initial_capital": 100000,
        "risk_per_trade": 0.02
    }
    
    response = requests.post(API_URL, json=payload, timeout=60)
    result = response.json()
    
    if result['success']:
        candles = result.get('candles_analyzed', 0)
        first_regime = result.get('debug', {}).get('first_regime', 'N/A')
        regime_changes = result.get('adaptability', {}).get('regime_changes', 0)
        
        # Extrair primeiro preço de close do debug
        debug = result.get('debug', {})
        
        print(f"✅ Sucesso:")
        print(f"   Candles: {candles}")
        print(f"   Primeiro Regime: {first_regime}")
        print(f"   Mudanças Regime: {regime_changes}")
        
        # Tentar extrair informação de preço do resultado
        perf = result.get('performance', {})
        print(f"   Capital Final: ${perf.get('final_capital', 0):,.2f}")
        print(f"   Return: {perf.get('total_return_pct', 0):.2f}%")
    else:
        print(f"❌ Falhou: {result.get('error', 'Unknown error')}")

print(f"\n{'='*80}")
print("💡 CONCLUSÃO:")
print("   Se os 3 símbolos têm MESMA quantidade de candles → Dados corretos")
print("   Se os 3 têm MESMOS resultados → Bug de cache/estado")
print("="*80)
