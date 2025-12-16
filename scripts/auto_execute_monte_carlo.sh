#!/bin/bash

###############################################
# AUTO-EXECUTOR MONTE CARLO
# Aguarda simulação atual e executa próximas
###############################################

API_URL="http://localhost:3008"
ITERATIONS=1000  # Análise rápida
LOOKBACK=30

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=========================================="
echo -e "🤖 AUTO-EXECUTOR MONTE CARLO"
echo -e "==========================================${NC}"
echo ""

# Aguardar simulação atual completar
echo -e "${YELLOW}⏳ Aguardando simulação de 10,000 iterações completar...${NC}"
echo ""

MAX_WAIT=3600  # 1 hora máximo
ELAPSED=0
CHECK_INTERVAL=30  # Verificar a cada 30 segundos

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Verificar se há nova entrada no log de "completed"
    COMPLETED=$(docker logs aitrading-execution-engine 2>&1 | grep "Simulation completed" | tail -1)
    
    if [[ "$COMPLETED" == *"10000"* ]] || [[ "$COMPLETED" == *"completed"* ]]; then
        # Aguardar mais 10 segundos para garantir que salvou
        sleep 10
        
        # Verificar se o relatório foi salvo
        SAVED=$(docker logs aitrading-execution-engine 2>&1 | grep "Report saved" | tail -1)
        
        if [[ "$SAVED" == *"monte_carlo"* ]]; then
            echo -e "${GREEN}✅ Simulação de 10,000 iterações completada!${NC}"
            echo ""
            break
        fi
    fi
    
    # Aguardar intervalo
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
    
    # Mostrar progresso
    MINUTES=$((ELAPSED / 60))
    echo -ne "\r⏱️  Aguardando há ${MINUTES} minutos..."
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo -e "\n${RED}❌ Timeout: Simulação demorou mais de 1 hora${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}=========================================="
echo -e "🚀 INICIANDO ANÁLISE RÁPIDA"
echo -e "==========================================${NC}"
echo ""

# Executar simulações nas outras 4 estratégias
STRATEGIES=(
    "macd_rsi_combo"
    "trend_following"
    "volatility_breakout"
    "bollinger_bands"
)

for i in "${!STRATEGIES[@]}"; do
    STRATEGY="${STRATEGIES[$i]}"
    NUM=$((i + 1))
    
    echo -e "${YELLOW}[${NUM}/4] Executando: ${STRATEGY}${NC}"
    
    if ./scripts/run_monte_carlo.sh "$STRATEGY" "$ITERATIONS" "$LOOKBACK"; then
        echo -e "${GREEN}✅ ${STRATEGY} concluída${NC}"
    else
        echo -e "${RED}❌ ${STRATEGY} falhou${NC}"
    fi
    
    echo ""
    
    if [ $NUM -lt 4 ]; then
        echo -e "${YELLOW}⏸️  Pausa de 3 segundos...${NC}"
        sleep 3
    fi
done

echo -e "${CYAN}=========================================="
echo -e "📊 GERANDO RELATÓRIO FINAL"
echo -e "==========================================${NC}"
echo ""

# Buscar todos os relatórios
REPORTS=$(curl -s "${API_URL}/api/monte-carlo/reports")

if [ $? -eq 0 ]; then
    REPORT_COUNT=$(echo "$REPORTS" | jq '.reports | length')
    echo -e "${GREEN}✅ Total de relatórios: ${REPORT_COUNT}${NC}"
    echo ""
    
    # Tabela comparativa
    echo -e "${CYAN}┌─────────────────────────┬──────────────┬──────────────┬──────────────┐${NC}"
    echo -e "${CYAN}│ ${YELLOW}ESTRATÉGIA${CYAN}              │ ${YELLOW}RETORNO (%)${CYAN}  │ ${YELLOW}PROB LUCRO${CYAN}   │ ${YELLOW}SHARPE${CYAN}       │${NC}"
    echo -e "${CYAN}├─────────────────────────┼──────────────┼──────────────┼──────────────┤${NC}"
    
    ALL_STRATEGIES=("momentum" "macd_rsi_combo" "trend_following" "volatility_breakout" "bollinger_bands")
    
    for STRATEGY in "${ALL_STRATEGIES[@]}"; do
        LATEST=$(echo "$REPORTS" | jq -r ".reports[] | select(.strategy == \"$STRATEGY\") | .filename" | head -1)
        
        if [ -n "$LATEST" ] && [ "$LATEST" != "null" ]; then
            REPORT=$(curl -s "${API_URL}/api/monte-carlo/report/${LATEST}")
            
            RETURN=$(echo "$REPORT" | jq -r '.report.mean_return')
            PROB=$(echo "$REPORT" | jq -r '.report.probability_of_profit')
            SHARPE=$(echo "$REPORT" | jq -r '.report.mean_sharpe_ratio')
            
            # Colorir
            if (( $(echo "$RETURN > 0" | bc -l) )); then
                COLOR=$GREEN
            else
                COLOR=$RED
            fi
            
            printf "${CYAN}│${NC} %-23s ${CYAN}│${NC} ${COLOR}%11.2f%%${NC} ${CYAN}│${NC} %11.1f%% ${CYAN}│${NC} %12.2f ${CYAN}│${NC}\n" \
                "$STRATEGY" "$RETURN" "$PROB" "$SHARPE"
        fi
    done
    
    echo -e "${CYAN}└─────────────────────────┴──────────────┴──────────────┴──────────────┘${NC}"
    echo ""
    
    # Identificar top 3
    echo -e "${GREEN}🏆 TOP 3 ESTRATÉGIAS:${NC}"
    echo ""
    
    TEMP_SCORES=$(mktemp)
    
    for STRATEGY in "${ALL_STRATEGIES[@]}"; do
        LATEST=$(echo "$REPORTS" | jq -r ".reports[] | select(.strategy == \"$STRATEGY\") | .filename" | head -1)
        
        if [ -n "$LATEST" ] && [ "$LATEST" != "null" ]; then
            REPORT=$(curl -s "${API_URL}/api/monte-carlo/report/${LATEST}")
            
            RETURN=$(echo "$REPORT" | jq -r '.report.mean_return')
            PROB=$(echo "$REPORT" | jq -r '.report.probability_of_profit')
            SHARPE=$(echo "$REPORT" | jq -r '.report.mean_sharpe_ratio')
            VAR=$(echo "$REPORT" | jq -r '.report.value_at_risk_95')
            
            SCORE=$(echo "scale=4; ($RETURN * 0.3) + ($PROB * 0.3) + ($SHARPE * 10 * 0.2) + ($VAR * -0.2)" | bc -l)
            
            echo "${SCORE}|${STRATEGY}|${RETURN}|${PROB}|${SHARPE}|${VAR}" >> "$TEMP_SCORES"
        fi
    done
    
    RANK=1
    sort -t'|' -k1 -nr "$TEMP_SCORES" | head -3 | while IFS='|' read -r SCORE STRATEGY RETURN PROB SHARPE VAR; do
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
        echo ""
        
        RANK=$((RANK + 1))
    done
    
    rm -f "$TEMP_SCORES"
fi

echo -e "${CYAN}=========================================="
echo -e "✅ ANÁLISE COMPLETA FINALIZADA"
echo -e "==========================================${NC}"
echo ""
echo -e "${GREEN}🌐 Acesse o dashboard: ${CYAN}http://localhost:8081/monte-carlo${NC}"
echo ""
