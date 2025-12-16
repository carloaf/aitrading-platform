#!/bin/bash

# Script de Monitoramento Contínuo do Paper Trading
# Uso: ./monitor_paper_trading.sh <session_id>

SESSION_ID="$1"

if [ -z "$SESSION_ID" ]; then
  echo "❌ Erro: Session ID é obrigatório"
  echo "Uso: $0 <session_id>"
  echo ""
  echo "Para ver sessões ativas:"
  echo "  curl http://localhost:3008/paper-trading/sessions | jq '.sessions[]'"
  exit 1
fi

API_URL="http://localhost:3008"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    PAPER TRADING - MONITORAMENTO EM TEMPO REAL  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Session ID: $SESSION_ID${NC}"
echo -e "${CYAN}Pressione Ctrl+C para parar${NC}"
echo ""
sleep 2

# Contador de iterações
iteration=0

while true; do
  iteration=$((iteration + 1))
  clear
  
  echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║          PAPER TRADING - MONITORAMENTO         ║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "${CYAN}🕐 $(date '+%Y-%m-%d %H:%M:%S')${NC}"
  echo -e "${YELLOW}Session: $SESSION_ID | Atualização #$iteration${NC}"
  echo ""
  
  # Buscar status
  status=$(curl -s $API_URL/paper-trading/$SESSION_ID/status 2>/dev/null)
  
  if [ $? -ne 0 ] || [ -z "$status" ]; then
    echo -e "${RED}❌ Erro ao conectar com a API${NC}"
    echo ""
    echo "Verifique se o container está rodando:"
    echo "  docker ps | grep execution-engine"
    sleep 10
    continue
  fi
  
  # Verificar se sessão existe
  is_running=$(echo "$status" | jq -r '.is_running // "error"')
  
  if [ "$is_running" == "error" ] || [ "$is_running" == "null" ]; then
    echo -e "${RED}❌ Sessão não encontrada${NC}"
    echo ""
    echo "Sessões ativas:"
    curl -s $API_URL/paper-trading/sessions | jq '.sessions[]'
    exit 1
  fi
  
  # Extrair dados
  strategy=$(echo "$status" | jq -r '.strategy_name')
  symbol=$(echo "$status" | jq -r '.symbol')
  timeframe=$(echo "$status" | jq -r '.timeframe')
  uptime=$(echo "$status" | jq -r '.uptime_seconds')
  candles=$(echo "$status" | jq -r '.candles_collected')
  signals=$(echo "$status" | jq -r '.signals_generated')
  trades=$(echo "$status" | jq -r '.trades_executed')
  position_open=$(echo "$status" | jq -r '.position_open')
  last_signal=$(echo "$status" | jq -r '.last_signal')
  
  # Dados da conta
  balance=$(echo "$status" | jq -r '.account_summary.balance')
  equity=$(echo "$status" | jq -r '.account_summary.equity')
  pnl=$(echo "$status" | jq -r '.account_summary.total_pnl')
  pnl_pct=$(echo "$status" | jq -r '.account_summary.total_pnl_percent')
  open_pos=$(echo "$status" | jq -r '.account_summary.open_positions')
  
  # Status de execução
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}📊 STATUS DA EXECUÇÃO${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  
  if [ "$is_running" == "true" ]; then
    echo -e "Status: ${GREEN}✓ RODANDO${NC}"
  else
    echo -e "Status: ${RED}✗ PARADO${NC}"
  fi
  
  uptime_min=$((uptime / 60))
  uptime_sec=$((uptime % 60))
  echo -e "Estratégia: ${CYAN}$strategy${NC}"
  echo -e "Par: ${CYAN}$symbol${NC} | Timeframe: ${CYAN}$timeframe${NC}"
  echo -e "Tempo ativo: ${YELLOW}${uptime_min}m ${uptime_sec}s${NC}"
  echo ""
  
  # Dados coletados
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}📡 DADOS COLETADOS${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "Candles: ${CYAN}$candles${NC}"
  
  if [ "$candles" -lt 50 ]; then
    echo -e "Status: ${YELLOW}⚠ Coletando dados... (mínimo: 50)${NC}"
  else
    echo -e "Status: ${GREEN}✓ Dados suficientes${NC}"
  fi
  echo ""
  
  # Sinais e Trades
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}📈 ATIVIDADE DE TRADING${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "Sinais gerados: ${CYAN}$signals${NC}"
  echo -e "Trades executados: ${CYAN}$trades${NC}"
  
  if [ "$last_signal" == "1" ]; then
    echo -e "Último sinal: ${GREEN}▲ COMPRA (1)${NC}"
  elif [ "$last_signal" == "-1" ]; then
    echo -e "Último sinal: ${RED}▼ VENDA (-1)${NC}"
  else
    echo -e "Último sinal: ${YELLOW}● NEUTRO (0)${NC}"
  fi
  
  if [ "$position_open" == "true" ]; then
    echo -e "Posição: ${GREEN}✓ ABERTA${NC}"
  else
    echo -e "Posição: ${YELLOW}○ FECHADA${NC}"
  fi
  echo ""
  
  # Conta
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}💰 RESUMO DA CONTA${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "Balance: ${CYAN}\$$(printf "%.2f" $balance)${NC}"
  echo -e "Equity: ${CYAN}\$$(printf "%.2f" $equity)${NC}"
  
  # Colorir PnL
  if (( $(echo "$pnl > 0" | bc -l) )); then
    echo -e "PnL Total: ${GREEN}\$$(printf "%.2f" $pnl) (+$(printf "%.2f" $pnl_pct)%)${NC}"
  elif (( $(echo "$pnl < 0" | bc -l) )); then
    echo -e "PnL Total: ${RED}\$$(printf "%.2f" $pnl) ($(printf "%.2f" $pnl_pct)%)${NC}"
  else
    echo -e "PnL Total: ${YELLOW}\$0.00 (0.00%)${NC}"
  fi
  
  echo -e "Posições abertas: ${CYAN}$open_pos${NC}"
  echo ""
  
  # Posições Abertas
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}📍 POSIÇÕES ABERTAS${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  
  positions=$(curl -s $API_URL/paper-trading/$SESSION_ID/positions)
  position_count=$(echo "$positions" | jq 'length')
  
  if [ "$position_count" -gt 0 ]; then
    echo "$positions" | jq -r '.[] | 
      "Par: \(.symbol) | Qtd: \(.quantity) | Entrada: $\(.entry_price) | Atual: $\(.current_price) | PnL: $\(.unrealized_pnl)"'
  else
    echo -e "${YELLOW}⚠ Nenhuma posição aberta${NC}"
  fi
  echo ""
  
  # Últimos Trades
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}📋 ÚLTIMOS 3 TRADES${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  
  recent_trades=$(curl -s "$API_URL/paper-trading/$SESSION_ID/trades?limit=3")
  trade_count=$(echo "$recent_trades" | jq 'length')
  
  if [ "$trade_count" -gt 0 ]; then
    echo "$recent_trades" | jq -r '.[] | 
      "\(.timestamp) | \(.side) \(.quantity) @ $\(.price) | Balance: $\(.balance_after | tonumber | floor)"'
  else
    echo -e "${YELLOW}⚠ Nenhum trade executado ainda${NC}"
  fi
  echo ""
  
  # Footer
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}🔄 Próxima atualização em 10 segundos...${NC}"
  echo -e "${CYAN}Pressione Ctrl+C para parar o monitoramento${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  
  sleep 10
done
