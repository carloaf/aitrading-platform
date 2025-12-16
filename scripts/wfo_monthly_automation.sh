#!/bin/bash
# PASSO 26: Walk-Forward Optimization Automation para 2026
# Executa WFO mensal, detecta degradação e recomenda recalibração

set -e

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================
API_URL="${API_URL:-http://localhost:3008}"
SYMBOL="${SYMBOL:-BTCUSDT}"
TIMEFRAME="${TIMEFRAME:-1h}"
INITIAL_CAPITAL="${INITIAL_CAPITAL:-100000}"

# Thresholds de alerta
ALERT_SHARPE_MIN=0.5          # Sharpe < 0.5 = alerta
ALERT_DD_MAX=10.0             # DD > 10% = alerta
ALERT_WIN_RATE_MIN=45.0       # Win rate < 45% = alerta
ALERT_RETURN_MIN=-2.0         # Return < -2% = alerta crítico
DEGRADATION_THRESHOLD=-20     # -20% return vs mês anterior = degradação

# Log file
LOG_DIR="logs/wfo"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/wfo_$(date +%Y%m).log"

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

# Calcula o primeiro e último dia do mês anterior
get_previous_month() {
    python3 -c "
from datetime import datetime, timedelta
today = datetime.now()
first_this_month = today.replace(day=1)
last_last_month = first_this_month - timedelta(days=1)
first_last_month = last_last_month.replace(day=1)
print(first_last_month.strftime('%Y-%m-%d'), last_last_month.strftime('%Y-%m-%d'))
"
}

# Executa backtest via API
run_backtest() {
    local start_date=$1
    local end_date=$2
    local params=${3:-""}
    
    log "Executando backtest: $start_date → $end_date"
    
    # Construir JSON dinâmicamente
    local json_payload="{
        \"symbol\": \"$SYMBOL\",
        \"start_date\": \"$start_date\",
        \"end_date\": \"$end_date\",
        \"interval\": \"$TIMEFRAME\",
        \"initial_capital\": $INITIAL_CAPITAL,
        \"max_trades\": 1000,
        \"include_trades\": false
    }"
    
    curl -sS -X POST "$API_URL/api/meta-backtest/run" \
        -H "Content-Type: application/json" \
        -d "$json_payload"
}

# Extrai métricas do resultado JSON
extract_metrics() {
    python3 -c "
import json, sys
data = json.load(sys.stdin)
perf = data['performance']
risk = data['risk_metrics']
stats = data['trade_stats']
print(f\"{perf['total_return_pct']:.2f}\")
print(f\"{risk['sharpe_ratio']:.2f}\")
print(f\"{risk['sortino_ratio']:.2f}\")
print(f\"{risk['profit_factor']:.2f}\")
print(f\"{perf['max_drawdown_pct']:.2f}\")
print(f\"{stats['win_rate']:.1f}\")
print(f\"{stats['total_trades']}\")
"
}

# Detecta degradação comparando com mês anterior
check_degradation() {
    local current_return=$1
    local previous_return=$2
    
    python3 -c "
current = float('$current_return')
previous = float('$previous_return')

if previous == 0:
    print('N/A')
    exit(0)

degradation_pct = ((current - previous) / abs(previous)) * 100

if degradation_pct < $DEGRADATION_THRESHOLD:
    print(f'CRITICAL: {degradation_pct:.1f}% degradação')
    exit(2)
elif current < $ALERT_RETURN_MIN:
    print(f'WARNING: Return {current:.2f}% < {$ALERT_RETURN_MIN}%')
    exit(1)
else:
    print(f'OK: {degradation_pct:+.1f}% vs mês anterior')
    exit(0)
"
}

# Gera alertas baseado em thresholds
generate_alerts() {
    local ret=$1
    local sharpe=$2
    local dd=$3
    local wr=$4
    
    python3 -c "
ret = float('$ret')
sharpe = float('$sharpe')
dd = float('$dd')
wr = float('$wr')

alerts = []

if sharpe < $ALERT_SHARPE_MIN:
    alerts.append(f'⚠️  Sharpe {sharpe:.2f} < {$ALERT_SHARPE_MIN} (qualidade baixa)')

if dd > $ALERT_DD_MAX:
    alerts.append(f'🔴 Max DD {dd:.2f}% > {$ALERT_DD_MAX}% (risco alto)')

if wr < $ALERT_WIN_RATE_MIN:
    alerts.append(f'⚠️  Win Rate {wr:.1f}% < {$ALERT_WIN_RATE_MIN}% (eficácia baixa)')

if ret < $ALERT_RETURN_MIN:
    alerts.append(f'🔴 Return {ret:.2f}% < {$ALERT_RETURN_MIN}% (perda crítica)')

if len(alerts) == 0:
    print('✅ Todas as métricas dentro dos limites')
else:
    print('\\n'.join(alerts))
"
}

# Recomendação de recalibração
recommend_recalibration() {
    local ret=$1
    local sharpe=$2
    local dd=$3
    local wr=$4
    
    python3 -c "
ret = float('$ret')
sharpe = float('$sharpe')
dd = float('$dd')
wr = float('$wr')

score = 0
if ret < 0: score += 3
if sharpe < 1.0: score += 2
if dd > 10: score += 2
if wr < 50: score += 1

if score >= 5:
    print('🚨 RECALIBRAÇÃO URGENTE RECOMENDADA')
    print('   → Return negativo + múltiplas métricas degradadas')
    print('   → Ação: Revisar parâmetros ou pausar trading')
elif score >= 3:
    print('⚠️  RECALIBRAÇÃO RECOMENDADA')
    print('   → Métricas abaixo do esperado')
    print('   → Ação: Ajustar hysteresis, TP multipliers, ou min_quality')
elif score >= 1:
    print('🟡 MONITORAMENTO ATIVO')
    print('   → Algumas métricas precisam atenção')
    print('   → Ação: Continuar monitorando próximo mês')
else:
    print('✅ SISTEMA OPERANDO NORMALMENTE')
    print('   → Sem necessidade de recalibração')
"
}

# ============================================================================
# MAIN WORKFLOW
# ============================================================================

main() {
    log "=========================================="
    log "WALK-FORWARD OPTIMIZATION - 2026"
    log "=========================================="
    log ""
    
    # 1. Obter período do mês anterior
    read -r START_DATE END_DATE < <(get_previous_month)
    log "📅 Período: $START_DATE → $END_DATE"
    log ""
    
    # 2. Executar backtest do mês anterior
    log "🔄 Executando backtest..."
    result=$(run_backtest "$START_DATE" "$END_DATE" "")
    
    if [ $? -ne 0 ]; then
        log_error "Falha ao executar backtest"
        echo "$result" >> "$LOG_FILE"
        exit 1
    fi
    
    # 3. Extrair métricas
    metrics=$(echo "$result" | extract_metrics)
    RETURN=$(echo "$metrics" | sed -n '1p')
    SHARPE=$(echo "$metrics" | sed -n '2p')
    SORTINO=$(echo "$metrics" | sed -n '3p')
    PF=$(echo "$metrics" | sed -n '4p')
    DD=$(echo "$metrics" | sed -n '5p')
    WR=$(echo "$metrics" | sed -n '6p')
    TRADES=$(echo "$metrics" | sed -n '7p')
    
    log "📊 RESULTADOS:"
    log "   Return: $RETURN%"
    log "   Sharpe: $SHARPE"
    log "   Sortino: $SORTINO"
    log "   Profit Factor: $PF"
    log "   Max DD: $DD%"
    log "   Win Rate: $WR%"
    log "   Trades: $TRADES"
    log ""
    
    # 4. Verificar degradação (comparar com histórico se disponível)
    HISTORY_FILE="$LOG_DIR/history.csv"
    if [ -f "$HISTORY_FILE" ]; then
        PREV_RETURN=$(tail -1 "$HISTORY_FILE" | cut -d',' -f3)
        log "📉 ANÁLISE DE DEGRADAÇÃO:"
        degradation_msg=$(check_degradation "$RETURN" "$PREV_RETURN")
        degradation_status=$?
        log "   $degradation_msg"
        log ""
    fi
    
    # 5. Gerar alertas
    log "🔔 ALERTAS:"
    alerts=$(generate_alerts "$RETURN" "$SHARPE" "$DD" "$WR")
    log "$alerts"
    log ""
    
    # 6. Recomendação de recalibração
    log "🎯 RECOMENDAÇÃO:"
    recommendation=$(recommend_recalibration "$RETURN" "$SHARPE" "$DD" "$WR")
    log "$recommendation"
    log ""
    
    # 7. Salvar histórico
    if [ ! -f "$HISTORY_FILE" ]; then
        echo "date,start_date,end_date,return,sharpe,sortino,pf,dd,wr,trades" > "$HISTORY_FILE"
    fi
    echo "$(date +%Y-%m-%d),$START_DATE,$END_DATE,$RETURN,$SHARPE,$SORTINO,$PF,$DD,$WR,$TRADES" >> "$HISTORY_FILE"
    log "💾 Histórico salvo em: $HISTORY_FILE"
    
    # 8. Exit code baseado em alertas críticos
    if [ "$degradation_status" = "2" ] || [[ "$alerts" == *"🔴"* ]]; then
        log_error "Alertas críticos detectados!"
        exit 2
    elif [ "$degradation_status" = "1" ] || [[ "$alerts" == *"⚠️"* ]]; then
        log "Alertas moderados detectados"
        exit 1
    fi
    
    log "✅ WFO concluído com sucesso"
    exit 0
}

# ============================================================================
# EXECUÇÃO
# ============================================================================

main "$@"
