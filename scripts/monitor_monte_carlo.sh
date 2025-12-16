#!/bin/bash

###############################################
# MONITOR DE PROGRESSO MONTE CARLO
# Acompanha simulações em tempo real
###############################################

API_URL="http://localhost:3008"

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear

echo -e "${CYAN}=========================================="
echo -e "📊 MONITOR MONTE CARLO"
echo -e "==========================================${NC}"
echo ""

# Loop de monitoramento
while true; do
    # Limpar área de status (manter cabeçalho)
    tput cup 4 0
    tput ed
    
    # Verificar logs recentes
    LAST_LOGS=$(docker logs aitrading-execution-engine 2>&1 | grep -E "Monte Carlo|iterations|completed|Progress|Mean Return" | tail -20)
    
    # Status atual
    echo -e "${YELLOW}📡 Status Atual:${NC}"
    echo "$LAST_LOGS" | grep -E "Iniciando Monte Carlo|iterations|Progress" | tail -5
    echo ""
    
    # Última simulação completada
    COMPLETED=$(echo "$LAST_LOGS" | grep "completed" | tail -1)
    if [ -n "$COMPLETED" ]; then
        echo -e "${GREEN}✅ Última simulação completada:${NC}"
        echo "$COMPLETED"
        echo ""
    fi
    
    # Estatísticas se disponíveis
    MEAN_RETURN=$(echo "$LAST_LOGS" | grep "Mean Return" | tail -1)
    if [ -n "$MEAN_RETURN" ]; then
        echo -e "${BLUE}📈 Últimos resultados:${NC}"
        echo "$LAST_LOGS" | grep -E "Mean Return|Probability|VaR|Sharpe" | tail -4
        echo ""
    fi
    
    # Relatórios salvos
    echo -e "${CYAN}📄 Relatórios disponíveis:${NC}"
    REPORTS=$(curl -s "${API_URL}/api/monte-carlo/reports" 2>/dev/null)
    if [ $? -eq 0 ]; then
        REPORT_COUNT=$(echo "$REPORTS" | jq '.reports | length' 2>/dev/null)
        if [ -n "$REPORT_COUNT" ] && [ "$REPORT_COUNT" != "null" ]; then
            echo -e "   Total: ${GREEN}${REPORT_COUNT}${NC} relatórios"
            
            # Últimos 3 relatórios
            echo "$REPORTS" | jq -r '.reports[:3] | .[] | "   • \(.strategy): \(.iterations) iter, Return \(.mean_return)%"' 2>/dev/null
        fi
    fi
    
    echo ""
    echo -e "${YELLOW}⏱️  Atualização a cada 5 segundos... (Ctrl+C para sair)${NC}"
    
    # Aguardar antes da próxima atualização
    sleep 5
done
