#!/bin/bash
# Backtest RSI Divergence - Multi-Par + Multi-Timeframe
# Símbolos: BTC, ETH, SOL, BNB, XRP, ADA, AVAX, DOT, MATIC, LINK
# Timeframes: 1h, 4h, 1d

API_URL="http://localhost:3008"

SYMBOLS=("BTCUSDT" "ETHUSDT" "SOLUSDT" "BNBUSDT" "XRPUSDT" "ADAUSDT" "AVAXUSDT" "DOTUSDT" "MATICUSDT" "LINKUSDT")
TIMEFRAMES=("1h" "4h" "1d")

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║      BACKTEST RSI DIVERGENCE - MULTI-PAR + MULTI-TIMEFRAME                   ║"
echo "║      Período: 2021-01-01 a 2024-12-31 (4 anos)                               ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Criar arquivo de resultados
RESULTS_FILE="/tmp/backtest_results_$(date +%Y%m%d_%H%M%S).csv"
echo "Symbol,Timeframe,Return%,Sharpe,MaxDD%,WinRate%,Trades,TP,SL" > $RESULTS_FILE

for TF in "${TIMEFRAMES[@]}"; do
    echo ""
    echo "┌──────────────────────────────────────────────────────────────────────────────┐"
    echo "│  TIMEFRAME: $TF                                                              │"
    echo "├──────────────────────────────────────────────────────────────────────────────┤"
    printf "│ %-12s │ %8s │ %7s │ %7s │ %8s │ %6s │ %4s │ %4s │\n" "SYMBOL" "RETURN" "SHARPE" "MAX DD" "WIN RATE" "TRADES" "TP" "SL"
    echo "├──────────────────────────────────────────────────────────────────────────────┤"
    
    TF_TOTAL_RETURN=0
    TF_TOTAL_TRADES=0
    TF_COUNT=0
    
    for SYMBOL in "${SYMBOLS[@]}"; do
        # Chamar API de backtest RSI Divergence
        RESULT=$(curl -s -X POST "$API_URL/api/backtest/rsi-divergence" \
            -H "Content-Type: application/json" \
            -d "{
                \"symbol\": \"$SYMBOL\",
                \"start_date\": \"2021-01-01\",
                \"end_date\": \"2024-12-31\",
                \"timeframe\": \"$TF\",
                \"initial_capital\": 10000,
                \"risk_per_trade\": 0.02,
                \"stop_loss_atr_mult\": 2.0,
                \"take_profit_atr_mult\": 4.0,
                \"min_signal_strength\": 0.25
            }" 2>/dev/null)
        
        if [ -z "$RESULT" ] || echo "$RESULT" | grep -q "error"; then
            printf "│ %-12s │ %8s │ %7s │ %7s │ %8s │ %6s │ %4s │ %4s │\n" "$SYMBOL" "ERROR" "-" "-" "-" "-" "-" "-"
            continue
        fi
        
        # Extrair métricas
        RETURN=$(echo $RESULT | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('total_return_pct', 0):.2f}\")" 2>/dev/null || echo "0.00")
        SHARPE=$(echo $RESULT | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('sharpe_ratio', 0):.2f}\")" 2>/dev/null || echo "0.00")
        MAXDD=$(echo $RESULT | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('max_drawdown_pct', 0):.2f}\")" 2>/dev/null || echo "0.00")
        WINRATE=$(echo $RESULT | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('win_rate', 0)*100:.1f}\")" 2>/dev/null || echo "0.0")
        TRADES=$(echo $RESULT | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_trades', 0))" 2>/dev/null || echo "0")
        TP=$(echo $RESULT | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('take_profits', 0))" 2>/dev/null || echo "0")
        SL=$(echo $RESULT | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stop_losses', 0))" 2>/dev/null || echo "0")
        
        # Colorir baseado no retorno
        if (( $(echo "$RETURN > 0" | bc -l) )); then
            COLOR="\033[0;32m"  # Verde
        else
            COLOR="\033[0;31m"  # Vermelho
        fi
        RESET="\033[0m"
        
        printf "│ %-12s │ ${COLOR}%7s%%${RESET} │ %7s │ %6s%% │ %7s%% │ %6s │ %4s │ %4s │\n" \
            "$SYMBOL" "$RETURN" "$SHARPE" "$MAXDD" "$WINRATE" "$TRADES" "$TP" "$SL"
        
        # Salvar em CSV
        echo "$SYMBOL,$TF,$RETURN,$SHARPE,$MAXDD,$WINRATE,$TRADES,$TP,$SL" >> $RESULTS_FILE
        
        # Acumular totais
        TF_TOTAL_RETURN=$(echo "$TF_TOTAL_RETURN + $RETURN" | bc -l)
        TF_TOTAL_TRADES=$(echo "$TF_TOTAL_TRADES + $TRADES" | bc)
        TF_COUNT=$((TF_COUNT + 1))
        
        sleep 0.5  # Rate limiting
    done
    
    # Média do timeframe
    if [ $TF_COUNT -gt 0 ]; then
        AVG_RETURN=$(echo "scale=2; $TF_TOTAL_RETURN / $TF_COUNT" | bc)
        echo "├──────────────────────────────────────────────────────────────────────────────┤"
        printf "│ %-12s │ %7s%% │ %7s │ %7s │ %8s │ %6s │ %4s │ %4s │\n" \
            "MÉDIA $TF" "$AVG_RETURN" "-" "-" "-" "$TF_TOTAL_TRADES" "-" "-"
    fi
    echo "└──────────────────────────────────────────────────────────────────────────────┘"
done

echo ""
echo "📊 Resultados salvos em: $RESULTS_FILE"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
