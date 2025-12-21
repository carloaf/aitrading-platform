#!/bin/bash

# Lista dos 80 símbolos selecionados no scanner (formato Binance com /)
SYMBOLS=(
    "BTC/USDT" "ETH/USDT" "BNB/USDT" "SOL/USDT" "XRP/USDT" "ADA/USDT" "DOGE/USDT" "TRX/USDT"
    "AVAX/USDT" "TON/USDT" "LINK/USDT" "DOT/USDT" "MATIC/USDT" "SHIB/USDT" "LTC/USDT" "BCH/USDT"
    "UNI/USDT" "ATOM/USDT" "XLM/USDT" "ETC/USDT" "NEAR/USDT" "ICP/USDT" "APT/USDT" "FIL/USDT"
    "VET/USDT" "HBAR/USDT" "INJ/USDT" "SUI/USDT" "IMX/USDT" "RENDER/USDT" "ARB/USDT" "OP/USDT"
    "STX/USDT" "MANTA/USDT" "METIS/USDT" "ZK/USDT" "STRK/USDT" "LOOM/USDT" "SKL/USDT" "CELO/USDT"
    "ZETA/USDT" "CYBER/USDT" "GLM/USDT" "CELR/USDT" "CTSI/USDT" "AAVE/USDT" "MKR/USDT" "CRV/USDT"
    "SNX/USDT" "COMP/USDT" "LDO/USDT" "SUSHI/USDT" "1INCH/USDT" "DYDX/USDT" "GMX/USDT" "PENDLE/USDT"
    "JUP/USDT" "RUNE/USDT" "YFI/USDT" "BAL/USDT" "FET/USDT" "AGIX/USDT" "OCEAN/USDT" "TAO/USDT"
    "WLD/USDT" "ARKM/USDT" "GRT/USDT" "NMR/USDT" "IOTX/USDT" "RNDR/USDT" "THETA/USDT" "AR/USDT"
    "KAS/USDT" "SEI/USDT" "TIA/USDT" "ROSE/USDT" "FTM/USDT" "ALGO/USDT" "EGLD/USDT" "FLOW/USDT"
)

echo "======================================"
echo "🔍 ANÁLISE DE COBERTURA DE SÍMBOLOS"
echo "======================================"
echo ""
echo "Total de símbolos esperados: ${#SYMBOLS[@]}"
echo ""

# Get symbols from database
DB_SYMBOLS=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "SELECT symbol FROM market_data_cache ORDER BY symbol;" | tr -d ' ' | grep -v '^$')

# Convert to array
mapfile -t DB_ARRAY <<< "$DB_SYMBOLS"

echo "Símbolos no banco de dados: ${#DB_ARRAY[@]}"
echo ""

# Check missing symbols
MISSING=0
FOUND=0

echo "📊 STATUS POR SÍMBOLO:"
echo "-------------------------------------"

for symbol in "${SYMBOLS[@]}"; do
    if echo "$DB_SYMBOLS" | grep -q "^$symbol$"; then
        echo "✅ $symbol - OK"
        ((FOUND++))
    else
        echo "❌ $symbol - FALTANDO"
        ((MISSING++))
    fi
done

echo ""
echo "======================================"
echo "📈 RESUMO:"
echo "======================================"
echo "✅ Símbolos encontrados: $FOUND"
echo "❌ Símbolos faltando: $MISSING"
echo "📊 Taxa de cobertura: $((FOUND * 100 / ${#SYMBOLS[@]}))%"
echo ""

if [ $MISSING -gt 0 ]; then
    echo "⚠️  AÇÃO NECESSÁRIA:"
    echo "   - Verificar logs do market-data-collector"
    echo "   - Verificar se símbolos faltando existem na Binance"
    echo "   - Considerar adicionar download manual"
fi

# Check data freshness
echo ""
echo "======================================"
echo "🕐 ATUALIZAÇÃO DOS DADOS:"
echo "======================================"

docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
SELECT 
    CASE 
        WHEN EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/60 < 5 THEN '✅ < 5 min'
        WHEN EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/60 < 60 THEN '🟡 < 1 hora'
        ELSE '❌ > 1 hora'
    END as freshness,
    COUNT(*) as symbols
FROM market_data_cache
GROUP BY 1
ORDER BY 1;"

# Check if we have historical data (14h ago)
echo ""
echo "======================================"
echo "📚 DADOS HISTÓRICOS (14 horas atrás):"
echo "======================================"

docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
SELECT 
    COUNT(DISTINCT symbol) as symbols_with_history,
    MIN(timestamp) as oldest_data,
    MAX(timestamp) as newest_data,
    COUNT(*) as total_candles
FROM market_data
WHERE timestamp >= NOW() - INTERVAL '14 hours';"

echo ""
