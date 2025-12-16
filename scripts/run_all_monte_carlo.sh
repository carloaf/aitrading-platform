#!/bin/bash

#############################################
# SCRIPT DE ANÁLISE COMPLETA MONTE CARLO
# Executa 10,000 iterações em todas as 5 estratégias
# Tempo estimado: 2-3 horas
#############################################

set -e  # Exit on error

ITERATIONS=10000
LOOKBACK=30
API_URL="http://localhost:3008"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Array com todas as estratégias
STRATEGIES=(
    "momentum"
    "macd_rsi_combo"
    "trend_following"
    "volatility_breakout"
    "bollinger_bands"
)

echo -e "${CYAN}=========================================="
echo -e "🎲 ANÁLISE MONTE CARLO COMPLETA"
echo -e "==========================================${NC}"
echo -e "${YELLOW}📊 Estratégias: ${#STRATEGIES[@]}"
echo -e "🔢 Iterações por estratégia: ${ITERATIONS}"
echo -e "📅 Lookback: ${LOOKBACK} dias${NC}"
echo -e "${CYAN}==========================================${NC}"
echo ""

# Timestamp de início
START_TIME=$(date +%s)
echo -e "${BLUE}⏱️  Início: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""

# Contador de sucessos/falhas
SUCCESS_COUNT=0
FAILED_COUNT=0
declare -a FAILED_STRATEGIES

# Loop através de todas as estratégias
for i in "${!STRATEGIES[@]}"; do
    STRATEGY="${STRATEGIES[$i]}"
    STRATEGY_NUM=$((i + 1))
    
    echo -e "${MAGENTA}=========================================="
    echo -e "📈 ESTRATÉGIA ${STRATEGY_NUM}/${#STRATEGIES[@]}: ${STRATEGY}"
    echo -e "==========================================${NC}"
    
    STRATEGY_START=$(date +%s)
    
    # Executar simulação
    if ./scripts/run_monte_carlo.sh "$STRATEGY" "$ITERATIONS" "$LOOKBACK"; then
        STRATEGY_END=$(date +%s)
        STRATEGY_DURATION=$((STRATEGY_END - STRATEGY_START))
        
        echo -e "${GREEN}✅ ${STRATEGY} concluída em ${STRATEGY_DURATION}s${NC}"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo -e "${RED}❌ ${STRATEGY} FALHOU${NC}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_STRATEGIES+=("$STRATEGY")
    fi
    
    echo ""
    
    # Pausa entre estratégias (evitar sobrecarga)
    if [ $STRATEGY_NUM -lt ${#STRATEGIES[@]} ]; then
        echo -e "${YELLOW}⏸️  Aguardando 5 segundos antes da próxima estratégia...${NC}"
        sleep 5
    fi
done

# Timestamp de fim
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))
SECONDS=$((TOTAL_DURATION % 60))

echo -e "${CYAN}=========================================="
echo -e "📊 RESUMO DA ANÁLISE"
echo -e "==========================================${NC}"
echo -e "${GREEN}✅ Estratégias bem-sucedidas: ${SUCCESS_COUNT}/${#STRATEGIES[@]}${NC}"

if [ $FAILED_COUNT -gt 0 ]; then
    echo -e "${RED}❌ Estratégias falhadas: ${FAILED_COUNT}${NC}"
    echo -e "${RED}   Falhas: ${FAILED_STRATEGIES[*]}${NC}"
fi

echo -e "${YELLOW}⏱️  Tempo total: ${HOURS}h ${MINUTES}m ${SECONDS}s${NC}"
echo -e "${BLUE}🏁 Fim: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""

# Gerar relatório comparativo
echo -e "${CYAN}=========================================="
echo -e "📈 RELATÓRIO COMPARATIVO"
echo -e "==========================================${NC}"
echo ""

# Buscar todos os relatórios via API
echo -e "${YELLOW}📄 Buscando relatórios salvos...${NC}"
REPORTS_RESPONSE=$(curl -s "${API_URL}/api/monte-carlo/reports")

if [ $? -eq 0 ]; then
    # Extrair lista de relatórios
    REPORT_COUNT=$(echo "$REPORTS_RESPONSE" | jq '.reports | length')
    
    if [ "$REPORT_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✅ Encontrados ${REPORT_COUNT} relatórios${NC}"
        echo ""
        
        # Tabela comparativa
        echo -e "${CYAN}╔════════════════════════╦═══════════════╦═══════════════╦═══════════════╦═══════════════╦═══════════════╗${NC}"
        echo -e "${CYAN}║ ${YELLOW}ESTRATÉGIA${CYAN}             ║ ${YELLOW}RETORNO MÉDIO${CYAN} ║ ${YELLOW}PROB. LUCRO${CYAN}   ║ ${YELLOW}SHARPE MÉDIO${CYAN}  ║ ${YELLOW}VAR 95%${CYAN}       ║ ${YELLOW}MAX DRAWDOWN${CYAN}  ║${NC}"
        echo -e "${CYAN}╠════════════════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╬═══════════════╣${NC}"
        
        # Iterar pelos últimos 5 relatórios (um de cada estratégia)
        for STRATEGY in "${STRATEGIES[@]}"; do
            # Buscar relatório mais recente desta estratégia
            LATEST_REPORT=$(echo "$REPORTS_RESPONSE" | jq -r ".reports[] | select(.strategy == \"$STRATEGY\") | .filename" | head -1)
            
            if [ -n "$LATEST_REPORT" ] && [ "$LATEST_REPORT" != "null" ]; then
                # Buscar dados completos do relatório
                REPORT_DATA=$(curl -s "${API_URL}/api/monte-carlo/report/${LATEST_REPORT}")
                
                if [ $? -eq 0 ]; then
                    # Extrair métricas
                    MEAN_RETURN=$(echo "$REPORT_DATA" | jq -r '.report.mean_return')
                    PROB_PROFIT=$(echo "$REPORT_DATA" | jq -r '.report.probability_of_profit')
                    MEAN_SHARPE=$(echo "$REPORT_DATA" | jq -r '.report.mean_sharpe_ratio')
                    VAR_95=$(echo "$REPORT_DATA" | jq -r '.report.value_at_risk_95')
                    MAX_DD=$(echo "$REPORT_DATA" | jq -r '.report.mean_max_drawdown')
                    
                    # Formatar valores
                    MEAN_RETURN_FMT=$(printf "%.2f%%" "$MEAN_RETURN")
                    PROB_PROFIT_FMT=$(printf "%.1f%%" "$PROB_PROFIT")
                    MEAN_SHARPE_FMT=$(printf "%.2f" "$MEAN_SHARPE")
                    VAR_95_FMT=$(printf "%.2f%%" "$VAR_95")
                    MAX_DD_FMT=$(printf "%.2f%%" "$MAX_DD")
                    
                    # Colorir baseado em rentabilidade
                    if (( $(echo "$MEAN_RETURN > 0" | bc -l) )); then
                        COLOR=$GREEN
                    else
                        COLOR=$RED
                    fi
                    
                    # Imprimir linha da tabela
                    printf "${CYAN}║${NC} %-22s ${CYAN}║${NC} ${COLOR}%13s${NC} ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC}\n" \
                        "$STRATEGY" "$MEAN_RETURN_FMT" "$PROB_PROFIT_FMT" "$MEAN_SHARPE_FMT" "$VAR_95_FMT" "$MAX_DD_FMT"
                else
                    printf "${CYAN}║${NC} %-22s ${CYAN}║${NC} ${RED}%13s${NC} ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC}\n" \
                        "$STRATEGY" "ERRO" "-" "-" "-" "-"
                fi
            else
                printf "${CYAN}║${NC} %-22s ${CYAN}║${NC} ${YELLOW}%13s${NC} ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC} %13s ${CYAN}║${NC}\n" \
                    "$STRATEGY" "N/A" "-" "-" "-" "-"
            fi
        done
        
        echo -e "${CYAN}╚════════════════════════╩═══════════════╩═══════════════╩═══════════════╩═══════════════╩═══════════════╝${NC}"
        echo ""
        
        # Análise automática: selecionar top 3
        echo -e "${MAGENTA}=========================================="
        echo -e "🏆 TOP 3 ESTRATÉGIAS (ANÁLISE AUTOMÁTICA)"
        echo -e "==========================================${NC}"
        echo ""
        
        # Criar arquivo temporário com scores
        TEMP_SCORES=$(mktemp)
        
        for STRATEGY in "${STRATEGIES[@]}"; do
            LATEST_REPORT=$(echo "$REPORTS_RESPONSE" | jq -r ".reports[] | select(.strategy == \"$STRATEGY\") | .filename" | head -1)
            
            if [ -n "$LATEST_REPORT" ] && [ "$LATEST_REPORT" != "null" ]; then
                REPORT_DATA=$(curl -s "${API_URL}/api/monte-carlo/report/${LATEST_REPORT}")
                
                MEAN_RETURN=$(echo "$REPORT_DATA" | jq -r '.report.mean_return')
                PROB_PROFIT=$(echo "$REPORT_DATA" | jq -r '.report.probability_of_profit')
                MEAN_SHARPE=$(echo "$REPORT_DATA" | jq -r '.report.mean_sharpe_ratio')
                VAR_95=$(echo "$REPORT_DATA" | jq -r '.report.value_at_risk_95')
                
                # Calcular score composto (pode ser ajustado)
                # Score = (Retorno * 0.3) + (Prob Lucro * 0.3) + (Sharpe * 10 * 0.2) + (VaR * -0.2)
                SCORE=$(echo "scale=4; ($MEAN_RETURN * 0.3) + ($PROB_PROFIT * 0.3) + ($MEAN_SHARPE * 10 * 0.2) + ($VAR_95 * -0.2)" | bc -l)
                
                echo "${SCORE}|${STRATEGY}|${MEAN_RETURN}|${PROB_PROFIT}|${MEAN_SHARPE}|${VAR_95}" >> "$TEMP_SCORES"
            fi
        done
        
        # Ordenar por score (descendente) e pegar top 3
        TOP_3=$(sort -t'|' -k1 -nr "$TEMP_SCORES" | head -3)
        
        RANK=1
        while IFS='|' read -r SCORE STRATEGY MEAN_RETURN PROB_PROFIT MEAN_SHARPE VAR_95; do
            echo -e "${YELLOW}${RANK}º Lugar: ${GREEN}${STRATEGY}${NC}"
            echo -e "   📊 Retorno Médio: ${MEAN_RETURN}%"
            echo -e "   🎯 Prob. Lucro: ${PROB_PROFIT}%"
            echo -e "   ⚡ Sharpe: ${MEAN_SHARPE}"
            echo -e "   ⚠️  VaR 95%: ${VAR_95}%"
            echo -e "   🏅 Score Composto: ${SCORE}"
            echo ""
            
            RANK=$((RANK + 1))
        done <<< "$TOP_3"
        
        # Limpar arquivo temporário
        rm -f "$TEMP_SCORES"
        
        # Recomendações
        echo -e "${CYAN}=========================================="
        echo -e "💡 RECOMENDAÇÕES"
        echo -e "==========================================${NC}"
        echo ""
        echo -e "${YELLOW}📌 Critérios para seleção:${NC}"
        echo -e "   ✅ Retorno Médio > 3%"
        echo -e "   ✅ Probabilidade de Lucro > 60%"
        echo -e "   ✅ Sharpe Ratio > 1.5"
        echo -e "   ✅ VaR 95% > -15%"
        echo -e "   ✅ Max Drawdown < -25%"
        echo ""
        echo -e "${GREEN}🚀 Próximos passos:${NC}"
        echo -e "   1. Revisar relatórios completos das top 3 estratégias"
        echo -e "   2. Executar testes adicionais se necessário"
        echo -e "   3. Criar dashboard de visualização"
        echo -e "   4. Iniciar paper trading com estratégias aprovadas"
        echo ""
        
    else
        echo -e "${RED}❌ Nenhum relatório encontrado${NC}"
    fi
else
    echo -e "${RED}❌ Erro ao conectar à API${NC}"
fi

echo -e "${CYAN}=========================================="
echo -e "✅ ANÁLISE COMPLETA FINALIZADA"
echo -e "==========================================${NC}"
echo ""

# Salvar resumo em arquivo
SUMMARY_FILE="logs/monte_carlo_summary_$(date +%Y%m%d_%H%M%S).txt"
mkdir -p logs

{
    echo "=========================================="
    echo "RESUMO MONTE CARLO - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""
    echo "Estratégias analisadas: ${#STRATEGIES[@]}"
    echo "Iterações por estratégia: ${ITERATIONS}"
    echo "Lookback: ${LOOKBACK} dias"
    echo ""
    echo "Sucessos: ${SUCCESS_COUNT}"
    echo "Falhas: ${FAILED_COUNT}"
    echo "Tempo total: ${HOURS}h ${MINUTES}m ${SECONDS}s"
    echo ""
    echo "Relatórios salvos em: /app/logs/"
    echo "=========================================="
} > "$SUMMARY_FILE"

echo -e "${GREEN}💾 Resumo salvo em: ${SUMMARY_FILE}${NC}"
echo ""
