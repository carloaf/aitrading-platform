# 🚀 PAPER TRADING ENGINE - Guia Completo

## 📋 Visão Geral

O **Paper Trading Engine** permite executar estratégias de trading em tempo real usando dados ao vivo da Binance, **sem risco financeiro**. Todas as ordens são simuladas, mas os dados e a lógica são idênticos ao trading real.

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI REST API                         │
│                    (http://localhost:3008)                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│   │  WebSocket   │───▶│   Strategy   │───▶│    Order     │ │
│   │    Client    │    │   Executor   │    │   Manager    │ │
│   └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    │                    │         │
│         ▼                    ▼                    ▼         │
│   Binance Stream      Indicators/         Simulated        │
│   (Ticker, Klines)    Signals            Executions        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Como Usar

### 1. Iniciar o Container

```bash
# Build e iniciar todos os serviços
cd /home/dellno/worksapace/aitrading-platform
docker compose up -d --build execution-engine

# Verificar se está rodando
docker ps | grep execution-engine

# Ver logs
docker logs -f aitrading-execution-engine
```

### 2. Verificar Health

```bash
curl http://localhost:3008/health
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "service": "execution-engine",
  "timestamp": "2025-12-09T...",
  "active_sessions": 0
}
```

---

## 📊 Endpoints da API

### Documentação Completa
```bash
curl http://localhost:3008/ | jq '.'
```

### 1. Iniciar Paper Trading

```bash
curl -X POST http://localhost:3008/paper-trading/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_momentum_001",
    "strategy_name": "momentum",
    "strategy_parameters": {
      "roc_period": 10,
      "threshold": 0
    },
    "symbol": "BTCUSDT",
    "timeframe": "1m",
    "initial_balance": 10000.0,
    "commission_rate": 0.001,
    "slippage_rate": 0.0005
  }' | jq '.'
```

**Estratégias disponíveis:**
- `momentum`
- `macd_rsi_combo`
- `trend_following`
- `mean_reversion`
- `volatility_breakout`
- `bollinger_bands`
- `volume_profile`
- `multi_timeframe`
- `dynamic_position_sizing`

### 2. Verificar Status

```bash
curl http://localhost:3008/paper-trading/test_momentum_001/status | jq '.'
```

**Resposta:**
```json
{
  "is_running": true,
  "strategy_name": "Momentum Strategy",
  "symbol": "BTCUSDT",
  "timeframe": "1m",
  "position_open": false,
  "last_signal": 0,
  "uptime_seconds": 120.5,
  "signals_generated": 2,
  "trades_executed": 1,
  "candles_collected": 75,
  "account_summary": {
    "balance": 9950.50,
    "equity": 10100.25,
    "total_pnl": 100.25,
    "total_pnl_percent": 1.00
  }
}
```

### 3. Ver Resumo da Conta

```bash
curl http://localhost:3008/paper-trading/test_momentum_001/account | jq '.'
```

### 4. Ver Posições Abertas

```bash
curl http://localhost:3008/paper-trading/test_momentum_001/positions | jq '.'
```

**Resposta:**
```json
[
  {
    "symbol": "BTCUSDT",
    "quantity": 0.1,
    "entry_price": 42000.00,
    "current_price": 42500.00,
    "side": "BUY",
    "unrealized_pnl": 50.00,
    "realized_pnl": 0.00
  }
]
```

### 5. Ver Histórico de Trades

```bash
curl "http://localhost:3008/paper-trading/test_momentum_001/trades?limit=10" | jq '.'
```

### 6. Criar Ordem Manual (Intervenção)

```bash
curl -X POST http://localhost:3008/paper-trading/test_momentum_001/order \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_momentum_001",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 0.05
  }' | jq '.'
```

### 7. Parar Paper Trading

```bash
curl -X POST http://localhost:3008/paper-trading/test_momentum_001/stop | jq '.'
```

### 8. Listar Todas as Sessões Ativas

```bash
curl http://localhost:3008/paper-trading/sessions | jq '.'
```

---

## 🧪 Testes Completos

### Script de Teste Automatizado

```bash
#!/bin/bash

echo "🧪 TESTANDO PAPER TRADING ENGINE"
echo "================================"

API_URL="http://localhost:3008"
SESSION_ID="test_auto_$(date +%s)"

# 1. Health Check
echo -e "\n1️⃣ Health Check..."
curl -s $API_URL/health | jq '.status'

# 2. Iniciar Paper Trading
echo -e "\n2️⃣ Iniciando paper trading..."
curl -s -X POST $API_URL/paper-trading/start \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"strategy_name\": \"momentum\",
    \"strategy_parameters\": {\"roc_period\": 10, \"threshold\": 0},
    \"symbol\": \"BTCUSDT\",
    \"timeframe\": \"1m\",
    \"initial_balance\": 1000.0
  }" | jq '.message'

# 3. Aguardar coletar dados
echo -e "\n3️⃣ Aguardando coleta de dados (60s)..."
sleep 60

# 4. Verificar Status
echo -e "\n4️⃣ Status da sessão:"
curl -s $API_URL/paper-trading/$SESSION_ID/status | jq '{
  running: .is_running,
  candles: .candles_collected,
  signals: .signals_generated,
  trades: .trades_executed,
  pnl: .account_summary.total_pnl
}'

# 5. Ver Conta
echo -e "\n5️⃣ Resumo da conta:"
curl -s $API_URL/paper-trading/$SESSION_ID/account | jq '{
  balance: .balance,
  equity: .equity,
  pnl: .total_pnl,
  pnl_pct: .total_pnl_percent
}'

# 6. Aguardar mais tempo
echo -e "\n6️⃣ Aguardando mais atividade (120s)..."
sleep 120

# 7. Status Final
echo -e "\n7️⃣ Status final:"
curl -s $API_URL/paper-trading/$SESSION_ID/status | jq '{
  uptime: .uptime_seconds,
  signals: .signals_generated,
  trades: .trades_executed,
  final_pnl: .account_summary.total_pnl_percent
}'

# 8. Histórico de Trades
echo -e "\n8️⃣ Histórico de trades:"
curl -s "$API_URL/paper-trading/$SESSION_ID/trades?limit=5" | jq '.[]  | {timestamp, side, price, balance_after}'

# 9. Parar
echo -e "\n9️⃣ Parando paper trading..."
curl -s -X POST $API_URL/paper-trading/$SESSION_ID/stop | jq '.message'

echo -e "\n✅ Teste concluído!"
```

**Salvar e executar:**
```bash
# Salvar script
cat > test_paper_trading.sh << 'EOF'
[cole o script acima]
EOF

chmod +x test_paper_trading.sh
./test_paper_trading.sh
```

---

## 📈 Monitoramento em Tempo Real

### Loop de Monitoramento Contínuo

```bash
#!/bin/bash

SESSION_ID="$1"

if [ -z "$SESSION_ID" ]; then
  echo "Uso: $0 <session_id>"
  exit 1
fi

API_URL="http://localhost:3008"

echo "📊 MONITORANDO SESSÃO: $SESSION_ID"
echo "Pressione Ctrl+C para parar"
echo ""

while true; do
  clear
  echo "🕐 $(date '+%H:%M:%S')"
  echo "========================================"
  
  # Status
  status=$(curl -s $API_URL/paper-trading/$SESSION_ID/status)
  
  echo "📡 STATUS:"
  echo "$status" | jq '{
    running: .is_running,
    uptime_min: (.uptime_seconds / 60 | floor),
    candles: .candles_collected,
    signals: .signals_generated,
    trades: .trades_executed
  }'
  
  echo ""
  echo "💰 CONTA:"
  echo "$status" | jq '.account_summary | {
    balance: .balance,
    equity: .equity,
    pnl: .total_pnl,
    pnl_pct: (.total_pnl_percent | tostring + "%")
  }'
  
  echo ""
  echo "📈 POSIÇÕES:"
  curl -s $API_URL/paper-trading/$SESSION_ID/positions | jq -c '.[] | {symbol, qty: .quantity, entry: .entry_price, current: .current_price, pnl: .unrealized_pnl}'
  
  echo ""
  echo "🔄 Próxima atualização em 10s..."
  sleep 10
done
```

**Uso:**
```bash
chmod +x monitor_paper_trading.sh
./monitor_paper_trading.sh test_momentum_001
```

---

## 🎯 Casos de Uso

### 1. Testar Parâmetros Otimizados

Depois de otimizar no backtesting, validar em tempo real:

```bash
# Parâmetros otimizados do backtesting
BEST_PARAMS='{"roc_period": 20, "threshold": 0.0}'

curl -X POST http://localhost:3008/paper-trading/start \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"optimized_momentum\",
    \"strategy_name\": \"momentum\",
    \"strategy_parameters\": $BEST_PARAMS,
    \"symbol\": \"BTCUSDT\",
    \"timeframe\": \"1m\",
    \"initial_balance\": 10000.0
  }"
```

### 2. Comparar Múltiplas Estratégias

```bash
# Estratégia 1: Momentum
curl -X POST http://localhost:3008/paper-trading/start \
  -d '{"session_id": "compare_momentum", "strategy_name": "momentum", ...}'

# Estratégia 2: MACD+RSI
curl -X POST http://localhost:3008/paper-trading/start \
  -d '{"session_id": "compare_macd_rsi", "strategy_name": "macd_rsi_combo", ...}'

# Comparar resultados após 1 hora
curl http://localhost:3008/paper-trading/sessions | jq '.sessions'
```

### 3. Trading 24/7 Automatizado

```bash
# Iniciar e deixar rodando
curl -X POST http://localhost:3008/paper-trading/start \
  -d '{
    "session_id": "production_bot_001",
    "strategy_name": "multi_timeframe",
    "strategy_parameters": {"trend_ema": 50, "entry_ema_fast": 20},
    "symbol": "BTCUSDT",
    "timeframe": "5m",
    "initial_balance": 10000.0
  }'

# Verificar diariamente via cron
# crontab -e
# 0 */6 * * * curl http://localhost:3008/paper-trading/production_bot_001/account
```

---

## ⚙️ Configurações Avançadas

### Ajustar Comissão e Slippage

```json
{
  "commission_rate": 0.001,     // 0.1% (padrão Binance)
  "slippage_rate": 0.0005       // 0.05% slippage simulado
}
```

### Timeframes Disponíveis

- `1m` - 1 minuto (alta frequência)
- `5m` - 5 minutos
- `15m` - 15 minutos
- `1h` - 1 hora
- `4h` - 4 horas
- `1d` - 1 dia

### Símbolos Suportados

Qualquer par da Binance Spot:
- `BTCUSDT`
- `ETHUSDT`
- `BNBUSDT`
- `ADAUSDT`
- `SOLUSDT`
- etc.

---

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs detalhados
docker logs aitrading-execution-engine --tail 100

# Verificar dependências
docker ps | grep -E "(redis|postgres|backtesting)"

# Restart
docker compose restart execution-engine
```

### WebSocket não conecta

```bash
# Testar conectividade
docker exec -it aitrading-execution-engine python -c "
import asyncio
from src.websocket_client import BinanceWebSocketClient

async def test():
    client = BinanceWebSocketClient()
    print('Testando conexão...')
    await client.connect_ticker('btcusdt', lambda x: print(f'Price: {x.price}'))
    await asyncio.sleep(5)
    await client.disconnect_all()

asyncio.run(test())
"
```

### Estratégia não gera sinais

```bash
# Verificar se está coletando candles
curl -s http://localhost:3008/paper-trading/YOUR_SESSION/status | jq '.candles_collected'

# Deve ter pelo menos 50+ candles antes de gerar sinais

# Ver último sinal
curl -s http://localhost:3008/paper-trading/YOUR_SESSION/status | jq '.last_signal'
```

---

## 📚 Próximos Passos

1. **Frontend Dashboard** - Interface visual para monitorar paper trading
2. **Performance Tracker** - Gráficos de equity curve em tempo real
3. **Alertas** - Notificações via Telegram quando houver trades
4. **Multi-Symbol** - Rodar múltiplos pares simultaneamente
5. **Trading Real** - Conectar à Binance real (com extremo cuidado!)

---

## 🎓 Recursos Adicionais

- **Documentação Binance WebSocket:** https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams
- **Backtest vs Paper Trading:** Compare resultados para detectar overfitting
- **Walk-Forward no Tempo Real:** Re-otimizar parâmetros a cada semana

---

**Última Atualização:** 9 de dezembro de 2025  
**Status:** ✅ Implementado e funcional  
**Versão:** 1.0.0
