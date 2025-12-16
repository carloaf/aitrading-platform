# 📁 Estrutura do Projeto - AI Trading Platform

## 🗂️ Visão Geral da Arquitetura

```
aitrading-platform/
├── 📊 services/                         # Microserviços especializados
│   ├── 🔄 market-data-collector/        # Coleta dados de exchanges
│   ├── 📰 news-collector/               # Coleta notícias e RSS
│   ├── 📈 indicator-calculator/         # Cálculos técnicos (TA-Lib)
│   ├── 🧠 sentiment-analyzer/           # IA para análise de sentimento
│   ├── 🎯 signal-generator/             # Geração de sinais de trading
│   ├── 🌐 api-gateway/                  # Gateway central + autenticação
│   └── 🔔 notification-service/         # Sistema de alertas
│
├── 🎨 frontend/                         # Interface web React/Next.js
│
├── 🤖 ai-models/                        # Modelos de IA locais
│   ├── sentiment/                       # Modelos de sentimento
│   ├── prediction/                      # Modelos preditivos
│   └── cache/                           # Cache de modelos
│
├── 🏗️ infrastructure/                   # Configurações de infraestrutura
│   ├── db/                             # Scripts de banco
│   ├── monitoring/                     # Prometheus + Grafana
│   ├── nginx/                          # Configurações do proxy
│   └── terraform/                      # IaC para deploy
│
├── 📚 shared/                           # Bibliotecas compartilhadas
│   ├── utils/                          # Utilitários comuns
│   ├── types/                          # Definições de tipos
│   └── constants/                      # Constantes globais
│
├── 🧪 tests/                            # Testes automatizados
│   ├── unit/                           # Testes unitários
│   ├── integration/                    # Testes de integração
│   └── e2e/                            # Testes end-to-end
│
├── 📜 scripts/                          # Scripts de automação
│   ├── deploy/                         # Scripts de deploy
│   ├── backup/                         # Scripts de backup
│   └── maintenance/                    # Scripts de manutenção
│
├── 📋 docs/                             # Documentação
│   ├── api/                            # Documentação das APIs
│   ├── deployment/                     # Guias de deploy
│   └── development/                    # Guias de desenvolvimento
│
├── 🔧 docker-compose.new.yml            # Orquestração otimizada
├── 🌍 .env.example                      # Configurações de exemplo
├── 🛠️ Makefile                          # Comandos de automação
└── 📖 README.md                         # Documentação principal
```

## 🔄 Fluxo de Dados

### 1. **Coleta de Dados** 📥
```
Exchanges (Binance, Coinbase) 
    ↓ WebSocket/REST
Market Data Collector 
    ↓ Redis Pub/Sub
TimescaleDB (OHLCV)
```

### 2. **Processamento de Notícias** 📰
```
NewsAPI, RSS Feeds 
    ↓ HTTP
News Collector 
    ↓ Event Queue
MongoDB (Articles) 
    ↓ Processing
Sentiment Analyzer (BERT Local)
```

### 3. **Análise Técnica** 📈
```
TimescaleDB (Market Data) 
    ↓ SQL Queries
Indicator Calculator (Python + TA-Lib)
    ↓ gRPC
TimescaleDB (Technical Indicators)
```

### 4. **Geração de Sinais** 🎯
```
Technical Indicators + Sentiment Analysis 
    ↓ ML Pipeline
Signal Generator 
    ↓ Event-Driven
API Gateway + WebSocket
    ↓ Real-time
Dashboard Frontend
```

## 🛠️ Stack Tecnológica por Componente

### **Backend Services**
| Serviço | Linguagem | Framework | Responsabilidade |
|---------|-----------|-----------|------------------|
| Market Data Collector | Node.js | Express + WebSocket | Coleta em tempo real |
| News Collector | Node.js | Express + Cron | Agregação de notícias |
| Indicator Calculator | Python | FastAPI + TA-Lib | Cálculos matemáticos |
| Sentiment Analyzer | Python | FastAPI + Transformers | IA para sentimento |
| Signal Generator | Python | FastAPI + Scikit-learn | Lógica de sinais |
| API Gateway | Node.js/Go | Express/Gin + JWT | Proxy + auth |
| Notification Service | Node.js | Socket.io | Alertas em tempo real |

### **Bancos de Dados**
| Banco | Tipo | Uso | Otimização |
|-------|------|-----|------------|
| TimescaleDB | SQL (Time Series) | Dados OHLCV + Indicadores | Hypertables + Continuous Aggregates |
| PostgreSQL | SQL (Relacional) | Usuários + Configurações | Índices + Particionamento |
| MongoDB | NoSQL (Documento) | Notícias + Metadados | Índices de texto + Agregações |
| Redis | Cache (In-Memory) | Cache + Pub/Sub | Cluster + Persistência |

### **Frontend**
| Componente | Tecnologia | Responsabilidade |
|------------|------------|------------------|
| Dashboard | React/Next.js | Interface principal |
| Charts | TradingView Widgets | Gráficos financeiros |
| Real-time | Socket.io Client | Dados ao vivo |
| State Management | Redux Toolkit | Estado da aplicação |
| UI Library | Chakra UI / Tailwind | Componentes e styling |

### **IA/ML Local**
| Modelo | Biblioteca | Uso | Performance |
|--------|------------|-----|-------------|
| Sentiment Analysis | Transformers (BERT) | Análise de notícias | GPU opcional |
| Technical Indicators | TA-Lib | Cálculos matemáticos | CPU otimizado |
| Prediction Models | PyTorch/Scikit-learn | Modelos futuros | GPU recomendado |

## 🔄 Comunicação entre Serviços

### **Padrões de Comunicação**
1. **REST APIs**: Operações CRUD e consultas
2. **WebSocket**: Dados em tempo real
3. **Redis Pub/Sub**: Eventos entre serviços
4. **gRPC**: Comunicação de alta performance
5. **Event Queue**: Processamento assíncrono

### **Protocolos de Segurança**
- **JWT**: Autenticação stateless
- **Rate Limiting**: Proteção contra abuso
- **CORS**: Controle de acesso cross-origin
- **HTTPS**: Comunicação criptografada
- **Secret Management**: Variáveis sensíveis

## 📊 Configurações de Performance

### **TimescaleDB Otimizações**
```sql
-- Hypertables para séries temporais
SELECT create_hypertable('market_data', 'timestamp');

-- Continuous Aggregates para consultas rápidas
CREATE MATERIALIZED VIEW market_data_hourly AS ...

-- Políticas de retenção automática
SELECT add_retention_policy('market_data', INTERVAL '2 years');
```

### **Redis Configurações**
```redis
# Cache com TTL automático
SET market:BTCUSDT:price 50000 EX 60

# Pub/Sub para eventos em tempo real
PUBLISH market:updates "{"symbol":"BTCUSDT","price":50000}"
```

### **Node.js Performance**
```javascript
// Clustering para múltiplos cores
const cluster = require('cluster');
const numCPUs = require('os').cpus().length;

// Connection pooling para bancos
const pool = new Pool({ max: 20 });

// WebSocket com otimizações
const io = new Server(server, {
  transports: ['websocket'],
  upgradeTimeout: 30000
});
```

## 🚀 Deploy e Escalabilidade

### **Ambientes**
- **Development**: Docker Compose local
- **Staging**: Docker Swarm ou Kubernetes
- **Production**: Kubernetes com auto-scaling

### **Monitoramento**
- **Prometheus**: Métricas de sistema
- **Grafana**: Dashboards visuais
- **ELK Stack**: Logs centralizados
- **Health Checks**: Verificação automática de serviços

### **Backup e Recuperação**
- **TimescaleDB**: Backup automático diário
- **MongoDB**: Replica set com backup
- **Redis**: Persistência AOF + RDB
- **Código**: Git com CI/CD pipeline

## 🔧 Comandos Úteis

```bash
# Setup inicial
make setup

# Iniciar desenvolvimento
make start

# Ver logs em tempo real
make logs

# Backup do banco
make db-backup

# Deploy para produção
make deploy-prod

# Verificar saúde dos serviços
make health
```

Esta estrutura garante escalabilidade, manutenibilidade e performance para o sistema de análise de criptoativos com IA local.
