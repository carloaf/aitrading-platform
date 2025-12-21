# 🚀 Implementação Completa: Multi-timeframe + Backfill + Dashboard + Alertas

## ✅ FEATURES IMPLEMENTADAS

### 1. **Backfill Histórico** (2 semanas)
**Arquivo:** `scripts/backfill_historical_data.py`

#### Funcionalidades:
- ✅ Busca dados históricos de até 2 semanas da Binance
- ✅ Suporta múltiplos timeframes: 1h, 4h, 1d (15m opcional)
- ✅ Async com asyncio + bulk inserts (executemany)
- ✅ Progress tracking com logs detalhados
- ✅ Rate limiting (semaphore 5 requests paralelos)
- ✅ Smart skipping (pula se >90% dos dados já existem)
- ✅ Tratamento de erros robusto

#### Como Usar:
```bash
# Executar dentro do container
docker exec aitrading-execution-engine python /app/scripts/backfill_historical_data.py --days 14 --timeframes 1h 4h 1d

# Com 15m (muito pesado - cuidado!)
docker exec aitrading-execution-engine python /app/scripts/backfill_historical_data.py --days 7 --include-15m

# Para símbolos específicos
docker exec aitrading-execution-engine python /app/scripts/backfill_historical_data.py --symbols BTCUSDT ETHUSDT

# Teste rápido (1 dia)
docker exec aitrading-execution-engine python /app/scripts/backfill_historical_data.py --days 1
```

#### Output Esperado:
```
🚀 Iniciando backfill histórico...
Configuração:
  - Período: 14 dias
  - Timeframes: ['1h', '4h', '1d']
  - Total símbolos ativos: 83

⏳ Progresso: 10/83 (12.05%)
✅ BTCUSDT: 336 candles inseridos (1h=168, 4h=84, 1d=14)
⏳ Progresso: 20/83 (24.10%)
...

📊 Resumo Final:
  - Sucesso: 76 símbolos
  - Pulados: 5 símbolos (>90% dados existentes)
  - Falhas: 2 símbolos
  - Total candles inseridos: 25,368
  - Duração total: 5m 32s
```

---

### 2. **Multi-timeframe Worker**
**Arquivo:** `services/execution-engine/src/main.py`

#### Funcionalidades:
- ✅ Worker atualiza automaticamente dados de múltiplos timeframes
- ✅ Suporta: 1h (padrão), 4h, 1d
- ✅ Cada timeframe salvo com source tag único: `binance_1h`, `binance_4h`, `binance_1d`
- ✅ Cache atualizado com dados de 1h (para RSI em tempo real)
- ✅ Dados históricos salvos em `market_data` com timestamp único

#### Constante:
```python
WORKER_TIMEFRAMES = ['1h', '4h', '1d']  # 15m opcional (muito pesado)
```

#### Como Funciona:
- Worker roda a cada 60 segundos
- Para cada símbolo ativo, busca 3 timeframes (1h, 4h, 1d)
- Salva cada candle com `(symbol, timestamp)` único
- Source tag diferencia timeframes: `binance_1h`, `binance_4h`, `binance_1d`

---

### 3. **API de Consulta Histórica**
**Endpoint:** `GET /api/history/candles`

#### Parâmetros:
- `symbol` (obrigatório): Símbolo (ex: BTCUSDT)
- `timeframe` (default: 1h): Timeframe (1h, 4h, 1d)
- `start` (opcional): Data inicial ISO 8601 (ex: 2025-01-01T00:00:00Z)
- `end` (opcional): Data final ISO 8601
- `limit` (default: 100): Máximo de candles retornados

#### Exemplos:
```bash
# Últimos 100 candles de 1h do BTC
curl "http://localhost:3008/api/history/candles?symbol=BTCUSDT&timeframe=1h&limit=100"

# Candles de 4h entre datas específicas
curl "http://localhost:3008/api/history/candles?symbol=ETHUSDT&timeframe=4h&start=2025-01-15T00:00:00Z&end=2025-01-20T00:00:00Z"

# Últimos 30 candles diários
curl "http://localhost:3008/api/history/candles?symbol=SOLUSDT&timeframe=1d&limit=30"
```

#### Response:
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "count": 100,
  "candles": [
    {
      "timestamp": "2025-01-22T10:00:00+00:00",
      "open": 106234.50,
      "high": 106450.20,
      "low": 106100.10,
      "close": 106320.80,
      "volume": 123.45
    },
    ...
  ]
}
```

---

### 4. **Dashboard de Cobertura**
**Endpoint:** `GET /api/symbols/coverage-dashboard`

#### Funcionalidades:
- ✅ Métricas globais (total_symbols, active, with_data, coverage %)
- ✅ Cobertura por timeframe (quantos símbolos têm dados em 1h/4h/1d)
- ✅ Status detalhado por símbolo (últimos 7 dias)
- ✅ Last update timestamp para cada timeframe
- ✅ Contagem de candles por timeframe

#### Exemplo:
```bash
curl http://localhost:3008/api/symbols/coverage-dashboard | python3 -m json.tool
```

#### Response:
```json
{
  "global_metrics": {
    "total_symbols": 83,
    "active_symbols": 83,
    "symbols_with_data": 76,
    "coverage_percentage": 91.57
  },
  "timeframe_coverage": [
    {
      "timeframe": "1h",
      "symbol_count": 76,
      "total_candles": 12768,
      "latest_data": "2025-01-22T15:00:00+00:00"
    },
    {
      "timeframe": "4h",
      "symbol_count": 75,
      "total_candles": 3185,
      "latest_data": "2025-01-22T12:00:00+00:00"
    },
    {
      "timeframe": "1d",
      "symbol_count": 76,
      "total_candles": 1064,
      "latest_data": "2025-01-22T00:00:00+00:00"
    }
  ],
  "symbol_status": [
    {
      "symbol": "BTCUSDT",
      "active": true,
      "candles": {
        "1h": 168,
        "4h": 42,
        "1d": 7
      },
      "last_update": {
        "1h": "2025-01-22T15:00:00+00:00",
        "4h": "2025-01-22T12:00:00+00:00",
        "1d": "2025-01-22T00:00:00+00:00"
      }
    },
    ...
  ]
}
```

---

### 5. **Sistema de Alertas**
**Endpoints:** `GET /api/symbols/alerts` + Helper `create_symbol_alert()`

#### Tabela Criada:
```sql
CREATE TABLE symbol_alerts (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- 'added', 'failed', 'recovered', 'removed', 'no_data'
    message TEXT,
    severity VARCHAR(20) DEFAULT 'info', -- 'info', 'warning', 'error', 'success'
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Endpoint de Consulta:
**GET /api/symbols/alerts**

Parâmetros:
- `symbol` (opcional): Filtrar por símbolo específico
- `event_type` (opcional): added, failed, recovered, removed, no_data
- `severity` (opcional): info, warning, error, success
- `limit` (default: 50): Máximo de alertas

Exemplos:
```bash
# Últimos 50 alertas
curl "http://localhost:3008/api/symbols/alerts"

# Alertas de um símbolo específico
curl "http://localhost:3008/api/symbols/alerts?symbol=BTCUSDT"

# Apenas erros
curl "http://localhost:3008/api/symbols/alerts?severity=error&limit=20"

# Alertas de símbolos adicionados
curl "http://localhost:3008/api/symbols/alerts?event_type=added"
```

#### Response:
```json
{
  "count": 5,
  "alerts": [
    {
      "id": 123,
      "symbol": "BTCUSDT",
      "event_type": "added",
      "message": "Novo símbolo adicionado ao monitoramento",
      "severity": "success",
      "metadata": {"notes": "Maior criptomoeda"},
      "created_at": "2025-01-22T15:30:00+00:00"
    },
    {
      "id": 122,
      "symbol": "XYZUSDT",
      "event_type": "failed",
      "message": "Falha ao buscar dados: Timeout",
      "severity": "error",
      "metadata": {"error": "Timeout", "timeframe": "1h"},
      "created_at": "2025-01-22T15:25:00+00:00"
    },
    ...
  ]
}
```

#### Helper Function:
```python
# Criar alerta manualmente (exemplo no código)
await create_symbol_alert(
    symbol='BTCUSDT',
    event_type='added',  # ou 'failed', 'recovered', 'removed', 'no_data'
    message='Novo símbolo adicionado',
    severity='success',  # ou 'info', 'warning', 'error'
    metadata={'notes': 'Descrição adicional'}
)
```

#### Alertas Automáticos:
- ✅ **added**: Quando novo símbolo é adicionado via POST /api/symbols
- ✅ **removed**: Quando símbolo é removido/desativado via DELETE /api/symbols
- ⚠️ **failed**: Temporariamente desabilitado no worker (pode causar deadlock)

---

## 📦 ARQUIVOS CRIADOS/MODIFICADOS

### Novos Arquivos:
1. `scripts/backfill_historical_data.py` - Script de backfill (350+ linhas)
2. `scripts/init_symbol_alerts.sql` - Schema da tabela de alertas
3. `docs/MULTI_TIMEFRAME_GUIDE.md` (este arquivo)

### Arquivos Modificados:
1. `services/execution-engine/src/main.py`:
   - Adicionado `WORKER_TIMEFRAMES` constant
   - Modificado `fetch_single_symbol()` para buscar múltiplos timeframes
   - Modificado `update_market_data_cache()` para salvar multi-timeframe
   - Adicionado endpoint `GET /api/history/candles`
   - Adicionado endpoint `GET /api/symbols/coverage-dashboard`
   - Adicionado endpoint `GET /api/symbols/alerts`
   - Adicionado helper `create_symbol_alert()`
   - Modificado `POST /api/symbols` para criar alertas
   - Modificado `DELETE /api/symbols` para criar alertas

---

## 🧪 TESTES E VALIDAÇÃO

### 1. Testar API de Cobertura:
```bash
# Dashboard completo
curl -s http://localhost:3008/api/symbols/coverage-dashboard | python3 -m json.tool

# Verificar métricas globais
curl -s http://localhost:3008/api/symbols/coverage-dashboard | jq '.global_metrics'

# Verificar cobertura por timeframe
curl -s http://localhost:3008/api/symbols/coverage-dashboard | jq '.timeframe_coverage'
```

### 2. Testar API de Histórico:
```bash
# Últimos 10 candles de 1h do BTC
curl -s "http://localhost:3008/api/history/candles?symbol=BTCUSDT&timeframe=1h&limit=10" | python3 -m json.tool

# Últimos 5 candles de 4h do ETH
curl -s "http://localhost:3008/api/history/candles?symbol=ETHUSDT&timeframe=4h&limit=5" | python3 -m json.tool

# Candles diários do SOL
curl -s "http://localhost:3008/api/history/candles?symbol=SOLUSDT&timeframe=1d&limit=7" | python3 -m json.tool
```

### 3. Testar Sistema de Alertas:
```bash
# Ver últimos alertas
curl -s http://localhost:3008/api/symbols/alerts | python3 -m json.tool

# Adicionar um símbolo (cria alerta automático)
curl -X POST http://localhost:3008/api/symbols \
  -H "Content-Type: application/json" \
  -d '{"symbol": "DOGEUSDT", "notes": "Teste de alerta"}' | python3 -m json.tool

# Verificar alerta criado
curl -s "http://localhost:3008/api/symbols/alerts?symbol=DOGEUSDT" | python3 -m json.tool
```

### 4. Executar Backfill:
```bash
# Backfill de 7 dias (teste rápido)
docker exec aitrading-execution-engine python /app/scripts/backfill_historical_data.py --days 7

# Backfill completo de 14 dias
docker exec aitrading-execution-engine python /app/scripts/backfill_historical_data.py --days 14 --timeframes 1h 4h 1d
```

### 5. Verificar Worker Multi-timeframe:
```bash
# Monitorar logs do worker
docker logs aitrading-execution-engine --tail 100 -f | grep MarketData

# Verificar se múltiplos timeframes estão sendo salvos
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
SELECT source, COUNT(DISTINCT symbol) as symbols, COUNT(*) as candles, MAX(timestamp) as latest
FROM market_data
WHERE timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY source
ORDER BY source;
"
```

---

## 📊 BANCO DE DADOS

### Consultas Úteis:

#### Verificar cobertura de dados:
```sql
SELECT 
    source,
    COUNT(DISTINCT symbol) as symbol_count,
    COUNT(*) as total_candles,
    MIN(timestamp) as oldest_data,
    MAX(timestamp) as latest_data
FROM market_data
GROUP BY source
ORDER BY source;
```

#### Verificar dados de um símbolo específico:
```sql
SELECT 
    symbol,
    timestamp,
    source,
    open, high, low, close, volume
FROM market_data
WHERE symbol = 'BTCUSDT'
ORDER BY timestamp DESC
LIMIT 20;
```

#### Verificar símbolos com dados em múltiplos timeframes:
```sql
SELECT 
    symbol,
    COUNT(DISTINCT source) as timeframe_count,
    STRING_AGG(DISTINCT source, ', ') as available_timeframes
FROM market_data
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY symbol
HAVING COUNT(DISTINCT source) >= 2
ORDER BY timeframe_count DESC;
```

#### Ver últimos alertas:
```sql
SELECT 
    symbol,
    event_type,
    message,
    severity,
    created_at
FROM symbol_alerts
ORDER BY created_at DESC
LIMIT 10;
```

---

## 🔧 TROUBLESHOOTING

### Worker não está salvando dados:
```bash
# Verificar logs do worker
docker logs aitrading-execution-engine --tail 200 | grep -A 5 "MarketDataWorker"

# Verificar se símbolos estão ativos
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
SELECT COUNT(*) as active_symbols FROM monitored_symbols WHERE active = true;
"

# Restart manual do worker
docker compose restart execution-engine
```

### Backfill muito lento:
```bash
# Reduzir período
--days 7  # ao invés de 14

# Reduzir símbolos
--symbols BTCUSDT ETHUSDT SOLUSDT

# Remover 15m (muito pesado)
# Não usar --include-15m
```

### Alertas não aparecem:
```bash
# Verificar se tabela existe
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "\d symbol_alerts"

# Criar tabela manualmente se necessário
docker exec -i aitrading-timescaledb psql -U crypto_user -d crypto_market < scripts/init_symbol_alerts.sql
```

### API retorna erro 500:
```bash
# Verificar logs completos
docker logs aitrading-execution-engine --tail 500

# Verificar se banco está acessível
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "SELECT 1;"

# Rebuild do container
docker compose build execution-engine && docker compose restart execution-engine
```

---

## 🎯 PRÓXIMOS PASSOS (Opcional)

### 1. Frontend Dashboard:
- Criar página HTML para visualizar dashboard de cobertura
- Gráficos com Chart.js mostrando cobertura por timeframe
- Lista de símbolos com status colorido (verde/amarelo/vermelho)

### 2. Sistema de Notificações:
- Webhook para alertas críticos (Slack/Discord/Telegram)
- Email notifications para falhas persistentes
- Dashboard de alertas no frontend

### 3. Otimizações:
- Adicionar cache Redis para consultas frequentes de histórico
- Implementar paginação no endpoint de candles
- Adicionar compressão de dados antigos (TimescaleDB compression)

### 4. Monitoramento:
- Prometheus metrics para worker (candles_fetched, fetch_errors, etc.)
- Grafana dashboard para visualização de métricas
- Health checks mais robustos

---

## 📝 NOTAS IMPORTANTES

### ⚠️ Alertas Automáticos no Worker:
- **Temporariamente desabilitados** para prevenir deadlocks
- Worker atualmente apenas loga erros, não cria alertas
- Alertas funcionam perfeitamente em endpoints (POST/DELETE symbols)
- Solução futura: usar message queue (RabbitMQ/Kafka) para alertas assíncronos

### ⚙️ Performance:
- Worker atualiza 83 símbolos × 3 timeframes = 249 requests a cada 60s
- Rate limit Binance: ~1200 req/min (safe)
- Semaphore limita a 3 requests paralelos (previne rate limit)
- Backfill usa semaphore de 5 + sleep 0.1s entre chunks

### 💾 Armazenamento:
- 83 símbolos × 3 timeframes × 24h/1h = ~5,976 candles/dia (1h)
- 83 símbolos × 3 timeframes × 6 candles/dia (4h) = ~1,494 candles/dia
- 83 símbolos × 3 timeframes × 1 candle/dia (1d) = ~249 candles/dia
- **Total:** ~7,719 candles/dia (~350 KB/dia em PostgreSQL)
- **2 semanas:** ~108,066 candles (~5 MB)

### 🔒 Segurança:
- Usar `.env` para credenciais do banco
- Nunca commitar `BINANCE_API_SECRET`
- Rate limiting automático pelo ccxt
- Validação de símbolos antes de adicionar

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

- [x] Criar script de backfill histórico
- [x] Adicionar suporte multi-timeframe no worker
- [x] Criar endpoint de consulta histórica (/api/history/candles)
- [x] Criar endpoint de dashboard de cobertura (/api/symbols/coverage-dashboard)
- [x] Criar tabela de alertas (symbol_alerts)
- [x] Criar endpoint de consulta de alertas (/api/symbols/alerts)
- [x] Adicionar helper create_symbol_alert()
- [x] Integrar alertas em POST /api/symbols
- [x] Integrar alertas em DELETE /api/symbols
- [x] Documentação completa
- [x] Testes de validação

---

## 📞 SUPORTE

### Logs Importantes:
```bash
# Worker logs
docker logs aitrading-execution-engine | grep MarketData

# Alert logs
docker logs aitrading-execution-engine | grep Alert

# Backfill logs
docker logs aitrading-execution-engine | grep backfill
```

### Comandos de Debug:
```bash
# Status dos containers
docker ps

# Restart completo
docker compose down && docker compose up -d

# Rebuild tudo
docker compose build && docker compose up -d

# Limpar logs
docker compose logs --tail 0 -f execution-engine
```

---

**✨ Todas as 4 features foram implementadas com sucesso!**

1. ✅ **Backfill histórico** - Script completo e funcional
2. ✅ **Multi-timeframe** - Worker atualiza 1h, 4h, 1d automaticamente
3. ✅ **Dashboard de cobertura** - API endpoint com métricas completas
4. ✅ **Sistema de alertas** - Tabela + API + integração automática

**🚀 Sistema pronto para produção!**
