# SIMULAÇÕES MONTE CARLO ROBUSTAS - GUIA DE EXECUÇÃO

## 📋 OBJETIVO

Realizar simulações estatisticamente significativas (200 iterações cada) para subsidiar decisões sobre qual estratégia de trading implementar em produção.

---

## 🎯 ESTRATÉGIAS SENDO TESTADAS

### 1. Momentum Strategy
- **Conceito**: Compra ativos com momentum positivo, vende com momentum negativo
- **Indicador**: Rate of Change (ROC)
- **Parâmetros**:
  - `roc_period`: 5-25 períodos
  - `threshold`: 0.3-4.0%
- **Iterações**: 200

### 2. MACD + RSI Combo
- **Conceito**: Convergência de tendência (MACD) + sobrecompra/sobrevenda (RSI)
- **Indicadores**: MACD e RSI
- **Parâmetros**:
  - `macd_fast`: 6-18
  - `macd_slow`: 18-35
  - `macd_signal`: 6-15
  - `rsi_period`: 8-25
  - `rsi_overbought`: 60-80
  - `rsi_oversold`: 20-40
- **Iterações**: 200

### 3. Trend Following
- **Conceito**: Segue tendências de médio/longo prazo com filtro de força
- **Indicadores**: EMA Crossover + ADX
- **Parâmetros**:
  - `ema_fast`: 8-35
  - `ema_slow`: 35-90
  - `adx_period`: 8-25
  - `adx_threshold`: 15-35
- **Iterações**: 200

### 4. Volatility Breakout
- **Conceito**: Captura rompimentos em períodos de alta volatilidade
- **Indicadores**: ATR + Volume MA
- **Parâmetros**:
  - `atr_period`: 8-25
  - `atr_multiplier`: 1.2-3.5
  - `volume_ma_period`: 10-40
- **Iterações**: 200

---

## 📊 MÉTRICAS DE AVALIAÇÃO

### Retorno
- Total Return (%)
- Retorno Médio e Mediano
- Desvio Padrão
- Percentis 5% e 95%

### Risco
- Probability of Profit/Loss (%)
- Value at Risk (VaR 95%)
- Conditional VaR
- Max Drawdown

### Performance Ajustada ao Risco
- **Sharpe Ratio**:
  - < 0: Perde dinheiro
  - 0-1: Abaixo do aceitável
  - 1-2: Bom
  - 2-3: Muito bom
  - \> 3: Excelente
  
- **Profit Factor**:
  - < 1.0: Não lucrativo
  - 1.0-1.5: Marginal
  - 1.5-2.0: Bom
  - \> 2.0: Excelente

### Operacionais
- Total de Trades
- Win Rate (%)
- Retorno Médio por Trade

---

## 🚀 COMO EXECUTAR

### Método 1: Via Dashboard (Recomendado)
```bash
# Abrir dashboard
xdg-open http://localhost:8081/monte-carlo

# Clicar em cada estratégia e configurar:
# - Iterações: 200
# - Aceitar parâmetros padrão
# - Clicar em "Iniciar Simulação"
```

### Método 2: Via API
```bash
# Momentum
curl -X POST http://localhost:3008/api/monte-carlo/simulate \
  -H "Content-Type: application/json" \
  -d '{
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

# MACD+RSI
curl -X POST http://localhost:3008/api/monte-carlo/simulate \
  -H "Content-Type: application/json" \
  -d '{
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

# Trend Following
curl -X POST http://localhost:3008/api/monte-carlo/simulate \
  -H "Content-Type: application/json" \
  -d '{
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

# Volatility Breakout
curl -X POST http://localhost:3008/api/monte-carlo/simulate \
  -H "Content-Type: application/json" \
  -d '{
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
```

### Método 3: Script Automático
```bash
python3 scripts/analyze_monte_carlo.py
```

---

## ⏱️ TEMPO ESTIMADO

- Por estratégia: ~60-120 segundos (200 iterações)
- Total (4 estratégias): ~5-8 minutos
- Processamento paralelo: 4 cores

---

## 📈 ACOMPANHAMENTO EM TEMPO REAL

### Via Dashboard
- Acesse: http://localhost:8081/monte-carlo
- Barra de progresso atualiza a cada segundo
- Gráficos renderizados automaticamente ao concluir

### Via API
```bash
# Verificar progresso
curl -s http://localhost:3008/api/monte-carlo/progress/momentum | jq '.'

# Monitorar todas
for s in momentum macd_rsi_combo trend_following volatility_breakout; do
  echo "$s:"
  curl -s "http://localhost:3008/api/monte-carlo/progress/$s" | jq -r '"\(.status) - \(.progress)%"'
done
```

---

## 📊 ANÁLISE DOS RESULTADOS

### Automática
```bash
# Gera relatório completo em Markdown
python3 scripts/analyze_monte_carlo.py

# Visualizar
cat analise_monte_carlo.md
```

### Manual via Dashboard
1. Acesse http://localhost:8081/monte-carlo
2. Visualize gráficos de distribuição
3. Compare métricas na tabela
4. Analise cenários (melhor/mediano/pior)

### Manual via Logs
```bash
# Verificar logs detalhados
docker exec aitrading-execution-engine ls -lh /app/logs/monte_carlo_*.json
docker exec aitrading-execution-engine cat /app/logs/monte_carlo_momentum_*.json | jq '.scenarios'
```

---

## 🎯 CRITÉRIOS DE DECISÃO

### Estratégia Ideal
- ✅ Sharpe Ratio > 1.5
- ✅ Profit Factor > 1.5
- ✅ Probability of Profit > 50%
- ✅ Win Rate > 40%
- ✅ Max Drawdown < 25%

### Red Flags
- ❌ Sharpe Ratio < 0
- ❌ Probability of Loss > 80%
- ❌ Max Drawdown > 50%
- ❌ Profit Factor < 1.0

---

## 📝 PRÓXIMOS PASSOS

Após análise:

1. **Selecionar estratégia vencedora**
2. **Configurar parâmetros ótimos** (do melhor cenário)
3. **Iniciar paper trading** (2 semanas)
4. **Validar em produção** (capital limitado)
5. **Scale up gradual**

---

## 🔗 LINKS ÚTEIS

- Dashboard: http://localhost:8081/monte-carlo
- API Docs: http://localhost:3008/docs
- Script de Análise: `scripts/analyze_monte_carlo.py`
- Logs: `docker exec aitrading-execution-engine ls /app/logs/`

---

## ⚠️ DISCLAIMERS

- Resultados passados não garantem performance futura
- Simulações assumem execução perfeita (sem slippage)
- Custos de transação podem impactar retornos reais
- Mercado de criptomoedas é altamente volátil
- Teste extensivamente antes de usar capital real
- Nunca invista mais do que pode perder

---

**Última atualização**: 10/12/2025  
**Versão**: 1.0  
**Autor**: CryptoDev Assistant
