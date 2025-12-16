#!/bin/bash
# MULTI-ASSET WALK-FORWARD OPTIMIZATION - PASSO 27.2
# =====================================================
# Executa WFO simultaneamente em BTC, ETH e SOL
# Gera análise comparativa de performance
#
# Uso: bash scripts/wfo_multi_asset.sh [period] [start_date] [end_date]
# Exemplo: bash scripts/wfo_multi_asset.sh "q4_2025" "2025-10-01" "2025-12-31"
#
# Autor: CryptoDev Assistant
# Data: 16/Dez/2025

set -euo pipefail

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuração
PERIOD_NAME="${1:-monthly}"
START_DATE="${2:-$(date -d '1 month ago' +%Y-%m-01)}"
END_DATE="${3:-$(date -d 'yesterday' +%Y-%m-%d)}"

API_URL="http://localhost:3008/api/meta-backtest/run"
OUTPUT_DIR="logs/wfo/multi_asset"
HISTORY_FILE="$OUTPUT_DIR/history.csv"

mkdir -p "$OUTPUT_DIR"

# Símbolos a testar
declare -a SYMBOLS=("BTCUSDT" "ETHUSDT" "SOLUSDT")

# Banner
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}         MULTI-ASSET WALK-FORWARD OPTIMIZATION            ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📅 Period Name:${NC} $PERIOD_NAME"
echo -e "${BLUE}📊 Date Range:${NC} $START_DATE → $END_DATE"
echo -e "${BLUE}🪙 Assets:${NC} ${SYMBOLS[*]}"
echo ""

# Arrays para armazenar resultados
declare -A RESULTS_RETURN
declare -A RESULTS_SHARPE
declare -A RESULTS_DD
declare -A RESULTS_WR
declare -A RESULTS_TRADES

# Função para executar backtest individual
run_backtest() {
    local symbol=$1
    
    echo -e "${YELLOW}[1/3]${NC} Testing ${symbol}..."
    
    # Executar backtest via API (chamada direta do host)
    result=$(curl -sS "$API_URL" \
        -H 'Content-Type: application/json' \
        -d "{
            \"symbol\": \"$symbol\",
            \"start_date\": \"$START_DATE 00:00:00\",
            \"end_date\": \"$END_DATE 23:59:59\",
            \"initial_capital\": 10000,
            \"use_synthetic\": false
        }")
    
    # Extrair métricas com jq (ou parsing manual)
    if command -v jq &> /dev/null; then
        local return_pct=$(echo "$result" | jq -r '.performance.total_return_pct // 0')
        local sharpe=$(echo "$result" | jq -r '.risk_metrics.sharpe_ratio // 0')
        local max_dd=$(echo "$result" | jq -r '.risk_metrics.max_drawdown_pct // 0')
        local win_rate=$(echo "$result" | jq -r '.trade_stats.win_rate // 0')
        local trades=$(echo "$result" | jq -r '.trade_stats.total_trades // 0')
    else
        # Parsing manual se jq não disponível
        local return_pct=$(echo "$result" | grep -oP '"total_return_pct":\s*\K[-0-9.]+' | head -1 || echo "0")
        local sharpe=$(echo "$result" | grep -oP '"sharpe_ratio":\s*\K[-0-9.]+' | head -1 || echo "0")
        local max_dd=$(echo "$result" | grep -oP '"max_drawdown_pct":\s*\K[-0-9.]+' | head -1 || echo "0")
        local win_rate=$(echo "$result" | grep -oP '"win_rate":\s*\K[-0-9.]+' | head -1 || echo "0")
        local trades=$(echo "$result" | grep -oP '"total_trades":\s*\K[0-9]+' | head -1 || echo "0")
    fi
    
    # Armazenar resultados
    RESULTS_RETURN[$symbol]=$return_pct
    RESULTS_SHARPE[$symbol]=$sharpe
    RESULTS_DD[$symbol]=$max_dd
    RESULTS_WR[$symbol]=$win_rate
    RESULTS_TRADES[$symbol]=$trades
    
    echo -e "   Return: ${return_pct}% | Sharpe: ${sharpe} | DD: ${max_dd}% | WR: ${win_rate}% | Trades: ${trades}"
}

# Executar backtests para cada símbolo
for symbol in "${SYMBOLS[@]}"; do
    run_backtest "$symbol"
    echo ""
done

# Análise Comparativa
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}              ANÁLISE COMPARATIVA                          ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Calcular médias
total_return=0
total_sharpe=0
total_dd=0
total_wr=0
total_trades=0
count=0

echo -e "${BLUE}Par      | Return  | Sharpe | Max DD | Win Rate | Trades${NC}"
echo "---------|---------|--------|--------|----------|--------"

for symbol in "${SYMBOLS[@]}"; do
    ret=${RESULTS_RETURN[$symbol]}
    shp=${RESULTS_SHARPE[$symbol]}
    dd=${RESULTS_DD[$symbol]}
    wr=${RESULTS_WR[$symbol]}
    trd=${RESULTS_TRADES[$symbol]}
    
    # Acumular para médias
    total_return=$(echo "$total_return + $ret" | bc -l)
    total_sharpe=$(echo "$total_sharpe + $shp" | bc -l)
    total_dd=$(echo "$total_dd + $dd" | bc -l)
    total_wr=$(echo "$total_wr + $wr" | bc -l)
    total_trades=$(echo "$total_trades + $trd" | bc -l)
    count=$((count + 1))
    
    # Formatar output (forçar locale C para usar ponto decimal)
    LC_NUMERIC=C printf "%-9s| %7.2f%% | %6.2f | %6.2f%% | %8.1f%% | %6d\n" \
        "$symbol" "$ret" "$shp" "$dd" "$wr" "$trd"
done

echo "---------|---------|--------|--------|----------|--------"

# Calcular e exibir médias
avg_return=$(echo "scale=2; $total_return / $count" | bc -l)
avg_sharpe=$(echo "scale=2; $total_sharpe / $count" | bc -l)
avg_dd=$(echo "scale=2; $total_dd / $count" | bc -l)
avg_wr=$(echo "scale=2; $total_wr / $count" | bc -l)
avg_trades=$(echo "scale=0; $total_trades / $count" | bc -l)

LC_NUMERIC=C printf "%-9s| %7.2f%% | %6.2f | %6.2f%% | %8.1f%% | %6d\n" \
    "MÉDIA" "$avg_return" "$avg_sharpe" "$avg_dd" "$avg_wr" "$avg_trades"

echo ""

# Identificar best/worst performers
best_symbol=""
best_return="-999999"
worst_symbol=""
worst_return="999999"

for symbol in "${SYMBOLS[@]}"; do
    ret=${RESULTS_RETURN[$symbol]}
    
    if (( $(echo "$ret > $best_return" | bc -l) )); then
        best_return=$ret
        best_symbol=$symbol
    fi
    
    if (( $(echo "$ret < $worst_return" | bc -l) )); then
        worst_return=$ret
        worst_symbol=$symbol
    fi
done

echo -e "${GREEN}🏆 BEST PERFORMER:${NC} $best_symbol ($best_return%)"
if (( $(echo "$worst_return < 0" | bc -l) )); then
    echo -e "${RED}⚠️  WORST PERFORMER:${NC} $worst_symbol ($worst_return%)"
else
    echo -e "${YELLOW}🟡 WEAKEST PERFORMER:${NC} $worst_symbol ($worst_return%)"
fi

echo ""

# Análise de Correlação
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}            ANÁLISE DE CORRELAÇÃO                          ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

positive_count=0
negative_count=0

for symbol in "${SYMBOLS[@]}"; do
    ret=${RESULTS_RETURN[$symbol]}
    if (( $(echo "$ret > 0" | bc -l) )); then
        positive_count=$((positive_count + 1))
    else
        negative_count=$((negative_count + 1))
    fi
done

echo -e "${BLUE}Pares Positivos:${NC} $positive_count/${#SYMBOLS[@]}"
echo -e "${BLUE}Pares Negativos:${NC} $negative_count/${#SYMBOLS[@]}"

if [ $positive_count -eq ${#SYMBOLS[@]} ]; then
    echo -e "${GREEN}✅ CONSISTÊNCIA TOTAL:${NC} Todos os pares positivos"
    correlation="high_positive"
elif [ $negative_count -eq ${#SYMBOLS[@]} ]; then
    echo -e "${RED}⚠️  PROBLEMA SISTÊMICO:${NC} Todos os pares negativos"
    correlation="high_negative"
elif [ $positive_count -gt $negative_count ]; then
    echo -e "${YELLOW}🟡 MAIORIA POSITIVA:${NC} Sistema funcionando com desvios"
    correlation="moderate_positive"
else
    echo -e "${YELLOW}🟡 MAIORIA NEGATIVA:${NC} Sistema com problemas em múltiplos pares"
    correlation="moderate_negative"
fi

echo ""

# Salvar em CSV
if [ ! -f "$HISTORY_FILE" ]; then
    echo "date,period,btc_return,btc_sharpe,btc_dd,btc_wr,btc_trades,eth_return,eth_sharpe,eth_dd,eth_wr,eth_trades,sol_return,sol_sharpe,sol_dd,sol_wr,sol_trades,avg_return,avg_sharpe,avg_dd,avg_wr,correlation" > "$HISTORY_FILE"
fi

csv_line="$(date +%Y-%m-%d),$PERIOD_NAME"
for symbol in "${SYMBOLS[@]}"; do
    csv_line="$csv_line,${RESULTS_RETURN[$symbol]},${RESULTS_SHARPE[$symbol]},${RESULTS_DD[$symbol]},${RESULTS_WR[$symbol]},${RESULTS_TRADES[$symbol]}"
done
csv_line="$csv_line,$avg_return,$avg_sharpe,$avg_dd,$avg_wr,$correlation"

echo "$csv_line" >> "$HISTORY_FILE"

echo -e "${GREEN}✅ Resultados salvos em:${NC} $HISTORY_FILE"
echo ""

# Resumo Final
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}                    RESUMO FINAL                           ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Período:${NC} $PERIOD_NAME ($START_DATE → $END_DATE)"
echo -e "${BLUE}Return Médio:${NC} $avg_return%"
echo -e "${BLUE}Sharpe Médio:${NC} $avg_sharpe"
echo -e "${BLUE}Drawdown Médio:${NC} $avg_dd%"
echo -e "${BLUE}Win Rate Médio:${NC} $avg_wr%"
echo -e "${BLUE}Trades Médios:${NC} $avg_trades"
echo -e "${BLUE}Correlação:${NC} $correlation"
echo ""

# Exit code baseado em performance
if (( $(echo "$avg_return > 0 && $positive_count >= 2" | bc -l) )); then
    echo -e "${GREEN}✅ Multi-Asset WFO: APROVADO${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Multi-Asset WFO: ATENÇÃO NECESSÁRIA${NC}"
    exit 1
fi
