#!/bin/bash

# Download 1 ano de dados para 6 moedas com histórico insuficiente
# Data: 23/Dez/2025

echo "=========================================="
echo "DOWNLOAD HISTÓRICO - 6 MOEDAS"
echo "Período: 1 ano (Jan/2024 - Dez/2025)"
echo "=========================================="
echo ""

SYMBOLS=("PENDLEUSDT" "ZETAUSDT" "KASUSDT" "SUSHIUSDT" "SKLUSDT" "THETAUSDT")
START_DATE="2024-01-01"
END_DATE="2025-12-23"
TIMEFRAME="1h"

for SYMBOL in "${SYMBOLS[@]}"; do
    echo "📊 Baixando $SYMBOL..."
    
    # Formato: python3 script.py <symbol> <timeframe> <start_date> <end_date>
    # Converte PENDLEUSDT para PENDLE/USDT
    SYMBOL_FORMATTED="${SYMBOL:0:$((${#SYMBOL}-4))}/${SYMBOL: -4}"
    
    docker exec aitrading-execution-engine python3 /app/src/download_historical_data.py \
        "$SYMBOL_FORMATTED" "$TIMEFRAME" "$START_DATE" "$END_DATE"
    
    if [ $? -eq 0 ]; then
        echo "  ✅ Sucesso: $SYMBOL"
    else
        echo "  ❌ Erro: $SYMBOL"
    fi
    echo ""
    sleep 2  # Rate limit protection
done

echo "=========================================="
echo "VALIDANDO DADOS BAIXADOS"
echo "=========================================="
echo ""

for SYMBOL in "${SYMBOLS[@]}"; do
    COUNT=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c \
        "SELECT COUNT(*) FROM market_data WHERE symbol = '$SYMBOL';" | tr -d ' ')
    
    FIRST=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c \
        "SELECT MIN(timestamp) FROM market_data WHERE symbol = '$SYMBOL';" | xargs)
    
    LAST=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c \
        "SELECT MAX(timestamp) FROM market_data WHERE symbol = '$SYMBOL';" | xargs)
    
    echo "$SYMBOL: $COUNT candles ($FIRST → $LAST)"
done

echo ""
echo "✅ Download concluído!"
