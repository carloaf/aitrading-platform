#!/bin/bash
#
# Script para coletar dados históricos usando o container execution-engine
# Executa dentro do container onde já temos todas as dependências Python
#

set -e

echo "======================================================================"
echo "🚀 COLETANDO DADOS HISTÓRICOS DA BINANCE"
echo "======================================================================"
echo ""
echo "📊 Períodos que serão coletados:"
echo "   • 2021: Bull Run"
echo "   • 2022: Bear Market (Crítico para teste SHORT)"
echo "   • 2023: Recovery"
echo "   • 2024: Bull"
echo "   • 2025 Q1: Validação"
echo ""
echo "⏱️  Tempo estimado: 3-5 minutos"
echo ""

# Copiar script para o container
echo "📦 Copiando script para o container..."
docker cp scripts/fetch_historical_data.py aitrading-execution-engine:/app/fetch_historical_data.py

# Executar dentro do container
echo ""
echo "🔄 Executando coleta de dados..."
echo ""
docker exec aitrading-execution-engine python3 fetch_historical_data.py

echo ""
echo "======================================================================"
echo "✅ COLETA COMPLETA!"
echo "======================================================================"
echo ""
echo "🎯 Próximos passos:"
echo "   1. Validar dados: docker exec aitrading-timescaledb psql -U postgres -d trading_data -c \"SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM market_data WHERE symbol='BTCUSDT';\""
echo "   2. Executar testes: python3 test_passo14.py"
echo ""
