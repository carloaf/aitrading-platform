#!/bin/bash

echo "=================================================="
echo "🚀 AI TRADING PLATFORM - INICIALIZANDO"
echo "=================================================="
echo ""

# Verificar se o Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker não está rodando. Por favor, inicie o Docker."
    exit 1
fi

echo "✅ Docker está rodando"
echo ""

# Iniciar todos os serviços
echo "🔄 Iniciando serviços..."
docker compose up -d

echo ""
echo "⏳ Aguardando serviços ficarem prontos..."
sleep 15

# Verificar status
echo ""
echo "📊 Status dos Serviços:"
docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=================================================="
echo "✅ SISTEMA PRONTO!"
echo "=================================================="
echo ""
echo "🌐 ACESSE AS INTERFACES:"
echo ""
echo "   📈 Estratégias: http://localhost:8081/strategies"
echo "   🏠 Dashboard:    http://localhost:8081/"
echo "   📊 Backtesting:  http://localhost:8081/backtesting"
echo ""
echo "🔧 API ENDPOINTS:"
echo ""
echo "   📡 API Gateway:      http://localhost:3000"
echo "   🤖 Backtesting:      http://localhost:3007"
echo "   📊 Market Data:      http://localhost:3002"
echo "   📰 News:             http://localhost:3004"
echo "   🧠 Sentiment:        http://localhost:3005"
echo "   🎯 Signals:          http://localhost:3006"
echo ""
echo "=================================================="
echo ""

# Tentar abrir o browser automaticamente
if command -v xdg-open > /dev/null 2>&1; then
    echo "🌐 Abrindo browser..."
    xdg-open "http://localhost:8081/strategies" 2>/dev/null &
elif command -v open > /dev/null 2>&1; then
    echo "🌐 Abrindo browser..."
    open "http://localhost:8081/strategies" 2>/dev/null &
else
    echo "💡 Abra manualmente: http://localhost:8081/strategies"
fi

echo ""
echo "📝 Para ver logs em tempo real:"
echo "   docker compose logs -f frontend"
echo ""
echo "🛑 Para parar tudo:"
echo "   docker compose down"
echo ""
