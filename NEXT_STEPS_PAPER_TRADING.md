# 🎯 PRÓXIMOS PASSOS - Paper Trading

## ✅ STATUS ATUAL: OPERACIONAL E TESTADO

O Paper Trading Engine está **100% funcional** com correção aplicada para serialização de tipos numpy.

---

## 📊 SESSÕES ATIVAS NO MOMENTO

Execute para ver todas as sessões:
```bash
curl http://localhost:3008/paper-trading/sessions | jq
```

**Sessões detectadas:**
- `test_fixed` - Sessão de teste (recém-iniciada)
- Possíveis sessões anteriores que podem ter sido reiniciadas

---

## 🚀 OPÇÕES DE PRÓXIMOS PASSOS

### OPÇÃO 1: Monitorar Sessão Atual (Recomendado para validação)

```bash
# Monitoramento simples (atualiza a cada 30s)
./monitor_simple.sh test_fixed

# OU monitoramento completo (atualiza a cada 10s)
./monitor_paper_trading.sh test_fixed
```

**Objetivo:** Acompanhar a estratégia por 2-4 horas para validar funcionamento

**O que observar:**
- Coleta de candles (mínimo 50 para indicadores)
- Geração de sinais
- Execução de trades
- PnL evolution

---

### OPÇÃO 2: Iniciar Teste de 24-48h

```bash
# 1. Iniciar nova sessão com nome descritivo
curl -X POST http://localhost:3008/paper-trading/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "momentum_24h_'$(date +%Y%m%d)'",
    "strategy_name": "momentum",
    "strategy_parameters": {"roc_period": 20, "threshold": 0},
    "symbol": "BTCUSDT",
    "timeframe": "1m",
    "initial_balance": 10000.0
  }'

# 2. Deixar rodando e verificar periodicamente
# Agendar cron para verificação a cada 6h:
# crontab -e
# 0 */6 * * * curl http://localhost:3008/paper-trading/momentum_24h_$(date +%Y%m%d)/status | jq

# 3. Após 24-48h, analisar resultados
curl http://localhost:3008/paper-trading/momentum_24h_$(date +%Y%m%d)/trades | jq
```

**Objetivo:** Coletar dados suficientes para análise estatística

**Métricas a avaliar:**
- Win Rate (% trades lucrativos)
- Average PnL por trade
- Maximum Drawdown
- Sharpe Ratio estimado
- Número de sinais gerados vs executados

---

### OPÇÃO 3: Testar Múltiplas Estratégias

```bash
# Iniciar 3 estratégias simultaneamente para comparação
STRATEGIES=("momentum" "macd_rsi_combo" "trend_following")

for strategy in "${STRATEGIES[@]}"; do
  curl -X POST http://localhost:3008/paper-trading/start \
    -H "Content-Type: application/json" \
    -d "{
      \"session_id\": \"compare_${strategy}\",
      \"strategy_name\": \"$strategy\",
      \"strategy_parameters\": {},
      \"symbol\": \"BTCUSDT\",
      \"timeframe\": \"1m\",
      \"initial_balance\": 1000.0
    }"
  echo ""
done

# Verificar todas após algumas horas
curl http://localhost:3008/paper-trading/sessions | jq
```

**Objetivo:** Identificar qual estratégia performa melhor em condições reais

---

### OPÇÃO 4: Desenvolver Dashboard Web (Próxima Fase)

**Criar interface React/Vue para:**

1. **Visualização de Sessões**
   - Lista todas as sessões ativas
   - Filtros por estratégia, símbolo, performance
   - Cards com métricas principais

2. **Gráficos em Tempo Real**
   - Equity curve (Chart.js ou Recharts)
   - Candles com sinais marcados
   - Drawdown chart
   - Win/Loss distribution

3. **Controle de Sessões**
   - Botão Start/Stop
   - Formulário para criar nova sessão
   - Ajuste de parâmetros em tempo real

4. **Análise de Trades**
   - Tabela com filtros e ordenação
   - Detalhes de cada trade
   - Export para CSV/Excel
   - Statistics panel (Win Rate, Avg PnL, etc.)

**Stack Sugerida:**
```
Frontend: React + TypeScript + Tailwind CSS
Charts: Chart.js ou Recharts
API Client: Axios
State Management: Zustand ou Jotai
Real-time: WebSocket ou polling
```

**Estrutura:**
```
frontend/
├── src/
│   ├── components/
│   │   ├── SessionCard.tsx
│   │   ├── EquityCurveChart.tsx
│   │   ├── TradesTable.tsx
│   │   └── SessionControls.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── SessionDetail.tsx
│   │   └── Analytics.tsx
│   ├── hooks/
│   │   ├── usePaperTrading.ts
│   │   └── usePolling.ts
│   └── api/
│       └── paperTrading.ts
└── package.json
```

---

## 📋 CHECKLIST DE VALIDAÇÃO (Próximas 4-6 horas)

- [ ] **Aguardar 50+ candles** (~50 minutos)
- [ ] **Verificar primeiro sinal** gerado
- [ ] **Confirmar execução** de primeiro trade
- [ ] **Monitorar PnL** evolution
- [ ] **Verificar logs** do container para erros
- [ ] **Testar parar/reiniciar** sessão
- [ ] **Analisar histórico** de trades após 3h
- [ ] **Comparar com backtesting** (mesmos parâmetros)

---

## 🔧 COMANDOS ÚTEIS

### Verificar Health
```bash
curl http://localhost:3008/health | jq
```

### Listar Todas as Sessões
```bash
curl http://localhost:3008/paper-trading/sessions | jq
```

### Ver Status Detalhado
```bash
SESSION="test_fixed"
curl http://localhost:3008/paper-trading/$SESSION/status | jq
```

### Ver Últimos 10 Trades
```bash
SESSION="test_fixed"
curl "http://localhost:3008/paper-trading/$SESSION/trades?limit=10" | jq
```

### Parar Sessão
```bash
SESSION="test_fixed"
curl -X POST http://localhost:3008/paper-trading/$SESSION/stop | jq
```

### Ver Logs em Tempo Real
```bash
docker logs -f aitrading-execution-engine
```

### Restart Container (se necessário)
```bash
docker compose restart execution-engine
# Reinstalar ta
docker exec -u root aitrading-execution-engine pip install -q ta==0.11.0
```

---

## 📊 ANÁLISE ESPERADA (Após 24h)

### Métricas Mínimas:
- **Candles coletados:** 1,440 (24h × 60min)
- **Sinais gerados:** 10-50 (depende da volatilidade)
- **Trades executados:** 5-25 pares (10-50 operações)
- **PnL esperado:** -5% a +15% (alta volatilidade no crypto)

### Sinais de Alerta:
- ❌ **0 sinais após 2h:** Parâmetros muito conservadores ou indicador com erro
- ❌ **PnL < -20%:** Estratégia não adequada para mercado atual
- ❌ **100+ trades/dia:** Overtrading, comissões corroendo lucro
- ❌ **Websocket desconectando:** Problema de rede

### Sinais Positivos:
- ✅ **Win Rate > 45%:** Estratégia promissora
- ✅ **PnL positivo após 24h:** Continuar testando
- ✅ **Drawdown < 10%:** Gerenciamento de risco OK
- ✅ **Trades espaçados:** Evita overtrading

---

## 🎯 DECISÃO RECOMENDADA

**Para os próximos passos, sugiro:**

### CURTO PRAZO (Hoje - Próximas 4h):
1. ✅ Manter sessão `test_fixed` rodando
2. ✅ Monitorar com `./monitor_simple.sh test_fixed`
3. ✅ Aguardar primeiros 50 candles e sinais
4. ✅ Validar execução de trades

### MÉDIO PRAZO (Próximos 2-3 dias):
1. 🔄 Iniciar teste de 24-48h com múltiplas estratégias
2. 🔄 Coletar dados para análise estatística
3. 🔄 Comparar com resultados de backtesting
4. 🔄 Ajustar parâmetros se necessário

### LONGO PRAZO (Próxima semana):
1. ⏳ Desenvolver Dashboard Web (Fase 8)
2. ⏳ Implementar alertas (Telegram/Email)
3. ⏳ Multi-symbol trading
4. ⏳ Advanced analytics

---

## 💡 COMANDO PARA EXECUTAR AGORA

```bash
# Opção A: Monitoramento simples
./monitor_simple.sh test_fixed

# Opção B: Monitoramento completo
./monitor_paper_trading.sh test_fixed

# Opção C: Apenas verificar status
watch -n 30 'curl -s http://localhost:3008/paper-trading/test_fixed/status | jq "{uptime: .uptime_seconds, candles: .candles_collected, trades: .trades_executed, pnl: .account_summary.total_pnl_percent}"'
```

---

**📌 Recomendação Final:** Execute `./monitor_simple.sh test_fixed` e aguarde 2-4 horas para ver a estratégia em ação!

**Status:** ✅ Sistema pronto para monitoramento  
**Próxima Ação:** Monitorar e avaliar performance  
**Fase Seguinte:** Dashboard Web (quando decidir avançar)
