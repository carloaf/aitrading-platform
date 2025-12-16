# API Backtesting Engine - Documentação

## 🚀 Serviço: AI Trading Platform - Backtesting Engine

**URL Base:** http://localhost:3007

**Versão:** 1.0.0

---

## 📋 Endpoints Disponíveis

### 1. Raiz da API
**GET** `/`

Retorna documentação completa da API com todos os endpoints disponíveis.

**Exemplo:**
```bash
curl http://localhost:3007/
```

---

### 2. Health Check
**GET** `/health`

Verifica o status do serviço.

**Resposta:**
```json
{
  "status": "healthy",
  "service": "backtesting-engine",
  "timestamp": "2025-12-09T19:30:00",
  "version": "1.0.0"
}
```

---

### 3. Listar Estratégias Profissionais
**GET** `/strategies/professional`

Lista todas as 9 estratégias profissionais implementadas.

**Exemplo:**
```bash
curl http://localhost:3007/strategies/professional
```

**Resposta:**
```json
{
  "total": 9,
  "strategies": [
    {
      "id": "trend_following",
      "name": "Trend Following Strategy",
      "default_parameters": {...},
      "entry_conditions": [...],
      "exit_conditions": [...]
    },
    ...
  ]
}
```

**Estratégias Disponíveis:**
1. `trend_following` - Segue tendências com EMA e volume
2. `mean_reversion` - Reversão à média com Bollinger Bands
3. `volatility_breakout` - Rompimento de volatilidade com ATR
4. `macd_rsi_combo` - Combinação MACD + RSI
5. `bollinger_bands` - Bandas de Bollinger puras
6. `momentum` - Estratégia de momentum
7. `volume_profile` - Baseada em perfil de volume
8. `multi_timeframe` - Análise multi-timeframe
9. `dynamic_position_sizing` - Gestão dinâmica de posição

---

### 4. Detalhes de uma Estratégia
**GET** `/strategies/{strategy_name}`

Obtém detalhes completos de uma estratégia específica.

**Parâmetros:**
- `strategy_name`: Nome da estratégia (ex: `trend_following`)

**Exemplo:**
```bash
curl http://localhost:3007/strategies/trend_following
```

**Resposta:**
```json
{
  "id": "trend_following",
  "name": "Trend Following Strategy",
  "class": "TrendFollowingStrategy",
  "description": "Estratégia que segue tendências...",
  "parameters": {...},
  "indicators": ["EMA", "Volume", "RSI", "ADX"],
  "risk_management": {...}
}
```

---

### 5. Executar Backtest
**POST** `/strategies/{strategy_name}/backtest`

Executa um backtest completo da estratégia selecionada.

**Parâmetros de Query:**
- `symbol`: Símbolo do par (ex: BTCUSDT, ETHUSDT)
- `start_date`: Data inicial (formato: YYYY-MM-DD)
- `end_date`: Data final (formato: YYYY-MM-DD)
- `initial_capital`: Capital inicial (padrão: 10000)

**Exemplo:**
```bash
curl -X POST "http://localhost:3007/strategies/trend_following/backtest?symbol=BTCUSDT&start_date=2024-01-01&end_date=2024-12-09&initial_capital=10000"
```

**Resposta:**
```json
{
  "strategy_name": "Trend Following Strategy",
  "symbol": "BTCUSDT",
  "start_date": "2024-01-01",
  "end_date": "2024-12-09",
  "initial_capital": 10000,
  "final_capital": 12500,
  "total_return_pct": 25.0,
  "total_trades": 15,
  "winning_trades": 10,
  "losing_trades": 5,
  "win_rate": 66.67,
  "sharpe_ratio": 1.85,
  "max_drawdown": -8.5,
  "profit_factor": 2.3,
  "equity_curve": [...],
  "trades": [...]
}
```

---

### 6. Exemplos de Estratégias
**GET** `/strategies/examples`

Retorna exemplos de configurações de estratégias.

**Exemplo:**
```bash
curl http://localhost:3007/strategies/examples
```

---

### 7. Símbolos Populares
**GET** `/symbols/popular`

Lista símbolos de trading populares.

**Exemplo:**
```bash
curl http://localhost:3007/symbols/popular
```

**Resposta:**
```json
{
  "symbols": [
    {
      "symbol": "BTCUSDT",
      "name": "Bitcoin/USDT",
      "exchange": "Binance",
      "type": "spot"
    },
    {
      "symbol": "ETHUSDT",
      "name": "Ethereum/USDT",
      "exchange": "Binance",
      "type": "spot"
    },
    ...
  ]
}
```

---

## 🎯 Exemplos Práticos

### Exemplo 1: Backtest Simples
```bash
# Executar backtest de Trend Following em BTCUSDT (2024)
curl -X POST "http://localhost:3007/strategies/trend_following/backtest?symbol=BTCUSDT&start_date=2024-01-01&end_date=2024-12-09&initial_capital=10000" | jq
```

### Exemplo 2: Comparar Múltiplas Estratégias
```bash
# Script para testar todas as estratégias
for strategy in trend_following mean_reversion volatility_breakout macd_rsi_combo bollinger_bands momentum volume_profile multi_timeframe dynamic_position_sizing; do
  echo "Testing $strategy..."
  curl -s -X POST "http://localhost:3007/strategies/$strategy/backtest?symbol=BTCUSDT&start_date=2024-01-01&end_date=2024-12-09&initial_capital=10000" | jq '.total_return_pct'
done
```

### Exemplo 3: Via JavaScript (Frontend)
```javascript
async function runBacktest(strategyName) {
  const url = `http://localhost:3007/strategies/${strategyName}/backtest?symbol=BTCUSDT&start_date=2024-01-01&end_date=2024-12-09&initial_capital=10000`;
  
  const response = await fetch(url, { method: 'POST' });
  const data = await response.json();
  
  console.log(`${strategyName}: ${data.total_return_pct}%`);
  return data;
}

// Executar
runBacktest('trend_following');
```

---

## 📊 Documentação Interativa

**Swagger UI:** http://localhost:3007/docs

**ReDoc:** http://localhost:3007/redoc

---

## 🔧 Integração com Frontend

O frontend em **http://localhost:8081/strategies** já está integrado e consome esta API automaticamente.

**Fluxo:**
1. Usuário acessa http://localhost:8081/strategies
2. Frontend carrega lista de estratégias via GET /strategies/professional
3. Usuário clica em "Executar Todas as Estratégias"
4. Frontend faz POST para cada estratégia via /strategies/{name}/backtest
5. Resultados são exibidos em cards com gráficos Chart.js

---

## 🐛 Troubleshooting

### Erro: "Not Found" ao acessar /
**Solução:** Container foi reconstruído. A rota raiz agora existe e retorna documentação.

### Erro: "Connection refused"
**Solução:** Verificar se o container está rodando:
```bash
docker compose ps backtesting-engine
docker logs aitrading-backtesting-engine --tail 20
```

### Erro: "No data available"
**Solução:** Verificar se o Market Data Collector está rodando:
```bash
docker compose ps market-data-collector
```

---

## 📝 Notas Importantes

1. **Dados de Mercado:** A API usa três fontes de dados em ordem de prioridade:
   - Binance API (direto)
   - TimescaleDB (cache)
   - Market Data Collector (serviço)

2. **Performance:** Backtests podem levar de 5-30 segundos dependendo do período e estratégia.

3. **Cache:** Resultados de backtests idênticos são cacheados no Redis por 1 hora.

4. **Rate Limiting:** Não há limite de requisições atualmente (desenvolvimento).

---

## 🚀 Comandos Úteis

```bash
# Ver status de todos os serviços
docker compose ps

# Ver logs do backtesting engine
docker logs aitrading-backtesting-engine --tail 50 -f

# Reiniciar serviço
docker compose restart backtesting-engine

# Reconstruir após mudanças no código
docker compose up -d --build backtesting-engine

# Testar conectividade
curl http://localhost:3007/health
```

---

**Última Atualização:** 9 de dezembro de 2025
