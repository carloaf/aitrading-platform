#!/bin/bash
# VALIDAÇÃO MULTI-PAR 2025 - Ajustes PASSO 24.3
# Testa ETH/USDT e SOL/USDT nos trimestres Q2 e Q4 de 2025
# para validar se os ajustes (TP 2.5x SIDEWAYS, hysteresis 8, min_quality 70)
# generalizam para outros pares além de BTC.

set -e
cd "$(dirname "$0")/.."

echo "🔍 VALIDAÇÃO MULTI-PAR 2025 (Q2 + Q4)"
echo "======================================"
echo ""

# Função helper para executar backtest e parsear resultado
run_backtest() {
  local symbol="$1"
  local start="$2"
  local end="$3"
  local label="$4"
  
  echo "📊 $label ($symbol: $start → $end)"
  
  curl -sS http://localhost:3008/api/meta-backtest/run \
    -H 'Content-Type: application/json' \
    -d '{
      "symbol": "'$symbol'",
      "timeframe": "1h",
      "start_date": "'$start'",
      "end_date": "'$end'",
      "initial_capital": 10000,
      "include_trades": false
    }' \
  | python3 -c '
import sys, json
j = json.load(sys.stdin)
perf = j.get("performance", {})
risk = j.get("risk_metrics", {})
stats = j.get("trade_stats", {})
adapt = j.get("adaptability", {})

ret = perf.get("total_return_pct", 0)
sharpe = risk.get("sharpe_ratio", 0)
pf = risk.get("profit_factor", 0)
dd = perf.get("max_drawdown_pct", 0)
wr = stats.get("win_rate", 0)
trades = stats.get("total_trades", 0)
regimes = adapt.get("regime_changes", 0)

print(f"  Return:        {ret:.2f}%")
print(f"  Sharpe:        {sharpe:.2f}")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Max DD:        {dd:.2f}%")
print(f"  Win Rate:      {wr:.1f}%")
print(f"  Total Trades:  {trades}")
print(f"  Regime Changes: {regimes}")
'
  echo ""
}

echo "=== ETHUSDT ==="
echo ""
run_backtest "ETHUSDT" "2025-04-01" "2025-06-30" "Q2/2025 (Abr-Jun)"
run_backtest "ETHUSDT" "2025-10-01" "2025-12-31" "Q4/2025 (Out-Dez)"

echo "=== SOLUSDT ==="
echo ""
run_backtest "SOLUSDT" "2025-04-01" "2025-06-30" "Q2/2025 (Abr-Jun)"
run_backtest "SOLUSDT" "2025-10-01" "2025-12-31" "Q4/2025 (Out-Dez)"

echo "=== BTCUSDT (baseline para comparação) ==="
echo ""
run_backtest "BTCUSDT" "2025-04-01" "2025-06-30" "Q2/2025 (Abr-Jun)"
run_backtest "BTCUSDT" "2025-10-01" "2025-12-31" "Q4/2025 (Out-Dez)"

echo "✅ Validação multi-par concluída!"
echo ""
echo "📌 PRÓXIMO PASSO:"
echo "   Comparar métricas entre pares e identificar se ajustes 24.3"
echo "   (TP 2.5x SIDEWAYS, hysteresis 8, min_quality 70) generalizam"
echo "   ou se requerem calibração específica por par."
