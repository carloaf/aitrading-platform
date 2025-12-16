#!/bin/bash
# Multi-Strategy Paper Trading Monitor
# Monitora todas as sessões de paper trading simultaneamente

export LC_NUMERIC=C

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

API_URL="http://localhost:3008"

clear_screen() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║       📊 MULTI-STRATEGY PAPER TRADING MONITOR - AI TRADING PLATFORM         ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

format_pnl() {
    local pnl=$1
    if (( $(echo "$pnl >= 0" | bc -l) )); then
        echo -e "${GREEN}+\$$(printf '%.2f' $pnl)${NC}"
    else
        echo -e "${RED}\$$(printf '%.2f' $pnl)${NC}"
    fi
}

format_uptime() {
    local seconds=$1
    local hours=$(echo "$seconds / 3600" | bc)
    local mins=$(echo "($seconds % 3600) / 60" | bc)
    local secs=$(echo "$seconds % 60" | bc)
    printf "%02dh %02dm %02ds" $hours $mins $secs
}

print_session() {
    local session_id=$1
    local data=$(curl -s "$API_URL/paper-trading/$session_id/status" 2>/dev/null)
    
    if [ -z "$data" ] || [ "$data" == "null" ]; then
        echo -e "${RED}  ❌ Erro ao obter dados de $session_id${NC}"
        return
    fi
    
    local strategy=$(echo $data | jq -r '.strategy_name // "Unknown"')
    local symbol=$(echo $data | jq -r '.symbol // "N/A"')
    local timeframe=$(echo $data | jq -r '.timeframe // "N/A"')
    local is_running=$(echo $data | jq -r '.is_running // false')
    local uptime=$(echo $data | jq -r '.uptime_seconds // 0')
    local candles=$(echo $data | jq -r '.candles_collected // 0')
    local signals=$(echo $data | jq -r '.signals_generated // 0')
    local trades=$(echo $data | jq -r '.trades_executed // 0')
    local balance=$(echo $data | jq -r '.account_summary.balance // 0')
    local pnl=$(echo $data | jq -r '.account_summary.total_pnl // 0')
    local pnl_pct=$(echo $data | jq -r '.account_summary.total_pnl_percent // 0')
    local position=$(echo $data | jq -r '.position_open // false')
    
    # Status icon
    local status_icon="🟢"
    if [ "$is_running" != "true" ]; then
        status_icon="🔴"
    fi
    
    # Position icon
    local pos_icon="⏸️"
    if [ "$position" == "true" ]; then
        pos_icon="📈"
    fi
    
    # Format PnL with color
    local pnl_formatted=$(format_pnl $pnl)
    local pnl_pct_formatted
    if (( $(echo "$pnl_pct >= 0" | bc -l) )); then
        pnl_pct_formatted="${GREEN}+$(printf '%.2f' $pnl_pct)%${NC}"
    else
        pnl_pct_formatted="${RED}$(printf '%.2f' $pnl_pct)%${NC}"
    fi
    
    echo -e "${BOLD}┌─────────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BOLD}│${NC} $status_icon ${CYAN}$session_id${NC}"
    echo -e "${BOLD}│${NC}    ${YELLOW}$strategy${NC} | $symbol | $timeframe"
    echo -e "${BOLD}├─────────────────────────────────────────────────────────────────────┤${NC}"
    printf "${BOLD}│${NC}  ⏱️  Uptime: %-15s 📊 Candles: %-8s 📡 Sinais: %-5s\n" "$(format_uptime $uptime)" "$candles" "$signals"
    printf "${BOLD}│${NC}  💰 Saldo: \$%-12.2f 📈 Trades: %-8s %s Posição: %-5s\n" "$balance" "$trades" "$pos_icon" "$position"
    echo -e "${BOLD}│${NC}  💵 PnL: $pnl_formatted ($pnl_pct_formatted)"
    echo -e "${BOLD}└─────────────────────────────────────────────────────────────────────┘${NC}"
    echo ""
}

print_summary() {
    local sessions_data=$(curl -s "$API_URL/paper-trading/sessions" 2>/dev/null)
    local total_sessions=$(echo $sessions_data | jq -r '.total_sessions // 0')
    
    local total_pnl=0
    local total_trades=0
    local running_count=0
    
    for row in $(echo $sessions_data | jq -r '.sessions[] | @base64'); do
        _jq() {
            echo ${row} | base64 --decode | jq -r ${1}
        }
        
        local pnl=$(_jq '.total_pnl')
        local trades=$(_jq '.trades_executed')
        local running=$(_jq '.is_running')
        
        total_pnl=$(echo "$total_pnl + $pnl" | bc -l)
        total_trades=$(echo "$total_trades + $trades" | bc)
        
        if [ "$running" == "true" ]; then
            running_count=$((running_count + 1))
        fi
    done
    
    echo -e "${BOLD}${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                              📈 RESUMO GERAL                                 ║"
    echo "╠══════════════════════════════════════════════════════════════════════════════╣"
    printf "║  Sessões: %d/%d ativas    Trades Total: %-10d PnL Total: " "$running_count" "$total_sessions" "$total_trades"
    
    if (( $(echo "$total_pnl >= 0" | bc -l) )); then
        printf "${GREEN}+\$%.2f${PURPLE}" "$total_pnl"
    else
        printf "${RED}\$%.2f${PURPLE}" "$total_pnl"
    fi
    echo "        ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Main loop
while true; do
    clear_screen
    
    # Get all sessions
    sessions=$(curl -s "$API_URL/paper-trading/sessions" | jq -r '.sessions[].session_id' 2>/dev/null)
    
    if [ -z "$sessions" ]; then
        echo -e "${RED}  ❌ Nenhuma sessão encontrada ou API indisponível${NC}"
    else
        for session in $sessions; do
            print_session "$session"
        done
    fi
    
    print_summary
    
    echo -e "${CYAN}Última atualização: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${YELLOW}Pressione Ctrl+C para sair | Atualizando a cada 15 segundos...${NC}"
    
    sleep 15
done
