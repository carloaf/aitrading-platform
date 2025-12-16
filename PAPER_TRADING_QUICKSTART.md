# 🚀 Paper Trading - Quick Start Guide

## ✅ Status: FUNCIONANDO

O **Paper Trading Engine** está operacional e pronto para uso!

---

## 📊 O Que Foi Implementado

### ✅ Componentes Completos:
1. **WebSocket Client** - Conectado à Binance (dados em tempo real)
2. **Order Manager** - Simulação de ordens com slippage e comissão
3. **Strategy Executor** - Execução de estratégias em tempo real
4. **REST API** - 11 endpoints para controle e monitoramento
5. **Docker Integration** - Container `execution-engine` rodando

### 📈 Estatísticas:
- **Porta:** 3008 (externa) → 8001 (interna)
- **Estratégias Disponíveis:** 9
- **Sessões Simultâneas:** Ilimitadas
- **Comissão Padrão:** 0.1%
- **Slippage Padrão:** 0.05%

---

## 🎯 Teste Rápido (1 minuto)

```bash
# 1. Verificar se está rodando
curl http://localhost:3008/health | jq

# 2. Iniciar paper trading com Momentum
curl -X POST http://localhost:3008/paper-trading/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_quick",
    "strategy_name": "momentum",
    "strategy_parameters": {"roc_period": 20, "threshold": 0},
    "symbol": "BTCUSDT",
    "timeframe": "1m",
    "initial_balance": 1000.0
  }' | jq

# 3. Aguardar 30s para coletar dados
sleep 30

# 4. Ver status
curl http://localhost:3008/paper-trading/test_quick/status | jq

# 5. Parar
curl -X POST http://localhost:3008/paper-trading/test_quick/stop | jq
```

---

## 📝 Comandos Essenciais

### Ver Sessões Ativas
```bash
curl http://localhost:3008/paper-trading/sessions | jq
```

### Ver Conta
```bash
curl http://localhost:3008/paper-trading/SESSI ON_ID/account | jq
```

### Ver Posições
```bash
curl http://localhost:3008/paper-trading/SESSION_ID/positions | jq
```

### Ver Trades
```bash
curl http://localhost:3008/paper-trading/SESSION_ID/trades | jq
```

### Criar Ordem Manual
```bash
curl -X POST http://localhost:3008/paper-trading/SESSION_ID/order \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "SESSION_ID",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 0.001
  }' | jq
```

---

## 🔧 Scripts Auxiliares Criados

### 1. Script de Teste Automatizado
```bash
./test_paper_trading.sh
```
**O que faz:**
- Health check
- Inicia paper trading
- Aguarda coleta de dados (180s)
- Mostra métricas finais
- Para sessão

**Tempo:** ~3 minutos

### 2. Monitor em Tempo Real
```bash
./monitor_paper_trading.sh SESSION_ID
```
**O que faz:**
- Atualiza status a cada 10s
- Mostra PnL em tempo real
- Lista posições abertas
- Histórico de trades

**Uso:**
```bash
# Iniciar monitoramento
./monitor_paper_trading.sh momentum_live_001

# Pressione Ctrl+C para parar
```

---

## 🎮 Guia de Uso Completo

### Passo 1: Escolher Estratégia

**Estratégias Disponíveis:**
- `momentum` - Momentum com ROC
- `macd_rsi_combo` - Combinação MACD + RSI
- `trend_following` - Seguidor de tendência com EMAs
- `mean_reversion` - Reversão à média com RSI
- `volatility_breakout` - Breakout de volatilidade
- `bollinger_bands` - Bandas de Bollinger
- `volume_profile` - Perfil de volume
- `multi_timeframe` - Multi timeframe
- `dynamic_position_sizing` - Posicionamento dinâmico

### Passo 2: Iniciar Sessão

```bash
SESSION_ID="my_strategy_$(date +%s)"

curl -X POST http://localhost:3008/paper-trading/start \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"strategy_name\": \"momentum\",
    \"strategy_parameters\": {\"roc_period\": 20, \"threshold\": 0},
    \"symbol\": \"BTCUSDT\",
    \"timeframe\": \"1m\",
    \"initial_balance\": 10000.0
  }"
```

### Passo 3: Monitorar

**Opção A - Script automático:**
```bash
./monitor_paper_trading.sh $SESSION_ID
```

**Opção B - Manual:**
```bash
# Loop de monitoramento
while true; do
  clear
  echo "=== $(date) ==="
  curl -s http://localhost:3008/paper-trading/$SESSION_ID/status | jq '{
    uptime: .uptime_seconds,
    candles: .candles_collected,
    trades: .trades_executed,
    pnl: .account_summary.total_pnl_percent
  }'
  sleep 10
done
```

### Passo 4: Analisar Resultados

```bash
# Resumo da conta
curl -s http://localhost:3008/paper-trading/$SESSION_ID/account | jq

# Histórico completo
curl -s "http://localhost:3008/paper-trading/$SESSION_ID/trades?limit=100" | jq

# Posições abertas
curl -s http://localhost:3008/paper-trading/$SESSION_ID/positions | jq
```

### Passo 5: Parar

```bash
curl -X POST http://localhost:3008/paper-trading/$SESSION_ID/stop
```

---

## 📈 Exemplo Real - Teste de 1 Hora

```bash
#!/bin/bash

echo "🚀 Iniciando teste de 1 hora com Momentum Strategy"

# Iniciar
SESSION="momentum_1h_$(date +%H%M)"

curl -X POST http://localhost:3008/paper-trading/start \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"strategy_name\": \"momentum\",
    \"strategy_parameters\": {\"roc_period\": 20, \"threshold\": 0},
    \"symbol\": \"BTCUSDT\",
    \"timeframe\": \"1m\",
    \"initial_balance\": 1000.0
  }" | jq

echo ""
echo "✓ Paper trading iniciado: $SESSION"
echo "⏱ Aguardando 1 hora..."
echo "📊 Monitore em: ./monitor_paper_trading.sh $SESSION"
echo ""

# Aguardar 1 hora
sleep 3600

# Resultados finais
echo "📊 RESULTADOS FINAIS:"
curl -s http://localhost:3008/paper-trading/$SESSION/status | jq '{
  strategy: .strategy_name,
  uptime_min: (.uptime_seconds / 60),
  candles: .candles_collected,
  signals: .signals_generated,
  trades: .trades_executed,
  pnl_percent: .account_summary.total_pnl_percent,
  final_balance: .account_summary.balance
}'

# Parar
curl -X POST http://localhost:3008/paper-trading/$SESSION/stop | jq
```

---

## 🔍 Troubleshooting

### Problema: Container não inicia
```bash
# Ver logs
docker logs aitrading-execution-engine --tail 50

# Reiniciar
docker compose restart execution-engine

# Rebuild
docker compose build execution-engine --no-cache
docker compose up -d execution-engine
```

### Problema: Estratégia não gera sinais
**Causa:** Poucos candles coletados (mínimo: 50)

**Solução:** Aguardar mais tempo
```bash
# Ver quantos candles foram coletados
curl -s http://localhost:3008/paper-trading/SESSION_ID/status | jq '.candles_collected'

# Deve ser >= 50 para indicadores funcionarem
```

### Problema: WebSocket desconecta
**Causa:** Rede instável ou Binance maintenance

**Solução:** Reconexão automática implementada
```bash
# Ver logs para confirmar reconexão
docker logs -f aitrading-execution-engine | grep "reconnect"
```

### Problema: Biblioteca 'ta' não encontrada
**Solução temporária:**
```bash
# Instalar manualmente
docker exec -u root aitrading-execution-engine pip install ta==0.11.0
docker compose restart execution-engine
```

**Solução permanente:**
```bash
# Já está no requirements.txt, rebuild do zero:
docker compose build --no-cache execution-engine
docker compose up -d execution-engine
```

---

## 📚 Documentação Adicional

- **Guia Completo:** `PAPER_TRADING_GUIDE.md`
- **Arquitetura:** `ARCHITECTURE.md`
- **Troubleshooting:** `TROUBLESHOOTING.md`

---

## 🎓 Próximos Passos

1. ✅ **Paper Trading funcionando** (COMPLETO)
2. 🔄 **Dashboard Web** (EM PROGRESSO)
   - Interface para monitorar múltiplas sessões
   - Gráficos de equity curve
   - Lista de trades em tempo real

3. ⏳ **Features Futuras:**
   - Notificações (Telegram/Email)
   - Multi-symbol (rodar vários pares)
   - Backtesting vs Paper Trading comparison
   - Performance analytics dashboard
   - Export de trades para CSV/Excel

---

## 🎯 Conclusão

O **Paper Trading Engine** está **100% funcional** e pronto para validar suas estratégias em condições de mercado reais, sem risco financeiro!

**Recomendação:**
1. Teste cada estratégia por pelo menos 24-48 horas
2. Compare resultados com backtesting
3. Ajuste parâmetros conforme necessário
4. **Só vá para trading real após 30+ dias de paper trading lucrativo**

---

**Status:** ✅ OPERACIONAL  
**Última Atualização:** 9 de dezembro de 2025  
**Versão:** 1.0.0

---

💡 **Dica:** Execute `./test_paper_trading.sh` agora para um teste completo automatizado!
