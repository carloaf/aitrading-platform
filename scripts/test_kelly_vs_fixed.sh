#!/bin/bash
# PASSO 25: Teste comparativo Kelly Position Sizing vs Fixed Risk
# Testa ano completo de 2024 (Q1+Q2+Q3+Q4)

echo "🧪 TESTE COMPARATIVO: KELLY POSITION SIZING vs FIXED RISK"
echo "========================================================="
echo ""
echo "📅 Período: 2024 Completo (Jan-Dez)"
echo "🪙 Par: BTCUSDT"
echo "⏰ Timeframe: 1h"
echo ""

# Teste 1: BASELINE (Fixed Risk 2%)
echo "1️⃣  BASELINE: Fixed Risk (2% per trade)"
echo "----------------------------------------"
result_fixed=$(curl -sS -X POST http://localhost:3008/api/meta-backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "interval": "1h",
    "initial_capital": 100000,
    "risk_per_trade": 0.02,
    "use_kelly_sizing": false,
    "include_trades": false
  }')

echo "$result_fixed" | python3 -c "
import json, sys
data = json.load(sys.stdin)
perf = data['performance']
risk = data['risk_metrics']
stats = data['trade_stats']

print(f\"Return: {perf['total_return_pct']:+.2f}%\")
print(f\"Sharpe: {risk['sharpe_ratio']:.2f}\")
print(f\"Sortino: {risk['sortino_ratio']:.2f}\")
print(f\"Profit Factor: {risk['profit_factor']:.2f}\")
print(f\"Max DD: {perf['max_drawdown_pct']:.2f}%\")
print(f\"Win Rate: {stats['win_rate']:.1f}%\")
print(f\"Trades: {stats['total_trades']}\")
print(f\"Avg Win: \${stats['avg_win']:.2f}\")
print(f\"Avg Loss: \${stats['avg_loss']:.2f}\")
"

echo ""
echo ""

# Teste 2: KELLY (25% fraction, min 30 trades)
echo "2️⃣  KELLY CRITERION: 25% Kelly Fraction"
echo "----------------------------------------"
result_kelly=$(curl -sS -X POST http://localhost:3008/api/meta-backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "interval": "1h",
    "initial_capital": 100000,
    "risk_per_trade": 0.02,
    "use_kelly_sizing": true,
    "kelly_fraction": 0.25,
    "kelly_min_trades": 30,
    "include_trades": false
  }')

echo "$result_kelly" | python3 -c "
import json, sys
data = json.load(sys.stdin)
perf = data['performance']
risk = data['risk_metrics']
stats = data['trade_stats']

print(f\"Return: {perf['total_return_pct']:+.2f}%\")
print(f\"Sharpe: {risk['sharpe_ratio']:.2f}\")
print(f\"Sortino: {risk['sortino_ratio']:.2f}\")
print(f\"Profit Factor: {risk['profit_factor']:.2f}\")
print(f\"Max DD: {perf['max_drawdown_pct']:.2f}%\")
print(f\"Win Rate: {stats['win_rate']:.1f}%\")
print(f\"Trades: {stats['total_trades']}\")
print(f\"Avg Win: \${stats['avg_win']:.2f}\")
print(f\"Avg Loss: \${stats['avg_loss']:.2f}\")
"

echo ""
echo ""

# Comparação
echo "📊 COMPARAÇÃO DIRETA"
echo "===================="
python3 -c "
import json

fixed = json.loads('''$result_fixed''')
kelly = json.loads('''$result_kelly''')

f_ret = fixed['performance']['total_return_pct']
k_ret = kelly['performance']['total_return_pct']
delta_ret = k_ret - f_ret

f_sharpe = fixed['risk_metrics']['sharpe_ratio']
k_sharpe = kelly['risk_metrics']['sharpe_ratio']
delta_sharpe = k_sharpe - f_sharpe

f_dd = fixed['performance']['max_drawdown_pct']
k_dd = kelly['performance']['max_drawdown_pct']
delta_dd = k_dd - f_dd

f_wr = fixed['trade_stats']['win_rate']
k_wr = kelly['trade_stats']['win_rate']
delta_wr = k_wr - f_wr

print(f\"| Métrica       | Fixed Risk | Kelly (25%) | Δ        | Status  |\")
print(f\"|---------------|------------|-------------|----------|---------||\")
print(f\"| Return        | {f_ret:+6.2f}%   | {k_ret:+6.2f}%    | {delta_ret:+5.2f}pp | {'✅ Melhor' if delta_ret > 0 else '🟡 Pior  '} |\")
print(f\"| Sharpe        | {f_sharpe:6.2f}    | {k_sharpe:6.2f}     | {delta_sharpe:+5.2f}   | {'✅ Melhor' if delta_sharpe > 0 else '🟡 Pior  '} |\")
print(f\"| Max DD        | {f_dd:6.2f}%   | {k_dd:6.2f}%    | {delta_dd:+5.2f}pp | {'✅ Menor ' if delta_dd < 0 else '🟡 Maior '} |\")
print(f\"| Win Rate      | {f_wr:6.1f}%   | {k_wr:6.1f}%    | {delta_wr:+5.1f}pp | {'✅ Melhor' if delta_wr > 0 else '🟡 Pior  '} |\")

# Veredito
if delta_ret > 2 and delta_sharpe > 0.1:
    print(f\"\")
    print(f\"🎯 VEREDITO: Kelly SUPERIOR (+{delta_ret:.1f}pp return, +{delta_sharpe:.2f} Sharpe)\")
elif delta_ret > 0:
    print(f\"\")
    print(f\"🟡 VEREDITO: Kelly MARGINAL (+{delta_ret:.1f}pp return)\")
else:
    print(f\"\")
    print(f\"❌ VEREDITO: Kelly INFERIOR ({delta_ret:.1f}pp return)\")
"

echo ""
echo "✅ Teste concluído!"
