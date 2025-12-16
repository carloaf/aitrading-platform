# 🧪 GUIA COMPLETO DE TESTES - Otimização de Parâmetros

## 📋 Índice
1. [Testes Rápidos (5 min)](#testes-rápidos)
2. [Testes Intermediários (15-30 min)](#testes-intermediários)
3. [Testes Completos (1-2h)](#testes-completos)
4. [Análise de Resultados](#análise-de-resultados)
5. [Troubleshooting](#troubleshooting)

---

## 🚀 TESTES RÁPIDOS (5 minutos)

### Teste 1: Verificar se API está respondendo
```bash
# Teste simples de health check
curl http://localhost:3007/health

# Verificar estratégias disponíveis
curl http://localhost:3007/strategies | jq '.'
```

**Resultado esperado:** Lista com 9 estratégias disponíveis

---

### Teste 2: Backtest simples (baseline)
```bash
# Executar backtest normal da estratégia Momentum
curl -X POST "http://localhost:3007/strategies/momentum/backtest?symbol=BTCUSDT&start_date=2023-06-01&end_date=2023-12-31" \
  -H "Content-Type: application/json" \
  -s | jq '.total_return, .total_trades, .win_rate'
```

**Resultado esperado:**
```json
28.708316746082836
19
26.31578947368421
```

**✅ SUCESSO**: Se você ver retorno positivo (~28%) e 19 trades
**❌ ERRO**: Se retornar erro 404 ou 500

---

### Teste 3: Otimização rápida (período curto, 1 split)
```bash
# Teste com apenas 3 meses e 1 split para ser rápido
curl -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=BTCUSDT&start_date=2023-10-01&end_date=2023-12-31&n_splits=1&train_ratio=0.7" \
  -H "Content-Type: application/json" \
  -s | python3 -m json.tool > test_optimization_quick.json

# Ver resultados
cat test_optimization_quick.json | jq '.best_parameters, .best_performance.out_sample_return'
```

**Resultado esperado:**
- `best_parameters`: Dicionário com parâmetros otimizados
- `out_sample_return`: Valor numérico (pode ser positivo ou negativo)

**⚠️ IMPORTANTE**: Se retornar `-999.0`, significa que não houve trades suficientes. Continue para Teste 4.

---

### Teste 4: Otimização com período mais longo
```bash
# Usar 1 ano completo com 2 splits
curl -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=BTCUSDT&start_date=2023-01-01&end_date=2023-12-31&n_splits=2&train_ratio=0.75" \
  -H "Content-Type: application/json" \
  -s | python3 -m json.tool > test_optimization_1year.json

# Ver resultados principais
echo "=== MELHORES PARÂMETROS ==="
cat test_optimization_1year.json | jq '.best_parameters'

echo -e "\n=== PERFORMANCE ==="
cat test_optimization_1year.json | jq '.best_performance'

echo -e "\n=== TOTAL TESTADO ==="
cat test_optimization_1year.json | jq '.total_combinations_tested'
```

**Resultado esperado:**
- `total_combinations_tested`: 16 (4 valores de roc_period × 4 valores de threshold)
- `best_performance.out_sample_return`: Valor válido (não -999)
- `best_performance.robustness_score`: > 0

---

## 🔬 TESTES INTERMEDIÁRIOS (15-30 minutos)

### Teste 5: Otimizar estratégia MACD+RSI (mais parâmetros)
```bash
# Estratégia com 3 parâmetros = mais combinações
curl -X POST "http://localhost:3007/strategies/macd_rsi_combo/optimize?symbol=BTCUSDT&start_date=2023-01-01&end_date=2023-12-31&n_splits=2&train_ratio=0.75" \
  -H "Content-Type: application/json" \
  -s | python3 -m json.tool > test_macd_rsi_optimization.json

# Analisar resultados
echo "=== TOP 5 COMBINAÇÕES ==="
cat test_macd_rsi_optimization.json | jq '.top_5_results[] | {params: .parameters, return: .out_sample_return, sharpe: .out_sample_sharpe, trades: .out_sample_trades}'
```

**Resultado esperado:**
- `total_combinations_tested`: 27 (3×3×3)
- Top 5 com diferentes parâmetros e performances

---

### Teste 6: Comparar múltiplas estratégias
```bash
# Script para otimizar e comparar 3 estratégias
cat > compare_strategies.sh << 'EOF'
#!/bin/bash

SYMBOL="BTCUSDT"
START="2023-01-01"
END="2023-12-31"
SPLITS=2

echo "🔄 Otimizando 3 estratégias..."

# 1. Momentum
echo "1️⃣ Momentum..."
curl -s -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=$SYMBOL&start_date=$START&end_date=$END&n_splits=$SPLITS" \
  | jq '{strategy: "Momentum", best_return: .best_performance.out_sample_return, best_sharpe: .best_performance.out_sample_sharpe, params: .best_parameters}' \
  > momentum_result.json

# 2. MACD+RSI
echo "2️⃣ MACD+RSI..."
curl -s -X POST "http://localhost:3007/strategies/macd_rsi_combo/optimize?symbol=$SYMBOL&start_date=$START&end_date=$END&n_splits=$SPLITS" \
  | jq '{strategy: "MACD+RSI", best_return: .best_performance.out_sample_return, best_sharpe: .best_performance.out_sample_sharpe, params: .best_parameters}' \
  > macd_rsi_result.json

# 3. Volatility Breakout
echo "3️⃣ Volatility Breakout..."
curl -s -X POST "http://localhost:3007/strategies/volatility_breakout/optimize?symbol=$SYMBOL&start_date=$START&end_date=$END&n_splits=$SPLITS" \
  | jq '{strategy: "Volatility Breakout", best_return: .best_performance.out_sample_return, best_sharpe: .best_performance.out_sample_sharpe, params: .best_parameters}' \
  > volatility_result.json

# Combinar resultados
echo -e "\n📊 COMPARAÇÃO DE RESULTADOS"
echo "============================"
jq -s '.' momentum_result.json macd_rsi_result.json volatility_result.json | jq '.[] | "Estratégia: \(.strategy)\nRetorno: \(.best_return)%\nSharpe: \(.best_sharpe)\n"'

# Limpar
rm momentum_result.json macd_rsi_result.json volatility_result.json

echo "✅ Comparação concluída!"
EOF

chmod +x compare_strategies.sh
./compare_strategies.sh
```

---

### Teste 7: Validar Walk-Forward Analysis
```bash
# Testar com diferentes números de splits
for splits in 1 2 3; do
  echo "=== Testando com $splits splits ==="
  
  curl -s -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=BTCUSDT&start_date=2023-01-01&end_date=2023-12-31&n_splits=$splits&train_ratio=0.75" \
    | jq "{splits: $splits, best_return: .best_performance.out_sample_return, robustness: .best_performance.robustness_score}" \
    > walkforward_${splits}splits.json
  
  cat walkforward_${splits}splits.json
  echo ""
done

# Comparar resultados
echo "=== COMPARAÇÃO DE SPLITS ==="
jq -s '.' walkforward_*.json | jq '.[] | "Splits: \(.splits) | Return: \(.best_return)% | Robustness: \(.robustness)"'

rm walkforward_*.json
```

**Análise esperada:**
- Com **1 split**: Menor robustez (pode ter overfitting)
- Com **2-3 splits**: Melhor validação out-of-sample
- Com **4+ splits**: Pode não ter dados suficientes por split

---

### Teste 8: Testar diferentes símbolos
```bash
# Testar com diferentes pares de crypto
for symbol in BTCUSDT ETHUSDT BNBUSDT; do
  echo "=== Otimizando $symbol ==="
  
  curl -s -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=$symbol&start_date=2023-06-01&end_date=2023-12-31&n_splits=2" \
    | jq "{symbol: \"$symbol\", best_return: .best_performance.out_sample_return, best_params: .best_parameters}" \
    > optimization_${symbol}.json
  
  cat optimization_${symbol}.json | jq '.'
  echo ""
done

echo "=== COMPARAÇÃO ENTRE SÍMBOLOS ==="
jq -s '.' optimization_*.json | jq '.[] | "Símbolo: \(.symbol) | Retorno: \(.best_return)% | Parâmetros: \(.best_params)"'

rm optimization_*.json
```

---

## 🎯 TESTES COMPLETOS (1-2 horas)

### Teste 9: Otimização batch de todas as estratégias
```bash
# Usar o script bash criado anteriormente
cd /home/dellno/worksapace/aitrading-platform

# Executar otimização completa
./optimize_strategies.sh BTCUSDT 2023-01-01 2023-12-31

# Ver relatório
cat optimization_results/optimization_summary.txt
```

---

### Teste 10: Grid Search detalhado com parâmetros customizados
```bash
# Criar teste customizado via CLI dentro do container
docker exec -it aitrading-backtesting-engine bash

# Dentro do container:
cd /app

# Executar otimização via CLI
python src/run_optimization.py \
  --strategy momentum \
  --symbol BTCUSDT \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --splits 3 \
  --train-ratio 0.75 \
  --output /app/optimization_cli_test.json

# Ver resultados
cat /app/optimization_cli_test.json | python -m json.tool

# Sair do container
exit
```

---

### Teste 11: Stress Test - Múltiplas otimizações simultâneas
```bash
# Criar script de stress test
cat > stress_test_optimization.sh << 'EOF'
#!/bin/bash

echo "🔥 STRESS TEST - 5 otimizações simultâneas"

# Executar 5 otimizações em paralelo
for i in {1..5}; do
  (
    echo "Thread $i iniciado..."
    curl -s -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=BTCUSDT&start_date=2023-06-01&end_date=2023-12-31&n_splits=2" \
      > stress_test_result_$i.json
    echo "Thread $i concluído"
  ) &
done

# Aguardar todos finalizarem
wait

echo "✅ Stress test concluído!"

# Verificar resultados
for i in {1..5}; do
  echo "=== Resultado Thread $i ==="
  cat stress_test_result_$i.json | jq '.best_performance.out_sample_return' 2>/dev/null || echo "ERRO"
done

rm stress_test_result_*.json
EOF

chmod +x stress_test_optimization.sh
./stress_test_optimization.sh
```

---

## 📊 ANÁLISE DE RESULTADOS

### Como interpretar métricas de otimização

```python
# Criar script de análise
cat > analyze_optimization.py << 'EOF'
import json
import sys

def analyze_optimization_result(filename):
    with open(filename, 'r') as f:
        data = json.load(f)
    
    print("=" * 60)
    print(f"ANÁLISE: {data['strategy_name'].upper()}")
    print("=" * 60)
    
    # Performance principal
    perf = data['best_performance']
    print(f"\n📈 PERFORMANCE OUT-OF-SAMPLE:")
    print(f"   Retorno: {perf['out_sample_return']:.2f}%")
    print(f"   Sharpe Ratio: {perf['out_sample_sharpe']:.2f}")
    print(f"   Win Rate: {perf['out_sample_win_rate']:.2f}%")
    print(f"   Max Drawdown: {perf['max_drawdown']:.2f}%")
    print(f"   Robustness Score: {perf['robustness_score']:.2f}")
    
    # Melhores parâmetros
    print(f"\n🎯 MELHORES PARÂMETROS:")
    for key, value in data['best_parameters'].items():
        print(f"   {key}: {value}")
    
    # Análise top 5
    print(f"\n🏆 TOP 5 COMBINAÇÕES:")
    for i, result in enumerate(data['top_5_results'][:5], 1):
        print(f"\n   #{i}")
        print(f"   Retorno Out: {result['out_sample_return']:.2f}%")
        print(f"   Trades Out: {result['out_sample_trades']}")
        print(f"   Parâmetros: {result['parameters']}")
    
    # Validação
    print(f"\n✅ VALIDAÇÃO:")
    if perf['out_sample_return'] > 0:
        print("   ✓ Retorno positivo em out-of-sample")
    else:
        print("   ✗ Retorno negativo - revisar parâmetros")
    
    if perf['robustness_score'] > 0.7:
        print("   ✓ Boa robustez (>0.7)")
    elif perf['robustness_score'] > 0:
        print("   ⚠ Robustez moderada")
    else:
        print("   ✗ Baixa robustez - possível overfitting")
    
    if perf['out_sample_win_rate'] > 40:
        print("   ✓ Win rate aceitável (>40%)")
    else:
        print("   ⚠ Win rate baixo (<40%)")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_optimization_result(sys.argv[1])
    else:
        print("Uso: python analyze_optimization.py <arquivo.json>")
EOF

# Usar o script
python3 analyze_optimization.py test_optimization_1year.json
```

---

### Métricas importantes

| Métrica | Valor Bom | Valor Ruim | Interpretação |
|---------|-----------|------------|---------------|
| **Out-Sample Return** | > 10% | < 0% | Retorno no período de teste |
| **Sharpe Ratio** | > 1.0 | < 0.5 | Retorno ajustado por risco |
| **Robustness Score** | > 0.7 | < 0.3 | Consistência entre in/out sample |
| **Win Rate** | > 40% | < 30% | Porcentagem de trades vencedores |
| **Max Drawdown** | < 20% | > 50% | Maior queda do capital |
| **Out-Sample Trades** | > 10 | < 5 | Número de trades no teste |

---

## 🐛 TROUBLESHOOTING

### Problema 1: Retorno `-999.0`
```bash
# Sintoma: out_sample_return = -999.0, out_sample_trades = 0

# CAUSA: Dados insuficientes ou período muito curto para Walk-Forward

# SOLUÇÃO 1: Aumentar período
curl -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=BTCUSDT&start_date=2022-01-01&end_date=2023-12-31&n_splits=2"

# SOLUÇÃO 2: Reduzir número de splits
curl -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=BTCUSDT&start_date=2023-01-01&end_date=2023-12-31&n_splits=1"

# SOLUÇÃO 3: Aumentar train_ratio
curl -X POST "http://localhost:3007/strategies/momentum/optimize?symbol=BTCUSDT&start_date=2023-01-01&end_date=2023-12-31&n_splits=2&train_ratio=0.85"
```

---

### Problema 2: Timeout ou Demora Excessiva
```bash
# Sintoma: Requisição demora mais de 5 minutos

# CAUSA: Muitas combinações de parâmetros

# VERIFICAR quantas combinações:
# momentum: 4 × 4 = 16 combinações (rápido)
# macd_rsi_combo: 3 × 3 × 3 = 27 combinações (médio)
# multi_timeframe: 3 × 3 = 9 combinações (rápido)

# SOLUÇÃO: Verificar logs do container
docker logs aitrading-backtesting-engine --tail 50 | grep -E "(Testando|combinação)"
```

---

### Problema 3: Erro de Coluna não encontrada
```bash
# Sintoma: "Coluna necessária 'Open' não encontrada no DataFrame"

# VERIFICAR logs
docker logs aitrading-backtesting-engine --tail 30 | grep "Coluna"

# SOLUÇÃO: Já foi corrigido, mas se persistir, verificar data provider
docker exec -it aitrading-backtesting-engine python -c "
from src.data_providers import get_market_data
data = get_market_data('BTCUSDT', '2023-10-01', '2023-10-31')
print(data.columns.tolist())
"
```

---

### Problema 4: Container não responde
```bash
# Verificar status
docker ps | grep backtesting

# Verificar logs de erro
docker logs aitrading-backtesting-engine --tail 100 | grep ERROR

# Reiniciar container
docker compose restart backtesting-engine

# Aguardar ficar healthy
sleep 15
docker ps | grep backtesting
```

---

## 📝 CHECKLIST DE VALIDAÇÃO

Antes de considerar a otimização bem-sucedida, verificar:

- [ ] **Backtest normal funciona** (retorno ~28% para Momentum)
- [ ] **Otimização retorna resultados válidos** (não -999)
- [ ] **Robustness score > 0.5** (evitar overfitting)
- [ ] **Out-sample trades > 5** (validação estatística)
- [ ] **Top 5 resultados são diferentes** (diversidade)
- [ ] **Parâmetros fazem sentido** (não são extremos)
- [ ] **Performance similar entre símbolos** (BTC, ETH, BNB)
- [ ] **Walk-Forward com 2-3 splits valida** (consistência)

---

## 🎓 PRÓXIMOS PASSOS

### Após validar a otimização:

1. **Aplicar melhores parâmetros**:
   ```python
   # Atualizar estratégia com parâmetros otimizados
   # Exemplo: momentum com roc_period=10, threshold=-1.0
   ```

2. **Paper Trading**:
   ```bash
   # Testar em tempo real sem risco
   curl -X POST "http://localhost:3007/strategies/momentum/paper-trade" \
     -d '{"parameters": {"roc_period": 10, "threshold": -1.0}}'
   ```

3. **Monitoramento**:
   - Criar alertas para performance degradada
   - Re-otimizar mensalmente
   - Comparar live vs backtest

4. **Documentar**:
   - Salvar melhores parâmetros em config
   - Registrar performance esperada
   - Anotar condições de mercado

---

## 📚 REFERÊNCIAS ÚTEIS

- **Documentação API**: http://localhost:3007/
- **Status Otimização**: `/home/dellno/worksapace/aitrading-platform/OPTIMIZATION_STATUS.md`
- **Logs do Sistema**: `docker logs aitrading-backtesting-engine`
- **Resultados Salvos**: `/home/dellno/worksapace/aitrading-platform/optimization_results/`

---

**Última Atualização**: 9 de dezembro de 2025  
**Versão**: 1.0  
**Status**: ✅ Sistema Operacional
