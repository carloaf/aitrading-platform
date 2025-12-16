#!/bin/bash
# PASSO 26: WFO Automation - Versão Simplificada
# Executa backtest do mês anterior e analisa resultados

set -e

API_URL="${API_URL:-http://localhost:3008}"
SYMBOL="${SYMBOL:-BTCUSDT}"

echo "🧪 WALK-FORWARD OPTIMIZATION - Mês Anterior"
echo "==========================================="
echo ""

# Calcular mês anterior
DATES=$(python3 << EOF
from datetime import datetime, timedelta
today = datetime.now()
first_this_month = today.replace(day=1)
last_last_month = first_this_month - timedelta(days=1)
first_last_month = last_last_month.replace(day=1)
print(f"{first_last_month.strftime('%Y-%m-%d')} {last_last_month.strftime('%Y-%m-%d')}")
EOF
)

START_DATE=$(echo "$DATES" | cut -d' ' -f1)
END_DATE=$(echo "$DATES" | cut -d' ' -f2)

echo "📅 Período: $START_DATE → $END_DATE"
echo "🪙 Par: $SYMBOL"
echo ""

# Executar backtest
echo "🔄 Executando backtest..."
RESULT=$(curl -sS -X POST "$API_URL/api/meta-backtest/run" \
  -H "Content-Type: application/json" \
  -d "{
    \"symbol\": \"$SYMBOL\",
    \"start_date\": \"$START_DATE\",
    \"end_date\": \"$END_DATE\",
    \"interval\": \"1h\",
    \"initial_capital\": 100000,
    \"max_trades\": 1000
  }")

# Extrair e exibir métricas
python3 << EOF
import json

data = json.loads('''$RESULT''')
perf = data['performance']
risk = data['risk_metrics']
stats = data['trade_stats']

ret = perf['total_return_pct']
sharpe = risk['sharpe_ratio']
sortino = risk['sortino_ratio']
pf = risk['profit_factor']
dd = perf['max_drawdown_pct']
wr = stats['win_rate']
trades = stats['total_trades']

print(f"")
print(f"📊 RESULTADOS:")
print(f"   Return: {ret:+.2f}%")
print(f"   Sharpe: {sharpe:.2f}")
print(f"   Sortino: {sortino:.2f}")
print(f"   Profit Factor: {pf:.2f}")
print(f"   Max DD: {dd:.2f}%")
print(f"   Win Rate: {wr:.1f}%")
print(f"   Trades: {trades}")
print(f"")

# Alertas
print(f"🔔 ALERTAS:")
alerts = []
if sharpe < 0.5:
    alerts.append(f"⚠️  Sharpe {sharpe:.2f} < 0.5 (qualidade baixa)")
if dd > 10:
    alerts.append(f"🔴 Max DD {dd:.2f}% > 10% (risco alto)")
if wr < 45:
    alerts.append(f"⚠️  Win Rate {wr:.1f}% < 45% (eficácia baixa)")
if ret < -2:
    alerts.append(f"🔴 Return {ret:.2f}% < -2% (perda crítica)")

if len(alerts) == 0:
    print("✅ Todas as métricas dentro dos limites")
else:
    for alert in alerts:
        print(f"   {alert}")
print("")

# Recomendação
print(f"🎯 RECOMENDAÇÃO:")
score = 0
if ret < 0: score += 3
if sharpe < 1.0: score += 2
if dd > 10: score += 2
if wr < 50: score += 1

if score >= 5:
    print("🚨 RECALIBRAÇÃO URGENTE")
    print("   → Return negativo + múltiplas métricas degradadas")
elif score >= 3:
    print("⚠️  RECALIBRAÇÃO RECOMENDADA")
    print("   → Ajustar hysteresis, TP, ou min_quality")
elif score >= 1:
    print("🟡 MONITORAMENTO ATIVO")
    print("   → Continuar observando")
else:
    print("✅ OPERANDO NORMALMENTE")
print("")

# Salvar histórico
import os
from datetime import datetime

log_dir = "logs/wfo"
os.makedirs(log_dir, exist_ok=True)

history_file = f"{log_dir}/history.csv"
if not os.path.exists(history_file):
    with open(history_file, 'w') as f:
        f.write("date,start_date,end_date,return,sharpe,sortino,pf,dd,wr,trades\\n")

# Extrair datas da string data
start_date = data['period'].split(' to ')[0]
end_date = data['period'].split(' to ')[1]

with open(history_file, 'a') as f:
    f.write(f"{datetime.now().strftime('%Y-%m-%d')},{start_date},{end_date},{ret:.2f},{sharpe:.2f},{sortino:.2f},{pf:.2f},{dd:.2f},{wr:.1f},{trades}\\n")

print(f"💾 Histórico salvo em: {history_file}")
print("")
print("✅ WFO concluído!")
EOF
