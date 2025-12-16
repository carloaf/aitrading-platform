#!/bin/bash

# Script de monitoramento do histórico de trading
# Monitora sessões e exibe resumo das métricas

EXECUTION_ENGINE_URL="http://localhost:3008"

echo "=========================================="
echo "📊 MONITOR DE HISTÓRICO DE TRADING"
echo "=========================================="
echo ""

# Buscar todas as sessões
SESSIONS_DATA=$(curl -s "${EXECUTION_ENGINE_URL}/api/history/all-sessions")
TOTAL_SESSIONS=$(echo "$SESSIONS_DATA" | jq -r '.total_sessions // 0')

echo "🔢 Total de Sessões: $TOTAL_SESSIONS"
echo ""

if [ "$TOTAL_SESSIONS" -eq 0 ]; then
    echo "⚠️  Nenhuma sessão encontrada"
    exit 0
fi

# Iterar sobre cada sessão
echo "$SESSIONS_DATA" | jq -r '.sessions[] | @json' | while read -r session; do
    SESSION_ID=$(echo "$session" | jq -r '.session_id')
    STRATEGY=$(echo "$session" | jq -r '.strategy_name')
    SYMBOL=$(echo "$session" | jq -r '.symbol')
    BALANCE=$(echo "$session" | jq -r '.current_balance')
    INITIAL=$(echo "$session" | jq -r '.initial_balance')
    TRADES=$(echo "$session" | jq -r '.total_trades // 0')
    RUNNING=$(echo "$session" | jq -r '.is_running')
    
    # Calcular P&L
    PNL=$(echo "scale=2; $BALANCE - $INITIAL" | bc)
    PNL_PCT=$(echo "scale=2; (($BALANCE - $INITIAL) / $INITIAL) * 100" | bc)
    
    # Status
    if [ "$RUNNING" == "true" ]; then
        STATUS="🟢 ATIVO"
    else
        STATUS="🔴 INATIVO"
    fi
    
    # Cor do P&L
    if (( $(echo "$PNL >= 0" | bc -l) )); then
        PNL_COLOR="✅"
    else
        PNL_COLOR="❌"
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📈 Sessão: $SESSION_ID"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "   Estratégia: $STRATEGY"
    echo "   Símbolo: $SYMBOL"
    echo "   Status: $STATUS"
    echo ""
    echo "💰 Saldo Atual: \$$BALANCE"
    echo "💵 Saldo Inicial: \$$INITIAL"
    echo "$PNL_COLOR P&L: \$$PNL ($PNL_PCT%)"
    echo "📊 Total de Trades: $TRADES"
    
    # Se houver trades, buscar performance detalhada
    if [ "$TRADES" -gt 0 ]; then
        echo ""
        echo "   📉 Métricas Detalhadas:"
        
        PERF_DATA=$(curl -s "${EXECUTION_ENGINE_URL}/api/history/performance/${SESSION_ID}")
        
        WIN_RATE=$(echo "$PERF_DATA" | jq -r '.win_rate // 0')
        SHARPE=$(echo "$PERF_DATA" | jq -r '.sharpe_ratio // 0')
        MAX_DD=$(echo "$PERF_DATA" | jq -r '.max_drawdown // 0')
        PROFIT_FACTOR=$(echo "$PERF_DATA" | jq -r '.profit_factor // 0')
        
        echo "   • Taxa de Acerto: ${WIN_RATE}%"
        echo "   • Sharpe Ratio: $SHARPE"
        echo "   • Max Drawdown: ${MAX_DD}%"
        echo "   • Profit Factor: $PROFIT_FACTOR"
        
        # Buscar últimos 3 trades
        echo ""
        echo "   📜 Últimos 3 Trades:"
        
        TRADES_DATA=$(curl -s "${EXECUTION_ENGINE_URL}/api/history/trades/${SESSION_ID}")
        
        echo "$TRADES_DATA" | jq -r '.trades[:3][] | 
            "      \(.timestamp | split("T")[0]) \((.timestamp | split("T")[1] | split(".")[0])) | \(.trade_type) | \(.symbol) | $\(.price) | P&L: $\(.pnl // 0)"'
    fi
    
    echo ""
done

echo "=========================================="
echo "🔗 Acesse o dashboard em:"
echo "   http://localhost:8081/history"
echo "=========================================="
