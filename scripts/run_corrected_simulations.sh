#!/bin/bash
###############################################################################
# MONTE CARLO SIMULATION - VERSÃO CORRIGIDA
# 600 iterações por estratégia com correções implementadas
###############################################################################

set -e  # Exit on error

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

API_URL="http://localhost:3008/api/monte-carlo"
ITERATIONS=600
PARALLEL=true
NUM_CORES=4

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      MONTE CARLO SIMULATION - VERSÃO CORRIGIDA v2.0             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✅ CORREÇÕES IMPLEMENTADAS:${NC}"
echo "   • Taxa de transação: 1% → 0.1% (Binance real)"
echo "   • Operações SHORT: Implementadas"
echo "   • Stop Loss: 2%"
echo "   • Take Profit: 4%"
echo ""
echo -e "${YELLOW}📊 CONFIGURAÇÃO:${NC}"
echo "   • Iterações por estratégia: $ITERATIONS"
echo "   • Processamento paralelo: $PARALLEL ($NUM_CORES cores)"
echo "   • Símbolo: BTCUSDT"
echo ""

# Função para verificar status
check_status() {
    local strategy=$1
    local max_wait=7200  # 2 horas máximo
    local elapsed=0
    local last_progress=0
    local stall_count=0
    
    while [ $elapsed -lt $max_wait ]; do
        response=$(curl -s "$API_URL/progress/$strategy" 2>/dev/null || echo '{"status":"error"}')
        status=$(echo $response | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        progress=$(echo $response | grep -o '"progress":[0-9]*' | cut -d':' -f2)
        current=$(echo $response | grep -o '"current_iteration":[0-9]*' | cut -d':' -f2)
        total=$(echo $response | grep -o '"total_iterations":[0-9]*' | cut -d':' -f2)
        
        if [ "$status" = "completed" ]; then
            echo -e "${GREEN}✅ CONCLUÍDO${NC}"
            return 0
        elif [ "$status" = "error" ] || [ "$status" = "failed" ]; then
            echo -e "${RED}❌ ERRO${NC}"
            return 1
        fi
        
        # Verificar se está travado
        if [ "$progress" = "$last_progress" ]; then
            stall_count=$((stall_count + 1))
            if [ $stall_count -gt 30 ]; then
                echo -e "${RED}❌ TRAVADO (sem progresso por 5min)${NC}"
                return 1
            fi
        else
            stall_count=0
        fi
        last_progress=$progress
        
        echo -ne "\r   ⏳ Progresso: $progress% ($current/$total)    "
        sleep 10
        elapsed=$((elapsed + 10))
    done
    
    echo -e "${RED}❌ TIMEOUT${NC}"
    return 1
}

# Função para executar simulação
run_simulation() {
    local strategy_name=$1
    local strategy_label=$2
    shift 2
    local param_ranges="$@"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🎯 Estratégia: $strategy_label${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    local start_time=$(date +%s)
    
    # Enviar requisição
    curl -X POST "$API_URL/simulate" \
        -H "Content-Type: application/json" \
        -d "{
            \"strategy_name\": \"$strategy_name\",
            \"symbol\": \"BTCUSDT\",
            \"iterations\": $ITERATIONS,
            \"parameter_ranges\": {$param_ranges},
            \"parallel\": $PARALLEL,
            \"num_cores\": $NUM_CORES
        }" \
        > /dev/null 2>&1 &
    
    sleep 3
    
    # Monitorar progresso
    if check_status "$strategy_name"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo ""
        echo -e "   ${GREEN}⏱️  Tempo: ${duration}s${NC}"
        
        # Buscar métricas finais
        response=$(curl -s "$API_URL/progress/$strategy_name" 2>/dev/null)
        elapsed=$(echo $response | grep -o '"elapsed_time":[0-9.]*' | cut -d':' -f2)
        echo -e "   ${GREEN}📊 Tempo real: ${elapsed}s${NC}"
        return 0
    else
        return 1
    fi
}

# Limpar resultados anteriores (opcional)
read -p "$(echo -e ${YELLOW}🗑️  Deseja limpar simulações anteriores? [y/N]: ${NC})" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🗑️  Limpando resultados anteriores...${NC}"
    docker exec aitrading-execution-engine bash -c "rm -f /app/logs/monte_carlo_*.json" 2>/dev/null || true
    echo -e "${GREEN}✅ Resultados limpos${NC}"
fi
echo ""

# Timestamp de início
START_TIMESTAMP=$(date +%s)
echo -e "${GREEN}🚀 Iniciando simulações em: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""

# ============================================================================
# ESTRATÉGIA 1: MOMENTUM
# ============================================================================
if run_simulation "momentum" "MOMENTUM" \
    '"roc_period": [8, 20], "threshold": [0.5, 2.5]'; then
    echo -e "${GREEN}✅ Momentum: SUCESSO${NC}\n"
else
    echo -e "${RED}❌ Momentum: FALHOU${NC}\n"
fi

sleep 5

# ============================================================================
# ESTRATÉGIA 2: MACD + RSI COMBO
# ============================================================================
if run_simulation "macd_rsi_combo" "MACD + RSI COMBO" \
    '"macd_fast": [10, 14], "macd_slow": [24, 30], "macd_signal": [8, 11], "rsi_period": [12, 18], "rsi_overbought": [68, 75], "rsi_oversold": [25, 32]'; then
    echo -e "${GREEN}✅ MACD+RSI: SUCESSO${NC}\n"
else
    echo -e "${RED}❌ MACD+RSI: FALHOU${NC}\n"
fi

sleep 5

# ============================================================================
# ESTRATÉGIA 3: TREND FOLLOWING
# ============================================================================
if run_simulation "trend_following" "TREND FOLLOWING" \
    '"ema_fast": [12, 25], "ema_slow": [45, 70], "adx_period": [12, 18], "adx_threshold": [15, 25]'; then
    echo -e "${GREEN}✅ Trend Following: SUCESSO${NC}\n"
else
    echo -e "${RED}❌ Trend Following: FALHOU${NC}\n"
fi

sleep 5

# ============================================================================
# ESTRATÉGIA 4: VOLATILITY BREAKOUT
# ============================================================================
if run_simulation "volatility_breakout" "VOLATILITY BREAKOUT" \
    '"atr_period": [12, 20], "atr_multiplier": [1.8, 2.8], "volume_ma_period": [18, 30]'; then
    echo -e "${GREEN}✅ Volatility Breakout: SUCESSO${NC}\n"
else
    echo -e "${RED}❌ Volatility Breakout: FALHOU${NC}\n"
fi

# ============================================================================
# RESUMO FINAL
# ============================================================================
END_TIMESTAMP=$(date +%s)
TOTAL_DURATION=$((END_TIMESTAMP - START_TIMESTAMP))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))
SECONDS=$((TOTAL_DURATION % 60))

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    SIMULAÇÕES CONCLUÍDAS                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}⏱️  Tempo total: ${HOURS}h ${MINUTES}m ${SECONDS}s${NC}"
echo -e "${GREEN}📊 Total de simulações: $((ITERATIONS * 4)) (600 × 4 estratégias)${NC}"
echo ""
echo -e "${YELLOW}📁 Resultados salvos em:${NC}"
echo "   • Container: /app/logs/monte_carlo_*.json"
echo "   • Host: docker cp aitrading-execution-engine:/app/logs/..."
echo ""
echo -e "${YELLOW}📈 Próximos passos:${NC}"
echo "   1. Copiar resultados: bash scripts/copy_results.sh"
echo "   2. Analisar resultados: python3 scripts/analyze_results.py"
echo "   3. Revisar relatório: cat RELATORIO_ANALISE_MONTE_CARLO_V2.md"
echo ""
echo -e "${GREEN}✨ Simulações com correções v2.0 concluídas!${NC}"
