#!/bin/bash
# Teste rápido das moedas com possível divergência bullish
# 23 de Dezembro de 2025

SYMBOLS=("ETHUSDT" "UNIUSDT" "PENDLEUSDT" "ZETAUSDT" "KASUSDT" "SUSHIUSDT" "SKLUSDT" "THETAUSDT")

echo "🔍 TESTE RSI DIVERGENCE - MOEDAS COM SINAIS IMINENTES"
echo "======================================================"
printf "%-12s | %8s | %8s | %10s | %7s\n" "SYMBOL" "PATTERNS" "TRADES" "RETURN%" "WR%"
echo "-------------|----------|----------|------------|--------"

for SYMBOL in "${SYMBOLS[@]}"; do
    RESULT=$(curl -s -X POST "http://localhost:3008/api/backtest/rsi-divergence" \
      -H "Content-Type: application/json" \
      -d "{
        \"symbol\": \"$SYMBOL\",
        \"start_date\": \"2023-12-23\",
        \"end_date\": \"2025-12-23\",
        \"timeframe\": \"1h\",
        \"initial_capital\": 100000,
        \"lookback_periods\": 10,
        \"min_adx_trend\": 15,
        \"min_signal_strength\": 0.3
      }")
    
    PATTERNS=$(echo $RESULT | jq -r '.pattern_statistics.total_patterns // 0')
    TRADES=$(echo $RESULT | jq -r '.results.total_trades // 0')
    RETURN=$(echo $RESULT | jq -r '.results.total_return_pct // 0')
    WIN_RATE=$(echo $RESULT | jq -r '.results.win_rate // 0')
    
    printf "%-12s | %8s | %8s | %10.2f | %7.1f\n" "$SYMBOL" "$PATTERNS" "$TRADES" "$RETURN" "$WIN_RATE"
done

echo ""
echo "✅ Teste concluído!"
echo "💡 Manual recomenda: lookback=10, min_strength=0.3, min_adx=15 (1h timeframe)"
