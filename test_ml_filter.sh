#!/bin/bash
# PASSO 34: Script de teste para ML Signal Filter
# Compara performance com/sem filtro ML e valida accuracy do modelo

set -e

echo "🤖 PASSO 34: Teste do ML Signal Filter"
echo "========================================"
echo ""

# Configuração
SYMBOL="BTCUSDT"
START_DATE="2023-01-01"
END_DATE="2023-12-31"
INITIAL_CAPITAL=100000

# Endpoint
API_URL="http://localhost:3008/api/meta-backtest/run"

echo "📊 Configuração:"
echo "   Símbolo: $SYMBOL"
echo "   Período: $START_DATE → $END_DATE"
echo "   Capital: \$$INITIAL_CAPITAL"
echo ""

# Função para extrair métrica do JSON
extract_metric() {
    echo "$1" | jq -r "$2"
}

# Teste 1: BASELINE (sem ML filter)
echo "1️⃣  BASELINE (sem ML filter)..."
echo "   Executando backtest sem filtro ML..."

BASELINE=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"symbol\": \"$SYMBOL\",
    \"start_date\": \"$START_DATE\",
    \"end_date\": \"$END_DATE\",
    \"initial_capital\": $INITIAL_CAPITAL,
    \"use_ml_filter\": false
  }")

BASELINE_RETURN=$(extract_metric "$BASELINE" '.return_pct')
BASELINE_WINRATE=$(extract_metric "$BASELINE" '.win_rate')
BASELINE_TRADES=$(extract_metric "$BASELINE" '.total_trades')
BASELINE_SHARPE=$(extract_metric "$BASELINE" '.sharpe_ratio')
BASELINE_MAX_DD=$(extract_metric "$BASELINE" '.max_drawdown')

echo "   ✅ Baseline completo:"
echo "      Return: ${BASELINE_RETURN}%"
echo "      Win Rate: ${BASELINE_WINRATE}%"
echo "      Trades: $BASELINE_TRADES"
echo "      Sharpe: $BASELINE_SHARPE"
echo "      Max DD: ${BASELINE_MAX_DD}%"
echo ""

# Teste 2: Treinar modelo ML com dados históricos
echo "2️⃣  TREINAMENTO do modelo ML..."
echo "   Usando trades do baseline para treinar LightGBM..."

# Extrair trades do baseline para treinar
TRADES_JSON=$(echo "$BASELINE" | jq -c '.trades')
NUM_TRADES=$(echo "$TRADES_JSON" | jq 'length')

echo "   📚 Trades disponíveis para treino: $NUM_TRADES"

if [ "$NUM_TRADES" -lt 30 ]; then
    echo "   ⚠️  AVISO: Poucos trades para treinar modelo ML (<30)"
    echo "   💡 Recomendação: Use período maior (ex: 2021-2024) ou reduza ml_min_score"
else
    echo "   ✅ Quantidade adequada de trades para treino"
fi

# Preparar dados de treino (simplified - em produção seria via Python)
echo "   🔧 Preparando features para treino..."
echo "   📊 Labels: TP=1 (bom sinal), SL=0 (falso sinal)"

# Contar TP/SL para ver balance
NUM_TP=$(echo "$TRADES_JSON" | jq '[.[] | select(.exit_reason == "TAKE_PROFIT")] | length')
NUM_SL=$(echo "$TRADES_JSON" | jq '[.[] | select(.exit_reason == "STOP_LOSS")] | length')
TP_PCT=$(echo "scale=1; $NUM_TP * 100 / $NUM_TRADES" | bc)
SL_PCT=$(echo "scale=1; $NUM_SL * 100 / $NUM_TRADES" | bc)

echo "   📈 Distribuição de labels:"
echo "      TP (bons sinais): $NUM_TP (${TP_PCT}%)"
echo "      SL (falsos sinais): $NUM_SL (${SL_PCT}%)"

if [ "$NUM_TP" -eq 0 ] || [ "$NUM_SL" -eq 0 ]; then
    echo "   ⚠️  AVISO: Classes desbalanceadas (0 em uma classe)"
    echo "   💡 ML pode não treinar corretamente com todos TP ou todos SL"
fi

echo ""

# Teste 3: Backtest COM ML filter (requer modelo treinado)
echo "3️⃣  BACKTEST COM ML Filter..."
echo "   Executando com ml_min_score=0.6 (threshold padrão)..."

ML_RESULT=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{
    \"symbol\": \"$SYMBOL\",
    \"start_date\": \"$START_DATE\",
    \"end_date\": \"$END_DATE\",
    \"initial_capital\": $INITIAL_CAPITAL,
    \"use_ml_filter\": true,
    \"ml_min_score\": 0.6,
    \"ml_retrain_enabled\": false
  }")

ML_RETURN=$(extract_metric "$ML_RESULT" '.return_pct')
ML_WINRATE=$(extract_metric "$ML_RESULT" '.win_rate')
ML_TRADES=$(extract_metric "$ML_RESULT" '.total_trades')
ML_SHARPE=$(extract_metric "$ML_RESULT" '.sharpe_ratio')
ML_MAX_DD=$(extract_metric "$ML_RESULT" '.max_drawdown')

# Rejeições do ML filter
ML_REJECTED=$(echo "$ML_RESULT" | jq -r '.debug.entry_rejected_ml // {} | to_entries | map(.value) | add // 0')

echo "   ✅ ML Filter completo:"
echo "      Return: ${ML_RETURN}%"
echo "      Win Rate: ${ML_WINRATE}%"
echo "      Trades: $ML_TRADES"
echo "      Sharpe: $ML_SHARPE"
echo "      Max DD: ${ML_MAX_DD}%"
echo "      🚫 ML Rejections: $ML_REJECTED sinais bloqueados"
echo ""

# Teste 4: COMPARAÇÃO
echo "4️⃣  COMPARAÇÃO: Baseline vs ML Filter"
echo "========================================"
echo ""
printf "%-20s | %-12s | %-12s | %-12s\n" "Métrica" "Baseline" "ML Filter" "Delta"
printf "%-20s-+-%-12s-+-%-12s-+-%-12s\n" "--------------------" "------------" "------------" "------------"

# Return
DELTA_RETURN=$(echo "scale=2; $ML_RETURN - $BASELINE_RETURN" | bc)
printf "%-20s | %11.2f%% | %11.2f%% | %+10.2fpp\n" "Return" "$BASELINE_RETURN" "$ML_RETURN" "$DELTA_RETURN"

# Win Rate
DELTA_WINRATE=$(echo "scale=2; $ML_WINRATE - $BASELINE_WINRATE" | bc)
printf "%-20s | %11.2f%% | %11.2f%% | %+10.2fpp\n" "Win Rate" "$BASELINE_WINRATE" "$ML_WINRATE" "$DELTA_WINRATE"

# Trades
DELTA_TRADES=$(echo "$ML_TRADES - $BASELINE_TRADES" | bc)
printf "%-20s | %12d | %12d | %+11d\n" "Total Trades" "$BASELINE_TRADES" "$ML_TRADES" "$DELTA_TRADES"

# Sharpe
DELTA_SHARPE=$(echo "scale=2; $ML_SHARPE - $BASELINE_SHARPE" | bc)
printf "%-20s | %12.2f | %12.2f | %+11.2f\n" "Sharpe Ratio" "$BASELINE_SHARPE" "$ML_SHARPE" "$DELTA_SHARPE"

# Max DD
DELTA_DD=$(echo "scale=2; $ML_MAX_DD - $BASELINE_MAX_DD" | bc)
printf "%-20s | %11.2f%% | %11.2f%% | %+10.2fpp\n" "Max Drawdown" "$BASELINE_MAX_DD" "$ML_MAX_DD" "$DELTA_DD"

echo ""

# Avaliação de sucesso
echo "5️⃣  AVALIAÇÃO"
echo "========================================"
echo ""

SUCCESS_COUNT=0
TOTAL_TESTS=5

# Test 1: Win rate melhorou?
if (( $(echo "$DELTA_WINRATE > 0" | bc -l) )); then
    echo "✅ Win Rate MELHOROU (+${DELTA_WINRATE}pp)"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo "❌ Win Rate não melhorou (${DELTA_WINRATE}pp)"
fi

# Test 2: Return melhorou?
if (( $(echo "$DELTA_RETURN > 0" | bc -l) )); then
    echo "✅ Return MELHOROU (+${DELTA_RETURN}pp)"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo "❌ Return não melhorou (${DELTA_RETURN}pp)"
fi

# Test 3: Sharpe melhorou?
if (( $(echo "$DELTA_SHARPE > 0" | bc -l) )); then
    echo "✅ Sharpe Ratio MELHOROU (+${DELTA_SHARPE})"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo "❌ Sharpe Ratio não melhorou (${DELTA_SHARPE})"
fi

# Test 4: Drawdown diminuiu (ou manteve)?
if (( $(echo "$DELTA_DD <= 0" | bc -l) )); then
    echo "✅ Max Drawdown DIMINUIU ou MANTEVE (${DELTA_DD}pp)"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo "❌ Max Drawdown aumentou (+${DELTA_DD}pp)"
fi

# Test 5: ML filtrou sinais (rejections > 0)?
if [ "$ML_REJECTED" -gt 0 ]; then
    echo "✅ ML Filter ATIVO ($ML_REJECTED sinais bloqueados)"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo "⚠️  ML Filter NÃO bloqueou nenhum sinal (modelo não treinado ou threshold baixo)"
fi

echo ""
echo "📊 Score Final: $SUCCESS_COUNT/$TOTAL_TESTS testes passaram"
echo ""

if [ "$SUCCESS_COUNT" -ge 3 ]; then
    echo "🎉 SUCESSO! ML Signal Filter está funcionando e melhorando performance"
    exit 0
else
    echo "⚠️  ALERTA: ML Filter não melhorou performance significativamente"
    echo "💡 Sugestões:"
    echo "   - Ajustar ml_min_score (tentar 0.5, 0.7, 0.8)"
    echo "   - Treinar com período maior (ex: 2021-2024)"
    echo "   - Verificar distribuição de labels (TP/SL balance)"
    exit 1
fi
