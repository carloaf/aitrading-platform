#!/bin/bash
###############################################################################
# Script para copiar resultados das simulações corrigidas
###############################################################################

set -e

RESULTS_DIR="results_monte_carlo_v2"
CONTAINER_NAME="aitrading-execution-engine"
CONTAINER_PATH="/app/logs"

echo "📦 Copiando resultados das simulações v2.0..."
echo ""

# Criar diretório se não existir
mkdir -p "$RESULTS_DIR"

# Listar arquivos disponíveis
echo "📂 Arquivos disponíveis no container:"
docker exec $CONTAINER_NAME ls -lh $CONTAINER_PATH/monte_carlo_*.json 2>/dev/null | tail -20

echo ""
echo "🔍 Identificando arquivos mais recentes (últimos 4)..."

# Copiar os 4 arquivos mais recentes (um de cada estratégia)
latest_files=$(docker exec $CONTAINER_NAME bash -c "ls -t $CONTAINER_PATH/monte_carlo_*.json 2>/dev/null | head -4")

if [ -z "$latest_files" ]; then
    echo "❌ Nenhum arquivo encontrado!"
    exit 1
fi

echo "📋 Arquivos a serem copiados:"
echo "$latest_files"
echo ""

count=0
for file in $latest_files; do
    filename=$(basename "$file")
    echo "   Copiando: $filename"
    docker cp "$CONTAINER_NAME:$file" "$RESULTS_DIR/" 2>/dev/null
    count=$((count + 1))
done

echo ""
echo "✅ $count arquivos copiados para $RESULTS_DIR/"
echo ""
echo "📊 Conteúdo do diretório:"
ls -lh "$RESULTS_DIR/"

echo ""
echo "🎯 Próximo passo:"
echo "   python3 scripts/analyze_results.py"
