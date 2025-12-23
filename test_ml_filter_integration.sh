#!/bin/bash
# Test ML Signal Filter Integration - PASSO 24.6 Prioridade 1
# Testa se o ML Filter está rejeitando sinais de baixa qualidade

echo "🧠 TESTE ML SIGNAL FILTER INTEGRATION"
echo "====================================="
echo ""

# 1. Verificar se modelo ML existe
echo "1️⃣  Verificando modelo ML..."
if docker exec aitrading-execution-engine test -f /tmp/ml_signal_filter_model.txt; then
    echo "   ✅ Modelo ML encontrado"
else
    echo "   ⚠️  Modelo ML não encontrado. Rodando sem ML filter."
fi
echo ""

# 2. Testar scanner com ML habilitado
echo "2️⃣  Rodando scanner com ML_FILTER_ENABLED=true..."
docker exec -e ML_FILTER_ENABLED=true \
            -e ML_FILTER_MIN_SCORE=0.6 \
            aitrading-execution-engine \
            python3 -c "
import asyncio
from multi_symbol_scanner import MultiSymbolScanner

async def test():
    scanner = MultiSymbolScanner()
    
    # Inicializar ML Filter
    await scanner.init_ml_filter()
    
    # Rodar scan único
    print('📊 Executando scan...')
    result = await scanner.scan_once()
    
    print(f'✅ Scan completo:')
    print(f'   Sinais detectados: {result[\"active_signals\"]}')
    print(f'   Total scans: {result[\"scan_count\"]}')
    
    # Estatísticas ML
    if scanner.ml_filter_enabled:
        stats = scanner.ml_stats
        print(f'\n🧠 Estatísticas ML:')
        print(f'   Total sinais avaliados: {stats[\"total_signals\"]}')
        print(f'   Aprovados: {stats[\"approved\"]} ({stats[\"approved\"]/max(stats[\"total_signals\"],1)*100:.1f}%)')
        print(f'   Rejeitados: {stats[\"rejected\"]} ({stats[\"rejected\"]/max(stats[\"total_signals\"],1)*100:.1f}%)')
        print(f'   Score médio: {stats[\"avg_score\"]:.3f}')
    else:
        print('⚠️  ML Filter não habilitado')

asyncio.run(test())
"

echo ""
echo "3️⃣  Verificando logs do scanner..."
docker logs aitrading-execution-engine --tail 20 | grep -E "ML (aprovou|rejeitou|Filter)" || echo "   Nenhum log ML encontrado"

echo ""
echo "✅ Teste completo!"
echo ""
echo "📊 RESUMO ESPERADO:"
echo "   - Se modelo ML existe: ~30% dos sinais rejeitados"
echo "   - Sinais aprovados terão ML score >= 0.6"
echo "   - Logs mostrarão '✅ ML aprovou' e '❌ ML rejeitou'"
echo "   - Position multiplier entre 1.0x e 1.6x baseado em confidence"
