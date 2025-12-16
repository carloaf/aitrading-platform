#!/bin/bash
# Script para comparar resultados multi-par em formato de tabela consolidada

echo "📊 COMPARAÇÃO MULTI-PAR 2025 - TABELA CONSOLIDADA"
echo "=================================================="
echo ""

# Função helper para executar backtest e extrair métricas específicas
run_comparison() {
  local symbol=$1
  local start=$2
  local end=$3
  local period=$4
  
  result=$(curl -sS http://localhost:3008/api/meta-backtest/run \
    -H 'Content-Type: application/json' \
    -d "{
      \"symbol\": \"$symbol\",
      \"timeframe\": \"1h\",
      \"start_date\": \"$start\",
      \"end_date\": \"$end\",
      \"initial_capital\": 10000,
      \"include_trades\": false
    }")
  
  # Extrair métricas usando Python
  echo "$result" | python3 -c "
import sys, json

symbol = '$symbol'
period = '$period'

try:
    j = json.load(sys.stdin)
    perf = j.get('performance', {})
    risk = j.get('risk_metrics', {})
    stats = j.get('trade_stats', {})
    
    ret = perf.get('total_return_pct', 0)
    sharpe = risk.get('sharpe_ratio', 0)
    pf = risk.get('profit_factor', 0)
    dd = perf.get('max_drawdown_pct', 0)
    wr = stats.get('win_rate', 0)
    trades = stats.get('total_trades', 0)
    
    # Formatar linha da tabela
    print(f'| {symbol:8} | {period:4} | {ret:6.2f}% | {sharpe:5.2f} | {pf:7.2f} | {dd:5.2f}% | {wr:5.1f}% | {trades:6} |')
except Exception as e:
    print(f'| {symbol:8} | {period:4} | ERROR  |       |         |        |        |        |', file=sys.stderr)
    print(f'Error: {e}', file=sys.stderr)
"
}

# Cabeçalho da tabela
echo "| Par      | Trim | Return | Sharpe | Profit F | Max DD | Win Rate | Trades |"
echo "|----------|------|--------|--------|----------|--------|----------|--------|"

# Q2/2025
run_comparison "BTCUSDT" "2025-04-01" "2025-06-30" "Q2"
run_comparison "ETHUSDT" "2025-04-01" "2025-06-30" "Q2"
run_comparison "SOLUSDT" "2025-04-01" "2025-06-30" "Q2"

echo "|----------|------|--------|--------|----------|--------|----------|--------|"

# Q4/2025
run_comparison "BTCUSDT" "2025-10-01" "2025-12-31" "Q4"
run_comparison "ETHUSDT" "2025-10-01" "2025-12-31" "Q4"
run_comparison "SOLUSDT" "2025-10-01" "2025-12-31" "Q4"

echo ""
echo "✅ Comparação concluída!"
echo ""
echo "📌 LEGENDA:"
echo "   Profit F = Profit Factor (999.99 indica 100% win rate)"
echo "   Trim = Trimestre testado"
