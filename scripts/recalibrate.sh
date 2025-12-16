#!/bin/bash
# ==============================================================================
# AUTO-RECALIBRATION SYSTEM - PASSO 27.1
# ==============================================================================
# Aplica ajustes automáticos de parâmetros baseado em resultados WFO
#
# Uso:
#   bash scripts/recalibrate.sh [--dry-run]
#
# Autor: CryptoDev Assistant
# Data: 16/Dez/2025
# ==============================================================================

set -e

# Parâmetros
DRY_RUN=false
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
    echo "🔍 MODE: DRY RUN (sem aplicar mudanças)"
fi

HISTORY_FILE="logs/wfo/history.csv"
BACKUP_DIR="logs/wfo/backups"

# Cores
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Banner
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           AUTO-RECALIBRATION SYSTEM - v1.0                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

# Verificar se WFO history existe
if [ ! -f "$HISTORY_FILE" ]; then
    echo -e "${RED}❌ Arquivo $HISTORY_FILE não encontrado!${NC}"
    echo "Execute primeiro: bash scripts/wfo_simple.sh"
    exit 1
fi

# Ler última execução
LAST_RUN=$(tail -1 "$HISTORY_FILE")

if [ -z "$LAST_RUN" ] || [ "$LAST_RUN" == "date,start_date,end_date,return,sharpe,sortino,pf,dd,wr,trades" ]; then
    echo -e "${RED}❌ Histórico WFO vazio!${NC}"
    exit 1
fi

# Parse métricas (formato: date,start_date,end_date,return,sharpe,sortino,pf,dd,wr,trades)
IFS=',' read -r DATE START_DATE END_DATE RETURN SHARPE SORTINO PROFIT_FACTOR MAX_DD WIN_RATE TRADES <<< "$LAST_RUN"

# Calcular score (0-10 baseado em múltiplas métricas)
SCORE=$(python3 -c "
return_score = max(0, min(3, ($RETURN + 10) / 5))
sharpe_score = max(0, min(3, ($SHARPE + 1) / 1))
dd_score = max(0, min(2, (20 - $MAX_DD) / 10))
wr_score = max(0, min(2, $WIN_RATE / 50))
total = return_score + sharpe_score + dd_score + wr_score
print(f'{total:.2f}')
")

echo ""
echo "📊 Última Execução WFO:"
echo "   Data: $DATE"
echo "   Período: $START_DATE → $END_DATE"
echo "   Return: $RETURN%"
echo "   Sharpe: $SHARPE"
echo "   Sortino: $SORTINO"
echo "   Profit Factor: $PROFIT_FACTOR"
echo "   Max DD: $MAX_DD%"
echo "   Win Rate: $WIN_RATE%"
echo "   Trades: $TRADES"
echo "   Score: $SCORE/10"
echo ""

# Decisão de recalibração
SEVERITY="none"

if [ "$(echo "$SCORE >= 5" | bc)" -eq 1 ]; then
    SEVERITY="critical"
    echo -e "${RED}🚨 RECALIBRAÇÃO CRÍTICA NECESSÁRIA (Score: $SCORE)${NC}"
elif [ "$(echo "$SCORE >= 3" | bc)" -eq 1 ]; then
    SEVERITY="moderate"
    echo -e "${YELLOW}⚠️  Recalibração Moderada Recomendada (Score: $SCORE)${NC}"
elif [ "$(echo "$SCORE >= 1" | bc)" -eq 1 ]; then
    echo -e "${YELLOW}🔍 Monitoramento recomendado (Score: $SCORE)${NC}"
    echo "Sistema estável, mas atenção necessária."
    exit 0
else
    echo -e "${GREEN}✅ Sistema operando normalmente (Score: $SCORE)${NC}"
    echo "Nenhuma recalibração necessária."
    exit 0
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              ANÁLISE DE RECALIBRAÇÃO                       ║"
echo "╚════════════════════════════════════════════════════════════╝"

# Criar backup antes de modificar
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/meta_simulation_${TIMESTAMP}.py"

if [ "$DRY_RUN" == "false" ]; then
    cp services/execution-engine/src/meta_simulation.py "$BACKUP_FILE"
    echo "💾 Backup criado: $BACKUP_FILE"
fi

# Calcular ajustes com Python
echo ""
echo "🔧 Calculando ajustes de parâmetros..."

ADJUSTMENTS=$(python3 scripts/adjust_parameters.py \
    --severity "$SEVERITY" \
    --return-pct "$RETURN" \
    --sharpe "$SHARPE" \
    --max-dd "$MAX_DD" \
    --win-rate "$WIN_RATE" \
    --dry-run)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Erro ao calcular ajustes!${NC}"
    exit 1
fi

echo ""
echo "$ADJUSTMENTS"
echo ""

if [ "$DRY_RUN" == "true" ]; then
    echo -e "${BLUE}🔍 DRY RUN: Ajustes não foram aplicados${NC}"
    echo "Execute sem --dry-run para aplicar mudanças"
    exit 0
fi

# Confirmar com usuário
echo -e "${YELLOW}⚠️  Deseja aplicar estes ajustes? (y/n)${NC}"
read -r CONFIRM

if [ "$CONFIRM" != "y" ]; then
    echo "❌ Recalibração cancelada pelo usuário"
    exit 0
fi

# Aplicar ajustes
echo ""
echo "🔧 Aplicando ajustes..."
python3 scripts/adjust_parameters.py \
    --severity "$SEVERITY" \
    --return "$RETURN" \
    --sharpe "$SHARPE" \
    --max-dd "$MAX_DD" \
    --win-rate "$WIN_RATE"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Erro ao aplicar ajustes!${NC}"
    echo "Restaurando backup..."
    cp "$BACKUP_FILE" services/execution-engine/src/meta_simulation.py
    exit 1
fi

# Validar novos parâmetros
echo ""
echo "🧪 Validando novos parâmetros com backtest..."

VALIDATION_RESULT=$(bash scripts/validate_new_params.sh 2>&1)
VALIDATION_STATUS=$?

if [ $VALIDATION_STATUS -ne 0 ]; then
    echo -e "${RED}❌ Validação falhou! Restaurando backup...${NC}"
    echo "$VALIDATION_RESULT"
    cp "$BACKUP_FILE" services/execution-engine/src/meta_simulation.py
    exit 1
fi

# Rebuild container com novos parâmetros
echo ""
echo "🔨 Rebuilding execution-engine container..."
docker compose build execution-engine > /dev/null 2>&1
docker compose restart execution-engine

echo ""
echo -e "${GREEN}✅ Recalibração aplicada com sucesso!${NC}"
echo ""
echo "📝 Resumo:"
echo "   Severidade: $SEVERITY"
echo "   Backup: $BACKUP_FILE"
echo "   Validação: PASSOU"
echo ""
echo "🔄 Próximos passos:"
echo "   1. Monitorar próxima execução WFO"
echo "   2. Comparar performance antes/depois"
echo "   3. Se piorar, restaurar: cp $BACKUP_FILE services/execution-engine/src/meta_simulation.py"
echo ""
echo "💾 Log salvo em: logs/wfo/recalibration_${TIMESTAMP}.log"

# Salvar log de recalibração
cat > "logs/wfo/recalibration_${TIMESTAMP}.log" <<EOF
RECALIBRATION LOG
=================
Date: $(date)
Severity: $SEVERITY
WFO Score: $SCORE
Previous Metrics:
  Return: $RETURN%
  Sharpe: $SHARPE
  Max DD: $MAX_DD%
  Win Rate: $WIN_RATE%

Adjustments Applied:
$ADJUSTMENTS

Backup: $BACKUP_FILE
Validation: PASSED
Status: APPLIED
EOF

echo -e "${GREEN}✅ Recalibration concluída!${NC}"
