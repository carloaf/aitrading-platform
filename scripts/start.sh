#!/bin/bash

# ==========================================
# SCRIPT DE INICIALIZAÇÃO - AI TRADING PLATFORM
# ==========================================

set -e

echo "🚀 Inicializando AI Trading Platform..."

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==========================================
# VERIFICAÇÕES INICIAIS
# ==========================================

echo -e "${BLUE}🔍 Verificando pré-requisitos...${NC}"

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado. Instale o Docker primeiro.${NC}"
    exit 1
fi

# Verificar Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose não encontrado. Instale o Docker Compose primeiro.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker e Docker Compose encontrados${NC}"

# ==========================================
# CONFIGURAÇÃO DE AMBIENTE
# ==========================================

echo -e "${BLUE}🔧 Configurando ambiente...${NC}"

# Copiar arquivo de ambiente se não existir
if [ ! -f .env ]; then
    echo -e "${YELLOW}📋 Copiando arquivo de configuração...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️  IMPORTANTE: Edite o arquivo .env com suas configurações!${NC}"
else
    echo -e "${GREEN}✅ Arquivo .env já existe${NC}"
fi

# Criar diretórios necessários
echo -e "${YELLOW}📁 Criando diretórios...${NC}"
mkdir -p {ai-models/cache,logs,data/timescale,data/mongodb,data/redis}
mkdir -p {services/market-data-collector/logs,services/api-gateway/logs}

# ==========================================
# BUILD DAS IMAGENS
# ==========================================

echo -e "${BLUE}🔨 Building imagens Docker...${NC}"

# Market Data Collector
echo -e "${YELLOW}📊 Building Market Data Collector...${NC}"
cd services/market-data-collector
docker build -t aitrading/market-data-collector .
cd ../..

# API Gateway
echo -e "${YELLOW}🌐 Building API Gateway...${NC}"
cd services/api-gateway
docker build -t aitrading/api-gateway .
cd ../..

echo -e "${GREEN}✅ Imagens construídas com sucesso!${NC}"

# ==========================================
# INICIALIZAR SERVIÇOS
# ==========================================

echo -e "${BLUE}🚀 Iniciando serviços...${NC}"

# Iniciar apenas infraestrutura primeiro
echo -e "${YELLOW}🗄️  Iniciando infraestrutura...${NC}"
docker-compose -f docker-compose.new.yml up -d timescaledb redis mongodb

# Aguardar serviços ficarem prontos
echo -e "${YELLOW}⏳ Aguardando serviços de infraestrutura...${NC}"
sleep 30

# Verificar saúde dos serviços
echo -e "${BLUE}🏥 Verificando saúde dos serviços...${NC}"

# TimescaleDB
if docker-compose -f docker-compose.new.yml exec -T timescaledb pg_isready -U crypto_user > /dev/null 2>&1; then
    echo -e "${GREEN}✅ TimescaleDB está pronto${NC}"
else
    echo -e "${RED}❌ TimescaleDB não está respondendo${NC}"
fi

# Redis
if docker-compose -f docker-compose.new.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis está pronto${NC}"
else
    echo -e "${RED}❌ Redis não está respondendo${NC}"
fi

# MongoDB
if docker-compose -f docker-compose.new.yml exec -T mongodb mongosh --eval "db.runCommand('ping')" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MongoDB está pronto${NC}"
else
    echo -e "${RED}❌ MongoDB não está respondendo${NC}"
fi

# Iniciar aplicações
echo -e "${YELLOW}🚀 Iniciando aplicações...${NC}"
docker-compose -f docker-compose.new.yml up -d market-data-collector api-gateway

# ==========================================
# VERIFICAÇÕES FINAIS
# ==========================================

echo -e "${BLUE}🔍 Verificações finais...${NC}"

# Aguardar aplicações ficarem prontas
sleep 15

# Verificar Market Data Collector
if curl -f http://localhost:3001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Market Data Collector está rodando${NC}"
else
    echo -e "${YELLOW}⚠️  Market Data Collector ainda está inicializando...${NC}"
fi

# Verificar API Gateway
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API Gateway está rodando${NC}"
else
    echo -e "${YELLOW}⚠️  API Gateway ainda está inicializando...${NC}"
fi

# ==========================================
# INFORMAÇÕES FINAIS
# ==========================================

echo -e "${GREEN}"
echo "🎉 AI Trading Platform inicializado com sucesso!"
echo "=========================================="
echo -e "${NC}"

echo -e "${BLUE}🌐 Serviços disponíveis:${NC}"
echo "  📊 Market Data Collector: http://localhost:3001/health"
echo "  🌐 API Gateway: http://localhost:8080/health"
echo "  🗄️  TimescaleDB: localhost:5433"
echo "  🔄 Redis: localhost:6379"
echo "  📄 MongoDB: localhost:27017"

echo -e "${BLUE}📋 Comandos úteis:${NC}"
echo "  🔍 Ver logs: docker-compose -f docker-compose.new.yml logs -f"
echo "  📊 Status: docker-compose -f docker-compose.new.yml ps"
echo "  🛑 Parar: docker-compose -f docker-compose.new.yml down"
echo "  🧹 Limpar: docker-compose -f docker-compose.new.yml down -v"

echo -e "${YELLOW}⚠️  Próximos passos:${NC}"
echo "  1. Edite o arquivo .env com suas chaves de API (Binance, NewsAPI, etc.)"
echo "  2. Reinicie os serviços: docker-compose -f docker-compose.new.yml restart"
echo "  3. Teste o login: curl -X POST http://localhost:8080/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"admin123\"}'"

echo -e "${GREEN}🚀 Plataforma pronta para uso!${NC}"
