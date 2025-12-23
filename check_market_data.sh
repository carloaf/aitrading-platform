#!/bin/bash
# Script para verificar cobertura de dados no TimescaleDB

echo "=================================================="
echo "RELATÓRIO DE COBERTURA DE DADOS - TimescaleDB"
echo "Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="
echo ""

# Total geral
echo "📊 RESUMO GERAL:"
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
SELECT '  Total de símbolos: ' || COUNT(DISTINCT symbol) || ' símbolos' FROM market_data;
"
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
SELECT '  Total de candles: ' || COUNT(*) || ' candles' FROM market_data;
"
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
SELECT '  Timeframes únicos: ' || COUNT(DISTINCT source) || ' timeframes' FROM market_data;
"

echo ""
echo "📈 SÍMBOLOS COM DADOS COMPLETOS (>1000 candles):"
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
SELECT 
    '  ' || symbol || ': ' || total_candles || ' candles (' || dias || ' dias)'
FROM (
    SELECT 
        symbol,
        SUM(total) as total_candles,
        ROUND(EXTRACT(EPOCH FROM (MAX(periodo_fim) - MIN(periodo_inicio))) / 86400, 0) as dias
    FROM (
        SELECT 
            symbol,
            source,
            COUNT(*) as total,
            MIN(timestamp) as periodo_inicio,
            MAX(timestamp) as periodo_fim
        FROM market_data
        GROUP BY symbol, source
    ) subquery
    GROUP BY symbol
) summary
WHERE total_candles >= 1000
ORDER BY total_candles DESC;
"

echo ""
echo "🟡 SÍMBOLOS COM DADOS RECENTES (~200 candles, últimos 8 dias):"
count=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
SELECT COUNT(*)
FROM (
    SELECT symbol, SUM(total) as total_candles
    FROM (
        SELECT symbol, source, COUNT(*) as total
        FROM market_data
        GROUP BY symbol, source
    ) subquery
    GROUP BY symbol
) summary
WHERE total_candles >= 200 AND total_candles < 1000;
")
echo "  Total: $count símbolos"

echo ""
echo "❌ SÍMBOLOS COM DADOS INSUFICIENTES (<10 candles):"
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
SELECT 
    '  ' || symbol || ': ' || total_candles || ' candles'
FROM (
    SELECT 
        symbol,
        SUM(total) as total_candles
    FROM (
        SELECT 
            symbol,
            source,
            COUNT(*) as total
        FROM market_data
        GROUP BY symbol, source
    ) subquery
    GROUP BY symbol
) summary
WHERE total_candles < 10
ORDER BY total_candles ASC;
"

echo ""
echo "📊 DISTRIBUIÇÃO POR TIMEFRAME:"
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
SELECT 
    '  ' || source || ': ' || COUNT(DISTINCT symbol) || ' símbolos, ' || COUNT(*) || ' candles'
FROM market_data
GROUP BY source
ORDER BY source;
"

echo ""
echo "=================================================="
echo "✅ Análise Completa"
echo "=================================================="
