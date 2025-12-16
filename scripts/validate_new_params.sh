#!/bin/bash
# VALIDATE NEW PARAMETERS - PASSO 27.1
# ====================================
# Valida parâmetros ajustados via backtest rápido
#
# Autor: CryptoDev Assistant
# Data: 16/Dez/2025

set -euo pipefail

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuração
VALIDATION_PERIOD="2025-01-01 00:00:00"  # Último mês
VALIDATION_SYMBOL="BTCUSDT"
REQUIRED_TRADES_MIN=2
MAX_DD_THRESHOLD=20.0

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}VALIDAÇÃO DE PARÂMETROS - PASSO 27.1${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# 1. Verificar se container está rodando
echo -e "${YELLOW}[1/5]${NC} Verificando container..."
if ! docker ps | grep -q aitrading-execution-engine; then
    echo -e "${RED}❌ Container não está rodando${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Container operacional${NC}"

# 2. Verificar se API responde
echo -e "${YELLOW}[2/5]${NC} Verificando API health..."
if ! curl -s http://localhost:3008/health > /dev/null; then
    echo -e "${RED}❌ API não responde${NC}"
    exit 1
fi
echo -e "${GREEN}✓ API operacional${NC}"

# 3. Executar backtest rápido (1 mês)
echo -e "${YELLOW}[3/5]${NC} Executando backtest de validação..."
echo "   Período: ${VALIDATION_PERIOD} até agora"
echo "   Símbolo: ${VALIDATION_SYMBOL}"
echo ""

VALIDATION_RESULT=$(curl -s -X POST http://localhost:3008/backtest \
  -H "Content-Type: application/json" \
  -d "{
    \"symbol\": \"${VALIDATION_SYMBOL}\",
    \"start_date\": \"${VALIDATION_PERIOD}\",
    \"initial_capital\": 10000,
    \"use_synthetic\": false
  }")

# Extrair métricas com jq (se disponível) ou parsing manual
if command -v jq &> /dev/null; then
    TOTAL_RETURN=$(echo "$VALIDATION_RESULT" | jq -r '.summary.total_return_pct')
    MAX_DD=$(echo "$VALIDATION_RESULT" | jq -r '.summary.max_drawdown_pct')
    NUM_TRADES=$(echo "$VALIDATION_RESULT" | jq -r '.summary.num_trades')
    WIN_RATE=$(echo "$VALIDATION_RESULT" | jq -r '.summary.win_rate_pct')
    SHARPE=$(echo "$VALIDATION_RESULT" | jq -r '.summary.sharpe_ratio')
else
    # Parsing manual
    TOTAL_RETURN=$(echo "$VALIDATION_RESULT" | grep -oP '"total_return_pct":\s*\K[-0-9.]+' | head -1)
    MAX_DD=$(echo "$VALIDATION_RESULT" | grep -oP '"max_drawdown_pct":\s*\K[-0-9.]+' | head -1)
    NUM_TRADES=$(echo "$VALIDATION_RESULT" | grep -oP '"num_trades":\s*\K[0-9]+' | head -1)
    WIN_RATE=$(echo "$VALIDATION_RESULT" | grep -oP '"win_rate_pct":\s*\K[-0-9.]+' | head -1)
    SHARPE=$(echo "$VALIDATION_RESULT" | grep -oP '"sharpe_ratio":\s*\K[-0-9.]+' | head -1)
fi

echo -e "${BLUE}📊 Resultados da Validação:${NC}"
echo "   Return: ${TOTAL_RETURN}%"
echo "   Max DD: ${MAX_DD}%"
echo "   Trades: ${NUM_TRADES}"
echo "   Win Rate: ${WIN_RATE}%"
echo "   Sharpe: ${SHARPE}"
echo ""

# 4. Aplicar critérios de validação
echo -e "${YELLOW}[4/5]${NC} Aplicando critérios de validação..."

VALIDATION_PASSED=true

# Critério 1: Mínimo de trades
if (( $(echo "$NUM_TRADES < $REQUIRED_TRADES_MIN" | bc -l) )); then
    echo -e "${RED}❌ FALHOU: Trades insuficientes ($NUM_TRADES < $REQUIRED_TRADES_MIN)${NC}"
    VALIDATION_PASSED=false
else
    echo -e "${GREEN}✓ Trades suficientes ($NUM_TRADES >= $REQUIRED_TRADES_MIN)${NC}"
fi

# Critério 2: Max DD não pode piorar muito
if (( $(echo "$MAX_DD > $MAX_DD_THRESHOLD" | bc -l) )); then
    echo -e "${RED}❌ FALHOU: Drawdown muito alto ($MAX_DD% > $MAX_DD_THRESHOLD%)${NC}"
    VALIDATION_PASSED=false
else
    echo -e "${GREEN}✓ Drawdown aceitável ($MAX_DD% <= $MAX_DD_THRESHOLD%)${NC}"
fi

# Critério 3: Sharpe positivo (mínimo)
if (( $(echo "$SHARPE < -0.5" | bc -l) )); then
    echo -e "${RED}❌ FALHOU: Sharpe muito baixo ($SHARPE < -0.5)${NC}"
    VALIDATION_PASSED=false
else
    echo -e "${GREEN}✓ Sharpe aceitável ($SHARPE >= -0.5)${NC}"
fi

# Critério 4: Return não pode ser muito negativo
if (( $(echo "$TOTAL_RETURN < -10.0" | bc -l) )); then
    echo -e "${RED}❌ FALHOU: Return muito negativo ($TOTAL_RETURN% < -10%)${NC}"
    VALIDATION_PASSED=false
else
    echo -e "${GREEN}✓ Return aceitável ($TOTAL_RETURN% >= -10%)${NC}"
fi

echo ""

# 5. Resultado final
echo -e "${YELLOW}[5/5]${NC} Resultado final..."
if [ "$VALIDATION_PASSED" = true ]; then
    echo -e "${GREEN}✅ VALIDAÇÃO APROVADA${NC}"
    echo "   Novos parâmetros são aceitáveis"
    exit 0
else
    echo -e "${RED}❌ VALIDAÇÃO REPROVADA${NC}"
    echo "   Parâmetros não atendem critérios mínimos"
    echo "   Considere rollback ou ajuste manual"
    exit 1
fi
