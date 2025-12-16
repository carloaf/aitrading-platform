#!/bin/bash

#############################################
# ANÁLISE MONTE CARLO RÁPIDA
# Executa 1,000 iterações em todas as estratégias
# Tempo estimado: 20-30 minutos
#############################################

set -e

ITERATIONS=1000  # Reduzido para análise mais rápida
LOOKBACK=30
API_URL="http://localhost:3008"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

STRATEGIES=(
    "momentum"
    "macd_rsi_combo"
    "trend_following"
    "volatility_breakout"
    "bollinger_bands"
)

echo -e "${CYAN}=========================================="
echo -e "🎲 ANÁLISE MONTE CARLO RÁPIDA"
echo -e "==========================================${NC}"
echo -e "${YELLOW}📊 Estratégias: ${#STRATEGIES[@]}"
echo -e "🔢 Iterações: ${ITERATIONS} (análise rápida)"
echo -e "📅 Lookback: ${LOOKBACK} dias${NC}"
echo -e "${CYAN}==========================================${NC}"
echo ""

START_TIME=$(date +%s)

# Executar todas as estratégias
for i in "${!STRATEGIES[@]}"; do
    STRATEGY="${STRATEGIES[$i]}"
    STRATEGY_NUM=$((i + 1))
    
    echo -e "${MAGENTA}=========================================="
    echo -e "📈 [${STRATEGY_NUM}/${#STRATEGIES[@]}] ${STRATEGY}"
    echo -e "==========================================${NC}"
    
    if ./scripts/run_monte_carlo.sh "$STRATEGY" "$ITERATIONS" "$LOOKBACK"; then
        echo -e "${GREEN}✅ ${STRATEGY} concluída${NC}"
    else
        echo -e "${RED}❌ ${STRATEGY} falhou${NC}"
    fi
    
    echo ""
    
    if [ $STRATEGY_NUM -lt ${#STRATEGIES[@]} ]; then
        echo -e "${YELLOW}⏸️  Pausa de 3 segundos...${NC}"
        sleep 3
    fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo -e "${CYAN}=========================================="
echo -e "✅ ANÁLISE CONCLUÍDA"
echo -e "==========================================${NC}"
echo -e "${YELLOW}⏱️  Tempo total: ${MINUTES}m ${SECONDS}s${NC}"
echo ""

# Gerar tabela comparativa
echo -e "${CYAN}=========================================="
echo -e "📊 COMPARATIVO DE ESTRATÉGIAS"
echo -e "==========================================${NC}"
echo ""

REPORTS=$(curl -s "${API_URL}/api/monte-carlo/reports")

if [ $? -eq 0 ]; then
    echo -e "${CYAN}┌────────────────────────┬─────────────┬─────────────┬─────────────┬─────────────┐${NC}"
    echo -e "${CYAN}│ ${YELLOW}ESTRATÉGIA${CYAN}             │ ${YELLOW}RETORNO (%)${CYAN} │ ${YELLOW}PROB LUCRO${CYAN}  │ ${YELLOW}SHARPE${CYAN}      │ ${YELLOW}VAR 95%${CYAN}     │${NC}"
    echo -e "${CYAN}├────────────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤${NC}"
    
    for STRATEGY in "${STRATEGIES[@]}"; do
        LATEST=$(echo "$REPORTS" | jq -r ".reports[] | select(.strategy == \"$STRATEGY\") | .filename" | head -1)
        
        if [ -n "$LATEST" ] && [ "$LATEST" != "null" ]; then
            REPORT=$(curl -s "${API_URL}/api/monte-carlo/report/${LATEST}")
            
            RETURN=$(echo "$REPORT" | jq -r '.report.mean_return')
            PROB=$(echo "$REPORT" | jq -r '.report.probability_of_profit')
            SHARPE=$(echo "$REPORT" | jq -r '.report.mean_sharpe_ratio')
            VAR=$(echo "$REPORT" | jq -r '.report.value_at_risk_95')
            
            # Colorir baseado em rentabilidade
            if (( $(echo "$RETURN > 0" | bc -l) )); then
                COLOR=$GREEN
                ICON="✅"
            else
                COLOR=$RED
                ICON="❌"
            fi
            
            printf "${CYAN}│${NC} ${ICON} %-20s ${CYAN}│${NC} ${COLOR}%10.2f%%${NC} ${CYAN}│${NC} %10.1f%% ${CYAN}│${NC} %11.2f ${CYAN}│${NC} %10.2f%% ${CYAN}│${NC}\n" \
                "$STRATEGY" "$RETURN" "$PROB" "$SHARPE" "$VAR"
        fi
    done
    
    echo -e "${CYAN}└────────────────────────┴─────────────┴─────────────┴─────────────┴─────────────┘${NC}"
    echo ""
    
    # Top 3 automático
    echo -e "${MAGENTA}🏆 TOP 3 ESTRATÉGIAS${NC}"
    echo -e "${CYAN}==========================================${NC}"
    echo ""
    
    TEMP_SCORES=$(mktemp)
    
    for STRATEGY in "${STRATEGIES[@]}"; do
        LATEST=$(echo "$REPORTS" | jq -r ".reports[] | select(.strategy == \"$STRATEGY\") | .filename" | head -1)
        
        if [ -n "$LATEST" ] && [ "$LATEST" != "null" ]; then
            REPORT=$(curl -s "${API_URL}/api/monte-carlo/report/${LATEST}")
            
            RETURN=$(echo "$REPORT" | jq -r '.report.mean_return')
            PROB=$(echo "$REPORT" | jq -r '.report.probability_of_profit')
            SHARPE=$(echo "$REPORT" | jq -r '.report.mean_sharpe_ratio')
            VAR=$(echo "$REPORT" | jq -r '.report.value_at_risk_95')
            MAX_DD=$(echo "$REPORT" | jq -r '.report.mean_max_drawdown')
            
            # Score: Return*0.3 + Prob*0.3 + Sharpe*10*0.2 - VaR*0.2
            SCORE=$(echo "scale=4; ($RETURN * 0.3) + ($PROB * 0.3) + ($SHARPE * 10 * 0.2) + ($VAR * -0.2)" | bc -l)
            
            echo "${SCORE}|${STRATEGY}|${RETURN}|${PROB}|${SHARPE}|${VAR}|${MAX_DD}" >> "$TEMP_SCORES"
        fi
    done
    
    RANK=1
    sort -t'|' -k1 -nr "$TEMP_SCORES" | head -3 | while IFS='|' read -r SCORE STRATEGY RETURN PROB SHARPE VAR MAX_DD; do
        case $RANK in
            1) MEDAL="🥇" ;;
            2) MEDAL="🥈" ;;
            3) MEDAL="🥉" ;;
        esac
        
        echo -e "${YELLOW}${MEDAL} ${RANK}º: ${GREEN}${STRATEGY}${NC}"
        echo -e "   📊 Retorno: ${RETURN}%"
        echo -e "   🎯 Prob Lucro: ${PROB}%"
        echo -e "   ⚡ Sharpe: ${SHARPE}"
        echo -e "   📉 VaR: ${VAR}%"
        echo -e "   💯 Score: ${SCORE}"
        echo ""
        
        RANK=$((RANK + 1))
    done
    
    rm -f "$TEMP_SCORES"
    
    echo -e "${CYAN}==========================================${NC}"
    echo -e "${GREEN}✅ Use os top 3 para paper trading${NC}"
    echo ""
fi
