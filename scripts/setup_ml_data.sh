#!/bin/bash
# Script para popular banco com trades históricos e verificar saúde dos dados

set -e

CONTAINER="aitrading-execution-engine"

echo "════════════════════════════════════════════════════════════════"
echo "🤖 DATA MANAGEMENT - Gestão de Dados Históricos"
echo "════════════════════════════════════════════════════════════════"

function check_health() {
    echo ""
    echo "🔍 [1/3] Verificando saúde dos dados..."
    docker exec $CONTAINER python3 src/data_health_check.py
}

function download_missing() {
    echo ""
    echo "📥 [2/3] Baixando dados faltantes do Binance..."
    docker exec $CONTAINER python3 src/auto_download_missing_data.py
}

function populate_trades() {
    echo ""
    echo "🤖 [3/3] Populando banco com trades históricos..."
    docker exec $CONTAINER python3 src/populate_historical_trades.py
}

function ml_status() {
    echo ""
    echo "📊 ML TRAINING STATUS:"
    curl -s http://localhost:3008/api/scanner/ml-filter-training-status | jq '.'
}

function full_setup() {
    echo ""
    echo "🚀 FULL SETUP - Executando setup completo..."
    check_health
    
    # Se health check falhou (exit code 1), baixar dados
    if [ $? -eq 1 ]; then
        download_missing
    fi
    
    populate_trades
    ml_status
    
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "✅ SETUP CONCLUÍDO!"
    echo ""
    echo "Próximos passos:"
    echo "  1. Treinar ML Filter:"
    echo "     curl -X POST 'http://localhost:3008/api/scanner/enable-ml-filter?min_score=0.6&min_trades=30'"
    echo ""
    echo "  2. Iniciar scanner:"
    echo "     curl -X POST http://localhost:3008/api/scanner/init \\"
    echo "       -H 'Content-Type: application/json' \\"
    echo "       -d '{\"symbols\": [\"BTCUSDT\", \"ETHUSDT\"], \"timeframes\": [\"1h\"], \"enable_auto_trade\": true}'"
    echo "════════════════════════════════════════════════════════════════"
}

# Menu de opções
case "${1:-full}" in
    health)
        check_health
        ;;
    download)
        download_missing
        ;;
    populate)
        populate_trades
        ;;
    ml-status)
        ml_status
        ;;
    full)
        full_setup
        ;;
    *)
        echo "Uso: $0 [health|download|populate|ml-status|full]"
        echo ""
        echo "Opções:"
        echo "  health     - Verifica saúde dos dados"
        echo "  download   - Baixa dados faltantes do Binance"
        echo "  populate   - Popula banco com trades históricos"
        echo "  ml-status  - Verifica status do ML Filter"
        echo "  full       - Executa setup completo (padrão)"
        exit 1
        ;;
esac
