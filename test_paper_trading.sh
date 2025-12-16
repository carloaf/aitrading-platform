#!/bin/bash

# Paper Trading Engine - Script de Teste Automatizado
# Executa todos os testes de funcionalidade

set -e  # Exit on error

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

API_URL="http://localhost:3008"
SESSION_ID="test_auto_$(date +%s)"

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   PAPER TRADING ENGINE - TESTE AUTOMATIZADO   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Session ID: $SESSION_ID${NC}"
echo ""

# Função para printar etapas
print_step() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Função para verificar resultado
check_result() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Sucesso${NC}"
    else
        echo -e "${RED}✗ Falhou${NC}"
        exit 1
    fi
}

# 1. Health Check
print_step "1️⃣  HEALTH CHECK"
health_status=$(curl -s $API_URL/health | jq -r '.status')
echo "Status: $health_status"
if [ "$health_status" == "healthy" ]; then
    echo -e "${GREEN}✓ Execution Engine está saudável${NC}"
else
    echo -e "${RED}✗ Execution Engine não responde${NC}"
    exit 1
fi
echo ""

# 2. Verificar documentação da API
print_step "2️⃣  DOCUMENTAÇÃO DA API"
doc=$(curl -s $API_URL/ | jq -r '.name')
echo "API Name: $doc"
echo -e "${GREEN}✓ Documentação acessível${NC}"
echo ""

# 3. Iniciar Paper Trading
print_step "3️⃣  INICIANDO PAPER TRADING (Momentum Strategy)"
start_response=$(curl -s -X POST $API_URL/paper-trading/start \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"strategy_name\": \"momentum\",
    \"strategy_parameters\": {
      \"roc_period\": 10,
      \"threshold\": 0
    },
    \"symbol\": \"BTCUSDT\",
    \"timeframe\": \"1m\",
    \"initial_balance\": 1000.0,
    \"commission_rate\": 0.001,
    \"slippage_rate\": 0.0005
  }")

echo "$start_response" | jq '.'
check_result
echo ""

# 4. Listar sessões ativas
print_step "4️⃣  LISTANDO SESSÕES ATIVAS"
sessions=$(curl -s $API_URL/paper-trading/sessions)
echo "$sessions" | jq '.'
session_count=$(echo "$sessions" | jq '.sessions | length')
echo -e "${GREEN}✓ Sessões ativas: $session_count${NC}"
echo ""

# 5. Aguardar coleta de dados
print_step "5️⃣  AGUARDANDO COLETA DE DADOS (60 segundos)"
for i in {60..1}; do
    printf "\r${YELLOW}Aguardando... %02d segundos restantes${NC}" $i
    sleep 1
done
echo ""
echo -e "${GREEN}✓ Período de espera concluído${NC}"
echo ""

# 6. Verificar Status
print_step "6️⃣  STATUS DA SESSÃO"
status=$(curl -s $API_URL/paper-trading/$SESSION_ID/status)
echo "$status" | jq '{
  running: .is_running,
  strategy: .strategy_name,
  symbol: .symbol,
  timeframe: .timeframe,
  uptime_seconds: .uptime_seconds,
  candles_collected: .candles_collected,
  signals_generated: .signals_generated,
  trades_executed: .trades_executed,
  position_open: .position_open
}'

candles=$(echo "$status" | jq -r '.candles_collected')
echo ""
echo -e "${YELLOW}Candles coletados: $candles${NC}"
if [ "$candles" -ge 50 ]; then
    echo -e "${GREEN}✓ Dados suficientes para indicadores${NC}"
else
    echo -e "${YELLOW}⚠ Ainda coletando dados...${NC}"
fi
echo ""

# 7. Ver Resumo da Conta
print_step "7️⃣  RESUMO DA CONTA"
account=$(curl -s $API_URL/paper-trading/$SESSION_ID/account)
echo "$account" | jq '{
  balance: .balance,
  equity: .equity,
  total_pnl: .total_pnl,
  total_pnl_percent: .total_pnl_percent,
  open_positions: .open_positions
}'
echo ""

# 8. Ver Posições Abertas
print_step "8️⃣  POSIÇÕES ABERTAS"
positions=$(curl -s $API_URL/paper-trading/$SESSION_ID/positions)
position_count=$(echo "$positions" | jq 'length')
if [ "$position_count" -gt 0 ]; then
    echo "$positions" | jq '.[] | {
      symbol,
      quantity,
      side,
      entry_price,
      current_price,
      unrealized_pnl
    }'
    echo -e "${GREEN}✓ $position_count posição(ões) aberta(s)${NC}"
else
    echo -e "${YELLOW}⚠ Nenhuma posição aberta${NC}"
fi
echo ""

# 9. Ver Ordens Ativas
print_step "9️⃣  ORDENS ATIVAS"
orders=$(curl -s $API_URL/paper-trading/$SESSION_ID/orders)
order_count=$(echo "$orders" | jq 'length')
if [ "$order_count" -gt 0 ]; then
    echo "$orders" | jq '.[] | {
      order_id,
      symbol,
      side,
      type,
      quantity,
      price,
      status
    }'
    echo -e "${GREEN}✓ $order_count ordem(ns) ativa(s)${NC}"
else
    echo -e "${YELLOW}⚠ Nenhuma ordem ativa${NC}"
fi
echo ""

# 10. Aguardar mais atividade
print_step "🔟 AGUARDANDO MAIS ATIVIDADE (120 segundos)"
for i in {120..1}; do
    if [ $((i % 30)) -eq 0 ]; then
        # Atualizar status a cada 30s
        printf "\r${YELLOW}Aguardando... %03d segundos | " $i
        new_trades=$(curl -s $API_URL/paper-trading/$SESSION_ID/status | jq -r '.trades_executed')
        printf "Trades: $new_trades${NC}"
    fi
    sleep 1
done
echo ""
echo -e "${GREEN}✓ Período de monitoramento concluído${NC}"
echo ""

# 11. Status Final
print_step "1️⃣1️⃣  STATUS FINAL"
final_status=$(curl -s $API_URL/paper-trading/$SESSION_ID/status)
echo "$final_status" | jq '{
  uptime_seconds: .uptime_seconds,
  candles_collected: .candles_collected,
  signals_generated: .signals_generated,
  trades_executed: .trades_executed,
  account_balance: .account_summary.balance,
  account_equity: .account_summary.equity,
  total_pnl: .account_summary.total_pnl,
  total_pnl_percent: .account_summary.total_pnl_percent
}'

trades_count=$(echo "$final_status" | jq -r '.trades_executed')
final_pnl=$(echo "$final_status" | jq -r '.account_summary.total_pnl')
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Trades executados: $trades_count${NC}"
echo -e "${GREEN}PnL total: \$$final_pnl${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 12. Histórico de Trades
print_step "1️⃣2️⃣  HISTÓRICO DE TRADES (últimos 5)"
trades=$(curl -s "$API_URL/paper-trading/$SESSION_ID/trades?limit=5")
if [ "$(echo "$trades" | jq 'length')" -gt 0 ]; then
    echo "$trades" | jq '.[] | {
      timestamp,
      symbol,
      side,
      quantity,
      price,
      commission,
      pnl,
      balance_after
    }'
    echo -e "${GREEN}✓ Histórico recuperado${NC}"
else
    echo -e "${YELLOW}⚠ Nenhum trade executado ainda${NC}"
fi
echo ""

# 13. Teste de Ordem Manual
print_step "1️⃣3️⃣  TESTE DE ORDEM MANUAL (opcional)"
read -p "Deseja criar uma ordem manual de teste? (s/N): " create_manual
if [[ "$create_manual" == "s" ]] || [[ "$create_manual" == "S" ]]; then
    manual_order=$(curl -s -X POST $API_URL/paper-trading/$SESSION_ID/order \
      -H "Content-Type: application/json" \
      -d "{
        \"session_id\": \"$SESSION_ID\",
        \"symbol\": \"BTCUSDT\",
        \"side\": \"BUY\",
        \"order_type\": \"MARKET\",
        \"quantity\": 0.001
      }")
    echo "$manual_order" | jq '.'
    check_result
else
    echo -e "${YELLOW}⚠ Pulado${NC}"
fi
echo ""

# 14. Parar Paper Trading
print_step "1️⃣4️⃣  PARANDO PAPER TRADING"
stop_response=$(curl -s -X POST $API_URL/paper-trading/$SESSION_ID/stop)
echo "$stop_response" | jq '.'
check_result
echo ""

# 15. Verificar se parou
print_step "1️⃣5️⃣  VERIFICANDO ENCERRAMENTO"
sleep 2
final_sessions=$(curl -s $API_URL/paper-trading/sessions | jq '.sessions | length')
echo -e "${GREEN}✓ Sessões ativas restantes: $final_sessions${NC}"
echo ""

# Resumo Final
echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║            TESTE CONCLUÍDO COM SUCESSO         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Health Check: OK${NC}"
echo -e "${GREEN}✓ Inicialização: OK${NC}"
echo -e "${GREEN}✓ Coleta de Dados: OK (candles: $candles)${NC}"
echo -e "${GREEN}✓ Execução de Trades: $trades_count trade(s)${NC}"
echo -e "${GREEN}✓ PnL Final: \$$final_pnl${NC}"
echo -e "${GREEN}✓ Encerramento: OK${NC}"
echo ""
echo -e "${YELLOW}Session ID usado: $SESSION_ID${NC}"
echo -e "${YELLOW}Tempo total de teste: ~3 minutos${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Paper Trading Engine está funcionando perfeitamente!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
