#!/bin/bash
# Script para popular dados históricos de múltiplos símbolos
# Baixa dados de 2021-2024 para os 73 símbolos que têm apenas ~8 dias de dados

set -e

echo "=================================================="
echo "DOWNLOAD DE DADOS HISTÓRICOS - MULTI-SÍMBOLO"
echo "Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="
echo ""

# Lista de símbolos para popular (excluindo descontinuados e os que já têm dados completos)
SYMBOLS=(
    "1INCHUSDT" "AAVEUSDT" "ADAUSDT" "ALGOUSDT" "APTUSDT" "ARBUSDT" "ARKMUSDT"
    "ARUSDT" "ATOMUSDT" "AVAXUSDT" "BCHUSDT" "BNBUSDT" "BONKUSDT"
    "CELOUSDT" "CELRUSDT" "COMPUSDT" "CRVUSDT" "CTSIUSDT" "CYBERUSDT"
    "DOGEUSDT" "DOTUSDT" "DYDXUSDT" "EGLDUSDT" "ETCUSDT" "FETUSDT"
    "FILUSDT" "FLOKIUSDT" "FLOWUSDT" "GLMUSDT" "GMXUSDT" "GRTUSDT"
    "HBARUSDT" "ICPUSDT" "IMXUSDT" "INJUSDT" "IOTXUSDT" "JUPUSDT"
    "KASUSDT" "LDOUSDT" "LINKUSDT" "LTCUSDT" "MANTAUSDT" "METISUSDT"
    "NEARUSDT" "NMRUSDT" "OPUSDT" "PENDLEUSDT" "PEPEUSDT" "RENDERUSDT"
    "ROSEUSDT" "RUNEUSDT" "SEIUSDT" "SHIBUSDT" "SKLUSDT" "SNXUSDT"
    "STRKUSDT" "STXUSDT" "SUIUSDT" "SUSHIUSDT" "TAOUSDT" "THETAUSDT"
    "TIAUSDT" "TONUSDT" "TRXUSDT" "UNIUSDT" "VETUSDT" "WIFUSDT"
    "WLDUSDT" "XLMUSDT" "XRPUSDT" "YFIUSDT" "ZETAUSDT" "ZKUSDT"
)

# Símbolos descontinuados (para remover depois)
DEPRECATED_SYMBOLS=("MATICUSDT" "AGIXUSDT" "OCEANUSDT" "LOOMUSDT" "MKRUSDT" "BALUSDT" "FTMUSDT")

# Configurações
START_DATE="2021-01-01"
END_DATE="2024-12-31"
TIMEFRAMES=("1h" "4h" "1d")

# Contadores
TOTAL_SYMBOLS=${#SYMBOLS[@]}
SUCCESS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

echo "📊 Configuração:"
echo "  Símbolos: $TOTAL_SYMBOLS"
echo "  Período: $START_DATE até $END_DATE"
echo "  Timeframes: ${TIMEFRAMES[*]}"
echo ""

# Função para baixar dados de um símbolo
download_symbol() {
    local symbol=$1
    local timeframe=$2
    local symbol_num=$3
    
    echo ""
    echo "[$symbol_num/$TOTAL_SYMBOLS] 📥 Baixando $symbol ($timeframe)..."
    
    # Verificar se já tem dados suficientes
    CANDLE_COUNT=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
        SELECT COUNT(*) FROM market_data 
        WHERE symbol = '$symbol' AND source = 'binance_$timeframe'
    " 2>/dev/null | tr -d ' ')
    
    if [ ! -z "$CANDLE_COUNT" ] && [ "$CANDLE_COUNT" -gt 5000 ]; then
        echo "  ⏭️  SKIP: Já tem $CANDLE_COUNT candles (suficiente)"
        return 2
    fi
    
    # Executar download
    docker exec aitrading-execution-engine python /app/download_historical_data.py \
        "${symbol/USDT//USDT}" \
        "$timeframe" \
        "$START_DATE" \
        "$END_DATE" 2>&1 | tail -n 5
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "  ✅ Sucesso: $symbol ($timeframe)"
        return 0
    else
        echo "  ❌ Erro ao baixar $symbol ($timeframe)"
        return 1
    fi
}

# Loop pelos símbolos
symbol_num=0
for symbol in "${SYMBOLS[@]}"; do
    symbol_num=$((symbol_num + 1))
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Processando: $symbol ($symbol_num/$TOTAL_SYMBOLS)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    symbol_success=0
    symbol_skip=0
    
    # Baixar cada timeframe
    for timeframe in "${TIMEFRAMES[@]}"; do
        download_symbol "$symbol" "$timeframe" "$symbol_num"
        result=$?
        
        if [ $result -eq 0 ]; then
            symbol_success=$((symbol_success + 1))
        elif [ $result -eq 2 ]; then
            symbol_skip=$((symbol_skip + 1))
        fi
        
        # Pequeno delay entre requests
        sleep 1
    done
    
    # Contabilizar resultado do símbolo
    if [ $symbol_success -gt 0 ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    elif [ $symbol_skip -eq ${#TIMEFRAMES[@]} ]; then
        SKIP_COUNT=$((SKIP_COUNT + 1))
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # Delay entre símbolos para respeitar rate limits
    sleep 2
done

echo ""
echo "=================================================="
echo "RELATÓRIO FINAL"
echo "=================================================="
echo "  Total processados: $TOTAL_SYMBOLS símbolos"
echo "  ✅ Sucesso: $SUCCESS_COUNT símbolos"
echo "  ⏭️  Pulados: $SKIP_COUNT símbolos (já tinham dados)"
echo "  ❌ Falhas: $FAIL_COUNT símbolos"
echo ""

# Executar relatório final de cobertura
echo "📊 Verificando cobertura final..."
./check_market_data.sh

echo ""
echo "🎉 Download de dados históricos concluído!"
echo "=================================================="
