#!/bin/bash
# Script para executar todas as simulações Monte Carlo robustas

API="http://localhost:3008/api/monte-carlo"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║      EXECUTANDO SIMULAÇÕES MONTE CARLO ROBUSTAS                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Função para executar simulação
execute_simulation() {
    local name=$1
    local strategy=$2
    local payload=$3
    
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│ $name"
    echo "└─────────────────────────────────────────────────────────────┘"
    
    curl -X POST "$API/simulate" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null 2>&1 &
    
    sleep 2
    
    # Monitorar
    for i in {1..120}; do
        resp=$(curl -s "$API/progress/$strategy" 2>/dev/null)
        status=$(echo "$resp" | jq -r '.status // "unknown"' 2>/dev/null)
        progress=$(echo "$resp" | jq -r '.progress // 0' 2>/dev/null)
        
        if [ "$status" = "completed" ]; then
            echo "✅ CONCLUÍDO!"
            elapsed=$(echo "$resp" | jq -r '.elapsed_time // 0' 2>/dev/null)
            printf "   Tempo: %.1fs\n\n" "$elapsed"
            break
        elif [ "$status" = "running" ]; then
            printf "\r   Progresso: %3.0f%%" "$progress"
        fi
        sleep 2
    done
}

# 1. Momentum
execute_simulation "MOMENTUM STRATEGY" "momentum" '{
    "strategy_name": "momentum",
    "symbol": "BTCUSDT",
    "iterations": 200,
    "parameter_ranges": {
        "roc_period": [5, 25],
        "threshold": [0.3, 4.0]
    },
    "parallel": true,
    "num_cores": 4
}'

# 2. MACD+RSI
execute_simulation "MACD + RSI COMBO" "macd_rsi_combo" '{
    "strategy_name": "macd_rsi_combo",
    "symbol": "BTCUSDT",
    "iterations": 200,
    "parameter_ranges": {
        "macd_fast": [6, 18],
        "macd_slow": [18, 35],
        "macd_signal": [6, 15],
        "rsi_period": [8, 25],
        "rsi_overbought": [60, 80],
        "rsi_oversold": [20, 40]
    },
    "parallel": true,
    "num_cores": 4
}'

# 3. Trend Following
execute_simulation "TREND FOLLOWING" "trend_following" '{
    "strategy_name": "trend_following",
    "symbol": "BTCUSDT",
    "iterations": 200,
    "parameter_ranges": {
        "ema_fast": [8, 35],
        "ema_slow": [35, 90],
        "adx_period": [8, 25],
        "adx_threshold": [15, 35]
    },
    "parallel": true,
    "num_cores": 4
}'

# 4. Volatility Breakout
execute_simulation "VOLATILITY BREAKOUT" "volatility_breakout" '{
    "strategy_name": "volatility_breakout",
    "symbol": "BTCUSDT",
    "iterations": 200,
    "parameter_ranges": {
        "atr_period": [8, 25],
        "atr_multiplier": [1.2, 3.5],
        "volume_ma_period": [10, 40]
    },
    "parallel": true,
    "num_cores": 4
}'

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║            TODAS AS SIMULAÇÕES CONCLUÍDAS!                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Gerando relatório de análise..."
python3 scripts/analyze_monte_carlo.py
echo ""
echo "✅ Processo completo!"
echo "📄 Relatório: analise_monte_carlo.md"
echo "🌐 Dashboard: http://localhost:8081/monte-carlo"

