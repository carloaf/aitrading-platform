# ==========================================
# MAKEFILE PARA AI TRADING PLATFORM
# ==========================================

.PHONY: help setup start stop restart logs clean test build deploy

# Configurações
DOCKER_COMPOSE_FILE = docker-compose.new.yml
ENV_FILE = .env
PROJECT_NAME = aitrading-platform

# Cores para output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

# ==========================================
# COMANDOS PRINCIPAIS
# ==========================================

help: ## 📋 Mostra todos os comandos disponíveis
	@echo "$(BLUE)🚀 AI Trading Platform$(NC)"
	@echo "$(BLUE)========================================$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## 🔧 Configura o ambiente inicial (primeira execução)
	@echo "$(YELLOW)🔧 Configurando ambiente inicial...$(NC)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(YELLOW)📋 Copiando arquivo de configuração...$(NC)"; \
		cp .env.example $(ENV_FILE); \
		echo "$(RED)⚠️  IMPORTANTE: Edite o arquivo .env com suas configurações!$(NC)"; \
	else \
		echo "$(GREEN)✅ Arquivo .env já existe$(NC)"; \
	fi
	@echo "$(YELLOW)📦 Criando diretórios necessários...$(NC)"
	@mkdir -p ai-models/cache logs data/timescale data/mongodb data/redis
	@mkdir -p services/market-data-collector/logs services/api-gateway/logs
	@echo "$(YELLOW)🔨 Building imagens Docker...$(NC)"
	@cd services/market-data-collector && docker build -t $(PROJECT_NAME)/market-data-collector .
	@cd services/api-gateway && docker build -t $(PROJECT_NAME)/api-gateway .
	@echo "$(GREEN)✅ Ambiente configurado!$(NC)"
	@echo "$(BLUE)🔍 Próximos passos:$(NC)"
	@echo "  1. Edite o arquivo .env com suas chaves de API"
	@echo "  2. Execute 'make start' para iniciar os serviços"

start: ## 🚀 Inicia todos os serviços
	@echo "$(YELLOW)🚀 Iniciando serviços...$(NC)"
	@echo "$(YELLOW)🗄️  Iniciando infraestrutura primeiro...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) up -d timescaledb redis mongodb
	@echo "$(YELLOW)⏳ Aguardando serviços ficarem prontos...$(NC)"
	@sleep 15
	@echo "$(YELLOW)🚀 Iniciando aplicações...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) up -d market-data-collector api-gateway
	@echo "$(GREEN)✅ Serviços iniciados!$(NC)"
	@echo "$(BLUE)🌐 Serviços disponíveis:$(NC)"
	@echo "  📊 Market Data: http://localhost:3001/health"
	@echo "  🌐 API Gateway: http://localhost:8080/health"
	@echo "  �️  TimescaleDB: localhost:5433"
	@echo "  � Redis: localhost:6379"
	@echo "  � MongoDB: localhost:27017"

stop: ## 🛑 Para todos os serviços
	@echo "$(YELLOW)🛑 Parando serviços...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) down
	@echo "$(GREEN)✅ Serviços parados!$(NC)"

restart: ## 🔄 Reinicia todos os serviços
	@echo "$(YELLOW)🔄 Reiniciando serviços...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) restart
	@echo "$(GREEN)✅ Serviços reiniciados!$(NC)"

# ==========================================
# COMANDOS DE DESENVOLVIMENTO
# ==========================================

logs: ## 📋 Mostra logs de todos os serviços
	@docker compose -f $(DOCKER_COMPOSE_FILE) logs -f

logs-service: ## 📋 Mostra logs de um serviço específico (uso: make logs-service SERVICE=api-gateway)
	@docker compose -f $(DOCKER_COMPOSE_FILE) logs -f $(SERVICE)

build: ## 🔨 Rebuilda todas as imagens
	@echo "$(YELLOW)🔨 Rebuilding imagens...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) build --no-cache
	@echo "$(GREEN)✅ Imagens rebuilds!$(NC)"

build-service: ## 🔨 Rebuilda uma imagem específica (uso: make build-service SERVICE=api-gateway)
	@echo "$(YELLOW)🔨 Rebuilding $(SERVICE)...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) build --no-cache $(SERVICE)
	@echo "$(GREEN)✅ $(SERVICE) rebuild!$(NC)"

# ==========================================
# COMANDOS DE BANCO DE DADOS
# ==========================================

db-init: ## 🗄️ Inicializa o banco de dados
	@echo "$(YELLOW)🗄️ Inicializando banco de dados...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec timescaledb psql -U crypto_user -d crypto_market -f /docker-entrypoint-initdb.d/init.sql
	@echo "$(GREEN)✅ Banco inicializado!$(NC)"

db-backup: ## 💾 Faz backup do banco de dados
	@echo "$(YELLOW)💾 Fazendo backup...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec timescaledb pg_dump -U crypto_user crypto_market > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ Backup criado!$(NC)"

db-shell: ## 🐚 Abre shell do banco TimescaleDB
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec timescaledb psql -U crypto_user -d crypto_market

redis-shell: ## 🐚 Abre shell do Redis
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec redis redis-cli

mongo-shell: ## 🐚 Abre shell do MongoDB
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec mongodb mongosh -u crypto_user -p crypto_pass crypto_news

# ==========================================
# COMANDOS DE MONITORAMENTO
# ==========================================

status: ## 📊 Mostra status dos serviços
	@echo "$(BLUE)📊 Status dos serviços:$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) ps

health: ## 🏥 Verifica saúde dos serviços
	@echo "$(BLUE)🏥 Verificando saúde dos serviços...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec api-gateway curl -f http://localhost:8080/health || echo "$(RED)❌ API Gateway$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec timescaledb pg_isready -U crypto_user && echo "$(GREEN)✅ TimescaleDB$(NC)" || echo "$(RED)❌ TimescaleDB$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec redis redis-cli ping && echo "$(GREEN)✅ Redis$(NC)" || echo "$(RED)❌ Redis$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec mongodb mongosh --eval "db.runCommand('ping')" && echo "$(GREEN)✅ MongoDB$(NC)" || echo "$(RED)❌ MongoDB$(NC)"

validate: ## 🔍 Executa validação completa da plataforma
	@echo "$(BLUE)🔍 Executando validação completa...$(NC)"
	@./scripts/validate-platform.sh

metrics: ## 📈 Abre Grafana para métricas
	@echo "$(BLUE)📈 Abrindo Grafana...$(NC)"
	@open http://localhost:3001 || xdg-open http://localhost:3001

# ==========================================
# COMANDOS DE TESTE
# ==========================================

test: ## 🧪 Executa todos os testes
	@echo "$(YELLOW)🧪 Executando testes...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec api-gateway npm test
	@docker compose -f $(DOCKER_COMPOSE_FILE) exec market-data-collector npm test
	@echo "$(GREEN)✅ Testes concluídos!$(NC)"

test-integration: ## 🔗 Executa testes de integração
	@echo "$(YELLOW)🔗 Executando testes de integração...$(NC)"
	@./scripts/integration-tests.sh
	@echo "$(GREEN)✅ Testes de integração concluídos!$(NC)"

# ==========================================
# COMANDOS DE LIMPEZA
# ==========================================

clean: ## 🧹 Remove containers, volumes e imagens
	@echo "$(YELLOW)🧹 Limpando ambiente...$(NC)"
	@docker compose -f $(DOCKER_COMPOSE_FILE) down -v --remove-orphans
	@docker system prune -f
	@echo "$(GREEN)✅ Ambiente limpo!$(NC)"

clean-data: ## 🗑️ Remove TODOS os dados (CUIDADO!)
	@echo "$(RED)⚠️  ATENÇÃO: Isso removerá TODOS os dados!$(NC)"
	@read -p "Tem certeza? [y/N] " -r && [[ $$REPLY =~ ^[Yy]$ ]] || exit 1
	@docker compose -f $(DOCKER_COMPOSE_FILE) down -v
	@docker volume prune -f
	@rm -rf data/
	@echo "$(GREEN)✅ Todos os dados removidos!$(NC)"

# ==========================================
# COMANDOS DE DEPLOY
# ==========================================

deploy-staging: ## 🚢 Deploy para staging
	@echo "$(YELLOW)🚢 Deploy para staging...$(NC)"
	@./scripts/deploy-staging.sh
	@echo "$(GREEN)✅ Deploy para staging concluído!$(NC)"

deploy-prod: ## 🏭 Deploy para produção
	@echo "$(YELLOW)🏭 Deploy para produção...$(NC)"
	@./scripts/deploy-production.sh
	@echo "$(GREEN)✅ Deploy para produção concluído!$(NC)"

# ==========================================
# COMANDOS DE UTILITÁRIOS
# ==========================================

env-check: ## ✅ Verifica configurações de ambiente
	@echo "$(BLUE)✅ Verificando configurações...$(NC)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)❌ Arquivo .env não encontrado!$(NC)"; \
		echo "$(YELLOW)Execute 'make setup' primeiro$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ Arquivo .env encontrado$(NC)"
	@if grep -q "your_.*_here" $(ENV_FILE); then \
		echo "$(YELLOW)⚠️  Algumas configurações precisam ser atualizadas no .env$(NC)"; \
	else \
		echo "$(GREEN)✅ Configurações parecem estar ok$(NC)"; \
	fi

install-dev: ## 🛠️ Instala dependências de desenvolvimento
	@echo "$(YELLOW)🛠️ Instalando dependências...$(NC)"
	@npm install
	@cd services/api-gateway && npm install
	@cd services/market-data-collector && npm install
	@cd services/news-collector && npm install
	@cd frontend && npm install
	@echo "$(GREEN)✅ Dependências instaladas!$(NC)"

update: ## 🔄 Atualiza o projeto
	@echo "$(YELLOW)🔄 Atualizando projeto...$(NC)"
	@git pull origin main
	@make build
	@echo "$(GREEN)✅ Projeto atualizado!$(NC)"

# ==========================================
# COMANDO PADRÃO
# ==========================================

# Comando padrão quando executar apenas 'make'
.DEFAULT_GOAL := help
