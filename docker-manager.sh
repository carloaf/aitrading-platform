#!/bin/bash

# Script para gerenciar containers Docker do AI Trading Platform
# Uso: ./docker-manager.sh [comando]

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para printar com cores
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Verificar se .env existe
check_env_file() {
    if [ ! -f .env ]; then
        print_error "Arquivo .env não encontrado!"
        print_info "Criando .env a partir de .env.example..."
        
        if [ -f .env.example ]; then
            cp .env.example .env
            print_success "Arquivo .env criado!"
            print_warning "IMPORTANTE: Edite o arquivo .env com suas configurações antes de continuar"
            exit 1
        else
            print_error "Arquivo .env.example não encontrado!"
            exit 1
        fi
    fi
}

# Verificar instalação do Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker não está instalado!"
        print_info "Instale o Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Detectar qual comando docker compose usar
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    elif command -v $DOCKER_COMPOSE &> /dev/null; then
        DOCKER_COMPOSE="$DOCKER_COMPOSE"
    else
        print_error "Docker Compose não está instalado!"
        print_info "Instale o Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    print_success "Docker e Docker Compose instalados ($DOCKER_COMPOSE)"
}

# Subir apenas os bancos de dados
start_databases() {
    print_info "Subindo apenas os bancos de dados..."
    $DOCKER_COMPOSE up -d postgres redis timescaledb
    
    print_info "Aguardando bancos de dados ficarem prontos..."
    sleep 15
    
    check_health postgres
    check_health redis
    check_health timescaledb
    
    print_success "Bancos de dados iniciados com sucesso!"
}

# Subir todos os serviços
start_all() {
    print_info "Subindo todos os serviços..."
    
    # Primeiro, bancos de dados
    print_info "Fase 1: Bancos de dados"
    $DOCKER_COMPOSE up -d postgres redis timescaledb
    
    print_info "Aguardando bancos ficarem prontos (30s)..."
    sleep 30
    
    # Depois, serviços de backend
    print_info "Fase 2: Serviços de backend"
    $DOCKER_COMPOSE up -d api-gateway market-data-collector backtesting-engine
    
    print_info "Aguardando serviços de backend (20s)..."
    sleep 20
    
    # Serviços adicionais (se existirem)
    print_info "Fase 3: Serviços adicionais (opcional)"
    $DOCKER_COMPOSE up -d indicator-calculator news-collector sentiment-analyzer signal-generator 2>/dev/null || true
    
    # Frontend e monitoramento
    print_info "Fase 4: Frontend e monitoramento (opcional)"
    $DOCKER_COMPOSE up -d frontend grafana 2>/dev/null || true
    
    print_success "Todos os serviços foram iniciados!"
}

# Parar todos os serviços
stop_all() {
    print_info "Parando todos os serviços..."
    $DOCKER_COMPOSE down
    print_success "Todos os serviços foram parados"
}

# Parar e remover volumes
stop_clean() {
    print_warning "ATENÇÃO: Isso irá remover TODOS os dados (volumes)!"
    read -p "Tem certeza? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        print_info "Parando e limpando tudo..."
        $DOCKER_COMPOSE down -v
        print_success "Sistema limpo completamente"
    else
        print_info "Operação cancelada"
    fi
}

# Verificar saúde de um container
check_health() {
    local service=$1
    local max_attempts=30
    local attempt=0
    
    print_info "Verificando saúde de $service..."
    
    while [ $attempt -lt $max_attempts ]; do
        health=$(docker inspect --format='{{.State.Health.Status}}' aitrading-$service 2>/dev/null || echo "no-health")
        
        if [ "$health" = "healthy" ]; then
            print_success "$service está saudável"
            return 0
        elif [ "$health" = "no-health" ]; then
            # Container sem healthcheck, verificar se está rodando
            if docker ps --filter "name=aitrading-$service" --filter "status=running" | grep -q aitrading-$service; then
                print_success "$service está rodando"
                return 0
            fi
        fi
        
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done
    
    print_warning "$service não ficou saudável no tempo esperado"
    return 1
}

# Ver status de todos os containers
status() {
    print_info "Status dos containers:\n"
    $DOCKER_COMPOSE ps
    
    echo ""
    print_info "Saúde dos containers:\n"
    
    for container in postgres redis timescaledb api-gateway market-data-collector backtesting-engine; do
        if docker ps -a --filter "name=aitrading-$container" | grep -q aitrading-$container; then
            health=$(docker inspect --format='{{.State.Health.Status}}' aitrading-$container 2>/dev/null || echo "N/A")
            status=$(docker inspect --format='{{.State.Status}}' aitrading-$container 2>/dev/null)
            
            if [ "$health" = "healthy" ] || [ "$status" = "running" ]; then
                echo -e "  ${GREEN}●${NC} aitrading-$container: $status (health: $health)"
            else
                echo -e "  ${RED}●${NC} aitrading-$container: $status (health: $health)"
            fi
        fi
    done
}

# Ver logs de um serviço
logs() {
    local service=$1
    
    if [ -z "$service" ]; then
        print_error "Especifique um serviço!"
        print_info "Exemplo: ./docker-manager.sh logs backtesting-engine"
        exit 1
    fi
    
    print_info "Exibindo logs de $service (Ctrl+C para sair)..."
    $DOCKER_COMPOSE logs -f $service
}

# Rebuild de um serviço específico
rebuild() {
    local service=$1
    
    if [ -z "$service" ]; then
        print_error "Especifique um serviço!"
        print_info "Exemplo: ./docker-manager.sh rebuild backtesting-engine"
        exit 1
    fi
    
    print_info "Rebuilding $service..."
    $DOCKER_COMPOSE build --no-cache $service
    $DOCKER_COMPOSE up -d $service
    print_success "$service reconstruído e reiniciado"
}

# Executar comando em um container
exec_cmd() {
    local service=$1
    shift
    local cmd="$@"
    
    if [ -z "$service" ]; then
        print_error "Especifique um serviço!"
        print_info "Exemplo: ./docker-manager.sh exec backtesting-engine bash"
        exit 1
    fi
    
    print_info "Executando comando em $service..."
    $DOCKER_COMPOSE exec $service $cmd
}

# Testar backtesting engine
test_backtesting() {
    print_info "Testando Backtesting Engine..."
    
    if ! docker ps --filter "name=aitrading-backtesting-engine" | grep -q aitrading-backtesting-engine; then
        print_error "Backtesting Engine não está rodando!"
        exit 1
    fi
    
    print_info "Executando testes dentro do container..."
    $DOCKER_COMPOSE exec backtesting-engine python test_all_strategies.py
}

# Instalar dependências no container
install_deps() {
    local service=$1
    
    if [ -z "$service" ]; then
        print_error "Especifique um serviço!"
        print_info "Exemplo: ./docker-manager.sh install-deps backtesting-engine"
        exit 1
    fi
    
    print_info "Instalando dependências em $service..."
    
    if [ "$service" = "backtesting-engine" ] || [ "$service" = "indicator-calculator" ] || [ "$service" = "news-collector" ]; then
        $DOCKER_COMPOSE exec $service pip install -r requirements.txt
    elif [ "$service" = "api-gateway" ] || [ "$service" = "market-data-collector" ]; then
        $DOCKER_COMPOSE exec $service npm install
    else
        print_warning "Tipo de serviço desconhecido, tentando npm install..."
        $DOCKER_COMPOSE exec $service npm install || print_error "Falhou!"
    fi
    
    print_success "Dependências instaladas!"
}

# Menu de ajuda
show_help() {
    cat << EOF
${BLUE}╔══════════════════════════════════════════════════════════════╗
║         AI Trading Platform - Docker Manager                 ║
╚══════════════════════════════════════════════════════════════╝${NC}

${GREEN}Comandos Principais:${NC}

  ${YELLOW}start-db${NC}          Inicia apenas os bancos de dados
  ${YELLOW}start${NC}             Inicia todos os serviços
  ${YELLOW}stop${NC}              Para todos os serviços
  ${YELLOW}stop-clean${NC}        Para e remove todos os volumes (CUIDADO!)
  ${YELLOW}restart${NC}           Reinicia todos os serviços
  
${GREEN}Monitoramento:${NC}

  ${YELLOW}status${NC}            Mostra status de todos os containers
  ${YELLOW}logs [serviço]${NC}   Mostra logs de um serviço específico
  ${YELLOW}health${NC}            Verifica saúde de todos os serviços

${GREEN}Desenvolvimento:${NC}

  ${YELLOW}rebuild [serviço]${NC} Reconstrói um serviço específico
  ${YELLOW}exec [serviço] [cmd]${NC} Executa comando em um container
  ${YELLOW}install-deps [serv]${NC} Instala dependências em um serviço
  ${YELLOW}test-backtest${NC}     Testa o backtesting engine

${GREEN}Exemplos:${NC}

  ./docker-manager.sh start
  ./docker-manager.sh logs backtesting-engine
  ./docker-manager.sh rebuild backtesting-engine
  ./docker-manager.sh exec backtesting-engine bash
  ./docker-manager.sh test-backtest

${GREEN}Serviços disponíveis:${NC}

  • postgres, redis, timescaledb (bancos)
  • api-gateway (gateway principal)
  • market-data-collector (coleta dados)
  • backtesting-engine (backtesting)
  • indicator-calculator (indicadores)
  • news-collector (notícias)
  • sentiment-analyzer (sentimentos)
  • signal-generator (sinais)
  • frontend (interface web)
  • grafana (monitoramento)

EOF
}

# Main
main() {
    local command=$1
    shift
    
    # Header
    echo ""
    print_info "AI Trading Platform - Docker Manager"
    echo ""
    
    check_docker
    check_env_file
    
    case $command in
        start-db|startdb)
            start_databases
            ;;
        start)
            start_all
            status
            ;;
        stop)
            stop_all
            ;;
        stop-clean|clean)
            stop_clean
            ;;
        restart)
            stop_all
            sleep 3
            start_all
            ;;
        status)
            status
            ;;
        logs)
            logs "$@"
            ;;
        rebuild)
            rebuild "$@"
            ;;
        exec)
            exec_cmd "$@"
            ;;
        install-deps)
            install_deps "$@"
            ;;
        test-backtest|test)
            test_backtesting
            ;;
        health)
            for service in postgres redis timescaledb api-gateway market-data-collector backtesting-engine; do
                check_health $service || true
            done
            ;;
        help|--help|-h|"")
            show_help
            ;;
        *)
            print_error "Comando desconhecido: $command"
            show_help
            exit 1
            ;;
    esac
}

# Executar
main "$@"
