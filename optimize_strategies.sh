#!/bin/bash

# Script para executar otimização de parâmetros via API
# Data: 9 de dezembro de 2025

echo "🔧 AI Trading Platform - Otimização de Parâmetros"
echo "=================================================="
echo ""

# Configurações padrão
API_URL="http://localhost:3007"
SYMBOL="${1:-BTCUSDT}"
START_DATE="${2:-2023-01-01}"
END_DATE="${3:-$(date +%Y-%m-%d)}"

# Estratégias top performers
STRATEGIES=(
    "volume_profile"
    "momentum"
    "macd_rsi_combo"
    "multi_timeframe"
    "volatility_breakout"
)

echo "Configuração:"
echo "  Símbolo: $SYMBOL"
echo "  Período: $START_DATE até $END_DATE"
echo "  Estratégias: ${#STRATEGIES[@]}"
echo ""
echo "=================================================="
echo ""

# Criar diretório para resultados
mkdir -p optimization_results
cd optimization_results

# Executar otimização para cada estratégia
for strategy in "${STRATEGIES[@]}"; do
    echo ""
    echo "🚀 Otimizando estratégia: $strategy"
    echo "--------------------------------------------------"
    
    # Fazer requisição POST
    response=$(curl -s -X POST "${API_URL}/strategies/${strategy}/optimize?symbol=${SYMBOL}&start_date=${START_DATE}&end_date=${END_DATE}")
    
    # Verificar se teve sucesso
    if [ $? -eq 0 ]; then
        # Salvar resposta
        echo "$response" > "${strategy}_${SYMBOL}_optimization.json"
        
        # Extrair informações principais
        best_return=$(echo "$response" | jq -r '.best_performance.out_sample_return')
        best_sharpe=$(echo "$response" | jq -r '.best_performance.out_sample_sharpe')
        best_winrate=$(echo "$response" | jq -r '.best_performance.out_sample_win_rate')
        robustness=$(echo "$response" | jq -r '.best_performance.robustness_score')
        best_params=$(echo "$response" | jq -r '.best_parameters')
        
        echo "✅ Otimização concluída!"
        echo ""
        echo "📊 Melhores Parâmetros:"
        echo "$best_params" | jq '.'
        echo ""
        echo "📈 Performance:"
        echo "  Retorno Out-Sample: ${best_return}%"
        echo "  Sharpe Ratio: ${best_sharpe}"
        echo "  Win Rate: ${best_winrate}%"
        echo "  Robustness Score: ${robustness}"
        echo ""
        echo "💾 Resultados salvos em: ${strategy}_${SYMBOL}_optimization.json"
    else
        echo "❌ Erro ao otimizar $strategy"
    fi
    
    echo ""
    echo "--------------------------------------------------"
    
    # Aguardar 2 segundos entre estratégias
    sleep 2
done

echo ""
echo "=================================================="
echo "✅ Todas as otimizações concluídas!"
echo ""
echo "📁 Resultados disponíveis em: $(pwd)"
echo ""

# Criar relatório comparativo
echo "📊 RELATÓRIO COMPARATIVO" > optimization_summary.txt
echo "=======================" >> optimization_summary.txt
echo "" >> optimization_summary.txt

for strategy in "${STRATEGIES[@]}"; do
    if [ -f "${strategy}_${SYMBOL}_optimization.json" ]; then
        echo "Estratégia: $strategy" >> optimization_summary.txt
        jq -r '.best_performance | "  Retorno: \(.out_sample_return)% | Sharpe: \(.out_sample_sharpe) | Win Rate: \(.out_sample_win_rate)% | Robustness: \(.robustness_score)"' "${strategy}_${SYMBOL}_optimization.json" >> optimization_summary.txt
        echo "" >> optimization_summary.txt
    fi
done

cat optimization_summary.txt

echo ""
echo "=================================================="
