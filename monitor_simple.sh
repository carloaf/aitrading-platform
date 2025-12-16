#!/bin/bash

# Forçar locale inglês para números decimais
export LC_NUMERIC=C

# Script simplificado para monitorar paper trading
SESSION_ID="$1"

if [ -z "$SESSION_ID" ]; then
    echo "❌ Uso: $0 <session_id>"
    echo ""
    echo "Sessões ativas:"
    curl -s http://localhost:3008/paper-trading/sessions | jq -r '.sessions[] | "  - \(.session_id) (\(.strategy))"'
    exit 1
fi

API_URL="http://localhost:3008"

echo "📊 MONITORANDO: $SESSION_ID"
echo "Atualizando a cada 30 segundos (Ctrl+C para parar)"
echo ""

while true; do
    clear
    echo "═══════════════════════════════════════════════════════════"
    echo " 🚀 PAPER TRADING - $(date '+%H:%M:%S')"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    
    status=$(curl -s $API_URL/paper-trading/$SESSION_ID/status 2>/dev/null)
    
    if [ $? -ne 0 ] || [ -z "$status" ]; then
        echo "❌ Erro ao conectar com API"
        sleep 30
        continue
    fi
    
    # Extrair dados
    uptime=$(echo "$status" | jq -r '.uptime_seconds // 0')
    candles=$(echo "$status" | jq -r '.candles_collected // 0')
    signals=$(echo "$status" | jq -r '.signals_generated // 0')
    trades=$(echo "$status" | jq -r '.trades_executed // 0')
    balance=$(echo "$status" | jq -r '.account_summary.balance // 1000')
    pnl=$(echo "$status" | jq -r '.account_summary.total_pnl // 0')
    pnl_pct=$(echo "$status" | jq -r '.account_summary.total_pnl_percent // 0')
    
    uptime_min=$(echo "$uptime" | awk '{printf "%.0f", $1 / 60}')
    
    echo "⏱️  Tempo: ${uptime_min} minutos"
    echo "📊 Candles: $candles | Sinais: $signals | Trades: $trades"
    echo ""
    printf "💰 Balance: \$%.2f\n" "$balance"
    printf "📈 PnL: \$%.2f (%.2f%%)\n" "$pnl" "$pnl_pct"
    echo ""
    
    # Posições
    positions=$(curl -s $API_URL/paper-trading/$SESSION_ID/positions 2>/dev/null)
    pos_count=$(echo "$positions" | jq 'length' 2>/dev/null || echo "0")
    
    if [ "$pos_count" -gt 0 ]; then
        echo "📍 POSIÇÕES ABERTAS:"
        echo "$positions" | jq -r '.[] | "  \(.symbol): \(.quantity) @ \(.entry_price) | PnL: \(.unrealized_pnl)"'
    else
        echo "📍 Nenhuma posição aberta"
    fi
    
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "Próxima atualização em 30s..."
    
    sleep 30
done
