FROM python:3.9-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Configurar diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY src/ ./src/
COPY proto/ ./proto/

# Compilar protobuf
RUN python -m grpc_tools.protoc -I./proto --python_out=./src --grpc_python_out=./src ./proto/*.proto

# Criar diretório de logs
RUN mkdir -p logs

# Configurar variáveis de ambiente
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Health check
COPY healthcheck.py .
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python healthcheck.py

# Expor porta
EXPOSE 50051

# Comando para iniciar o serviço
CMD ["python", "src/main.py"]
