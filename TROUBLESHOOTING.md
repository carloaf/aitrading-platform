# AI Trading Platform - Guia de Solução de Problemas

## 📋 Resumo das Correções Implementadas

Este documento registra todas as correções realizadas durante a implementação do projeto AI Trading Platform, servindo como referência para futuras manutenções e troubleshooting.

---

## 🐳 1. Problemas com Docker Compose

### **Problema**: Incompatibilidade Docker Compose v1 vs v2
```
ERROR: The Compose file './docker-compose.yml' is invalid because:
Unsupported config option for services.postgres: 'depends_on'
```

### **Solução**: Atualização da sintaxe de comandos
- **Arquivo afetado**: `Makefile`
- **Mudança**: `docker-compose` → `docker compose`

```makefile
# ANTES
start:
	docker-compose up -d

# DEPOIS  
start:
	docker compose up -d
```

### **Status**: ✅ RESOLVIDO

---

## 🔧 2. Configuração de Variáveis de Ambiente

### **Problema**: Variáveis de ambiente ausentes ou incorretas
```
Error: Environment variable POSTGRES_PASSWORD is not set
```

### **Solução**: Configuração completa do arquivo `.env`
- **Arquivo criado**: `.env`
- **Configurações adicionadas**:

```env
# Database Configuration
POSTGRES_DB=aitrading_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# TimescaleDB Configuration  
TIMESCALE_DB=crypto_market
TIMESCALE_USER=crypto_user
TIMESCALE_PASSWORD=crypto_pass

# JWT Secret
JWT_SECRET=your-super-secure-jwt-secret-key-here-change-in-production

# API Keys (placeholders)
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
POLYGON_API_KEY=your_polygon_key
BRAPI_TOKEN=your_brapi_token

# Grafana
GRAFANA_PASSWORD=admin123
```

### **Status**: ✅ RESOLVIDO

---

## 🗄️ 3. Problemas com TimescaleDB

### **Problema**: Falhas na inicialização e políticas de agregação contínua
```
ERROR: invalid parameter value for add_continuous_aggregate_policy
```

### **Solução**: Correção do script de inicialização
- **Arquivo afetado**: `scripts/init-timescale.sql`
- **Principais correções**:

1. **Políticas de agregação com janelas maiores**:
```sql
-- ANTES (causava erro)
SELECT add_continuous_aggregate_policy('ohlcv_1h',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes');

-- DEPOIS (corrigido)
SELECT add_continuous_aggregate_policy('ohlcv_1h',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '30 minutes', 
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE);
```

2. **Adição de validações `if_not_exists`**:
```sql
SELECT add_retention_policy('market_data', INTERVAL '1 year', if_not_exists => TRUE);
```

### **Status**: ✅ RESOLVIDO

---

## 🌐 4. Problemas com Health Checks

### **Problema**: Containers sempre "unhealthy" apesar de funcionarem
```
STATUS: Up 2 minutes (unhealthy)
```

### **Causa Raiz**: Health checks tentando conectar via IPv6 (`::1`) em vez de IPv4

### **Solução**: Forçar uso de IPv4 nos health checks
- **Arquivos afetados**: 
  - `services/api-gateway/healthcheck.js`
  - `services/market-data-collector/healthcheck.js`

```javascript
// ANTES (problemático)
const options = {
  host: 'localhost',
  port: process.env.API_GATEWAY_PORT || 8080,
  path: '/health',
  timeout: 2000
};

// DEPOIS (corrigido)
const options = {
  hostname: '127.0.0.1', // Use IPv4 explicitly
  port: process.env.API_GATEWAY_PORT || 8080,
  path: '/health', 
  timeout: 2000,
  family: 4 // Force IPv4
};
```

### **Status**: ✅ RESOLVIDO

---

## 🔌 5. Problemas de Mapeamento de Portas

### **Problema**: Inconsistências entre portas do container e configuração
- API Gateway configurado para porta 8080 internamente
- Docker Compose mapeando para porta 3000 externamente

### **Solução**: Padronização das configurações de porta
- **Arquivo afetado**: `docker-compose.yml`

```yaml
# CORREÇÕES APLICADAS
api-gateway:
  environment:
    API_GATEWAY_PORT: 8080  # Porta interna
  ports:
    - "3000:8080"          # Mapeamento correto
    
market-data-collector:
  environment:
    PORT: 3001             # Porta interna
  ports:
    - "3002:3001"          # Novo mapeamento
```

### **Status**: ✅ RESOLVIDO

---

## 🔗 6. Problemas de Conexão entre Serviços

### **Problema**: Serviços não conseguindo conectar aos bancos de dados

### **Solução**: URLs de conexão completas nas variáveis de ambiente
- **Arquivo afetado**: `docker-compose.yml`

```yaml
# ADICIONADO
environment:
  TIMESCALE_URL: postgresql://${TIMESCALE_USER}:${TIMESCALE_PASSWORD}@timescaledb:5432/${TIMESCALE_DB}
  REDIS_URL: redis://redis:6379
```

### **Status**: ✅ RESOLVIDO

---

## 📊 Status Final dos Serviços

### ✅ **Todos os Containers Healthy**

| Serviço | Status | Porta Externa | Porta Interna | Health Check |
|---------|--------|---------------|---------------|--------------|
| API Gateway | ✅ Healthy | 3000 | 8080 | ✅ Funcionando |
| Market Data Collector | ✅ Healthy | 3002 | 3001 | ✅ Funcionando |  
| TimescaleDB | ✅ Healthy | 5433 | 5432 | ✅ Funcionando |
| PostgreSQL | ✅ Healthy | 5432 | 5432 | ✅ Funcionando |
| Redis | ✅ Healthy | 6379 | 6379 | ✅ Funcionando |
| Grafana | ✅ Running | 3001 | 3000 | N/A |

---

## 🧪 Comandos de Verificação

### **Verificar Status Geral**
```bash
docker ps
docker compose logs --tail=20
```

### **Testar Health Checks**
```bash
curl -s http://localhost:3000/health | jq
curl -s http://localhost:3002/health | jq
```

### **Verificar Logs Específicos**
```bash
docker logs aitrading-api-gateway --tail=20
docker logs aitrading-market-data-collector --tail=20
docker logs aitrading-timescaledb --tail=20
```

### **Testar Conexões de Banco**
```bash
# TimescaleDB
docker exec -it aitrading-timescaledb psql -U crypto_user -d crypto_market -c "SELECT version();"

# PostgreSQL
docker exec -it aitrading-postgres psql -U postgres -d aitrading_db -c "SELECT version();"

# Redis
docker exec -it aitrading-redis redis-cli ping
```

---

## 🚀 Próximos Passos Recomendados

1. **Implementar Serviços Restantes**:
   - News Collector (porta 3003)
   - Indicator Calculator (porta 3004)
   - Sentiment Analyzer (porta 3005)
   - Signal Generator (porta 3006)

2. **Monitoramento Avançado**:
   - Configurar dashboards no Grafana
   - Implementar alertas de sistema
   - Logs estruturados com ELK Stack

3. **Segurança**:
   - Implementar SSL/TLS
   - Configurar autenticação OAuth
   - Secrets management com Docker Secrets

4. **Performance**:
   - Implementar cache Redis para dados frequentes
   - Otimizar queries do TimescaleDB
   - Load balancing entre instâncias

---

## 📝 Lições Aprendidas

1. **Docker Compose v2**: Sempre usar `docker compose` (sem hífen)
2. **Health Checks**: Especificar IPv4 explicitamente em ambientes containerizados
3. **TimescaleDB**: Políticas de agregação requerem janelas maiores que o intervalo
4. **Variáveis de Ambiente**: Centralizar todas as configurações no `.env`
5. **Portas**: Manter consistência entre configuração interna e mapeamento externo

---

**Documento criado em**: 4 de Agosto de 2025  
**Última atualização**: 4 de Agosto de 2025  
**Versão do projeto**: 1.0.0  
**Status**: ✅ Todos os problemas resolvidos
