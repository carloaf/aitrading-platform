# 🎲 Guia do Lançador Interativo de Simulação Monte Carlo

## 🎯 Visão Geral

O dashboard Monte Carlo agora possui um **lançador interativo de simulações** com monitoramento de progresso em tempo real. Este guia explica como usar as novas funcionalidades.

---

## ✨ Novas Funcionalidades

### 1. Modal de Configuração Interativa
Ao clicar em qualquer botão de estratégia (exceto "Todas"), abre-se um modal onde você pode configurar:

- **Número de Iterações** (100 - 10.000)
  - Slider interativo com valor em tempo real
  - Badge mostrando quantidade selecionada
  
- **Período de Análise** (7, 14, 30, 60, 90 dias)
  - Dropdown simples para selecionar lookback
  
- **Símbolo** (ex: BTCUSDT)
  - Campo de texto editável
  
- **Intervalo** (1m, 5m, 15m, 1h, 4h, 1d)
  - Dropdown com timeframes comuns
  
- **Capital Inicial** ($1.000 - infinito)
  - Campo numérico com validação
  
- **Faixas de Parâmetros**
  - Lista automática dos parâmetros da estratégia
  - Ranges mostrados como min-max

### 2. Estimativa de Tempo
O modal mostra automaticamente uma estimativa do tempo necessário:

| Iterações | Tempo Estimado |
|-----------|----------------|
| 100-500   | 1-3 minutos    |
| 501-1000  | 2-5 minutos    |
| 1001-5000 | 10-20 minutos  |
| 5001+     | 20-40 minutos  |

### 3. Painel de Progresso em Tempo Real

Após clicar em "Iniciar Simulação", aparece um painel flutuante mostrando:

#### 📊 Barra de Progresso
- Animação suave de 0% a 100%
- Cor gradiente (azul → verde)
- Porcentagem exibida na barra

#### 📈 Contador de Iterações
- "X / Y iterações" em tempo real
- Atualiza aproximadamente a cada 2 segundos

#### ⏱️ Tempo Decorrido
- Cronômetro mostrando MM:SS
- Atualização a cada segundo

#### ⏳ Tempo Estimado
- Calculado dinamicamente baseado no progresso
- Atualiza conforme simulação avança
- Formato MM:SS

#### 🛑 Botão Cancelar
- Permite interromper a simulação
- Confirmação antes de cancelar

---

## 🚀 Como Usar

### Passo 1: Acesse o Dashboard
```bash
# URL do dashboard
http://localhost:8081/monte-carlo
```

### Passo 2: Selecione uma Estratégia
Clique em um dos botões de estratégia:

- 🚀 **Momentum** - Rate of Change com threshold dinâmico
- 📊 **MACD + RSI** - Combinação de osciladores
- 📈 **Trend Following** - Médias móveis + ATR
- ⚡ **Volatility Breakout** - Rompimento baseado em ATR
- 📉 **Bollinger Bands** - Bandas + RSI

### Passo 3: Configure a Simulação

O modal aparece automaticamente. Configure:

1. **Arraste o slider** para ajustar iterações
   - Veja o badge atualizar em tempo real
   - Observe a estimativa de tempo mudar

2. **Selecione o período de análise**
   - 30 dias é recomendado para início

3. **Ajuste símbolo e intervalo** (opcional)
   - Padrão: BTCUSDT, 1h

4. **Defina capital inicial** (opcional)
   - Padrão: $10.000

5. Revise os **parâmetros da estratégia**
   - Valores mostrados automaticamente

### Passo 4: Inicie a Simulação

Clique em **"Iniciar Simulação"**

O modal fecha e o painel de progresso aparece.

### Passo 5: Monitore o Progresso

Observe em tempo real:

```
🎲 Simulação em Andamento
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Momentum

[████████████░░░░░░░░] 65%

523 / 1000 iterações

Tempo Decorrido: 02:14
Tempo Estimado: 01:18

[ 🛑 Cancelar ]
```

### Passo 6: Resultados Automáticos

Quando a simulação completa:

1. Barra atinge 100%
2. Painel fecha automaticamente (2 segundos)
3. Dashboard carrega os novos resultados
4. Métricas, gráficos e tabelas atualizadas

---

## 🔧 Detalhes Técnicos

### Sistema de Polling
A interface monitora o progresso através de:

```javascript
// Polling a cada 2 segundos
- Verifica endpoint /api/monte-carlo/reports
- Busca relatório mais recente da estratégia
- Se encontrado: simulação completada
- Se não: atualiza progresso simulado
```

### Progresso Simulado
Como a API atual não retorna progresso incremental, usa-se uma **curva exponencial** para estimar:

```javascript
progress = 100 * (1 - exp(-pollCount / 60))
```

Isso cria um progresso realista que:
- Cresce rápido no início
- Desacelera perto do fim
- Nunca passa de 95% até completar
- Atinge 100% apenas quando relatório existe

### Tempo Estimado
Calculado dinamicamente:

```javascript
elapsed = tempo desde início (segundos)
rate = progress / elapsed (% por segundo)
remaining = (100 - progress) / rate
```

---

## 🎨 Interface do Modal

### Estrutura Visual

```
┌─────────────────────────────────────────┐
│  ⚙️ Configurar Simulação           [×]  │
├─────────────────────────────────────────┤
│                                         │
│  Estratégia Selecionada                 │
│  Momentum                               │
│                                         │
│  Número de Iterações                    │
│  [━━━━━━━━○━━━━━━━━]                    │
│          1000 iterações                 │
│                                         │
│  Período de Análise (dias)              │
│  [ 30 dias ▼ ]                          │
│                                         │
│  Símbolo          Intervalo             │
│  [BTCUSDT]        [1 hora ▼]            │
│                                         │
│  Capital Inicial                        │
│  $ [10000]                              │
│                                         │
│  💡 Estimativa:                         │
│  Com 1000 iterações, a simulação        │
│  levará aproximadamente 2-5 minutos.    │
│                                         │
│  Faixas de Parâmetros:                  │
│  • roc_period: 5 - 20                   │
│  • threshold: 0.5 - 3.0                 │
│                                         │
├─────────────────────────────────────────┤
│         [Cancelar]  [▶ Iniciar]        │
└─────────────────────────────────────────┘
```

### Cores e Estilo

- **Primary**: #2c3e50 (azul escuro)
- **Success**: #27ae60 (verde)
- **Info**: #3498db (azul claro)
- **Danger**: #e74c3c (vermelho)

- **Barra de Progresso**: Gradiente azul → verde
- **Overlay**: Escurecimento suave (rgba(0,0,0,0.7))
- **Modal**: Branco com sombra profunda
- **Cards**: Cinza claro (#f8f9fa)

---

## 📋 Estratégias e Parâmetros

### Momentum
```json
{
  "roc_period": [5, 20],
  "threshold": [0.5, 3.0]
}
```

### MACD + RSI
```json
{
  "macd_fast": [8, 16],
  "macd_slow": [20, 30],
  "macd_signal": [7, 12],
  "rsi_period": [10, 20],
  "rsi_overbought": [65, 75],
  "rsi_oversold": [25, 35]
}
```

### Trend Following
```json
{
  "fast_ma": [10, 30],
  "slow_ma": [40, 80],
  "atr_period": [10, 20],
  "atr_mult": [1.5, 3.0]
}
```

### Volatility Breakout
```json
{
  "atr_period": [10, 20],
  "atr_mult": [1.5, 3.0],
  "lookback": [15, 30]
}
```

### Bollinger Bands
```json
{
  "bb_period": [15, 25],
  "bb_std": [1.5, 2.5],
  "rsi_period": [10, 20]
}
```

---

## 🐛 Solução de Problemas

### Modal não abre
**Causa**: JavaScript não carregou
**Solução**: 
```bash
# Verifique console do navegador
# Reconstrua frontend
docker compose up -d --build frontend
```

### Progresso não atualiza
**Causa**: API não está respondendo
**Solução**:
```bash
# Verifique execution-engine
docker logs aitrading-execution-engine --tail 50

# Teste API manualmente
curl http://localhost:3008/api/monte-carlo/reports
```

### Simulação nunca completa (fica em 95%)
**Causa**: Erro na execução da simulação
**Solução**:
```bash
# Verifique logs
docker logs aitrading-execution-engine 2>&1 | grep -i error

# Cancele e tente com menos iterações
```

### "Timeout: simulação demorou muito tempo"
**Causa**: Mais de 10 minutos decorridos (600 polls)
**Solução**: 
- Use menos iterações (≤ 1000)
- Verifique se há erro no backend
- Reduza período de análise

---

## 🔄 Fluxo Completo

```
┌─────────────────────────────────────────────────┐
│  1. Usuário clica em botão de estratégia        │
│     (ex: "Momentum")                            │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  2. JavaScript detecta clique                   │
│     - selectStrategy('momentum') chamado        │
│     - showConfigModal('momentum') executado     │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  3. Modal Bootstrap aparece                     │
│     - Nome da estratégia preenchido             │
│     - Parâmetros carregados dinamicamente       │
│     - Valores padrão definidos                  │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  4. Usuário ajusta configurações                │
│     - Move slider (iterações)                   │
│     - Badge atualiza em tempo real              │
│     - Estimativa de tempo recalcula             │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  5. Usuário clica "Iniciar Simulação"           │
│     - startSimulation() chamado                 │
│     - Validação de campos                       │
│     - Montagem do objeto request                │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  6. Modal fecha, progresso aparece              │
│     - Overlay escurecido ativo                  │
│     - Painel de progresso visível               │
│     - Cronômetro iniciado                       │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  7. POST /api/monte-carlo/simulate enviado      │
│     - Backend recebe request                    │
│     - Carrega dados do TimescaleDB              │
│     - Inicia MonteCarloSimulator                │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  8. Polling iniciado (cada 2 segundos)          │
│     - GET /api/monte-carlo/reports              │
│     - Busca relatório da estratégia             │
│     - Se não encontrado: atualiza progresso     │
│     - Se encontrado: vai para passo 10          │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  9. Atualização de progresso                    │
│     - Barra cresce exponencialmente             │
│     - Contador de iterações ~estimado           │
│     - Tempo decorrido atualiza (1s)             │
│     - Tempo estimado recalcula                  │
│     - Loop: volta para passo 8                  │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  10. Simulação completa (relatório existe)      │
│      - Progresso vai para 100%                  │
│      - Espera 2 segundos                        │
│      - Painel de progresso fecha                │
└────────────────┬────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────┐
│  11. Resultados carregados automaticamente      │
│      - loadReports() chamado                    │
│      - renderData(strategy) executado           │
│      - Métricas, gráficos e tabela atualizados  │
│      - Botão da estratégia fica ativo           │
└─────────────────────────────────────────────────┘
```

---

## 📊 Comparação: Antes vs Depois

### ❌ Antes (Linha de Comando)
```bash
$ ./scripts/run_monte_carlo.sh momentum 1000 30

🎲 MONTE CARLO SIMULATION
📊 Estratégia: momentum
🔢 Iterações: 1000
📅 Lookback: 30 dias
🎲 Iniciando simulação...

# Aguarda sem feedback...
# Sem progresso visível
# Sem tempo estimado
# Ctrl+C para cancelar (dados perdidos)
```

### ✅ Depois (Interface Gráfica)
```
[Click no botão "Momentum"]

┌───────────────────────────┐
│  ⚙️ Configurar Simulação  │
│  Momentum                 │
│  [Slider: 1000]           │
│  [30 dias]                │
│  💡 ~2-5 minutos          │
│  [▶ Iniciar]             │
└───────────────────────────┘

[Click em "Iniciar"]

┌───────────────────────────┐
│  🎲 Simulação em Andamento│
│  Momentum                 │
│  [████████░░] 65%        │
│  523 / 1000 iterações     │
│  ⏱️ 02:14  ⏳ 01:18      │
│  [🛑 Cancelar]           │
└───────────────────────────┘

[Automaticamente ao completar]

┌───────────────────────────┐
│  📊 Resultados            │
│  Mean Return: +15.2%      │
│  Sharpe: 1.85             │
│  [Gráficos atualizados]   │
└───────────────────────────┘
```

---

## 🎯 Benefícios da Nova Interface

1. **Configuração Visual**
   - Não precisa lembrar sintaxe CLI
   - Validação instantânea de valores
   - Feedback visual em tempo real

2. **Estimativa de Tempo**
   - Sabe quando esperar resultados
   - Pode planejar outras tarefas
   - Evita timeout mental

3. **Progresso Transparente**
   - Vê que sistema está funcionando
   - Tracking de iterações
   - Tempo restante estimado

4. **Experiência Profissional**
   - Interface moderna e polida
   - Animações suaves
   - Design responsivo

5. **Cancelamento Gracioso**
   - Botão sempre disponível
   - Confirmação antes de cancelar
   - Feedback imediato

---

## 🔮 Melhorias Futuras Sugeridas

### 1. Progresso Real do Backend
Implementar endpoint de status:
```python
# services/execution-engine/src/main.py
@app.get("/api/monte-carlo/status/{task_id}")
async def get_simulation_status(task_id: str):
    # Retorna progresso real do Redis
    return {
        "status": "running",
        "current": 523,
        "total": 1000,
        "elapsed": 134,
        "strategy": "momentum"
    }
```

### 2. WebSocket para Atualizações Push
```javascript
// Frontend recebe updates instantâneos
const ws = new WebSocket('ws://localhost:3008/ws/monte-carlo');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateProgress(data.current, data.total);
};
```

### 3. Histórico de Simulações
```javascript
// Salvar configurações usadas
localStorage.setItem('last_config', JSON.stringify(config));

// Botão "Repetir última simulação"
<button onclick="repeatLastSim()">🔄 Repetir</button>
```

### 4. Comparação Lado a Lado
```javascript
// Selecionar múltiplas estratégias
<checkbox> Momentum
<checkbox> MACD+RSI
<checkbox> Trend Following

[Comparar Estratégias]
→ Executa todas e gera relatório comparativo
```

### 5. Exportação de Resultados
```javascript
// Baixar relatório em PDF/Excel
<button onclick="exportPDF()">📄 Exportar PDF</button>
<button onclick="exportCSV()">📊 Exportar CSV</button>
```

---

## 📚 Recursos Adicionais

### Arquivos Relacionados
- `frontend/views/monte-carlo.ejs` - Template principal
- `services/execution-engine/src/main.py` - API de simulação
- `services/execution-engine/src/monte_carlo.py` - Simulador
- `services/execution-engine/src/monte_carlo_adapters.py` - Estratégias

### Endpoints da API
```
POST   /api/monte-carlo/simulate
GET    /api/monte-carlo/reports
GET    /api/monte-carlo/report/{filename}
```

### Bibliotecas Usadas
- **Frontend**: Bootstrap 5, Chart.js 4.4.0, jQuery
- **Backend**: FastAPI, asyncpg, pandas, numpy
- **Infraestrutura**: Docker, TimescaleDB, Redis

---

## 🤝 Contribuindo

Quer melhorar o lançador interativo? Sugestões:

1. **Adicione novos parâmetros configuráveis**
   - Edite `showConfigModal()` em monte-carlo.ejs
   - Adicione campos no modal HTML

2. **Melhore a estimativa de tempo**
   - Ajuste fórmula exponencial
   - Implemente machine learning baseado em histórico

3. **Crie temas customizáveis**
   - Adicione seletor de tema
   - CSS variables para cores

4. **Implemente notificações**
   - Browser notifications quando completar
   - Som de conclusão (opcional)

---

## 📝 Changelog

### v1.0.0 (2024-12-10)
- ✨ Lançador interativo de simulações
- 📊 Painel de progresso em tempo real
- ⏱️ Estimativa de tempo dinâmica
- 🎨 Interface moderna com Bootstrap 5
- 🔧 5 estratégias pré-configuradas
- 📈 Validação de parâmetros
- 🛑 Cancelamento gracioso
- 📱 Design responsivo

---

**Desenvolvido com ❤️ para a AI Trading Platform**

© 2024 - Todos os direitos reservados
