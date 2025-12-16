FROM python:3.9-slim

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro para aproveitar cache do Docker
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Baixar dados NLTK necessários
RUN python -c "import nltk; nltk.download('vader_lexicon', quiet=True); nltk.download('punkt', quiet=True)"

# Baixar modelo RoBERTa (cache para acelerar inicialização)
RUN python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
    model_name='cardiffnlp/twitter-roberta-base-sentiment-latest'; \
    print('Downloading tokenizer...'); \
    AutoTokenizer.from_pretrained(model_name); \
    print('Downloading model...'); \
    AutoModelForSequenceClassification.from_pretrained(model_name); \
    print('Model cache created successfully')"

# Copiar código fonte
COPY src/ ./src/

# Criar usuário não-root
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python src/healthcheck.py || exit 1

# Comando para iniciar o serviço
CMD ["python", "src/main.py"]
