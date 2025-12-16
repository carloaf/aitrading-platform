#!/bin/bash

# Script para testar todas as estratégias profissionais
# Data: 9 de dezembro de 2025

echo "🚀 AI Trading Platform - Teste de Todas as Estratégias"
echo "======================================================"
echo ""
echo "Período: 2024-01-01 a 2024-12-09"
echo "Símbolo: BTCUSDT"
echo "Capital Inicial: \$10,000"
echo ""
echo "======================================================"
echo ""

strategies=(
    "trend_following"
    "mean_reversion"
    "volatility_breakout"
    "macd_rsi_combo"
    "bollinger_bands"
    "momentum"
    "volume_profile"
    "multi_timeframe"
    "dynamic_position_sizing"
)

results=()

for strategy in "${strategies[@]}"; do
    echo -n "⏳ Testando $strategy..."
    
    response=$(curl -s -X POST "http://localhost:3007/strategies/$strategy/backtest?symbol=BTCUSDT&start_date=2024-01-01&end_date=2024-12-09&initial_capital=10000")
    
    if [ $? -eq 0 ]; then
        return_pct=$(echo "$response" | jq -r '.total_return')
        trades=$(echo "$response" | jq -r '.total_trades')
        win_rate=$(echo "$response" | jq -r '.win_rate')
        final_capital=$(echo "$response" | jq -r '.final_capital')
        
        # Formatar resultado
        printf "\r✅ %-30s | Retorno: %8.2f%% | Trades: %3d | Win Rate: %6.2f%% | Capital Final: \$%10.2f\n" \
            "$strategy" "$return_pct" "$trades" "$win_rate" "$final_capital"
        
        # Armazenar para ranking
        results+=("$return_pct|$strategy|$trades|$win_rate|$final_capital")
    else
        echo "\r❌ $strategy - Erro ao executar backtest"
    fi
done

echo ""
echo "======================================================"
echo "🏆 RANKING DAS ESTRATÉGIAS (por retorno)"
echo "======================================================"
echo ""

# Ordenar resultados por retorno (descendente)
IFS=$'\n' sorted=($(sort -t'|' -k1 -rn <<<"${results[*]}"))
unset IFS

position=1
for result in "${sorted[@]}"; do
    IFS='|' read -r return strategy trades win_rate final_capital <<< "$result"
    
    # Emoji baseado na posição
    if [ $position -eq 1 ]; then
        emoji="🥇"
    elif [ $position -eq 2 ]; then
        emoji="🥈"
    elif [ $position -eq 3 ]; then
        emoji="🥉"
    else
        emoji="  "
    fi
    
    # Cor baseada no retorno
    if (( $(echo "$return > 0" | bc -l) )); then
        color="\033[0;32m" # Verde
    else
        color="\033[0;31m" # Vermelho
    fi
    reset="\033[0m"
    
    printf "%s %d. %-30s | ${color}%8.2f%%${reset} | %3d trades | %6.2f%% win rate\n" \
        "$emoji" "$position" "$strategy" "$return" "$trades" "$win_rate"
    
    ((position++))
done

echo ""
echo "======================================================"
echo "📊 ESTATÍSTICAS GERAIS"
echo "======================================================"
echo ""

# Calcular média de retorno
total_return=0
for result in "${results[@]}"; do
    return=$(echo "$result" | cut -d'|' -f1)
    total_return=$(echo "$total_return + $return" | bc -l)
done
avg_return=$(echo "scale=2; $total_return / ${#results[@]}" | bc -l)

echo "Total de estratégias testadas: ${#results[@]}"
echo "Retorno médio: $avg_return%"
echo ""

# Contar estratégias lucrativas
profitable=0
for result in "${results[@]}"; do
    return=$(echo "$result" | cut -d'|' -f1)
    if (( $(echo "$return > 0" | bc -l) )); then
        ((profitable++))
    fi
done

echo "Estratégias lucrativas: $profitable / ${#results[@]}"
echo ""

echo "======================================================"
echo "✅ Teste concluído!"
echo "======================================================"
