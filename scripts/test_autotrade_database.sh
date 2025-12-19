#!/bin/bash

# ========================================
# Script de Teste: AutoTrade Database Integration
# Valida toda a cadeia de persistência
# ========================================

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AutoTrade Database Integration - Validation Suite      ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Variáveis
API_BASE="http://localhost:3008"
SESSION_ID=""

# Função de teste
test_step() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

success_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

error_step() {
    echo -e "${RED}[✗]${NC} $1"
    exit 1
}

# ========================================
# TESTE 1: Verificar Tabelas no Banco
# ========================================
test_step "1. Verificando tabelas no banco de dados..."

TABLES=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
    SELECT COUNT(*) FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name LIKE 'autotrade%';
")

if [ "$TABLES" -ge 2 ]; then
    success_step "Tabelas encontradas: $TABLES"
else
    error_step "Tabelas autotrade não encontradas! Execute: scripts/init-autotrade-tables.sql"
fi

# ========================================
# TESTE 2: Verificar API do AutoTrade
# ========================================
test_step "2. Testando endpoint /api/autotrade/status..."

STATUS=$(curl -s "$API_BASE/api/autotrade/status")
if echo "$STATUS" | grep -q "active"; then
    success_step "API AutoTrade respondendo"
else
    error_step "API AutoTrade não está respondendo corretamente"
fi

# ========================================
# TESTE 3: Iniciar AutoTrade em DRY RUN
# ========================================
test_step "3. Iniciando AutoTrade em modo DRY RUN..."

START_RESPONSE=$(curl -s -X POST "$API_BASE/api/autotrade/start" \
    -H "Content-Type: application/json" \
    -d '{
        "dry_run": true,
        "min_signal_strength": 0.3,
        "initial_balance": 10000.0,
        "risk_per_trade": 0.02,
        "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    }')

if echo "$START_RESPONSE" | grep -q '"success":true'; then
    SESSION_ID=$(echo "$START_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
    success_step "AutoTrade iniciado! Session ID: $SESSION_ID"
else
    echo "$START_RESPONSE"
    error_step "Falha ao iniciar AutoTrade"
fi

# ========================================
# TESTE 4: Verificar Sessão no Banco
# ========================================
test_step "4. Verificando se sessão foi criada no banco..."

sleep 1  # Aguardar persist

SESSION_COUNT=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
    SELECT COUNT(*) FROM autotrade_sessions WHERE session_id = '$SESSION_ID';
")

if [ "$SESSION_COUNT" -ge 1 ]; then
    success_step "Sessão encontrada no banco: $SESSION_ID"
else
    error_step "Sessão NÃO foi criada no banco!"
fi

# ========================================
# TESTE 5: Simular Sinal do Scanner
# ========================================
test_step "5. Simulando sinal do Scanner..."

SIGNAL_RESPONSE=$(curl -s -X POST "$API_BASE/api/autotrade/process-signal" \
    -H "Content-Type: application/json" \
    -d '{
        "symbol": "BTCUSDT",
        "direction": 1,
        "signal_type": "bullish_divergence",
        "strength": 0.65,
        "entry_price": 45000.0,
        "stop_loss": 44000.0,
        "take_profit": 48000.0,
        "timeframe": "1h"
    }')

if echo "$SIGNAL_RESPONSE" | grep -q '"success":true'; then
    SIGNAL_ID=$(echo "$SIGNAL_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('signal_id', 'N/A'))" 2>/dev/null || echo "N/A")
    success_step "Sinal processado! Signal ID: $SIGNAL_ID"
else
    echo "$SIGNAL_RESPONSE"
    error_step "Falha ao processar sinal"
fi

# ========================================
# TESTE 6: Verificar Sinal no Banco
# ========================================
test_step "6. Verificando se sinal foi salvo no banco..."

sleep 2  # Aguardar async save

SIGNAL_COUNT=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
    SELECT COUNT(*) FROM autotrade_signals WHERE session_id = '$SESSION_ID';
")

if [ "$SIGNAL_COUNT" -ge 1 ]; then
    success_step "Sinais encontrados no banco: $SIGNAL_COUNT"
    
    # Mostrar último sinal
    echo -e "${BLUE}Último sinal:${NC}"
    docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
        SELECT timestamp, symbol, direction, signal_type, strength, executed, reason
        FROM autotrade_signals 
        WHERE session_id = '$SESSION_ID'
        ORDER BY timestamp DESC 
        LIMIT 1;
    "
else
    error_step "Sinal NÃO foi salvo no banco!"
fi

# ========================================
# TESTE 7: Testar Analytics API
# ========================================
test_step "7. Testando endpoint de analytics..."

ANALYTICS=$(curl -s "$API_BASE/api/autotrade/analytics/session/$SESSION_ID")

if echo "$ANALYTICS" | grep -q "session_stats"; then
    success_step "Analytics API funcionando"
    echo -e "${BLUE}Stats da sessão:${NC}"
    echo "$ANALYTICS" | python3 -m json.tool | head -20
else
    echo "$ANALYTICS"
    error_step "Analytics API não está funcionando"
fi

# ========================================
# TESTE 8: Parar AutoTrade
# ========================================
test_step "8. Parando AutoTrade..."

STOP_RESPONSE=$(curl -s -X POST "$API_BASE/api/autotrade/stop")

if echo "$STOP_RESPONSE" | grep -q '"success":true'; then
    success_step "AutoTrade parado com sucesso"
else
    echo "$STOP_RESPONSE"
    error_step "Falha ao parar AutoTrade"
fi

# ========================================
# TESTE 9: Verificar Sessão Finalizada
# ========================================
test_step "9. Verificando se sessão foi finalizada no banco..."

sleep 1

IS_ACTIVE=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
    SELECT is_active FROM autotrade_sessions WHERE session_id = '$SESSION_ID';
" | tr -d ' ')

if [ "$IS_ACTIVE" = "f" ]; then
    success_step "Sessão marcada como inativa no banco"
else
    error_step "Sessão ainda está ativa no banco!"
fi

# ========================================
# TESTE 10: View Performance Summary
# ========================================
test_step "10. Testando view autotrade_performance_summary..."

VIEW_DATA=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -t -c "
    SELECT COUNT(*) FROM autotrade_performance_summary WHERE session_id = '$SESSION_ID';
")

if [ "$VIEW_DATA" -ge 1 ]; then
    success_step "View performance_summary funcionando"
    
    echo -e "${BLUE}Performance Summary:${NC}"
    docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
        SELECT 
            session_id, mode, total_signals_processed, total_trades_executed,
            win_rate, total_pnl, duration_hours
        FROM autotrade_performance_summary 
        WHERE session_id = '$SESSION_ID';
    "
else
    error_step "View performance_summary não está funcionando"
fi

# ========================================
# RESUMO FINAL
# ========================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✓ TODOS OS TESTES PASSARAM!                  ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Sessão de Teste:${NC} $SESSION_ID"
echo -e "${BLUE}Sinais Processados:${NC} $SIGNAL_COUNT"
echo ""
echo -e "${YELLOW}Próximos Passos:${NC}"
echo "1. Abra o Scanner Dashboard: http://localhost:3000/scanner-dashboard"
echo "2. Desative DRY RUN e inicie AutoTrade em modo LIVE"
echo "3. Aguarde sinais reais serem detectados"
echo "4. Consulte analytics: curl $API_BASE/api/autotrade/analytics/session/[SESSION_ID]"
echo ""
echo -e "${GREEN}✓ Sistema AutoTrade com Database está OPERACIONAL!${NC}"
echo ""
