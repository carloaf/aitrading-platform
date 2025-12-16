#!/bin/bash
# ==============================================================================
# VALIDAÇÃO MULTI-PAR OBRIGATÓRIA
# ==============================================================================
# TODA estratégia ou ajuste deve ser validado em BTC, ETH e SOL
# 
# Uso:
#   bash scripts/validate_multipar.sh [STRATEGY_NAME] [START_DATE] [END_DATE]
#
# Exemplo:
#   bash scripts/validate_multipar.sh "kelly" "2023-01-01" "2023-12-31"
#   bash scripts/validate_multipar.sh "wfo_q3" "2025-07-01" "2025-09-30"
#
# Autor: CryptoDev Assistant
# Data: 16/Dez/2025
# ==============================================================================

set -e  # Exit on error

# Parâmetros
STRATEGY=${1:-"default"}
START_DATE=${2:-"2023-01-01"}
END_DATE=${3:-"2023-12-31"}
API_URL="http://localhost:3008/api/meta-backtest/run"

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     VALIDAÇÃO MULTI-PAR OBRIGATÓRIA - $STRATEGY             ${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo -e "${YELLOW}⚠️  REGRA: Todo backtest deve validar em BTC + ETH + SOL${NC}"
echo -e "${YELLOW}    Período: $START_DATE → $END_DATE${NC}"
echo ""

# Arrays para armazenar resultados
declare -a SYMBOLS=("BTCUSDT" "ETHUSDT" "SOLUSDT")
declare -a RETURNS=()
declare -a SHARPES=()
declare -a MAX_DDS=()
declare -a WIN_RATES=()
declare -a TRADES=()

# Função para executar backtest
run_backtest() {
    local SYMBOL=$1
    echo -e "${BLUE}📊 Testing $SYMBOL...${NC}"
    
    # Executa backtest
    RESULT=$(curl -sS "$API_URL" \
      -H 'Content-Type: application/json' \
      -d "{
        \"symbol\": \"$SYMBOL\",
        \"start_date\": \"$START_DATE\",
        \"end_date\": \"$END_DATE\"
      }" 2>/dev/null)
    
    # Extrai métricas
    local RETURN=$(echo "$RESULT" | jq -r '.metrics.return_pct // 0')
    local SHARPE=$(echo "$RESULT" | jq -r '.metrics.sharpe_ratio // 0')
    local MAX_DD=$(echo "$RESULT" | jq -r '.metrics.max_drawdown_pct // 0')
    local WIN_RATE=$(echo "$RESULT" | jq -r '.metrics.win_rate // 0' | awk '{print $1 * 100}')
    local TOTAL_TRADES=$(echo "$RESULT" | jq -r '.metrics.total_trades // 0')
    
    # Armazena resultados
    RETURNS+=("$RETURN")
    SHARPES+=("$SHARPE")
    MAX_DDS+=("$MAX_DD")
    WIN_RATES+=("$WIN_RATE")
    TRADES+=("$TOTAL_TRADES")
    
    # Exibe resultado
    echo -e "   Return: ${GREEN}${RETURN}%${NC}"
    echo -e "   Sharpe: $SHARPE"
    echo -e "   Max DD: $MAX_DD%"
    echo -e "   Win Rate: $WIN_RATE%"
    echo -e "   Trades: $TOTAL_TRADES"
    echo ""
}

# Executa backtests em todos os pares
for SYMBOL in "${SYMBOLS[@]}"; do
    run_backtest "$SYMBOL"
done

# Calcula médias
AVG_RETURN=$(python3 -c "import sys; nums=[${RETURNS[0]}, ${RETURNS[1]}, ${RETURNS[2]}]; print(f'{sum(nums)/len(nums):.2f}')")
AVG_SHARPE=$(python3 -c "import sys; nums=[${SHARPES[0]}, ${SHARPES[1]}, ${SHARPES[2]}]; print(f'{sum(nums)/len(nums):.2f}')")
AVG_DD=$(python3 -c "import sys; nums=[${MAX_DDS[0]}, ${MAX_DDS[1]}, ${MAX_DDS[2]}]; print(f'{sum(nums)/len(nums):.2f}')")
AVG_WR=$(python3 -c "import sys; nums=[${WIN_RATES[0]}, ${WIN_RATES[1]}, ${WIN_RATES[2]}]; print(f'{sum(nums)/len(nums):.1f}')")
TOTAL_TRADES=$(python3 -c "import sys; nums=[${TRADES[0]}, ${TRADES[1]}, ${TRADES[2]}]; print(int(sum(nums)))")

# Calcula variação de return (para detectar overfitting)
MAX_RETURN=$(python3 -c "import sys; nums=[${RETURNS[0]}, ${RETURNS[1]}, ${RETURNS[2]}]; print(max(nums))")
MIN_RETURN=$(python3 -c "import sys; nums=[${RETURNS[0]}, ${RETURNS[1]}, ${RETURNS[2]}]; print(min(nums))")
VARIATION=$(python3 -c "
max_r = $MAX_RETURN
min_r = $MIN_RETURN
if max_r == 0:
    print('N/A')
else:
    var = ((max_r - min_r) / abs(max_r)) * 100
    print(f'{var:.1f}')
")

# Tabela de resultados
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   RESULTADOS MULTI-PAR                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
printf "%-12s | %10s | %8s | %8s | %10s | %7s\n" "Par" "Return" "Sharpe" "Max DD" "Win Rate" "Trades"
echo "-----------------------------------------------------------------------"
printf "%-12s | %9.2f%% | %8.2f | %7.2f%% | %9.1f%% | %7d\n" "BTCUSDT" "${RETURNS[0]}" "${SHARPES[0]}" "${MAX_DDS[0]}" "${WIN_RATES[0]}" "${TRADES[0]}"
printf "%-12s | %9.2f%% | %8.2f | %7.2f%% | %9.1f%% | %7d\n" "ETHUSDT" "${RETURNS[1]}" "${SHARPES[1]}" "${MAX_DDS[1]}" "${WIN_RATES[1]}" "${TRADES[1]}"
printf "%-12s | %9.2f%% | %8.2f | %7.2f%% | %9.1f%% | %7d\n" "SOLUSDT" "${RETURNS[2]}" "${SHARPES[2]}" "${MAX_DDS[2]}" "${WIN_RATES[2]}" "${TRADES[2]}"
echo "-----------------------------------------------------------------------"
printf "%-12s | %9s%% | %8s | %7s%% | %9s%% | %7d\n" "MÉDIA" "$AVG_RETURN" "$AVG_SHARPE" "$AVG_DD" "$AVG_WR" "$TOTAL_TRADES"
echo ""

# Análise de aprovação
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                 CRITÉRIOS DE APROVAÇÃO                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

PASS_COUNT=0
TOTAL_CRITERIA=5

# Critério 1: Média return > 0%
echo -n "1. Média return > 0%: "
if (( $(echo "$AVG_RETURN > 0" | bc -l) )); then
    echo -e "${GREEN}✅ PASSOU${NC} ($AVG_RETURN%)"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FALHOU${NC} ($AVG_RETURN%)"
fi

# Critério 2: Todos win_rate > 45%
echo -n "2. Todos win_rate > 45%: "
ALL_WR_PASS=true
for WR in "${WIN_RATES[@]}"; do
    if (( $(echo "$WR < 45" | bc -l) )); then
        ALL_WR_PASS=false
        break
    fi
done
if $ALL_WR_PASS; then
    echo -e "${GREEN}✅ PASSOU${NC} (min: $(printf "%.1f%%" $(echo "${WIN_RATES[@]}" | tr ' ' '\n' | sort -n | head -1)))"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FALHOU${NC}"
fi

# Critério 3: Variação return < 50% (evita overfitting)
echo -n "3. Variação return < 50%: "
if [[ "$VARIATION" != "N/A" ]] && (( $(echo "$VARIATION < 50" | bc -l) )); then
    echo -e "${GREEN}✅ PASSOU${NC} ($VARIATION%)"
    ((PASS_COUNT++))
else
    echo -e "${YELLOW}⚠️  ATENÇÃO${NC} ($VARIATION% - possível especialização)"
fi

# Critério 4: Todos max_dd < 20%
echo -n "4. Todos max_dd < 20%: "
ALL_DD_PASS=true
for DD in "${MAX_DDS[@]}"; do
    if (( $(echo "$DD > 20" | bc -l) )); then
        ALL_DD_PASS=false
        break
    fi
done
if $ALL_DD_PASS; then
    echo -e "${GREEN}✅ PASSOU${NC} (max: $(printf "%.2f%%" $(echo "${MAX_DDS[@]}" | tr ' ' '\n' | sort -n -r | head -1)))"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FALHOU${NC}"
fi

# Critério 5: Todos return > -5% (sem perdas catastróficas)
echo -n "5. Nenhum par < -5%: "
ALL_RETURN_SAFE=true
for RET in "${RETURNS[@]}"; do
    if (( $(echo "$RET < -5" | bc -l) )); then
        ALL_RETURN_SAFE=false
        break
    fi
done
if $ALL_RETURN_SAFE; then
    echo -e "${GREEN}✅ PASSOU${NC} (min: $(printf "%.2f%%" $(echo "${RETURNS[@]}" | tr ' ' '\n' | sort -n | head -1)))"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FALHOU${NC}"
fi

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                      DECISÃO FINAL                         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Decisão final
if [ $PASS_COUNT -ge 4 ]; then
    echo -e "${GREEN}✅ ESTRATÉGIA APROVADA PARA PRODUÇÃO${NC}"
    echo -e "${GREEN}   Score: $PASS_COUNT/$TOTAL_CRITERIA critérios passados${NC}"
    echo ""
    echo -e "${BLUE}📋 Próximos passos:${NC}"
    echo "   1. Testar em out-of-sample (2024/2025)"
    echo "   2. Paper trading 30 dias"
    echo "   3. Monitorar correlação entre pares em live"
    exit 0
elif [ $PASS_COUNT -ge 3 ]; then
    echo -e "${YELLOW}⚠️  ESTRATÉGIA NECESSITA AJUSTES${NC}"
    echo -e "${YELLOW}   Score: $PASS_COUNT/$TOTAL_CRITERIA critérios passados${NC}"
    echo ""
    echo -e "${YELLOW}📋 Ações recomendadas:${NC}"
    echo "   1. Revisar parâmetros dos pares que falharam"
    echo "   2. Validar em período diferente"
    echo "   3. Considerar filtros adicionais"
    exit 1
else
    echo -e "${RED}❌ ESTRATÉGIA REJEITADA${NC}"
    echo -e "${RED}   Score: $PASS_COUNT/$TOTAL_CRITERIA critérios passados${NC}"
    echo ""
    echo -e "${RED}⚠️  POSSÍVEL OVERFITTING EM BTC${NC}"
    echo ""
    echo -e "${RED}📋 Ações obrigatórias:${NC}"
    echo "   1. NÃO colocar em produção"
    echo "   2. Redesenhar estratégia com foco em robustez"
    echo "   3. Testar em mais pares (BNB, ADA, MATIC)"
    echo "   4. Revisar lógica de entrada/saída"
    exit 2
fi
