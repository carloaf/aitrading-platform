#!/bin/bash

echo "🐻 TESTANDO ESTRATÉGIAS BEAR MARKET"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

strategies=("bear_market_short" "breakdown_momentum" "death_cross")

for strategy in "${strategies[@]}"; do
  echo "📊 Testando: $strategy (50 iterações)..."
  
  response=$(curl -s -X POST "http://localhost:3008/api/monte-carlo/simulate" \
    -H "Content-Type: application/json" \
    -d "{
      \"strategy_name\": \"$strategy\",
      \"symbol\": \"BTCUSDT\",
      \"timeframe\": \"15m\",
      \"iterations\": 50,
      \"start_capital\": 10000,
      \"lookback_days\": 60
    }")
  
  echo "Aguardando 15s..."
  sleep 15
  
  # Buscar resultado
  result=$(curl -s "http://localhost:3008/api/monte-carlo/reports" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    reports = data.get('reports', [])
    target = [r for r in reports if r.get('strategy') == '$strategy']
    if target:
        r = target[-1]  # Último report desta estratégia
        print(f\"✅ Return: {r.get('mean_return', 0):.2f}%\")
        print(f\"   Profit Prob: {r.get('probability_of_profit', 0):.1f}%\")
        print(f\"   Sharpe: {r.get('mean_sharpe', 0):.2f}\")
    else:
        print(f\"❌ Nenhum report encontrado\")
except Exception as e:
    print(f\"⚠️  Erro: {e}\")
" 2>&1)
  
  echo "$result"
  echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Teste concluído!"
