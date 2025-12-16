# 📦 SISTEMA DE ARMAZENAMENTO DE DADOS HISTÓRICOS

## Visão Geral

A plataforma AI Trading armazena **todos os dados** coletados e executados em um banco de dados TimescaleDB (PostgreSQL otimizado para séries temporais). Isso permite análises históricas, backtesting e auditoria completa.

---

## 🗄️ Estrutura de Dados

### 1. **Dados de Mercado (Market Data)**

**Tabela:** `market_data_realtime` e `market_data`

**Armazenamento:**
- ✅ **Candles em tempo real** coletados via WebSocket
- ✅ **Dados históricos** coletados via REST API (100 últimas velas a cada 1 hora)
- ✅ **Múltiplos timeframes:** 1m, 5m, 15m, 1h, 4h, 1d

**Campos:**
```sql
CREATE TABLE market_data_realtime (
    id BIGSERIAL,
    symbol VARCHAR(20),           -- Ex: BTCUSDT
    exchange VARCHAR(20),          -- Ex: binance
    timestamp TIMESTAMPTZ,         -- Momento da vela
    open_price DECIMAL(20,8),     -- Preço abertura
    high_price DECIMAL(20,8),     -- Preço máximo
    low_price DECIMAL(20,8),      -- Preço mínimo
    close_price DECIMAL(20,8),    -- Preço fechamento
    volume DECIMAL(20,8),         -- Volume negociado
    quote_volume DECIMAL(20,8),   -- Volume em USDT
    trades_count INTEGER,         -- Número de trades
    interval_type VARCHAR(10),    -- 1m, 5m, 15m, 1h, etc.
    created_at TIMESTAMPTZ
);
```

**Retenção:** 2 anos (política automática do TimescaleDB)

**Agregações:**
- `market_data_hourly`: Velas agregadas por hora
- `market_data_daily`: Velas agregadas por dia

**Local no código:**
- Coleta: `services/market-data-collector/src/index.js`
- Salvamento: Método `saveMarketData()` linha 301

---

### 2. **Sinais de Trading (Trading Signals)**

**Tabela:** `trading_signals`

**Armazenamento:**
- ✅ **Sinais gerados** pelas estratégias (BUY/SELL/HOLD)
- ✅ **Confidence score** de cada sinal
- ✅ **Razões técnicas** que geraram o sinal

**Campos:**
```sql
CREATE TABLE trading_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    timestamp TIMESTAMPTZ,
    signal_type VARCHAR(10),      -- BUY, SELL, HOLD
    confidence DECIMAL(5,4),      -- 0.0 a 1.0
    price DECIMAL(20,8),          -- Preço no momento
    
    -- Scores individuais
    technical_score DECIMAL(5,4),
    sentiment_score DECIMAL(5,4),
    volume_score DECIMAL(5,4),
    
    -- Metadata
    strategy_name VARCHAR(50),
    conditions JSONB,             -- Condições que geraram sinal
    
    -- Status
    status VARCHAR(20),           -- ACTIVE, EXPIRED, EXECUTED
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ
);
```

**Status:**
- `ACTIVE`: Sinal válido aguardando execução
- `EXECUTED`: Ordem executada com base neste sinal
- `EXPIRED`: Sinal expirou sem execução

---

### 3. **Indicadores Técnicos (Technical Indicators)**

**Tabela:** `technical_indicators`

**Armazenamento:**
- ✅ **Valores calculados** de indicadores por timeframe
- ✅ **RSI, MACD, Bollinger Bands, EMAs, etc.**

**Campos:**
```sql
CREATE TABLE technical_indicators (
    id BIGSERIAL,
    symbol VARCHAR(20),
    timestamp TIMESTAMPTZ,
    interval_type VARCHAR(10),
    
    -- Moving Averages
    sma_20 DECIMAL(20,8),
    sma_50 DECIMAL(20,8),
    sma_200 DECIMAL(20,8),
    ema_12 DECIMAL(20,8),
    ema_26 DECIMAL(20,8),
    
    -- Oscillators
    rsi_14 DECIMAL(10,4),
    macd_line DECIMAL(20,8),
    macd_signal DECIMAL(20,8),
    macd_histogram DECIMAL(20,8),
    
    -- Bollinger Bands
    bb_upper DECIMAL(20,8),
    bb_middle DECIMAL(20,8),
    bb_lower DECIMAL(20,8),
    
    -- Volume
    volume_sma_20 DECIMAL(20,8),
    
    -- Support/Resistance
    support_level DECIMAL(20,8),
    resistance_level DECIMAL(20,8),
    
    created_at TIMESTAMPTZ
);
```

**Retenção:** 1 ano

---

### 4. **Trades Executados (Paper Trading)**

**Status Atual:** ⚠️ **NÃO ESTÁ SENDO SALVO** (apenas em memória)

**Problema:** Se o container reiniciar, o histórico de trades é perdido.

**Solução:** Vamos criar a tabela `paper_trading_trades` (ver próxima seção)

---

### 5. **Logs do Sistema (System Logs)**

**Tabela:** `system_logs`

**Armazenamento:**
- ✅ **Logs de todos os serviços**
- ✅ **Erros, warnings, info**
- ✅ **Metadata em formato JSON**

**Retenção:** 3 meses

---

## 🚨 MELHORIAS NECESSÁRIAS

### ❌ Problema Identificado: Trades não persistidos

Atualmente, o **Paper Trading Engine** mantém os trades apenas em memória:

```python
# services/backtesting-engine/src/main.py
self.paper_trading_sessions = {}  # ❌ Dados voláteis!
```

**Impacto:**
- Se o container reiniciar, todo histórico de trades é perdido
- Impossível fazer análise histórica de performance
- Sem auditoria de execução

---

## ✅ SOLUÇÃO: Persistência de Trades

Vamos criar uma tabela dedicada para armazenar trades executados:

```sql
CREATE TABLE paper_trading_trades (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    
    -- Dados da ordem
    trade_type VARCHAR(10) NOT NULL,  -- BUY, SELL
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price DECIMAL(20,8) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    
    -- Financeiro
    value DECIMAL(20,8) NOT NULL,     -- price * quantity
    fee DECIMAL(20,8) DEFAULT 0,
    balance_before DECIMAL(20,8),
    balance_after DECIMAL(20,8),
    
    -- Performance
    pnl DECIMAL(20,8),                -- Profit/Loss em $
    pnl_percent DECIMAL(10,4),        -- P&L em %
    
    -- Contexto
    signal_confidence DECIMAL(5,4),
    indicators_snapshot JSONB,        -- Estado dos indicadores
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Hypertable para performance
SELECT create_hypertable('paper_trading_trades', 'timestamp', if_not_exists => TRUE);

-- Índices
CREATE INDEX idx_trades_session ON paper_trading_trades (session_id, timestamp DESC);
CREATE INDEX idx_trades_symbol ON paper_trading_trades (symbol, timestamp DESC);
```

---

## 📊 CONSULTAS ÚTEIS

### Ver últimos candles coletados
```sql
SELECT 
    symbol, 
    timestamp, 
    close_price, 
    volume,
    interval_type
FROM market_data_realtime
WHERE symbol = 'BTCUSDT' AND interval_type = '1m'
ORDER BY timestamp DESC
LIMIT 100;
```

### Ver total de dados armazenados
```sql
SELECT 
    symbol,
    interval_type,
    COUNT(*) as total_candles,
    MIN(timestamp) as primeira_vela,
    MAX(timestamp) as ultima_vela
FROM market_data_realtime
GROUP BY symbol, interval_type
ORDER BY symbol, interval_type;
```

### Ver sinais gerados por estratégia
```sql
SELECT 
    strategy_name,
    signal_type,
    COUNT(*) as total_signals,
    AVG(confidence) as avg_confidence
FROM trading_signals
WHERE status = 'EXECUTED'
GROUP BY strategy_name, signal_type;
```

---

## 🔄 FLUXO DE DADOS

```
┌─────────────────────────────────────────────────────────────┐
│                   BINANCE API (WebSocket)                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│         Market Data Collector (Node.js)                      │
│  - Recebe candles em tempo real                             │
│  - Formata dados                                            │
└─────────┬───────────────────────────┬───────────────────────┘
          │                           │
          ▼                           ▼
┌──────────────────┐       ┌──────────────────────┐
│   TimescaleDB    │       │       Redis          │
│  (Persistência)  │       │  (Cache + Pub/Sub)   │
└──────────────────┘       └──────────────────────┘
          │                           │
          └────────────┬──────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            Paper Trading Engine (Python)                     │
│  - Lê candles do Redis                                      │
│  - Executa estratégias                                      │
│  - Gera sinais                                              │
│  - Executa trades (simulados)                               │
│  - ⚠️ Deveria salvar no TimescaleDB                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📈 VOLUMES DE DADOS ESPERADOS

### Estimativa por símbolo/timeframe

| Timeframe | Candles/Dia | Candles/Mês | Tamanho/Mês |
|-----------|-------------|-------------|-------------|
| 1m        | 1,440       | ~43,000     | ~2 MB       |
| 5m        | 288         | ~8,600      | ~400 KB     |
| 15m       | 96          | ~2,900      | ~150 KB     |
| 1h        | 24          | ~720        | ~40 KB      |

**Para 5 símbolos com 4 timeframes:**
- **Dados/mês:** ~50 MB
- **Dados/ano:** ~600 MB
- **Dados/2 anos:** ~1.2 GB (bem dentro da política de retenção)

---

## 🛠️ COMANDOS DE MANUTENÇÃO

### Conectar ao banco
```bash
docker-compose exec timescaledb psql -U crypto_user -d crypto_market
```

### Ver tamanho das tabelas
```sql
SELECT 
    hypertable_name,
    pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name))) as size
FROM timescaledb_information.hypertables;
```

### Limpar dados antigos manualmente
```sql
DELETE FROM market_data_realtime 
WHERE timestamp < NOW() - INTERVAL '2 years';
```

### Backup de dados
```bash
# Backup completo
docker-compose exec timescaledb pg_dump -U crypto_user crypto_market > backup_$(date +%Y%m%d).sql

# Backup apenas de trades (quando implementado)
docker-compose exec timescaledb pg_dump -U crypto_user -t paper_trading_trades crypto_market > trades_backup.sql
```

---

## 🎯 PRÓXIMOS PASSOS RECOMENDADOS

### 1. ✅ Implementar persistência de trades
- Criar tabela `paper_trading_trades`
- Modificar Paper Trading Engine para salvar cada trade
- Restaurar sessões após restart

### 2. ✅ Criar endpoints de consulta histórica
```python
# GET /api/history/candles?symbol=BTCUSDT&timeframe=1m&limit=100
# GET /api/history/trades?session_id=macd_rsi_live
# GET /api/history/performance?session_id=macd_rsi_live
```

### 3. ✅ Dashboard de dados históricos
- Gráfico de equity curve
- Lista de trades executados
- Performance por estratégia
- Comparação entre sessões

### 4. 📊 Métricas agregadas
- Total de candles coletados
- Uptime do sistema
- Taxa de sucesso por estratégia
- Volume total negociado (simulado)

---

## 📞 RESPOSTAS ÀS SUAS PERGUNTAS

### ❓ "Vamos guardar esses dados em algum lugar como histórico?"

**Resposta:** ✅ **SIM! Já estamos guardando:**

1. ✅ **Candles de mercado** → `market_data_realtime` (TimescaleDB)
2. ✅ **Sinais gerados** → `trading_signals` (TimescaleDB)
3. ✅ **Indicadores** → `technical_indicators` (TimescaleDB)
4. ❌ **Trades executados** → ⚠️ **AINDA NÃO** (apenas em memória)

**Status:**
- 📦 **Dados de mercado:** Armazenados há ~5 minutos (desde que iniciamos as sessões)
- 🔄 **Coleta contínua:** WebSocket está salvando cada candle
- 💾 **Retenção:** 2 anos automática

**Localização física:**
```bash
# Volume Docker do TimescaleDB
/var/lib/docker/volumes/aitrading-platform_postgres-data/_data

# Verificar tamanho atual
docker-compose exec timescaledb du -sh /var/lib/postgresql/data
```

---

## 🚀 IMPLEMENTAÇÃO IMEDIATA

Posso implementar agora:

1. **Tabela de trades** ✅
2. **Salvamento automático de trades** ✅
3. **Endpoints de consulta histórica** ✅
4. **Dashboard de histórico no frontend** ✅

Deseja que eu implemente essas melhorias? Qual prioridade?

---

**Última atualização:** 10 de dezembro de 2025
