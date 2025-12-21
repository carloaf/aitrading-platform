# 🎯 SÍMBOLOS DINÂMICOS & DADOS HISTÓRICOS - DOCUMENTAÇÃO

## ✅ IMPLEMENTAÇÃO CONCLUÍDA (21/Dez/2025)

### 📋 **RESUMO DAS MUDANÇAS**

Sistema agora possui:
1. ✅ **Símbolos dinâmicos** gerenciados via banco de dados (não mais hardcoded)
2. ✅ **Salvamento automático de dados históricos** (OHLCV 1h) a cada 60 segundos
3. ✅ **API REST completa** para gerenciar símbolos
4. ✅ **83 símbolos** ativos inicialmente (pode aumentar/diminuir dinamicamente)

---

## 🗄️ **1. TABELA `monitored_symbols`**

### Estrutura:
```sql
CREATE TABLE monitored_symbols (
    symbol VARCHAR(20) PRIMARY KEY,           -- Ex: BTCUSDT
    active BOOLEAN NOT NULL DEFAULT true,     -- true = monitora, false = pausado
    added_at TIMESTAMP WITH TIME ZONE,        -- Data de adição
    updated_at TIMESTAMP WITH TIME ZONE,      -- Última modificação
    notes TEXT                                 -- Notas descritivas
);
```

### Inicialização:
```bash
# Script SQL já executado (83 símbolos inseridos)
cat scripts/init_monitored_symbols.sql | docker exec -i aitrading-timescaledb psql -U crypto_user -d crypto_market
```

### Status Atual:
- **Total**: 83 símbolos
- **Ativos**: 83 símbolos
- **Inativos**: 0 símbolos

---

## 📡 **2. API DE GERENCIAMENTO**

### 🔹 **GET /api/symbols** - Listar símbolos

**Parâmetros:**
- `active_only=true` (default) - retorna apenas ativos

**Exemplo:**
```bash
curl http://localhost:3008/api/symbols | jq .

# Retorna array de objetos:
[
  {
    "symbol": "BTCUSDT",
    "active": true,
    "added_at": "2025-12-21T12:58:40.483126+00:00",
    "updated_at": "2025-12-21T12:58:40.483126+00:00",
    "notes": "Bitcoin - Major Asset"
  },
  ...
]
```

---

### 🔹 **POST /api/symbols** - Adicionar novo símbolo

**Body:**
```json
{
  "symbol": "AVAUSDT",
  "notes": "Travala - Travel Token"
}
```

**Exemplo:**
```bash
curl -X POST http://localhost:3008/api/symbols \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AVAUSDT", "notes": "Travala - Travel"}'

# Retorna:
{
  "symbol": "AVAUSDT",
  "active": true,
  "added_at": "2025-12-21T13:15:30+00:00",
  "updated_at": "2025-12-21T13:15:30+00:00",
  "notes": "Travala - Travel"
}
```

**Validações automáticas:**
- ✅ Verifica se símbolo termina com `USDT`
- ✅ Valida se existe na Binance (via API)
- ❌ Rejeita se não encontrado

---

### 🔹 **DELETE /api/symbols/{symbol}** - Remover símbolo

**Parâmetros:**
- `permanent=false` (default) - desativa, mantém no banco
- `permanent=true` - deleta permanentemente

**Exemplo (desativar):**
```bash
curl -X DELETE http://localhost:3008/api/symbols/BONKUSDT

# Retorna:
{"status": "deactivated", "symbol": "BONKUSDT"}
```

**Exemplo (deletar permanentemente):**
```bash
curl -X DELETE "http://localhost:3008/api/symbols/BONKUSDT?permanent=true"

# Retorna:
{"status": "deleted", "symbol": "BONKUSDT"}
```

---

### 🔹 **GET /api/symbols/stats** - Estatísticas

**Exemplo:**
```bash
curl http://localhost:3008/api/symbols/stats | jq .

# Retorna:
{
  "total_symbols": 83,
  "active_symbols": 83,
  "inactive_symbols": 0,
  "first_added": "2025-12-21T12:58:40.483126+00:00",
  "last_added": "2025-12-21T12:58:40.483126+00:00",
  "top_symbols_by_data": [
    {
      "symbol": "SOLUSDT",
      "candle_count": 8374,
      "oldest_data": "2025-01-01T00:00:00+00:00",
      "latest_data": "2025-12-15T21:00:00+00:00"
    },
    {
      "symbol": "ETHUSDT",
      "candle_count": 8374,
      "oldest_data": "2025-01-01T00:00:00+00:00",
      "latest_data": "2025-12-15T21:00:00+00:00"
    },
    ...
  ]
}
```

---

## 💾 **3. DADOS HISTÓRICOS (OHLCV)**

### Como funciona:
1. **Background Worker** roda a cada **60 segundos**
2. Busca **símbolos ativos** de `monitored_symbols`
3. Faz chamada à Binance para obter dados 1h
4. Salva **2 locais**:
   - `market_data_cache` → tempo real (RSI, proximidade)
   - `market_data` → histórico completo (OHLCV)

### Tabela `market_data` (campos salvos):
```sql
symbol      VARCHAR(20)              -- Ex: BTCUSDT
timestamp   TIMESTAMP WITH TIME ZONE -- Ex: 2025-12-21 13:00:00+00
price       NUMERIC(15,8)            -- Preço de fechamento (close)
open        NUMERIC(15,8)            -- Preço de abertura
high        NUMERIC(15,8)            -- Máxima do candle
low         NUMERIC(15,8)            -- Mínima do candle
close       NUMERIC(15,8)            -- Fechamento (mesmo que price)
volume      BIGINT                   -- Volume negociado
source      VARCHAR(50)              -- Ex: 'binance_1h'
created_at  TIMESTAMP                -- Data de inserção no banco
```

### Verificar dados recentes:
```bash
# Últimos candles salvos (última hora)
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c \
  "SELECT symbol, COUNT(*), MAX(timestamp) as latest 
   FROM market_data 
   WHERE timestamp > NOW() - INTERVAL '1 hour' 
   GROUP BY symbol 
   ORDER BY COUNT(*) DESC"

# Resultado esperado (após 60s):
#    symbol   | count |         latest         
# -----------+-------+------------------------
#  BTCUSDT   |     1 | 2025-12-21 13:00:00+00
#  ETHUSDT   |     1 | 2025-12-21 13:00:00+00
#  SOLUSDT   |     1 | 2025-12-21 13:00:00+00
#  ... (83 símbolos)
```

### Verificar logs do worker:
```bash
docker compose logs -f execution-engine | grep MarketDataCache

# Output esperado:
# INFO:__main__:[MarketDataCache] Atualizado 83/83 símbolos (cache) + 83 candles históricos
```

---

## 📊 **4. COBERTURA ATUAL**

### Símbolos Monitorados (83 total):

#### 🏆 **Top 10 - Major Assets (10)**
- BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT
- ADAUSDT, DOGEUSDT, AVAXUSDT, DOTUSDT, LINKUSDT

#### 💰 **Large Cap (10)**
- TRXUSDT, TONUSDT, BCHUSDT, ETCUSDT, ICPUSDT
- FILUSDT, VETUSDT, HBARUSDT, MATICUSDT, SHIBUSDT

#### 🔷 **Mid Cap + Layer 2 (19)**
- LTCUSDT, ATOMUSDT, UNIUSDT, XLMUSDT, NEARUSDT
- IMXUSDT, STXUSDT, MANTAUSDT, METISUSDT, ZKUSDT
- STRKUSDT, LOOMUSDT, SKLUSDT, CELOUSDT, ZETAUSDT
- CYBERUSDT, GLMUSDT, CELRUSDT, CTSIUSDT

#### 🏦 **DeFi Protocols (15)**
- AAVEUSDT, MKRUSDT, CRVUSDT, SNXUSDT, COMPUSDT
- LDOUSDT, SUSHIUSDT, 1INCHUSDT, DYDXUSDT, GMXUSDT
- PENDLEUSDT, JUPUSDT, RUNEUSDT, YFIUSDT, BALUSDT

#### 🤖 **AI / Oracle / Data (12)**
- FETUSDT, AGIXUSDT, OCEANUSDT, TAOUSDT, WLDUSDT
- ARKMUSDT, GRTUSDT, NMRUSDT, IOTXUSDT, RENDERUSDT
- THETAUSDT, ARUSDT

#### ⛓️ **Alt Layer-1 / Infrastructure (5)**
- KASUSDT, ROSEUSDT, FTMUSDT, EGLDUSDT, FLOWUSDT

#### 🔥 **Hot / Trending + Memes (12)**
- APTUSDT, ARBUSDT, OPUSDT, INJUSDT, SUIUSDT
- SEIUSDT, TIAUSDT, ALGOUSDT, WIFUSDT, BONKUSDT
- PEPEUSDT, FLOKIUSDT

---

## 🛠️ **5. MANUTENÇÃO E USO**

### ➕ Adicionar novo símbolo:
```bash
# Exemplo: adicionar GMTUSDT (GMT - STEPN)
curl -X POST http://localhost:3008/api/symbols \
  -H "Content-Type: application/json" \
  -d '{"symbol": "GMTUSDT", "notes": "STEPN - Move to Earn"}'

# Sistema vai:
# 1. Validar se existe na Binance
# 2. Adicionar ao banco (monitored_symbols)
# 3. Na próxima execução do worker (60s), começar a coletar dados
```

### ⏸️ Pausar símbolo temporariamente:
```bash
# Desativar (não deleta do banco)
curl -X DELETE http://localhost:3008/api/symbols/BONKUSDT

# Reativar depois
curl -X POST http://localhost:3008/api/symbols \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BONKUSDT", "notes": "Bonk - Meme"}'
```

### 🗑️ Remover permanentemente:
```bash
curl -X DELETE "http://localhost:3008/api/symbols/BONKUSDT?permanent=true"
```

---

## 🔄 **6. FLUXO DO WORKER**

```
┌─────────────────────────────────────────────┐
│  Background Worker (a cada 60 segundos)     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  1. Query: SELECT symbol FROM               │
│     monitored_symbols WHERE active = true   │
│     → Retorna 83 símbolos                   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  2. Para cada símbolo (semáforo 3):         │
│     - Binance API: fetch_ohlcv('1h', 30)   │
│     - Calcula RSI, change_24h, trend        │
│     - Prepara dados OHLCV do último candle  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  3. Salva em 2 tabelas:                     │
│     ✅ market_data_cache (tempo real)       │
│        → symbol, price, rsi, trend...       │
│     ✅ market_data (histórico)              │
│        → symbol, timestamp, OHLCV...        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  4. Log: "Atualizado 83/83 símbolos         │
│     (cache) + 83 candles históricos"        │
└─────────────────────────────────────────────┘
```

---

## ⚙️ **7. CONFIGURAÇÃO**

### Variáveis de Ambiente (docker-compose.yml):
```yaml
TIMESCALE_HOST: timescaledb
TIMESCALE_PORT: 5432
TIMESCALE_DB: crypto_market
TIMESCALE_USER: crypto_user
TIMESCALE_PASSWORD: crypto_pass
```

### Worker Settings (main.py):
```python
WORKER_INTERVAL = 60  # segundos entre atualizações
BINANCE_LIMIT = 30    # candles por consulta
SEMAPHORE_LIMIT = 3   # máximo de chamadas paralelas à Binance
```

---

## 📈 **8. BENEFÍCIOS**

### ✅ **Antes** (lista fixa):
- ❌ Símbolos hardcoded no código
- ❌ Para adicionar novo, rebuild container
- ❌ Sem dados históricos salvos
- ❌ Apenas 30 símbolos monitorados

### ✅ **Agora** (dinâmico):
- ✅ **Símbolos gerenciados via API** (sem rebuild)
- ✅ **Validação automática** (Binance check)
- ✅ **Dados históricos salvos** automaticamente
- ✅ **83 símbolos** ativos (expansível)
- ✅ **Ativar/desativar** sem perder histórico
- ✅ **Análise temporal** possível (14h+ de dados)

---

## 🚀 **9. PRÓXIMOS PASSOS**

### Curto Prazo (1-2 dias):
1. ✅ Backfill histórico (preencher últimas 2 semanas)
2. ✅ Adicionar endpoint de busca por categoria
3. ✅ Dashboard de cobertura em tempo real

### Médio Prazo (1 semana):
4. ✅ Multi-timeframe (15m, 4h, 1d além de 1h)
5. ✅ Webhook para alertas de novos símbolos
6. ✅ Scheduler inteligente (prioriza símbolos com menos dados)

### Longo Prazo (1 mês):
7. ✅ Machine Learning para detectar símbolos emergentes
8. ✅ Auto-add de novos listings da Binance
9. ✅ Integração com outras exchanges (Coinbase, Kraken)

---

## 📝 **10. TROUBLESHOOTING**

### Worker não está rodando:
```bash
# Verificar status
docker compose ps execution-engine

# Verificar logs
docker compose logs execution-engine | grep MarketDataWorker

# Reiniciar
docker compose restart execution-engine
```

### Símbolo não está salvando dados:
```bash
# 1. Verificar se está ativo
curl http://localhost:3008/api/symbols | jq '.[] | select(.symbol=="BTCUSDT")'

# 2. Verificar se existe na Binance
curl -sS "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"

# 3. Logs específicos
docker compose logs execution-engine | grep "BTCUSDT"
```

### Erro "column does not exist":
- ✅ JÁ CORRIGIDO: `time` → `timestamp`
- ✅ JÁ CRIADO: índice único `(symbol, timestamp)`

---

## 📚 **11. REFERÊNCIAS**

- **Tabela principal**: `monitored_symbols`
- **Dados históricos**: `market_data`
- **Cache tempo real**: `market_data_cache`
- **Script SQL**: [scripts/init_monitored_symbols.sql](scripts/init_monitored_symbols.sql)
- **API Docs**: http://localhost:3008/docs (FastAPI Swagger)

---

**🎉 Sistema completamente funcional e testado!**

- ✅ 83 símbolos ativos
- ✅ Dados históricos sendo salvos a cada 60s
- ✅ API REST completa para gerenciamento
- ✅ Validação automática de símbolos
- ✅ Documentação completa

**Autor**: CryptoDev Assistant  
**Data**: 21 de dezembro de 2025  
**Status**: ✅ PRODUÇÃO READY
