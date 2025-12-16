# 🎨 Integração do Market Regime Widget nas Páginas

## 📋 Resumo

O **Market Regime Widget** é um componente reutilizável que mostra informações do regime de mercado em 3 modos diferentes:

| Página | Modo | Finalidade |
|--------|------|------------|
| **Paper Trading** | `recommendation` | Ajudar a escolher a estratégia certa |
| **Trading Dashboard** | `monitor` | Monitoramento em tempo real |
| **Monte Carlo** | `filter` | Filtrar estratégias por regime |

---

## 🚀 Como Integrar

### **1️⃣ Paper Trading (`paper-trading.ejs`)**

**Localização:** Logo acima do formulário de iniciar paper trading

**Código para adicionar:**

```ejs
<!-- Market Regime Recommendation -->
<div class="row mb-4">
    <div class="col-12">
        <%- include('partials/market-regime-widget', { 
            mode: 'recommendation',
            symbol: 'BTCUSDT',
            interval: '1h'
        }) %>
    </div>
</div>

<!-- Formulário de Paper Trading continua aqui... -->
<div class="card">
    <div class="card-header">
        <h3>Iniciar Paper Trading</h3>
    </div>
    ...
```

**O que faz:**
- ✅ Mostra regime atual (Bull/Bear/Sideways/Volatile)
- ✅ Recomenda melhor estratégia
- ✅ Mostra avisos de risco
- ✅ Ajusta tamanho de posição automaticamente
- ✅ Botão para usar estratégia recomendada (preenche o formulário)

**Exemplo visual:**
```
┌─────────────────────────────────────────────────────────┐
│ 🐻 Recomendação Inteligente de Estratégia   [85.7%]    │
├─────────────────────────────────────────────────────────┤
│ Regime Atual: BEAR                                      │
│                                                         │
│ 🎯 Estratégia Recomendada                               │
│    breakdown_momentum                                   │
│    Alternativas: bear_market_short, death_cross        │
│                                                         │
│ Deve tradear?        ✅ SIM                             │
│ Nível de risco:      HIGH                              │
│ Ajuste de posição:   0.5x                              │
│                                                         │
│ ⚠️ Avisos Importantes:                                  │
│ • Alta volatilidade - reduzir posição para 50%         │
│ • Volume baixo - sinais podem ser fracos               │
│                                                         │
│ [Usar breakdown_momentum] [Ver Análise Completa]       │
└─────────────────────────────────────────────────────────┘
```

---

### **2️⃣ Trading Dashboard (`trading-dashboard.ejs`)**

**Localização:** Sidebar direita ou card no topo

**Código para adicionar:**

```ejs
<!-- Sidebar Direita -->
<div class="col-lg-3">
    <!-- Market Regime Monitor -->
    <%- include('partials/market-regime-widget', { 
        mode: 'monitor',
        symbol: 'BTCUSDT',
        interval: '1h'
    }) %>
    
    <!-- Outros widgets da sidebar continuam aqui... -->
    <div class="card">
        <div class="card-header">Performance</div>
        ...
```

**O que faz:**
- ✅ Mostra regime atual em destaque
- ✅ Força da tendência e volatilidade
- ✅ Sinais técnicos (MA, ADX, RSI, Volume)
- ✅ Auto-refresh a cada 5 minutos
- ✅ Botão para atualizar manualmente

**Exemplo visual:**
```
┌───────────────────────────────┐
│ 🐻 Regime de Mercado  [85.7%] │
├───────────────────────────────┤
│                               │
│          BEAR                 │
│                               │
│ Força da Tendência: -85.7     │
│ Volatilidade: 13.35%          │
│                               │
│ Sinais Técnicos:              │
│ MA: BEAR                      │
│ ADX: STRONG_BEAR              │
│ RSI: BEARISH                  │
│ Volume: LOW                   │
│                               │
│ Última atualização: agora     │
│                               │
│ [🔄 Atualizar] [📊 Histórico] │
└───────────────────────────────┘
```

---

### **3️⃣ Monte Carlo (`monte-carlo.ejs`)**

**Localização:** Logo acima dos resultados da simulação

**Código para adicionar:**

```ejs
<!-- Market Regime Filter -->
<div class="row mb-4">
    <div class="col-12">
        <%- include('partials/market-regime-widget', { 
            mode: 'filter',
            symbol: 'BTCUSDT',
            interval: '1h'
        }) %>
    </div>
</div>

<!-- Resultados do Monte Carlo continuam aqui... -->
<div class="card">
    <div class="card-header">
        <h3>Resultados da Simulação</h3>
    </div>
    ...
```

**O que faz:**
- ✅ Mostra regime atual
- ✅ Lista estratégias recomendadas para o regime
- ✅ Explica por que certas estratégias são melhores
- ✅ Botão para filtrar apenas estratégias do regime
- ✅ Evita testar estratégias inadequadas

**Exemplo visual:**
```
┌─────────────────────────────────────────────────────────┐
│ 🐻 Análise de Regime para Monte Carlo       [85.7%]    │
├─────────────────────────────────────────────────────────┤
│ Regime Detectado: BEAR                                  │
│                                                         │
│ 💡 Recomendação:                                        │
│ Para resultados mais realistas em mercado BEAR,        │
│ simule apenas estratégias apropriadas para este        │
│ regime.                                                │
│                                                         │
│ ✅ Estratégias Recomendadas:                            │
│ ⭐ breakdown_momentum                                    │
│ • bear_market_short                                    │
│ • death_cross                                          │
│                                                         │
│ [Simular Apenas BEAR] [Ver Todas]                      │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 Instruções de Instalação

### **Passo 1: Criar o diretório de partials (se não existir)**

```bash
cd /home/dellno/worksapace/aitrading-platform/frontend/views
mkdir -p partials
```

### **Passo 2: O arquivo já foi criado**

O arquivo `partials/market-regime-widget.ejs` já está criado com todo o código necessário.

### **Passo 3: Integrar em cada página**

Edite os arquivos das páginas e adicione o código conforme mostrado acima:

1. **`paper-trading.ejs`** → Adicionar modo `recommendation`
2. **`trading-dashboard.ejs`** → Adicionar modo `monitor`
3. **`monte-carlo.ejs`** → Adicionar modo `filter`

---

## 🎨 Customização

### **Alterar símbolo e intervalo**

```ejs
<%- include('partials/market-regime-widget', { 
    mode: 'recommendation',
    symbol: 'ETHUSDT',      <!-- Mudar para outro par -->
    interval: '4h'          <!-- Mudar timeframe -->
}) %>
```

### **Desabilitar auto-refresh**

Edite o arquivo `market-regime-widget.ejs`, linha ~350:

```javascript
// Comentar ou remover esta linha para desabilitar auto-refresh
// setInterval(loadRegimeAnalysis, 5 * 60 * 1000);
```

### **Alterar cores do widget**

Edite as classes CSS no início do arquivo:

```css
.regime-widget.bear {
    /* Mudar cores do gradiente */
    background: linear-gradient(135deg, #ee0979 0%, #ff6a00 100%);
}
```

---

## 🧪 Testar Localmente

### **1. Reiniciar o frontend**

```bash
docker restart aitrading-frontend
```

### **2. Acessar as páginas**

- Paper Trading: http://localhost:3000/paper-trading
- Dashboard: http://localhost:3000/trading-dashboard
- Monte Carlo: http://localhost:3000/monte-carlo

### **3. Verificar no console do navegador**

Abra o DevTools (F12) e verifique se há erros. O widget deve carregar automaticamente.

---

## 🐛 Troubleshooting

### **Problema: Widget não aparece**

**Solução 1:** Verificar se a API está rodando
```bash
curl http://localhost:3008/health
```

**Solução 2:** Verificar console do navegador (F12)
- Procure por erros de CORS
- Verifique se a requisição foi feita

**Solução 3:** Testar a API diretamente
```bash
curl -X POST "http://localhost:3008/api/strategy/auto-select" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "interval": "1h"}'
```

---

### **Problema: CORS blocked**

**Solução:** Adicionar CORS no Execution Engine

O arquivo `main.py` já tem CORS configurado, mas se precisar ajustar:

```python
# services/execution-engine/src/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Depois, reiniciar o container:
```bash
docker restart aitrading-execution-engine
```

---

### **Problema: Widget mostra "Erro ao carregar análise"**

**Debug:**

1. Verificar logs do Execution Engine:
```bash
docker logs aitrading-execution-engine --tail 50
```

2. Verificar se há dados suficientes no banco:
```bash
docker exec -it aitrading-timescaledb psql -U crypto_user -d crypto_market -c \
  "SELECT COUNT(*) FROM market_data_realtime WHERE symbol='BTCUSDT';"
```

3. Reduzir `lookback_days` se houver poucos dados:
```ejs
<%- include('partials/market-regime-widget', { 
    mode: 'recommendation',
    symbol: 'BTCUSDT',
    interval: '1h'
}) %>
```

E no arquivo `market-regime-widget.ejs`, mudar linha ~75:
```javascript
lookback_days: 30  // Reduzir de 90 para 30
```

---

## 📊 Exemplo Completo de Integração

### **Arquivo: `paper-trading.ejs`**

```ejs
<!DOCTYPE html>
<html>
<head>
    <title>Paper Trading</title>
    <%- include('partials/head') %>
</head>
<body>
    <%- include('partials/navbar') %>
    
    <div class="container mt-4">
        <!-- ADICIONAR AQUI: Market Regime Widget -->
        <div class="row mb-4">
            <div class="col-12">
                <%- include('partials/market-regime-widget', { 
                    mode: 'recommendation',
                    symbol: 'BTCUSDT',
                    interval: '1h'
                }) %>
            </div>
        </div>
        
        <!-- Formulário de Paper Trading -->
        <div class="row">
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-header">
                        <h3>Iniciar Paper Trading</h3>
                    </div>
                    <div class="card-body">
                        <form id="startTradingForm">
                            <div class="form-group">
                                <label>Estratégia</label>
                                <select id="strategy_name" name="strategy_name" class="form-control">
                                    <option value="momentum">Momentum</option>
                                    <option value="breakdown_momentum">Breakdown Momentum</option>
                                    <!-- ... outras estratégias ... -->
                                </select>
                            </div>
                            <!-- ... resto do formulário ... -->
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <%- include('partials/footer') %>
</body>
</html>
```

---

## ✅ Checklist de Implementação

- [ ] Arquivo `partials/market-regime-widget.ejs` criado
- [ ] Integrado em `paper-trading.ejs` (modo: recommendation)
- [ ] Integrado em `trading-dashboard.ejs` (modo: monitor)
- [ ] Integrado em `monte-carlo.ejs` (modo: filter)
- [ ] Testado em cada página
- [ ] CORS configurado no backend
- [ ] API respondendo corretamente
- [ ] Widget carregando sem erros
- [ ] Botões funcionando

---

## 🚀 Próximos Passos (Opcional)

1. **Modal de Análise Completa:** Criar popup com detalhes técnicos
2. **Histórico de Regime:** Gráfico mostrando mudanças de regime
3. **Alertas por Email/Telegram:** Notificar quando regime mudar
4. **Comparação Multi-Timeframe:** Analisar 1h, 4h, 1d simultaneamente
5. **Backtesting por Regime:** Filtrar backtest por período de bull/bear

---

## 📚 Referências

- Widget Component: `frontend/views/partials/market-regime-widget.ejs`
- API Documentation: `MARKET_REGIME_GUIDE.md`
- Backend Code: `services/execution-engine/src/auto_strategy_selector.py`
- Examples: `services/execution-engine/examples/adaptive_trading_bot.py`
