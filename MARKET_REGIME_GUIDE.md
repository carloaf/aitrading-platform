# 🤖 Market Regime Detector - Guia de Uso Completo

## 📋 Índice
1. [Visão Geral](#visão-geral)
2. [3 Formas de Usar](#3-formas-de-usar)
3. [API Endpoints](#api-endpoints)
4. [Exemplos Práticos](#exemplos-práticos)
5. [Integração com Paper Trading](#integração-com-paper-trading)
6. [Casos de Uso Reais](#casos-de-uso-reais)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O **Market Regime Detector** é um sistema inteligente que:
- ✅ Identifica automaticamente o regime de mercado (Bull/Bear/Sideways/Volatile)
- ✅ Recomenda a melhor estratégia para o regime atual
- ✅ Fornece conselhos de trading (risco, tamanho de posição)
- ✅ Monitora mudanças de regime em tempo real
- ✅ Se adapta automaticamente às condições de mercado

---

## 🚀 3 Formas de Usar

### **1️⃣ USO MANUAL - Consulta Única**
**Quando usar:** Antes de iniciar trading para saber qual estratégia usar

```bash
# Consulta simples - retorna apenas o nome da estratégia
curl "http://localhost:3008/api/strategy/best?symbol=BTCUSDT&interval=1h"

# Resposta:
# {
#   "strategy": "breakdown_momentum",
#   "symbol": "BTCUSDT",
#   "interval": "1h"
# }
```

**Use caso:**
- Você está decidindo qual estratégia usar hoje
- Quer uma resposta rápida sem análise detalhada
- Está configurando um bot pela primeira vez

---

### **2️⃣ USO AUTOMÁTICO - Seleção Inteligente**
**Quando usar:** Para obter análise completa e conselhos de trading

```bash
curl -X POST "http://localhost:3008/api/strategy/auto-select" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "interval": "1h",
    "lookback_days": 90
  }'
```

**Resposta completa:**
```json
{
  "market_analysis": {
    "regime": "bear",
    "confidence": 85.7,
    "trend_strength": -85.71,
    "volatility": 13.35,
    "description": "Mercado em tendência de BAIXA...",
    "signals": {
      "ma_trend": "BEAR",
      "adx": "STRONG_BEAR",
      "rsi": "BEARISH",
      "volatility": "HIGH"
    }
  },
  "strategy_recommendation": {
    "primary": "breakdown_momentum",
    "alternatives": ["bear_market_short", "death_cross"],
    "reason": "Mercado em baixa - estratégias short"
  },
  "trading_advice": {
    "should_trade": true,
    "risk_level": "high",
    "position_size_multiplier": 0.5,
    "warnings": [
      "Alta volatilidade detectada - reduzir tamanho de posição",
      "Volume baixo - confirmação de sinais pode ser fraca"
    ]
  }
}
```

**Use caso:**
- Precisa entender o mercado em profundidade
- Quer ajustar parâmetros de risco
- Está tomando decisões de investimento importantes

---

### **3️⃣ USO ADAPTATIVO - Monitoramento Contínuo**
**Quando usar:** Sistema já está rodando e você quer saber se deve mudar

```bash
curl -X POST "http://localhost:3008/api/strategy/should-change" \
  -H "Content-Type: application/json" \
  -d '{
    "current_strategy": "momentum",
    "symbol": "BTCUSDT",
    "interval": "1h"
  }'
```

**Resposta:**
```json
{
  "should_change": true,
  "current_strategy": "momentum",
  "recommended_strategy": "breakdown_momentum",
  "regime": "bear",
  "confidence": 85.7,
  "reason": "Regime mudou para bear"
}
```

**Use caso:**
- Bot já está rodando com uma estratégia
- Quer verificar se deve adaptar
- Está fazendo monitoramento periódico (ex: a cada hora)

---

## 📡 API Endpoints

### **1. GET `/api/strategy/best`**
Retorna apenas o nome da melhor estratégia (uso simples)

**Query Parameters:**
- `symbol` (string): Par de trading (default: "BTCUSDT")
- `interval` (string): Timeframe (default: "1h")
- `lookback_days` (int): Dias de histórico (default: 90)

**Exemplo:**
```bash
curl "http://localhost:3008/api/strategy/best?symbol=ETHUSDT&interval=4h"
```

---

### **2. POST `/api/strategy/auto-select`**
Seleção automática com análise completa

**Request Body:**
```json
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "lookback_days": 90,
  "force_refresh": false
}
```

**Response:**
- `market_analysis`: Regime, confiança, sinais técnicos
- `strategy_recommendation`: Estratégia primária e alternativas
- `trading_advice`: Conselhos de risco e avisos

---

### **3. POST `/api/strategy/should-change`**
Verifica se deve trocar estratégia atual

**Request Body:**
```json
{
  "current_strategy": "momentum",
  "symbol": "BTCUSDT",
  "interval": "1h"
}
```

**Response:**
- `should_change`: true/false
- `recommended_strategy`: Nova estratégia (se deve mudar)
- `reason`: Explicação da recomendação

---

### **4. POST `/api/market-regime/detect`**
Detecção pura de regime (sem recomendação de estratégia)

**Request Body:**
```json
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "lookback_days": 90
}
```

---

## 💻 Exemplos Práticos

### **Python - Bot Adaptativo Completo**

Use o script fornecido:
```bash
cd services/execution-engine/examples

# Exemplo 1: Consulta manual
python3 adaptive_trading_bot.py 1

# Exemplo 2: Verificar se deve mudar estratégia
python3 adaptive_trading_bot.py 2

# Exemplo 3: Iniciar trading inteligente
python3 adaptive_trading_bot.py 3

# Exemplo 4: Monitoramento contínuo (rode em background)
python3 adaptive_trading_bot.py 4
```

---

### **Python - Integração Básica**

```python
import requests

# 1. Obter melhor estratégia
response = requests.get("http://localhost:3008/api/strategy/best")
strategy = response.json()['strategy']
print(f"Usar estratégia: {strategy}")

# 2. Obter análise completa
response = requests.post(
    "http://localhost:3008/api/strategy/auto-select",
    json={"symbol": "BTCUSDT", "interval": "1h", "lookback_days": 90}
)
analysis = response.json()

# Verificar se deve tradear
if analysis['trading_advice']['should_trade']:
    print("✅ Condições favoráveis para trading")
    print(f"🎯 Usar: {analysis['strategy_recommendation']['primary']}")
    print(f"⚠️  Risco: {analysis['trading_advice']['risk_level']}")
else:
    print("🚫 Não recomendado tradear agora")
```

---

### **JavaScript/Node.js**

```javascript
const axios = require('axios');

async function getBestStrategy() {
  const response = await axios.get('http://localhost:3008/api/strategy/best', {
    params: {
      symbol: 'BTCUSDT',
      interval: '1h',
      lookback_days: 90
    }
  });
  
  return response.data.strategy;
}

async function getFullAnalysis() {
  const response = await axios.post('http://localhost:3008/api/strategy/auto-select', {
    symbol: 'BTCUSDT',
    interval: '1h',
    lookback_days: 90
  });
  
  return response.data;
}

// Uso
(async () => {
  const strategy = await getBestStrategy();
  console.log(`Melhor estratégia: ${strategy}`);
  
  const analysis = await getFullAnalysis();
  console.log(`Regime: ${analysis.market_analysis.regime}`);
  console.log(`Confiança: ${analysis.market_analysis.confidence}%`);
})();
```

---

### **Bash - Script de Monitoramento**

```bash
#!/bin/bash
# monitor_regime.sh - Monitora regime a cada hora

while true; do
  echo "=========================================="
  echo "🔍 Verificando regime: $(date)"
  echo "=========================================="
  
  # Obter análise
  response=$(curl -s -X POST "http://localhost:3008/api/strategy/auto-select" \
    -H "Content-Type: application/json" \
    -d '{"symbol": "BTCUSDT", "interval": "1h", "lookback_days": 90}')
  
  # Extrair informações
  regime=$(echo $response | jq -r '.market_analysis.regime')
  confidence=$(echo $response | jq -r '.market_analysis.confidence')
  strategy=$(echo $response | jq -r '.strategy_recommendation.primary')
  
  echo "📊 Regime: $regime ($confidence% confiança)"
  echo "🎯 Estratégia recomendada: $strategy"
  
  # Alertar se mudou para BULL (oportunidade!)
  if [ "$regime" == "bull" ]; then
    echo "🚨 ALERTA: Mercado virou BULL! Considere entrar!"
    # Aqui você pode enviar notificação (email, Telegram, etc)
  fi
  
  echo ""
  echo "⏳ Próxima verificação em 1 hora..."
  sleep 3600  # 1 hora
done
```

---

## 🎮 Integração com Paper Trading

### **Início Automático com Estratégia Adaptativa**

```python
import requests

def start_adaptive_paper_trading():
    # 1. Obter análise completa
    analysis_response = requests.post(
        "http://localhost:3008/api/strategy/auto-select",
        json={"symbol": "BTCUSDT", "interval": "1h", "lookback_days": 90}
    )
    analysis = analysis_response.json()
    
    # 2. Verificar se deve tradear
    if not analysis['trading_advice']['should_trade']:
        print("🚫 Condições desfavoráveis - não iniciando trading")
        return
    
    # 3. Obter estratégia recomendada
    strategy = analysis['strategy_recommendation']['primary']
    position_multiplier = analysis['trading_advice']['position_size_multiplier']
    
    # 4. Ajustar capital inicial baseado no risco
    initial_balance = 10000.0 * position_multiplier
    
    # 5. Iniciar paper trading
    trading_response = requests.post(
        "http://localhost:3008/paper-trading/start",
        json={
            "session_id": f"adaptive_{int(time.time())}",
            "strategy_name": strategy,
            "symbol": "BTCUSDT",
            "initial_balance": initial_balance,
            "leverage": 1
        }
    )
    
    print(f"✅ Paper trading iniciado com estratégia: {strategy}")
    print(f"💰 Capital inicial ajustado: ${initial_balance:.2f}")
    
    return trading_response.json()

# Usar
start_adaptive_paper_trading()
```

---

## 🎯 Casos de Uso Reais

### **1. Trader Iniciante**
**Objetivo:** Saber qual estratégia usar hoje

```bash
# Consulta simples
curl "http://localhost:3008/api/strategy/best"

# Resultado: breakdown_momentum
# Ação: Iniciar paper trading com esta estratégia
```

---

### **2. Trader Experiente**
**Objetivo:** Análise detalhada antes de decisões importantes

```bash
# Análise completa
curl -X POST "http://localhost:3008/api/strategy/auto-select" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "interval": "4h", "lookback_days": 180}'

# Avaliar:
# - Confiança da análise (>70% = confiável)
# - Volatilidade (ajustar stop loss)
# - Warnings (considerar antes de entrar)
```

---

### **3. Bot Automatizado**
**Objetivo:** Sistema que se adapta sozinho

```python
# Monitoramento a cada hora
import time

while True:
    # Verificar se deve mudar estratégia
    response = requests.post(
        "http://localhost:3008/api/strategy/should-change",
        json={
            "current_strategy": current_strategy,
            "symbol": "BTCUSDT"
        }
    )
    
    result = response.json()
    
    if result['should_change']:
        # Trocar estratégia automaticamente
        stop_paper_trading(session_id)
        new_strategy = result['recommended_strategy']
        start_paper_trading(new_strategy)
        current_strategy = new_strategy
        
        # Enviar notificação
        send_telegram_alert(f"Estratégia trocada para: {new_strategy}")
    
    time.sleep(3600)  # 1 hora
```

---

### **4. Backtesting Adaptativo**
**Objetivo:** Testar estratégias apenas em regimes apropriados

```python
# Executar backtest APENAS quando regime é apropriado
analysis = get_market_analysis()

if analysis['market_analysis']['regime'] == 'bear':
    # Testar estratégias BEAR
    run_backtest('breakdown_momentum')
    run_backtest('bear_market_short')
elif analysis['market_analysis']['regime'] == 'bull':
    # Testar estratégias BULL
    run_backtest('momentum')
    run_backtest('trend_following')
```

---

## 🛠️ Troubleshooting

### **Problema: "Dados insuficientes"**
```
ValueError: Dados insuficientes: 150 candles
```

**Solução:** Precisa de pelo menos 200 candles
```bash
# Reduzir lookback_days ou usar timeframe menor
curl -X POST "http://localhost:3008/api/strategy/auto-select" \
  -d '{"symbol": "BTCUSDT", "interval": "1h", "lookback_days": 30}'
```

---

### **Problema: "Baixa confiança"**
```
"confidence": 45.2
```

**Interpretação:**
- <60%: Mercado confuso, evitar trading
- 60-80%: Confiança média, reduzir posição
- >80%: Alta confiança, estratégia clara

**Ação:** Aguardar até confiança >60%

---

### **Problema: "should_trade": false**
```json
{
  "should_trade": false,
  "warnings": ["Baixa confiança na análise (45.2%)"]
}
```

**Ação:** NÃO tradear! O detector identificou condições ruins.

---

### **Problema: API retorna erro 500**

**Debug:**
```bash
# 1. Verificar saúde da API
curl http://localhost:3008/health

# 2. Ver logs do container
docker logs aitrading-execution-engine --tail 50

# 3. Verificar se TimescaleDB está respondendo
docker exec -it aitrading-timescaledb psql -U crypto_user -d crypto_market -c "SELECT COUNT(*) FROM market_data_realtime;"
```

---

## 📊 Interpretação dos Resultados

### **Regimes de Mercado**

| Regime | Descrição | Estratégias Recomendadas |
|--------|-----------|-------------------------|
| **BULL** | Mercado em alta | momentum, trend_following, macd_rsi_combo |
| **BEAR** | Mercado em baixa | breakdown_momentum, bear_market_short, death_cross |
| **SIDEWAYS** | Mercado lateral | mean_reversion, bollinger_bands |
| **VOLATILE** | Alta volatilidade | volatility_breakout, bollinger_bands |

---

### **Níveis de Confiança**

| Confiança | Interpretação | Ação |
|-----------|---------------|------|
| < 60% | Mercado confuso | Evitar trading |
| 60-80% | Confiança média | Reduzir posição 50% |
| 80-100% | Alta confiança | Posição normal |

---

### **Níveis de Risco**

| Risco | Multiplicador | Ação |
|-------|---------------|------|
| **LOW** | 1.2x | Pode aumentar posição |
| **MEDIUM** | 1.0x | Posição normal |
| **HIGH** | 0.5x | Reduzir posição pela metade |

---

## 🚀 Próximos Passos

Após dominar o Market Regime Detector, você pode:

1. **Criar Dashboard:** Visualizar regime em tempo real
2. **Sistema de Alertas:** Notificações quando regime mudar
3. **Trading Automático:** Bot que troca estratégia sozinho
4. **Multi-timeframe:** Analisar múltiplos timeframes
5. **Backtesting Adaptativo:** Testar estratégias por regime

---

## 📚 Recursos Adicionais

- **Código Fonte:** `services/execution-engine/src/market_regime_detector.py`
- **Auto Selector:** `services/execution-engine/src/auto_strategy_selector.py`
- **Exemplos:** `services/execution-engine/examples/adaptive_trading_bot.py`
- **API Docs:** http://localhost:3008/docs (FastAPI Swagger)

---

## ✅ Resumo Rápido

```bash
# 1. CONSULTA RÁPIDA (qual estratégia usar hoje?)
curl "http://localhost:3008/api/strategy/best"

# 2. ANÁLISE COMPLETA (preciso de detalhes)
curl -X POST "http://localhost:3008/api/strategy/auto-select" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT"}'

# 3. VERIFICAR MUDANÇA (meu bot já está rodando)
curl -X POST "http://localhost:3008/api/strategy/should-change" \
  -H "Content-Type: application/json" \
  -d '{"current_strategy": "momentum"}'
```

**Pronto para usar! 🚀**
