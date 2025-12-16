# 🎲 Monte Carlo Simulation - Guia Completo

## 📊 Visão Geral

A Simulação Monte Carlo é um método estatístico que usa amostragem aleatória para avaliar o comportamento de estratégias de trading sob diferentes condições de mercado e parâmetros.

### O que faz?

- **Executa 10,000+ simulações** com parâmetros variados
- **Calcula distribuições de probabilidade** de retornos
- **Identifica riscos** (VaR, CVaR, worst-case scenarios)
- **Fornece intervalos de confiança** (5%, 50%, 95%)
- **Valida robustez** das estratégias

## 🚀 Uso Rápido

```bash
# Simulação Momentum (10,000 iterações)
./scripts/run_monte_carlo.sh momentum 10000 30

# Simulação MACD+RSI (1,000 iterações - teste)
./scripts/run_monte_carlo.sh macd_rsi_combo 1000 14

# Simulação Trend Following
./scripts/run_monte_carlo.sh trend_following 10000 30
```

## 📋 Parâmetros

```bash
./scripts/run_monte_carlo.sh <estratégia> <iterações> <lookback_days>
```

- **estratégia**: Nome da estratégia
  - `momentum`
  - `macd_rsi_combo`
  - `trend_following`
  - `volatility_breakout`
  - `bollinger_bands`

- **iterações**: Número de simulações (recomendado: 10000)
- **lookback_days**: Dias de histórico (recomendado: 30-90)

## 🔬 Como Funciona

### 1. Variação de Parâmetros

Para cada iteração, os parâmetros são randomizados dentro de ranges:

**Momentum:**
- `roc_period`: [5, 20]
- `threshold`: [0.5, 3.0]

**MACD+RSI:**
- `macd_fast`: [8, 16]
- `macd_slow`: [20, 30]
- `macd_signal`: [7, 11]
- `rsi_period`: [10, 18]
- `rsi_overbought`: [65, 75]
- `rsi_oversold`: [25, 35]

**Trend Following:**
- `ema_fast`: [8, 16]
- `ema_slow`: [20, 30]
- `adx_period`: [10, 18]
- `adx_threshold`: [20, 30]

**Volatility Breakout:**
- `atr_period`: [10, 20]
- `atr_multiplier`: [1.5, 3.0]
- `volume_ma_period`: [15, 25]

**Bollinger Bands:**
- `bb_period`: [15, 25]
- `bb_std`: [1.5, 2.5]
- `rsi_period`: [10, 18]

### 2. Simulação

- Aplica estratégia com parâmetros aleatórios
- Simula trades com slippage/comissões (1%)
- Calcula métricas: retorno, Sharpe, drawdown, win rate
- Armazena resultados

### 3. Análise Estatística

- **Distribuições**: Retornos, Sharpe Ratios, Drawdowns
- **Percentis**: 5%, 50% (mediana), 95%
- **Cenários**: Melhor caso, mediano, pior caso
- **Riscos**: VaR, CVaR

## 📊 Métricas Calculadas

### Estatísticas de Retorno

**Mean Return** (Retorno Médio)
```
Média aritmética dos retornos de todas as simulações
Interpretação:
  > 5%: Excelente
  2-5%: Bom
  0-2%: Mediano
  < 0%: Não rentável
```

**Median Return** (Retorno Mediano)
```
Valor central da distribuição (50º percentil)
Menos sensível a outliers que a média
```

**Standard Deviation** (Desvio Padrão)
```
Medida de volatilidade dos retornos
Menor = mais consistente
```

**Percentile 5% / 95%** (Intervalo de Confiança)
```
95% das simulações ficam dentro deste intervalo
Exemplo: [-5%, +15%] significa:
  - 5% chance de retorno < -5%
  - 5% chance de retorno > +15%
```

### Métricas de Risco

**Probability of Profit** (Probabilidade de Lucro)
```
% de simulações com retorno positivo
Interpretação:
  > 70%: Alta confiança
  60-70%: Boa
  50-60%: Moderada
  < 50%: Baixa
```

**Value at Risk 95% (VaR)**
```
Máxima perda esperada em 95% dos casos
Exemplo: VaR = -8% significa:
  - 95% das vezes, perda será <= 8%
  - 5% das vezes, perda pode ser > 8%
```

**Conditional VaR (CVaR / Expected Shortfall)**
```
Perda média nos 5% piores cenários
Mede o "tail risk" (risco da cauda)
Mais conservador que VaR
```

### Sharpe Ratio

```
Sharpe = (Retorno Médio - Taxa Livre de Risco) / Desvio Padrão

Interpretação:
  > 3.0: Excepcional
  2.0-3.0: Excelente
  1.0-2.0: Bom
  0.5-1.0: Aceitável
  < 0.5: Ruim
  < 0: Não rentável

Mean Sharpe: Média dos Sharpes de todas as simulações
Median Sharpe: Mediana (mais robusta)
```

### Drawdown

**Mean Max Drawdown** (Drawdown Médio)
```
Média das maiores quedas em cada simulação
Indica risco médio esperado
```

**Worst Drawdown** (Pior Drawdown)
```
Maior queda observada em todas as simulações
Indica worst-case scenario absoluto
```

**95th Percentile Drawdown**
```
95% das simulações tiveram drawdown menor que este valor
```

## 📈 Exemplo de Output

```bash
$ ./scripts/run_monte_carlo.sh macd_rsi_combo 10000 30

🎲 MONTE CARLO SIMULATION
📊 Estratégia: macd_rsi_combo
🔢 Iterações: 10000
📅 Lookback: 30 dias

✅ Simulação concluída com sucesso!

📊 RESULTADOS DA SIMULAÇÃO

📈 ESTATÍSTICAS DE RETORNO:
   Retorno Médio: 3.42%
   Retorno Mediano: 2.87%
   Desvio Padrão: 4.23%
   95% CI: [-4.15%, 11.98%]

⚠️  MÉTRICAS DE RISCO:
   Probabilidade de Lucro: 68.5%
   Probabilidade de Prejuízo: 31.5%
   95% VaR: -4.15%
   95% CVaR: -6.82%

⚡ SHARPE RATIO:
   Sharpe Médio: 1.85
   Sharpe Mediano: 1.72

📉 DRAWDOWN:
   Max DD Médio: -12.34%
   Pior DD: -28.67%

🎯 CENÁRIOS:
   Melhor Caso: +24.56%
   Cenário Mediano: +2.87%
   Pior Caso: -18.42%

💡 INTERPRETAÇÃO:
✅ Estratégia rentável (retorno médio positivo)
✅ Alta probabilidade de lucro (≥60%)
⚠️  Sharpe Ratio aceitável (1.0-2.0)
```

## 🔍 Interpretação de Resultados

### Estratégia RENTÁVEL

Critérios:
- ✅ Mean Return > 2%
- ✅ Probability of Profit > 60%
- ✅ Mean Sharpe > 1.0
- ✅ Worst Drawdown < -30%

Ação: **Aprovar para paper trading**

### Estratégia MARGINAL

Critérios:
- ⚠️  Mean Return: 0-2%
- ⚠️  Probability of Profit: 50-60%
- ⚠️  Mean Sharpe: 0.5-1.0

Ação: **Otimizar parâmetros ou rejeitar**

### Estratégia NÃO RENTÁVEL

Critérios:
- ❌ Mean Return < 0%
- ❌ Probability of Profit < 50%
- ❌ Mean Sharpe < 0.5

Ação: **Rejeitar ou redesenvolver**

## 🎯 Boas Práticas

### Número de Iterações

```bash
# Teste rápido (1-2 min)
./scripts/run_monte_carlo.sh momentum 1000 14

# Teste padrão (5-10 min)
./scripts/run_monte_carlo.sh momentum 5000 30

# Análise completa (20-30 min)
./scripts/run_monte_carlo.sh momentum 10000 60
```

**Recomendação**: 10,000 iterações para análise final

### Período de Lookback

```
7 dias: Teste rápido, poucos dados
14 dias: Mínimo recomendado
30 dias: Padrão (balanceado)
60-90 dias: Análise robusta
180+ dias: Incluir diferentes condições de mercado
```

**Recomendação**: 30-60 dias

### Comparação de Estratégias

```bash
# Executar todas as 5 estratégias
for strategy in momentum macd_rsi_combo trend_following volatility_breakout bollinger_bands; do
  echo "Testando $strategy..."
  ./scripts/run_monte_carlo.sh $strategy 5000 30
  sleep 5
done

# Ver relatórios
curl http://localhost:3008/api/monte-carlo/reports | jq '.'
```

## 📊 API Endpoints

### POST /api/monte-carlo/simulate

Executa simulação Monte Carlo.

**Request:**
```json
{
  "strategy_name": "momentum",
  "symbol": "BTCUSDT",
  "interval": "1h",
  "lookback_days": 30,
  "iterations": 10000,
  "initial_balance": 10000.0,
  "parameter_ranges": {
    "roc_period": [5, 20],
    "threshold": [0.5, 3.0]
  },
  "parallel": true
}
```

**Response:**
```json
{
  "status": "completed",
  "report": {
    "strategy_name": "momentum",
    "total_iterations": 10000,
    "successful_runs": 10000,
    "failed_runs": 0,
    "execution_time": 245.67,
    "return_statistics": {
      "mean": 3.42,
      "median": 2.87,
      "std": 4.23,
      "percentile_5": -4.15,
      "percentile_95": 11.98
    },
    "risk_metrics": {
      "probability_of_profit": 68.5,
      "probability_of_loss": 31.5,
      "value_at_risk_95": -4.15,
      "conditional_var_95": -6.82
    },
    "sharpe_statistics": {
      "mean": 1.85,
      "median": 1.72
    },
    "drawdown_statistics": {
      "mean": -12.34,
      "worst": -28.67,
      "percentile_95": -18.45
    },
    "scenarios": {
      "best_case": { ... },
      "worst_case": { ... },
      "median_case": { ... }
    },
    "distributions": {
      "returns": [...],
      "sharpe_ratios": [...],
      "max_drawdowns": [...],
      "win_rates": [...]
    }
  },
  "report_file": "/app/logs/monte_carlo_momentum_20251210_143022.json"
}
```

### GET /api/monte-carlo/reports

Lista todos os relatórios salvos.

```bash
curl http://localhost:3008/api/monte-carlo/reports | jq '.'
```

### GET /api/monte-carlo/report/{filename}

Retorna relatório completo.

```bash
curl http://localhost:3008/api/monte-carlo/report/monte_carlo_momentum_20251210_143022.json | jq '.'
```

## 🎨 Visualização (Futuro)

Frontend para visualizar:
- Histogramas de distribuição de retornos
- Curvas de densidade de probabilidade
- Scatter plots de Sharpe vs Drawdown
- Equity curves dos cenários (best/worst/median)
- Heatmaps de correlação entre parâmetros

## 🐛 Troubleshooting

### Erro: "Dados insuficientes"

```bash
# Verificar dados disponíveis
curl "http://localhost:3008/api/history/candles?symbol=BTCUSDT&interval=1h&limit=1000" | jq '.total_candles'

# Solução: Reduzir lookback_days ou aguardar mais dados
./scripts/run_monte_carlo.sh momentum 1000 7  # 7 dias em vez de 30
```

### Simulação muito lenta

```bash
# Reduzir iterações para teste
./scripts/run_monte_carlo.sh momentum 1000 14  # Rápido: ~1-2 min

# Processamento paralelo está habilitado por padrão
# Para desabilitar (debug): editar API request com "parallel": false
```

### Todas as simulações falharam

```bash
# Verificar logs
docker logs aitrading-execution-engine 2>&1 | grep ERROR | tail -20

# Causas comuns:
# - Parâmetros inválidos (ex: period=0)
# - Estratégia com bug
# - Dados com NaN/Inf
```

## 📚 Referências

**Monte Carlo em Finanças:**
- "Monte Carlo Methods in Financial Engineering" - Paul Glasserman
- "Risk Management and Financial Institutions" - John C. Hull

**Value at Risk:**
- "Value at Risk" - Philippe Jorion

**Trading Systems:**
- "Quantitative Trading" - Ernest Chan
- "Evidence-Based Technical Analysis" - David Aronson

## 🚀 Próximos Passos

Após Monte Carlo:

1. **Analisar Resultados**: Revisar distribuições e métricas
2. **Selecionar Estratégias**: Escolher as mais robustas (Sharpe > 1.5, Prob > 65%)
3. **Otimizar Parâmetros**: Refinar ranges baseado em simulações
4. **Paper Trading**: Testar estratégias aprovadas em tempo real
5. **Walk-Forward Out-of-Sample**: Validação adicional
6. **Live Trading**: Apenas após validação completa

---

**Dashboard URL**: http://localhost:8081/history  
**API Docs**: http://localhost:3008/docs  
**Relatórios**: `docker exec aitrading-execution-engine ls -lh /app/logs/monte_carlo_*`
