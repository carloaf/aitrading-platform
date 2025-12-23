# 💾 Guia de Persistência de Sinais do Scanner

**Data**: 22 de Dezembro de 2025
**Versão**: 1.0
**Autor**: AI Trading Platform

---

## 🎯 Visão Geral

Implementação completa de **persistência de sinais** do RSI Divergence Scanner no banco de dados, garantindo que sinais detectados **não sejam perdidos** após restart de containers e possam ser acessados por múltiplos usuários.

---

## 🔴 Problema Identificado

### Arquitetura Anterior (FALHA)

```
Scanner Backend → Memória RAM (active_signals)
                    ↓ (volátil)
                Container restart → ❌ Sinais perdidos

Frontend → localStorage (24h)
              ↓ (navegador)
          Apenas 1 usuário
```

**Problemas**:
- ❌ Sinais perdidos em restart de container
- ❌ Sem histórico permanente
- ❌ localStorage volátil (só navegador)
- ❌ Sem sincronização entre usuários

---

## ✅ Solução Implementada

### Nova Arquitetura (ROBUSTA)

```
Scanner Backend → TimescaleDB (autotrade_signals)
                    ↓ (persistente)
                Banco de dados PostgreSQL
                    ↑
Frontend ← /api/scanner/history (HTTP)
```

**Vantagens**:
- ✅ Sinais persistidos no banco PostgreSQL/TimescaleDB
- ✅ Histórico permanente (auditoria)
- ✅ Sincronização entre múltiplos usuários
- ✅ Container restart não afeta dados
- ✅ Queries SQL para análise histórica

---

## 📋 Modificações Implementadas

### 1. Backend - multi_symbol_scanner.py

#### Construtor atualizado:
```python
def __init__(self, config: ScannerConfig = None, db_pool=None):
    # ...
    self.db_pool = db_pool  # ✅ NOVO: Conexão com banco
```

#### Método de persistência:
```python
async def _save_signal_to_db(self, signal: DivergenceSignal):
    """
    💾 Salva sinal detectado no banco de dados (autotrade_signals)
    """
    if not self.db_pool:
        logger.warning("Database pool not configured, signal not saved")
        return
    
    try:
        async with self.db_pool.acquire() as conn:
            signal_id = f"scan_{uuid.uuid4().hex[:12]}"
            
            query = """
            INSERT INTO autotrade_signals (
                signal_id, session_id, symbol, timeframe, signal_type, direction,
                strength, entry_price, stop_loss, take_profit, current_price,
                rsi, adx, volume, volatility, market_regime, reason, timestamp
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            """
            
            await conn.execute(query, ...)
            logger.info(f"💾 Signal saved to DB: {signal_id}")
    except Exception as e:
        logger.error(f"Error saving signal to DB: {e}")
```

#### Query de histórico:
```python
async def get_recent_signals_from_db(self, limit: int = 50, hours: int = 24):
    """
    📊 Busca sinais recentes do banco de dados
    """
    query = """
    SELECT 
        signal_id, timestamp, symbol, timeframe, signal_type, direction,
        strength, entry_price, stop_loss, take_profit, current_price,
        rsi, adx, reason, executed, execution_reason
    FROM autotrade_signals
    WHERE timestamp >= NOW() - INTERVAL '%s hours'
      AND signal_type LIKE '%%divergence%%'
    ORDER BY timestamp DESC
    LIMIT $1
    """
    
    rows = await conn.fetch(query % hours, limit)
    return [convert_row_to_dict(row) for row in rows]
```

#### Scan com persistência:
```python
async def scan_all_symbols(self) -> List[DivergenceSignal]:
    # ... detecção de divergências ...
    
    # 💾 Salvar novos sinais no banco de dados
    if all_signals and self.db_pool:
        logger.info(f"💾 Saving {len(all_signals)} signals to database...")
        for signal in all_signals:
            await self._save_signal_to_db(signal)
    
    return all_signals
```

---

### 2. Backend - main.py

#### Injeção de db_pool no scanner:

**3 endpoints atualizados**:

1. **`/api/scanner/init`**:
```python
# Pass database pool for signal persistence
pool = await get_market_data_pool()
rsi_scanner = MultiSymbolScanner(config, db_pool=pool)
```

2. **`/api/scanner/scan-full`**:
```python
pool = await get_market_data_pool()
rsi_scanner = MultiSymbolScanner(config, db_pool=pool)
```

3. **`/api/scanner/start-continuous`**:
```python
pool = await get_market_data_pool()
rsi_scanner = MultiSymbolScanner(ScannerConfig(), db_pool=pool)
```

#### Novo endpoint de histórico:

```python
@app.get("/api/scanner/history")
async def get_scanner_history(limit: int = 50, hours: int = 24):
    """
    📊 Retorna histórico de sinais do banco de dados
    
    Query params:
    - limit: Número máximo de sinais (default: 50)
    - hours: Janela de tempo em horas (default: 24)
    
    Retorna sinais persistidos no banco, mesmo após restart do container.
    """
    if rsi_scanner and rsi_scanner.db_pool:
        signals = await rsi_scanner.get_recent_signals_from_db(limit, hours)
    else:
        # Criar conexão temporária se scanner não existir
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            # Query SQL direta...
    
    return {
        'success': True,
        'total': len(signals),
        'signals': signals,
        'period_hours': hours
    }
```

---

### 3. Frontend - scanner-dashboard.ejs

#### Nova função para carregar do banco:

```javascript
async function loadSignalHistoryFromDB(hours = 24) {
    try {
        const response = await fetch(`${API_BASE}/api/scanner/history?limit=50&hours=${hours}`);
        const data = await response.json();
        
        if (data.success && data.signals && data.signals.length > 0) {
            console.log(`[History] Carregados ${data.signals.length} sinais do banco de dados`);
            
            // Converter formato do banco para formato do frontend
            signalHistory = data.signals.map(s => ({
                signal_id: s.signal_id,
                symbol: s.symbol,
                timeframe: s.timeframe,
                type: s.type,
                direction: s.direction,
                strength: s.strength,
                entry: s.entry,
                stop_loss: s.stop_loss,
                take_profit: s.take_profit,
                price: s.price,
                rsi: s.rsi,
                adx: s.adx,
                reason: s.reason,
                executed: s.executed,
                execution_reason: s.execution_reason,
                time: new Date(s.timestamp).toLocaleTimeString(),
                timestamp: new Date(s.timestamp).getTime()
            }));
            
            updateHistoryTable();
            updateHistoryStats();
            
            showToast('Histórico Carregado', 
                `${data.signals.length} sinais carregados do banco (últimas ${hours}h)`, 
                'success');
        }
    } catch (error) {
        console.error('[History] Erro ao carregar do banco:', error);
        // Fallback: tentar localStorage
        restoreSignalHistory();
    }
}
```

#### Inicialização atualizada:

```javascript
document.addEventListener('DOMContentLoaded', function() {
    // ...
    
    // 💾 PRIORIDADE: Carregar histórico do BANCO DE DADOS (persistente)
    console.log('[Scanner] Loading signal history from database...');
    loadSignalHistoryFromDB(24);  // Async, não bloqueia UI
    
    // Não precisa mais: restoreSignalHistory();  ❌ localStorage deprecated
    
    // ...
});
```

---

## 📊 Tabela do Banco de Dados

### autotrade_signals (TimescaleDB)

```sql
CREATE TABLE autotrade_signals (
    signal_id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(100),
    timestamp TIMESTAMP DEFAULT NOW(),
    
    -- Informações do sinal
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10),
    signal_type VARCHAR(50),  -- 'bullish_divergence', 'bearish_divergence', etc
    direction VARCHAR(10),     -- 'BUY' ou 'SELL'
    strength FLOAT,
    
    -- Preços
    entry_price FLOAT,
    stop_loss FLOAT,
    take_profit FLOAT,
    current_price FLOAT,
    
    -- Indicadores
    rsi FLOAT,
    adx FLOAT,
    volume FLOAT,
    volatility FLOAT,
    
    -- Regime de mercado
    market_regime VARCHAR(20),
    regime_confidence FLOAT,
    
    -- Execução
    reason TEXT,
    executed BOOLEAN DEFAULT FALSE,
    execution_reason TEXT,
    trade_id INTEGER,
    
    -- Indexes
    INDEX idx_timestamp (timestamp DESC),
    INDEX idx_symbol (symbol),
    INDEX idx_signal_type (signal_type),
    INDEX idx_executed (executed)
);
```

---

## 🔌 Endpoints API

### GET /api/scanner/history

**Descrição**: Retorna histórico de sinais do banco de dados

**Query Parameters**:
| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| `limit` | int | 50 | Número máximo de sinais |
| `hours` | int | 24 | Janela de tempo em horas |

**Response**:
```json
{
  "success": true,
  "total": 12,
  "period_hours": 24,
  "signals": [
    {
      "signal_id": "scan_a1b2c3d4e5f6",
      "timestamp": "2025-12-22T15:30:00Z",
      "symbol": "BTCUSDT",
      "timeframe": "1h",
      "type": "bullish_divergence",
      "direction": "BUY",
      "strength": 0.65,
      "entry": 42500.0,
      "stop_loss": 41800.0,
      "take_profit": 43500.0,
      "price": 42450.0,
      "rsi": 28.5,
      "adx": 32.0,
      "reason": "RSI Divergence: bullish_divergence | Strength: 0.65",
      "executed": false,
      "execution_reason": null
    },
    // ... mais sinais
  ]
}
```

**Uso no Frontend**:
```javascript
const response = await fetch('http://localhost:3008/api/scanner/history?limit=50&hours=24');
const data = await response.json();
console.log(data.signals);
```

---

## 🚀 Testes e Validação

### 1. Verificar se sinais estão sendo salvos

```bash
# Logs do container
docker logs aitrading-execution-engine --tail 100 | grep "Signal saved"

# Expected output:
# 💾 Signal saved to DB: scan_a1b2c3d4 - BTCUSDT bullish_divergence
```

### 2. Query SQL direta

```bash
docker exec -it aitrading-timescaledb psql -U crypto_user -d crypto_market

# SQL:
SELECT 
    signal_id, 
    timestamp, 
    symbol, 
    signal_type, 
    direction, 
    strength,
    executed
FROM autotrade_signals
WHERE signal_type LIKE '%divergence%'
ORDER BY timestamp DESC
LIMIT 10;
```

### 3. Testar endpoint API

```bash
curl -X GET "http://localhost:3008/api/scanner/history?limit=10&hours=24" | jq '.'
```

### 4. Verificar frontend

1. Abrir http://localhost:8081/scanner
2. Abrir DevTools Console (F12)
3. Verificar log: `[History] Carregados X sinais do banco de dados`
4. Verificar tabela "Histórico de Sinais" populada

---

## 📈 Benefícios da Implementação

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Persistência** | ❌ RAM volátil | ✅ PostgreSQL |
| **Container Restart** | ❌ Sinais perdidos | ✅ Dados preservados |
| **Histórico** | ❌ 24h localStorage | ✅ Ilimitado no banco |
| **Multi-usuário** | ❌ 1 navegador | ✅ Todos usuários |
| **Auditoria** | ❌ Impossível | ✅ SQL queries |
| **Backup** | ❌ Manual | ✅ Automático (banco) |
| **Análise** | ❌ Limitada | ✅ SQL analytics |

---

## 🔧 Próximas Melhorias

### 1. Dashboard de Análise (1 hora)
- Gráficos de sinais por hora/dia
- Win rate por símbolo
- Distribuição de tipos de divergência

### 2. Alertas por Email/Telegram (2 horas)
- Enviar notificação quando novo sinal for detectado
- Configuração de threshold de força mínima

### 3. Export de Sinais (30 min)
- Endpoint para exportar sinais em CSV/Excel
- Filtros avançados (símbolo, período, força)

### 4. Limpeza Automática (30 min)
- Rotina para limpar sinais antigos (>30 dias)
- Manter apenas sinais executados ou relevantes

---

## 📞 Suporte

**Desenvolvedor**: AI Trading Platform
**Data**: 22 de Dezembro de 2025
**Versão**: 1.0

---

## ✅ Checklist de Implementação

- [x] Adicionar `db_pool` ao construtor do scanner
- [x] Criar método `_save_signal_to_db`
- [x] Criar método `get_recent_signals_from_db`
- [x] Modificar `scan_all_symbols` para salvar sinais
- [x] Passar `db_pool` em 3 endpoints do main.py
- [x] Criar endpoint `/api/scanner/history`
- [x] Criar função `loadSignalHistoryFromDB` no frontend
- [x] Atualizar `DOMContentLoaded` para usar banco
- [x] Testar persistência após restart
- [x] Criar documentação completa

**Status**: ✅ **100% COMPLETO**

---

🎉 **Sistema de persistência de sinais implementado com sucesso!**
