#!/bin/bash

# Script para executar simulação Monte Carlo em uma estratégia

EXECUTION_ENGINE_URL="http://localhost:3008"

echo "=========================================="
echo "🎲 MONTE CARLO SIMULATION"
echo "=========================================="
echo ""

# Parâmetros
STRATEGY=${1:-"momentum"}
ITERATIONS=${2:-10000}
LOOKBACK_DAYS=${3:-180}  # 6 meses para período balanceado

echo "📊 Estratégia: $STRATEGY"
echo "🔢 Iterações: $ITERATIONS"
echo "📅 Lookback: $LOOKBACK_DAYS dias"
echo ""

# Definir parameter ranges baseado na estratégia
case $STRATEGY in
    "momentum")
        PARAM_RANGES='{
            "roc_period": [5, 20],
            "threshold": [0.5, 3.0]
        }'
        ;;
    "macd_rsi_combo")
        PARAM_RANGES='{
            "macd_fast": [8, 16],
            "macd_slow": [20, 30],
            "macd_signal": [7, 11],
            "rsi_period": [10, 18],
            "rsi_overbought": [65, 75],
            "rsi_oversold": [25, 35]
        }'
        ;;
    "trend_following")
        PARAM_RANGES='{
            "ema_fast": [8, 16],
            "ema_slow": [20, 30],
            "adx_period": [10, 18],
            "adx_threshold": [20, 30]
        }'
        ;;
    "volatility_breakout")
        PARAM_RANGES='{
            "atr_period": [10, 20],
            "atr_multiplier": [1.5, 3.0],
            "volume_ma_period": [15, 25]
        }'
        ;;
    "bollinger_bands")
        PARAM_RANGES='{
            "bb_period": [15, 25],
            "bb_std": [1.5, 2.5],
            "rsi_period": [10, 18]
        }'
        ;;
    *)
        echo "❌ Estratégia desconhecida: $STRATEGY"
        echo ""
        echo "Estratégias disponíveis:"
        echo "  - momentum"
        echo "  - macd_rsi_combo"
        echo "  - trend_following"
        echo "  - volatility_breakout"
        echo "  - bollinger_bands"
        exit 1
        ;;
esac

echo "🎲 Iniciando simulação..."
echo ""

# Executar simulação
RESPONSE=$(curl -s -X POST "${EXECUTION_ENGINE_URL}/api/monte-carlo/simulate" \
    -H "Content-Type: application/json" \
    -d "{
        \"strategy_name\": \"$STRATEGY\",
        \"symbol\": \"BTCUSDT\",
        \"interval\": \"1h\",
        \"lookback_days\": $LOOKBACK_DAYS,
        \"iterations\": $ITERATIONS,
        \"initial_balance\": 10000.0,
        \"parameter_ranges\": $PARAM_RANGES,
        \"parallel\": true
    }")

# Verificar erro
if echo "$RESPONSE" | grep -q '"detail"'; then
    echo "❌ Erro na simulação:"
    echo "$RESPONSE" | jq -r '.detail'
    exit 1
fi

# Extrair resultados
STATUS=$(echo "$RESPONSE" | jq -r '.status')

if [ "$STATUS" == "completed" ]; then
    echo "✅ Simulação concluída com sucesso!"
    echo ""
    echo "=========================================="
    echo "📊 RESULTADOS DA SIMULAÇÃO"
    echo "=========================================="
    echo ""
    
    # Estatísticas de retorno
    MEAN_RETURN=$(echo "$RESPONSE" | jq -r '.report.return_statistics.mean')
    MEDIAN_RETURN=$(echo "$RESPONSE" | jq -r '.report.return_statistics.median')
    STD_RETURN=$(echo "$RESPONSE" | jq -r '.report.return_statistics.std')
    PERCENTILE_5=$(echo "$RESPONSE" | jq -r '.report.return_statistics.percentile_5')
    PERCENTILE_95=$(echo "$RESPONSE" | jq -r '.report.return_statistics.percentile_95')
    
    echo "📈 ESTATÍSTICAS DE RETORNO:"
    echo "   Retorno Médio: ${MEAN_RETURN}%"
    echo "   Retorno Mediano: ${MEDIAN_RETURN}%"
    echo "   Desvio Padrão: ${STD_RETURN}%"
    echo "   95% CI: [${PERCENTILE_5}%, ${PERCENTILE_95}%]"
    echo ""
    
    # Métricas de risco
    PROB_PROFIT=$(echo "$RESPONSE" | jq -r '.report.risk_metrics.probability_of_profit')
    PROB_LOSS=$(echo "$RESPONSE" | jq -r '.report.risk_metrics.probability_of_loss')
    VAR_95=$(echo "$RESPONSE" | jq -r '.report.risk_metrics.value_at_risk_95')
    CVAR_95=$(echo "$RESPONSE" | jq -r '.report.risk_metrics.conditional_var_95')
    
    echo "⚠️  MÉTRICAS DE RISCO:"
    echo "   Probabilidade de Lucro: ${PROB_PROFIT}%"
    echo "   Probabilidade de Prejuízo: ${PROB_LOSS}%"
    echo "   95% VaR (Value at Risk): ${VAR_95}%"
    echo "   95% CVaR (Expected Shortfall): ${CVAR_95}%"
    echo ""
    
    # Sharpe Ratio
    MEAN_SHARPE=$(echo "$RESPONSE" | jq -r '.report.sharpe_statistics.mean')
    MEDIAN_SHARPE=$(echo "$RESPONSE" | jq -r '.report.sharpe_statistics.median')
    
    echo "⚡ SHARPE RATIO:"
    echo "   Sharpe Médio: ${MEAN_SHARPE}"
    echo "   Sharpe Mediano: ${MEDIAN_SHARPE}"
    echo ""
    
    # Drawdown
    MEAN_DD=$(echo "$RESPONSE" | jq -r '.report.drawdown_statistics.mean')
    WORST_DD=$(echo "$RESPONSE" | jq -r '.report.drawdown_statistics.worst')
    
    echo "📉 DRAWDOWN:"
    echo "   Max DD Médio: ${MEAN_DD}%"
    echo "   Pior DD: ${WORST_DD}%"
    echo ""
    
    # Cenários
    BEST_RETURN=$(echo "$RESPONSE" | jq -r '.report.scenarios.best_case.total_return')
    WORST_RETURN=$(echo "$RESPONSE" | jq -r '.report.scenarios.worst_case.total_return')
    MEDIAN_CASE_RETURN=$(echo "$RESPONSE" | jq -r '.report.scenarios.median_case.total_return')
    
    echo "🎯 CENÁRIOS:"
    echo "   Melhor Caso: +${BEST_RETURN}%"
    echo "   Cenário Mediano: ${MEDIAN_CASE_RETURN}%"
    echo "   Pior Caso: ${WORST_RETURN}%"
    echo ""
    
    # Informações da execução
    TOTAL_ITERS=$(echo "$RESPONSE" | jq -r '.report.total_iterations')
    SUCCESSFUL=$(echo "$RESPONSE" | jq -r '.report.successful_runs')
    FAILED=$(echo "$RESPONSE" | jq -r '.report.failed_runs')
    EXEC_TIME=$(echo "$RESPONSE" | jq -r '.report.execution_time')
    
    echo "⏱️  PERFORMANCE:"
    echo "   Total de Iterações: ${TOTAL_ITERS}"
    echo "   Simulações bem-sucedidas: ${SUCCESSFUL}"
    echo "   Simulações falhadas: ${FAILED}"
    echo "   Tempo de Execução: ${EXEC_TIME}s"
    echo ""
    
    # Arquivo do relatório
    REPORT_FILE=$(echo "$RESPONSE" | jq -r '.report_file')
    echo "📄 Relatório salvo em: $REPORT_FILE"
    echo ""
    
    # Interpretação
    echo "=========================================="
    echo "💡 INTERPRETAÇÃO"
    echo "=========================================="
    echo ""
    
    # Avaliar rentabilidade
    if (( $(echo "$MEAN_RETURN > 0" | bc -l) )); then
        echo "✅ Estratégia rentável (retorno médio positivo)"
    else
        echo "❌ Estratégia não rentável (retorno médio negativo)"
    fi
    
    # Avaliar risco
    if (( $(echo "$PROB_PROFIT >= 60" | bc -l) )); then
        echo "✅ Alta probabilidade de lucro (≥60%)"
    elif (( $(echo "$PROB_PROFIT >= 50" | bc -l) )); then
        echo "⚠️  Probabilidade moderada de lucro (50-60%)"
    else
        echo "❌ Baixa probabilidade de lucro (<50%)"
    fi
    
    # Avaliar Sharpe
    if (( $(echo "$MEAN_SHARPE >= 2.0" | bc -l) )); then
        echo "✅ Excelente Sharpe Ratio (≥2.0)"
    elif (( $(echo "$MEAN_SHARPE >= 1.0" | bc -l) )); then
        echo "⚠️  Sharpe Ratio aceitável (1.0-2.0)"
    else
        echo "❌ Sharpe Ratio ruim (<1.0)"
    fi
    
    echo ""
    echo "=========================================="
    
else
    echo "❌ Falha na simulação"
    echo "$RESPONSE" | jq '.'
fi

echo ""
echo "🔗 Ver todos os relatórios:"
echo "   curl http://localhost:3008/api/monte-carlo/reports | jq ."
echo ""
