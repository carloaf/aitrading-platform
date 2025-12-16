#!/bin/bash

# Script de monitoramento das sessões de paper trading

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 PAPER TRADING - DASHBOARD DE MONITORAMENTO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Array com as sessões
sessions=(
    "macd_rsi_live:MACD+RSI:BTCUSDT:5m:3000:26"
    "momentum_live_v2:Momentum:BTCUSDT:1m:2000:20"
    "trend_btc_live:TrendFollow:BTCUSDT:15m:3500:55"
    "volatility_sol_live:Volatility:SOLUSDT:5m:2000:14"
    "bollinger_eth_live:Bollinger:ETHUSDT:15m:2500:20"
)

total_balance=0
total_pnl=0

for session_info in "${sessions[@]}"; do
    IFS=':' read -r session_id strategy symbol timeframe initial candles_needed <<< "$session_info"
    
    # Buscar status
    status=$(curl -s "http://localhost:3008/paper-trading/$session_id/status" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        balance=$(echo "$status" | jq -r '.account_summary.balance // 0')
        pnl=$(echo "$status" | jq -r '.account_summary.total_pnl // 0')
        pnl_pct=$(echo "$status" | jq -r '.account_summary.total_pnl_percent // 0')
        candles=$(echo "$status" | jq -r '.candles_collected // 0')
        signals=$(echo "$status" | jq -r '.signals_generated // 0')
        trades=$(echo "$status" | jq -r '.trades_executed // 0')
        position=$(echo "$status" | jq -r '.position_open // false')
        running=$(echo "$status" | jq -r '.is_running // false')
        
        # Status indicator
        if [ "$running" = "true" ]; then
            status_icon="✅"
        else
            status_icon="❌"
        fi
        
        # Position indicator
        if [ "$position" = "true" ]; then
            pos_icon="📈"
        else
            pos_icon="💤"
        fi
        
        # Candles progress
        if [ "$candles" -ge "$candles_needed" ]; then
            candle_status="🟢 READY"
        else
            candle_status="🟡 $candles/$candles_needed"
        fi
        
        # PnL color
        if (( $(echo "$pnl > 0" | bc -l) )); then
            pnl_color="🟢"
        elif (( $(echo "$pnl < 0" | bc -l) )); then
            pnl_color="🔴"
        else
            pnl_color="⚪"
        fi
        
        printf "%-15s %s %-13s | %-15s | %12s\n" \
            "$strategy" \
            "$status_icon" \
            "$symbol/$timeframe" \
            "$candle_status" \
            "\$$balance"
        
        printf "    %s P&L: %s\$%.2f (%.2f%%) | Trades: %d | Sinais: %d\n" \
            "$pnl_color" "$pos_icon" "$pnl" "$pnl_pct" "$trades" "$signals"
        echo ""
        
        total_balance=$(echo "$total_balance + $balance" | bc)
        total_pnl=$(echo "$total_pnl + $pnl" | bc)
    else
        echo "❌ $strategy: Erro ao conectar"
        echo ""
    fi
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "💰 TOTAL: \$%.2f | P&L: \$%.2f | Capital Inicial: \$13,000.00\n" "$total_balance" "$total_pnl"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Dashboard Web: http://localhost:8081/trading-dashboard"
echo "📡 API Docs: http://localhost:3008/docs"
echo ""
