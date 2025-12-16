#!/bin/bash

# ================================
# AI Trading Platform - Script de Validação
# ================================
# Este script verifica se todas as correções implementadas
# estão funcionando corretamente.

set -e

echo "🔍 Iniciando validação da plataforma AI Trading..."
echo "=================================================="
echo

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para print colorido
print_status() {
    if [ "$2" = "OK" ]; then
        echo -e "${GREEN}✅ $1${NC}"
    elif [ "$2" = "WARN" ]; then
        echo -e "${YELLOW}⚠️  $1${NC}"
    elif [ "$2" = "FAIL" ]; then
        echo -e "${RED}❌ $1${NC}"
    else
        echo -e "${BLUE}ℹ️  $1${NC}"
    fi
}

# 1. Verificar Docker Compose v2
echo "1. Verificando Docker Compose v2..."
if command -v "docker" &> /dev/null; then
    DOCKER_COMPOSE_VERSION=$(docker compose version 2>/dev/null || echo "not found")
    if [[ $DOCKER_COMPOSE_VERSION == *"Docker Compose version"* ]]; then
        print_status "Docker Compose v2 disponível" "OK"
    else
        print_status "Docker Compose v2 NÃO encontrado - usar 'docker compose' em vez de 'docker-compose'" "FAIL"
        exit 1
    fi
else
    print_status "Docker não encontrado" "FAIL"
    exit 1
fi

# 2. Verificar se containers estão rodando
echo
echo "2. Verificando status dos containers..."
CONTAINERS=("aitrading-api-gateway" "aitrading-market-data-collector" "aitrading-timescaledb" "aitrading-postgres" "aitrading-redis" "aitrading-grafana")

for container in "${CONTAINERS[@]}"; do
    if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
        STATUS=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep "$container" | awk '{print $2}')
        if [[ $STATUS == *"healthy"* ]] || [[ $STATUS == "Up" ]]; then
            print_status "Container $container está rodando ($STATUS)" "OK"
        else
            print_status "Container $container com problema: $STATUS" "WARN"
        fi
    else
        print_status "Container $container NÃO está rodando" "FAIL"
    fi
done

# 3. Verificar health checks
echo
echo "3. Testando endpoints de health check..."

# API Gateway
if curl -s -f http://localhost:3000/health > /dev/null; then
    HEALTH_STATUS=$(curl -s http://localhost:3000/health | jq -r '.status' 2>/dev/null || echo "unknown")
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        print_status "API Gateway health check" "OK"
    else
        print_status "API Gateway health check retornou: $HEALTH_STATUS" "WARN"
    fi
else
    print_status "API Gateway health check falhou" "FAIL"
fi

# Market Data Collector
if curl -s -f http://localhost:3002/health > /dev/null; then
    HEALTH_STATUS=$(curl -s http://localhost:3002/health | jq -r '.status' 2>/dev/null || echo "unknown")
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        print_status "Market Data Collector health check" "OK"
    else
        print_status "Market Data Collector health check retornou: $HEALTH_STATUS" "WARN"
    fi
else
    print_status "Market Data Collector health check falhou" "FAIL"
fi

# 4. Verificar conectividade dos bancos
echo
echo "4. Testando conectividade dos bancos de dados..."

# TimescaleDB
if docker exec aitrading-timescaledb pg_isready -U crypto_user > /dev/null 2>&1; then
    print_status "TimescaleDB conectividade" "OK"
else
    print_status "TimescaleDB conectividade falhou" "FAIL"
fi

# PostgreSQL
if docker exec aitrading-postgres pg_isready -U postgres > /dev/null 2>&1; then
    print_status "PostgreSQL conectividade" "OK"
else
    print_status "PostgreSQL conectividade falhou" "FAIL"
fi

# Redis
if docker exec aitrading-redis redis-cli ping | grep -q "PONG"; then
    print_status "Redis conectividade" "OK"
else
    print_status "Redis conectividade falhou" "FAIL"
fi

# 5. Verificar se dados estão sendo coletados
echo
echo "5. Verificando coleta de dados..."

# Verificar se há dados recentes no TimescaleDB
RECENT_DATA=$(docker exec aitrading-timescaledb psql -U crypto_user -d crypto_market \
    -t -c "SELECT COUNT(*) FROM market_data_realtime WHERE timestamp > NOW() - INTERVAL '5 minutes';" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$RECENT_DATA" -gt 0 ]; then
    print_status "Dados sendo coletados ($RECENT_DATA registros nos últimos 5 min)" "OK"
else
    print_status "Nenhum dado recente encontrado (pode ser normal se recém-iniciado)" "WARN"
fi

# 6. Verificar logs por erros críticos
echo
echo "6. Verificando logs por erros críticos..."

ERROR_COUNT=$(docker compose logs --tail=100 2>/dev/null | grep -i "error\|exception\|failed" | grep -v "health check" | wc -l || echo "0")

if [ "$ERROR_COUNT" -eq 0 ]; then
    print_status "Nenhum erro crítico encontrado nos logs" "OK"
else
    print_status "$ERROR_COUNT erros encontrados nos logs - verificar 'docker compose logs'" "WARN"
fi

# 7. Verificar WebSockets
echo
echo "7. Verificando WebSockets do Market Data Collector..."

WS_COUNT=$(curl -s http://localhost:3002/health 2>/dev/null | jq -r '.websockets' 2>/dev/null || echo "0")

if [ "$WS_COUNT" -gt 0 ]; then
    print_status "WebSockets ativos: $WS_COUNT" "OK"
else
    print_status "Nenhum WebSocket ativo" "WARN"
fi

# 8. Verificar arquivo .env
echo
echo "8. Verificando configurações..."

if [ -f ".env" ]; then
    print_status "Arquivo .env existe" "OK"
    
    # Verificar se variáveis críticas estão definidas
    CRITICAL_VARS=("POSTGRES_PASSWORD" "TIMESCALE_PASSWORD" "JWT_SECRET")
    for var in "${CRITICAL_VARS[@]}"; do
        if grep -q "^${var}=" .env; then
            print_status "Variável $var definida" "OK"
        else
            print_status "Variável $var NÃO definida em .env" "WARN"
        fi
    done
else
    print_status "Arquivo .env NÃO encontrado" "FAIL"
fi

# Resumo final
echo
echo "=================================================="
echo "🎯 Resumo da Validação:"
echo "=================================================="

# Contar sucessos e falhas
SUCCESS_COUNT=$(docker ps --format "{{.Names}}" | grep "aitrading-" | wc -l)
TOTAL_CONTAINERS=6

if [ "$SUCCESS_COUNT" -eq "$TOTAL_CONTAINERS" ]; then
    print_status "Todos os $TOTAL_CONTAINERS containers estão rodando" "OK"
    echo
    echo -e "${GREEN}🎉 Plataforma AI Trading está funcionando corretamente!${NC}"
    echo
    echo "📊 Endpoints disponíveis:"
    echo "  • API Gateway: http://localhost:3000"
    echo "  • Market Data: http://localhost:3002"  
    echo "  • Grafana: http://localhost:3001"
    echo
    echo "📚 Documentação:"
    echo "  • README.md - Instruções gerais"
    echo "  • TROUBLESHOOTING.md - Soluções de problemas"
    echo "  • ARCHITECTURE.md - Documentação técnica"
    echo
else
    print_status "Apenas $SUCCESS_COUNT de $TOTAL_CONTAINERS containers rodando" "WARN"
    echo
    echo -e "${YELLOW}⚠️  Alguns problemas encontrados. Verificar logs com:${NC}"
    echo "   docker compose logs --tail=50"
    echo
fi

echo "Validação concluída em $(date)"
echo "=================================================="
