FROM python:3.11-slim

LABEL maintainer="AI Trading Platform"
LABEL description="Execution Engine - Paper Trading & Live Trading"

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY src/ ./src/

# Criar usuário não-root
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app

# Healthcheck configurado no docker-compose.yml (não aqui para evitar conflitos)

# Trocar para usuário não-root
USER app

# Porta padrão
EXPOSE 8001

# Comando de execução
CMD ["python", "src/main.py"]
