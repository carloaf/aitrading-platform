#!/bin/bash
# Script para testar RSI Divergence em múltiplas moedas
# Data: 23 de Dezembro de 2025

echo "🔍 TESTE RSI DIVERGENCE - MÚLTIPLAS MOEDAS"
echo "=========================================="
echo "Período: 2023-12-23 → 2025-12-23 (2 anos)"
echo "Timeframe: 1h (padrão dos dados)"
echo "Parâmetros: lookback=10, min_strength=0.3, min_adx=15 (recomendados manual)"
echo ""

# Lista de moedas para testar
SYMBOLS=("BTCUSDT" "ETHUSDT" "BNBUSDT" "ADAUSDT" "XRPUSDT" "AVAXUSDT" "SOLUSDT")

# Criar arquivo de resultados
RESULTS_FILE="results_multi_coins_$(date +%Y%m%d_%H%M%S).txt"
echo "📊 RESULTADOS RSI DIVERGENCE - MÚLTIPLAS MOEDAS" > $RESULTS_FILE
echo "Data: $(date)" >> $RESULTS_FILE
echo "Período: 2023-12-23 → 2025-12-23" >> $RESULTS_FILE
echo "Parâmetros Manual (1h): lookback=10, min_strength=0.3, min_adx=15" >> $RESULTS_FILE
echo "===============================================" >> $RESULTS_FILE
echo "" >> $RESULTS_FILE

# Cabeçalho da tabela
printf "%-10s | %8s | %8s | %10s | %7s | %8s | %8s | %6s\n" "SYMBOL" "PATTERNS" "TRADES" "RETURN%" "WR%" "MAX_DD%" "SHARPE" "STATUS"
printf "%-10s | %8s | %8s | %10s | %7s | %8s | %8s | %6s\n" "SYMBOL" "PATTERNS" "TRADES" "RETURN%" "WR%" "MAX_DD%" "SHARPE" "STATUS" >> $RESULTS_FILE
echo "-----------|----------|----------|------------|---------|----------|----------|--------"
echo "-----------|----------|----------|------------|---------|----------|----------|--------" >> $RESULTS_FILE

for SYMBOL in "${SYMBOLS[@]}"; do
    echo "Testando $SYMBOL..." >&2
    
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
    
    # Extrair métricas
    PATTERNS=$(echo $RESULT | jq -r '.pattern_statistics.total_patterns // 0')
    TRADES=$(echo $RESULT | jq -r '.results.total_trades // 0')
    RETURN=$(echo $RESULT | jq -r '.results.total_return_pct // 0')
    WIN_RATE=$(echo $RESULT | jq -r '.results.win_rate // 0')
    MAX_DD=$(echo $RESULT | jq -r '.results.max_drawdown_pct // 0')
    SHARPE=$(echo $RESULT | jq -r '.results.sharpe_ratio // 0')
    
    # Status baseado no retorno
    if (( $(echo "$RETURN > 10" | bc -l) )); then
        STATUS="🟢"
    elif (( $(echo "$RETURN > 0" | bc -l) )); then
        STATUS="🟡"
    else
        STATUS="🔴"
    fi
    
    # Imprimir resultados
    printf "%-10s | %8s | %8s | %10.2f | %7.1f | %8.2f | %8.2f | %6s\n" "$SYMBOL" "$PATTERNS" "$TRADES" "$RETURN" "$WIN_RATE" "$MAX_DD" "$SHARPE" "$STATUS"
    printf "%-10s | %8s | %8s | %10.2f | %7.1f | %8.2f | %8.2f | %6s\n" "$SYMBOL" "$PATTERNS" "$TRADES" "$RETURN" "$WIN_RATE" "$MAX_DD" "$SHARPE" "$STATUS" >> $RESULTS_FILE
    
    sleep 2  # Evitar sobrecarregar a API
done

echo ""
echo "==============================================="
echo "✅ Teste concluído! Resultados salvos em: $RESULTS_FILE"
echo ""
echo "LEGENDA:"
echo "🟢 = Retorno > 10%"
echo "🟡 = Retorno > 0%"
echo "🔴 = Retorno negativo"
echo ""
echo "📋 ANÁLISE MANUAL vs RESULTADO:"
echo "Manual recomenda para 1h: lookback=10, min_adx=15, min_strength=0.3"
echo "Stop Loss: 2.0x ATR | Take Profit: 4.0x ATR"
