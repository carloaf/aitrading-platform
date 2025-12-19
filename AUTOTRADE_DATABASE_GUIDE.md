# 🚀 GUIA COMPLETO: AutoTrade com Persistência em Banco de Dados

## 📊 Visão Geral

Sistema AutoTrade agora salva **TODOS OS DADOS** no banco TimescaleDB:
- ✅ Todos os sinais detectados (executados ou ignorados)
- ✅ Trades simulados (DRY RUN) e reais (LIVE)
- ✅ Performance por símbolo e tipo de sinal
- ✅ Estatísticas completas de cada sessão
- ✅ Análises agregadas multi-sessão

---

## 📁 Arquivos Criados/Modificados

### ✅ **Novos Arquivos**

1. **`scripts/export_autotrade_data.html`**
   - Ferramenta para exportar dados do localStorage (backup dos 758 sinais atuais)
   - Suporta JSON, CSV e copiar para clipboard
   - Dashboard visual com estatísticas

2. **`scripts/init-autotrade-tables.sql`**
   - Tabelas: `autotrade_signals`, `autotrade_sessions`
   - Views: `autotrade_performance_summary`, `autotrade_performance_by_symbol`, `autotrade_performance_by_signal_type`
   - Funções: `update_autotrade_session_stats()`
   - **JÁ APLICADO NO BANCO** ✅

3. **`services/execution-engine/src/autotrade_manager.py`**
   - Classe `AutoTradeManager` para gerenciar persistência
   - Métodos para salvar/atualizar sinais e trades
   - Métodos para consultar performance e analytics

### 🔄 **Arquivos Modificados**

4. **`services/execution-engine/src/main.py`**
   - Importa `AutoTradeManager`
   - Adiciona lifecycle events (startup/shutdown)
   - Endpoints atualizados:
     - `POST /api/autotrade/start` - Cria sessão no banco
     - `POST /api/autotrade/stop` - Finaliza sessão e atualiza stats
     - `POST /api/autotrade/process-signal` - Salva TODOS os sinais (executados ou não)
   - Novos endpoints de analytics:
     - `GET /api/autotrade/analytics/session/{session_id}`
     - `GET /api/autotrade/analytics/symbols`
     - `GET /api/autotrade/analytics/signal-types`
     - `GET /api/autotrade/sessions`

---

## 🔧 PASSO 1: Backup dos Dados Atuais (localStorage)

### Opção A: Via Browser (Recomendado)

1. Abra o arquivo HTML no navegador:
```bash
cd /home/dellno/worksapace/aitrading-platform
firefox scripts/export_autotrade_data.html
# ou
google-chrome scripts/export_autotrade_data.html
```

2. Clique em **"Carregar Dados"** para ver os 758 sinais e 213 trades

3. Clique em **"Export JSON"** para baixar backup completo

4. Clique em **"Export CSV"** para análise em Excel/Sheets

### Opção B: Via Console do Navegador

1. Abra [http://localhost:3000/scanner-dashboard](http://localhost:3000/scanner-dashboard)

2. Pressione **F12** → Aba **Console**

3. Execute:
```javascript
// Exportar dados
const state = JSON.parse(localStorage.getItem('AUTOTRADE_STATE_KEY'));

// Salvar em arquivo
const dataStr = JSON.stringify(state, null, 2);
const blob = new Blob([dataStr], { type: 'application/json' });
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = `autotrade_backup_${new Date().toISOString().split('T')[0]}.json`;
a.click();
```

---

## 🔄 PASSO 2: Reiniciar o Backend (Aplicar Mudanças)

### Reconstruir e Reiniciar Container

```bash
cd /home/dellno/worksapace/aitrading-platform

# Rebuild do container
docker build -t aitrading-platform-execution-engine services/execution-engine/

# Restart do container
docker restart aitrading-execution-engine

# Verificar logs
docker logs -f aitrading-execution-engine --tail 50
```

### Verificar se Inicializou Corretamente

Você deve ver nos logs:
```
✅ AutoTradeManager conectado ao banco crypto_market
✅ AutoTradeManager inicializado
🚀 Iniciando Execution Engine na porta 8001
```

### Testar Conexão

```bash
curl http://localhost:3008/health
```

---

## 🚀 PASSO 3: Desativar DRY RUN e Ativar Paper Trading Real

### Via Frontend (Scanner Dashboard)

1. Acesse: [http://localhost:3000/scanner-dashboard](http://localhost:3000/scanner-dashboard)

2. Na seção **"AutoTrade - Scanner → Paper Trading"**:
   - Clique no ícone de **engrenagem** (⚙️) para expandir configurações
   - **DESMARQUE** a opção: `🔴 DRY RUN (Simulação)`
   - Agora deve mostrar: `🟢 LIVE (Execução Real)`
   - Ajuste **Capital Inicial** (ex: $10,000)
   - Ajuste **Força Mínima** do sinal (ex: 0.5 = 50%)

3. Clique em **"Iniciar AutoTrade"**

### Via API (Curl)

```bash
curl -X POST "http://localhost:3008/api/autotrade/start" \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": false,
    "min_signal_strength": 0.5,
    "initial_balance": 10000.0,
    "risk_per_trade": 0.02,
    "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
  }'
```

**Resposta Esperada:**
```json
{
  "success": true,
  "message": "AutoTrade iniciado em modo LIVE com 80 símbolos",
  "session_id": "autotrade_20251219_143052",
  "symbols_count": 80,
  "database_enabled": true
}
```

---

## 📊 PASSO 4: Aguardar Sinais e Verificar Persistência

### Monitorar Logs do Backend

```bash
docker logs -f aitrading-execution-engine --tail 100 | grep -E "AutoTrade|DRY RUN|LIVE"
```

### Verificar Sessão Ativa

```bash
curl "http://localhost:3008/api/autotrade/status" | python3 -m json.tool
```

### Quando um Sinal For Detectado

Você verá nos logs algo como:
```
💾 Sinal salvo: sig_a3b4c5d6 - ICPUSDT SELL
🟢 LIVE - Trade executado: ICPUSDT SELL qty=0.123456 @ 45.67
🔗 Sinal sig_a3b4c5d6 vinculado ao trade 123
```

---

## 🗄️ PASSO 5: Consultar Dados no Banco

### Ver Sessões Ativas

```sql
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
  SELECT session_id, mode, started_at, is_active, total_signals_processed, total_trades_executed
  FROM autotrade_sessions
  ORDER BY started_at DESC
  LIMIT 5;
"
```

### Ver Sinais Recentes

```sql
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
  SELECT timestamp, symbol, direction, signal_type, strength, executed, reason
  FROM autotrade_signals
  ORDER BY timestamp DESC
  LIMIT 10;
"
```

### Performance por Símbolo

```sql
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
  SELECT * FROM autotrade_performance_by_symbol
  ORDER BY total_pnl DESC
  LIMIT 10;
"
```

### Performance por Tipo de Sinal

```sql
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "
  SELECT * FROM autotrade_performance_by_signal_type
  ORDER BY total_pnl DESC;
"
```

---

## 📈 PASSO 6: Análise de Performance via API

### Analytics de uma Sessão Específica

```bash
SESSION_ID="autotrade_20251219_143052"  # Use o ID real da sua sessão

curl "http://localhost:3008/api/autotrade/analytics/session/${SESSION_ID}" | python3 -m json.tool
```

**Retorna:**
- Estatísticas gerais (win rate, total P&L, Sharpe, etc)
- Performance por símbolo
- Performance por tipo de sinal
- Últimos 20 sinais

### Performance Agregada por Símbolo (Todas as Sessões)

```bash
curl "http://localhost:3008/api/autotrade/analytics/symbols" | python3 -m json.tool
```

### Performance Agregada por Tipo de Sinal

```bash
curl "http://localhost:3008/api/autotrade/analytics/signal-types" | python3 -m json.tool
```

### Listar Todas as Sessões

```bash
# Todas as sessões
curl "http://localhost:3008/api/autotrade/sessions?limit=20" | python3 -m json.tool

# Apenas sessões ativas
curl "http://localhost:3008/api/autotrade/sessions?active_only=true" | python3 -m json.tool
```

---

## 🛑 PASSO 7: Parar AutoTrade

### Via Frontend

1. No Scanner Dashboard, clique em **"Parar AutoTrade"**

### Via API

```bash
curl -X POST "http://localhost:3008/api/autotrade/stop" | python3 -m json.tool
```

**O que acontece:**
1. Sessão é marcada como `is_active = FALSE`
2. `stopped_at` é registrado
3. Função `update_autotrade_session_stats()` é executada
4. Estatísticas finais são calculadas e salvas

---

## 📊 QUERIES SQL ÚTEIS PARA ANÁLISE

### 1. Resumo Executivo de uma Sessão

```sql
SELECT 
  session_id,
  mode,
  ROUND(EXTRACT(EPOCH FROM (COALESCE(stopped_at, NOW()) - started_at))/3600, 2) as duration_hours,
  total_signals_processed,
  total_trades_executed,
  ROUND((total_trades_executed::DECIMAL / NULLIF(total_signals_processed, 0) * 100), 2) as execution_rate_pct,
  win_rate,
  total_pnl,
  total_pnl_percent,
  sharpe_ratio
FROM autotrade_sessions
WHERE session_id = 'autotrade_20251219_143052';  -- Substitua pelo seu ID
```

### 2. Top 10 Melhores Trades

```sql
SELECT 
  sig.symbol,
  sig.direction,
  sig.signal_type,
  sig.strength,
  t.pnl,
  t.pnl_percent,
  t.timestamp
FROM autotrade_signals sig
JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
WHERE sig.session_id = 'autotrade_20251219_143052'
ORDER BY t.pnl DESC
LIMIT 10;
```

### 3. Taxa de Acerto por Direção (BUY vs SELL)

```sql
SELECT 
  direction,
  COUNT(*) as total_trades,
  SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as wins,
  ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100), 2) as win_rate,
  ROUND(SUM(t.pnl), 2) as total_pnl
FROM autotrade_signals sig
JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
WHERE sig.session_id = 'autotrade_20251219_143052'
GROUP BY direction;
```

### 4. Sinais Ignorados vs Executados

```sql
SELECT 
  executed,
  COUNT(*) as count,
  ROUND((COUNT(*)::DECIMAL / SUM(COUNT(*)) OVER () * 100), 2) as percentage,
  STRING_AGG(DISTINCT reason, ', ') as reasons
FROM autotrade_signals
WHERE session_id = 'autotrade_20251219_143052'
GROUP BY executed;
```

### 5. Correlação Força do Sinal vs Win Rate

```sql
SELECT 
  CASE 
    WHEN sig.strength < 0.3 THEN '0-30%'
    WHEN sig.strength < 0.5 THEN '30-50%'
    WHEN sig.strength < 0.7 THEN '50-70%'
    ELSE '70-100%'
  END as strength_range,
  COUNT(*) as trades,
  ROUND(AVG(sig.strength), 4) as avg_strength,
  SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as wins,
  ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100), 2) as win_rate,
  ROUND(AVG(t.pnl_percent), 2) as avg_pnl_pct
FROM autotrade_signals sig
JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
WHERE sig.session_id = 'autotrade_20251219_143052'
GROUP BY strength_range
ORDER BY avg_strength;
```

---

## 🔍 TROUBLESHOOTING

### Problema: Backend não conecta ao banco

**Sintoma:** Logs mostram `❌ Erro ao conectar ao banco`

**Solução:**
```bash
# Verificar se TimescaleDB está rodando
docker ps | grep timescale

# Verificar variáveis de ambiente
docker exec aitrading-execution-engine env | grep TIMESCALE

# Testar conexão manual
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "SELECT 1;"
```

### Problema: Dados não estão sendo salvos

**Sintoma:** Queries retornam 0 rows mesmo após sinais

**Diagnóstico:**
```bash
# Ver logs do backend
docker logs aitrading-execution-engine --tail 100 | grep -E "Sinal salvo|Erro ao salvar"

# Verificar se tabelas existem
docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market -c "\dt autotrade*"
```

**Solução:**
```bash
# Reaplicar SQL de criação de tabelas
docker exec -i aitrading-timescaledb psql -U crypto_user -d crypto_market < scripts/init-autotrade-tables.sql
```

### Problema: AutoTrade não está processando sinais

**Sintoma:** Status mostra "ativo" mas `total_signals_processed = 0`

**Diagnóstico:**
1. Verificar se Scanner está rodando:
```bash
curl "http://localhost:3008/api/scanner/status"
```

2. Verificar símbolos monitorados:
```bash
curl "http://localhost:3008/api/autotrade/status" | jq '.symbols'
```

3. Ver última execução do scanner:
```bash
curl "http://localhost:3008/api/scanner/last-scan"
```

---

## ✅ CHECKLIST DE SUCESSO

- [ ] **Backup criado**: Dados do localStorage exportados para JSON/CSV
- [ ] **Backend reiniciado**: Container rebuilded com novo código
- [ ] **Conexão OK**: AutoTradeManager conectado ao banco
- [ ] **Sessão criada**: Nova sessão aparece em `autotrade_sessions`
- [ ] **Sinais salvos**: Registros aparecem em `autotrade_signals`
- [ ] **Trades executados**: Registros aparecem em `paper_trading_trades`
- [ ] **Analytics funcionando**: Endpoints retornam dados de performance
- [ ] **Views operacionais**: `autotrade_performance_*` retornam dados

---

## 📋 PRÓXIMAS ETAPAS

Após validar que o sistema está funcionando:

1. **Rodar por 24-48 horas** para coletar dados significativos
2. **Analisar performance** por símbolo e tipo de sinal
3. **Otimizar parâmetros**:
   - `min_signal_strength` (aumentar se muitos falsos positivos)
   - Lista de símbolos (remover os de baixo desempenho)
4. **Criar dashboard visual** (PASSO 6 - em desenvolvimento)
5. **Implementar ML Filter** (PASSO 34 - futuro)

---

## 📞 SUPORTE

Para dúvidas ou problemas, verifique:

1. **Logs do backend**: `docker logs -f aitrading-execution-engine`
2. **Logs do TimescaleDB**: `docker logs -f aitrading-timescaledb`
3. **Documentação**: [PLANO_DE_MELHORAMENTO.md](../PLANO_DE_MELHORAMENTO.md)

---

**🎉 Sistema AutoTrade com Persistência Completa está PRONTO!**

Todos os dados agora são salvos no banco de dados para análise profunda e otimização contínua.
