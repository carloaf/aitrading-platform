#!/bin/bash
# Script para testar todas as estratégias profissionais

echo "=================================================="
echo "🚀 TESTE DE ESTRATÉGIAS PROFISSIONAIS - AI TRADING"
echo "=================================================="
echo ""

# Configurações
API_URL="http://localhost:3007"
SYMBOL="BTCUSDT"
START_DATE="2023-01-01"
END_DATE="2024-12-01"
INITIAL_CAPITAL=10000

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Lista de estratégias
strategies=(
    "trend_following"
    "mean_reversion"
    "volatility_breakout"
    "macd_rsi_combo"
    "bollinger_bands"
    "momentum"
    "volume_profile"
    "multi_timeframe"
    "dynamic_position_sizing"
)

echo "📊 Testando ${#strategies[@]} estratégias com:"
echo "   Símbolo: $SYMBOL"
echo "   Período: $START_DATE até $END_DATE"
echo "   Capital Inicial: \$$INITIAL_CAPITAL"
echo ""
echo "=================================================="
echo ""

# Função para formatar números
format_number() {
    printf "%.2f" $1
}

# Testar cada estratégia
for strategy in "${strategies[@]}"; do
    echo -n "🔄 Testando ${strategy}..."
    
    # Fazer requisição
    response=$(curl -s -X POST "$API_URL/strategies/$strategy/backtest?symbol=$SYMBOL&initial_capital=$INITIAL_CAPITAL&start_date=$START_DATE&end_date=$END_DATE")
    
    # Verificar se houve erro
    if echo "$response" | jq -e '.detail' > /dev/null 2>&1; then
        error=$(echo "$response" | jq -r '.detail')
        echo -e " ${RED}❌ ERRO${NC}"
        echo "   ↳ $error"
        echo ""
        continue
    fi
    
    # Extrair métricas
    final_capital=$(echo "$response" | jq -r '.final_capital')
    total_return=$(echo "$response" | jq -r '.total_return')
    total_trades=$(echo "$response" | jq -r '.total_trades')
    winning_trades=$(echo "$response" | jq -r '.winning_trades')
    losing_trades=$(echo "$response" | jq -r '.losing_trades')
    win_rate=$(echo "$response" | jq -r '.win_rate')
    
    # Determinar cor baseado no retorno
    if (( $(echo "$total_return > 0" | bc -l) )); then
        color=$GREEN
        icon="✅"
    else
        color=$RED
        icon="❌"
    fi
    
    echo -e " ${icon} ${color}Retorno: ${total_return}%${NC}"
    echo "   ├─ Capital Final: \$$(format_number $final_capital)"
    echo "   ├─ Total de Trades: $total_trades"
    echo "   ├─ Trades Vencedores: $winning_trades"
    echo "   ├─ Trades Perdedores: $losing_trades"
    echo "   └─ Win Rate: $(format_number $win_rate)%"
    echo ""
done

echo "=================================================="
echo "✅ Testes concluídos!"
echo "=================================================="
