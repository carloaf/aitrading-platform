# Dashboard de Histórico - Guia de Uso

## 📊 Visão Geral

O Dashboard de Histórico fornece visualização completa do desempenho das sessões de paper trading, incluindo:

- **Equity Curve**: Gráfico em tempo real da evolução do capital
- **Métricas de Performance**: Sharpe Ratio, Win Rate, ROI, Max Drawdown
- **Histórico de Trades**: Tabela detalhada com todos os trades executados
- **Atualização Automática**: Dados atualizados a cada 10 segundos

## 🚀 Acesso Rápido

```bash
# Abrir dashboard no navegador
http://localhost:8081/history

# Monitorar via terminal
./scripts/monitor_history.sh

# Verificar sessões ativas
./scripts/check_sessions.sh
```

## 📈 Funcionalidades

### 1. Seletor de Sessões
- Dropdown com todas as sessões de paper trading
- Filtro por símbolo e estratégia
- Indicador de status (Ativo/Inativo)

### 2. Cards de Métricas

#### 💰 Saldo Atual
- Valor atual da conta
- Comparação com saldo inicial
- Variação percentual
- Indicador visual (verde/vermelho)

#### 📈 ROI (Return on Investment)
- Retorno sobre investimento percentual
- Cálculo: `((Saldo Atual - Saldo Inicial) / Saldo Inicial) × 100`

#### 🎯 Taxa de Acerto (Win Rate)
- Percentual de trades lucrativos
- Cálculo: `(Trades Vencedores / Total de Trades) × 100`
- Indicador:
  - Verde: ≥ 50%
  - Vermelho: < 50%

#### ⚡ Sharpe Ratio
- Medida de retorno ajustado ao risco
- Interpretação:
  - `> 2.0`: Excelente
  - `1.0 - 2.0`: Bom
  - `0.5 - 1.0`: Aceitável
  - `< 0.5`: Ruim

#### 📉 Max Drawdown
- Maior queda percentual do capital
- Indica o risco máximo observado
- Sempre negativo

#### 🔢 Total de Trades
- Número total de operações executadas
- Inclui BUY e SELL

### 3. Gráfico de Equity Curve

**Características:**
- Linha azul: Capital atual
- Linha pontilhada: Capital inicial (referência)
- Tooltips interativos ao passar o mouse
- Zoom e pan habilitados
- Escala temporal automática (minutos/horas/dias)

**Interpretação:**
- Linha ascendente: Estratégia lucrativa
- Linha descendente: Estratégia com prejuízo
- Volatilidade: Variação do risco

### 4. Tabela de Trades

**Colunas:**
- **Data/Hora**: Timestamp da execução (formato BR)
- **Tipo**: Badge colorido (BUY verde / SELL vermelho)
- **Símbolo**: Par de trading (BTCUSDT, ETHUSDT, etc.)
- **Preço**: Preço de execução em USD
- **Quantidade**: Volume negociado em unidades da cripto
- **Valor**: Montante total da operação ($)
- **P&L**: Lucro/Prejuízo em dólares
- **P&L %**: Variação percentual
- **Saldo Após**: Capital após a operação

**Funcionalidades:**
- Ordenação por coluna (clique no header)
- Scroll horizontal em telas pequenas
- Hover highlighting
- Formatação monetária automática

### 5. Atualização em Tempo Real

**Comportamentos:**
- Auto-refresh a cada 10 segundos (padrão)
- Contador regressivo visível
- Toggle para habilitar/desabilitar
- Indicador de status (verde quando ativo)
- Botão manual de atualização

## 🔍 Métricas Calculadas

### Sharpe Ratio
```
Sharpe = (Retorno Médio - Taxa Livre de Risco) / Desvio Padrão dos Retornos

Onde:
- Retorno Médio: Média dos retornos percentuais de cada trade
- Taxa Livre de Risco: 0% (assumido para simplificação)
- Desvio Padrão: Volatilidade dos retornos
```

### Win Rate
```
Win Rate = (Número de Trades Lucrativos / Total de Trades) × 100
```

### Max Drawdown
```
Max DD = ((Pico - Vale) / Pico) × 100

Cálculo sequencial:
1. Encontrar o pico histórico do capital
2. Calcular a queda até o vale subsequente
3. Retornar a maior queda percentual
```

### Profit Factor
```
Profit Factor = Lucro Total dos Trades Vencedores / Prejuízo Total dos Trades Perdedores

Interpretação:
- > 2.0: Excelente
- 1.5 - 2.0: Bom
- 1.0 - 1.5: Mediano
- < 1.0: Não lucrativo
```

## 📱 Interface Responsiva

### Desktop (> 1200px)
- 6 cards de métricas em linha
- Gráfico full-width
- Tabela com todas as colunas

### Tablet (768px - 1200px)
- 3 cards por linha
- Gráfico adaptado
- Scroll horizontal na tabela

### Mobile (< 768px)
- 1-2 cards por linha
- Gráfico ajustado
- Tabela compacta com scroll

## 🎨 Tema Dark

**Paleta de Cores:**
- Background: `#0a0e27` (azul escuro)
- Cards: `#1e2746` (gradiente)
- Borders: `#2d3561` (cinza-azulado)
- Accent: `#00d4ff` (ciano)
- Text: `#e0e0e0` (branco suave)

**Indicadores:**
- Positivo: `#00ff88` (verde)
- Negativo: `#ff4757` (vermelho)
- Neutro: `#ffa502` (laranja)

## 🔧 Troubleshooting

### Sessões não aparecem no dropdown
```bash
# Verificar se execution-engine está rodando
docker ps | grep execution-engine

# Testar API manualmente
curl http://localhost:3008/api/history/all-sessions | jq .

# Verificar logs
docker logs aitrading-execution-engine --tail 50
```

### Gráfico não renderiza
```bash
# Verificar se há dados de trades
curl "http://localhost:3008/api/history/trades/momentum_live_v2" | jq '.trades | length'

# Se retornar 0, aguardar primeiro trade
./scripts/check_sessions.sh
```

### Métricas mostram "--"
- **Causa**: Sessão sem trades executados
- **Solução**: Aguardar estratégia coletar candles e gerar sinais

### Erro 404 na página
```bash
# Verificar se rota foi adicionada
grep "/history" frontend/server.js

# Rebuild frontend
docker compose up -d --build frontend

# Verificar logs
docker logs aitrading-frontend --tail 30
```

### Dados desatualizados
1. Desabilitar cache do navegador (F12 > Network > Disable cache)
2. Forçar refresh (Ctrl + Shift + R)
3. Verificar auto-refresh está habilitado
4. Testar API diretamente

## 📊 Exemplos de Uso

### Monitoramento Contínuo
```bash
# Terminal 1: Dashboard visual
watch -n 5 ./scripts/monitor_history.sh

# Terminal 2: Logs em tempo real
docker logs -f aitrading-execution-engine

# Terminal 3: Servidor web
# Abrir http://localhost:8081/history no navegador
```

### Análise de Performance
```bash
# Verificar sessão específica
SESSION_ID="momentum_live_v2"

# Performance detalhada
curl "http://localhost:3008/api/history/performance/${SESSION_ID}" | jq .

# Últimos 10 trades
curl "http://localhost:3008/api/history/trades/${SESSION_ID}" | jq '.trades[:10]'

# Equity curve
curl "http://localhost:3008/api/history/performance/${SESSION_ID}" | jq '.equity_curve'
```

### Comparação de Estratégias
```bash
# Buscar todas as sessões
curl "http://localhost:3008/api/history/all-sessions" | jq -r '
  .sessions[] | 
  "\(.strategy_name) | \(.symbol) | ROI: \(.roi)% | Trades: \(.total_trades)"
' | sort -k5 -nr
```

## 🚀 Próximos Passos

Após visualizar o dashboard:

1. **Aguardar Primeiro Trade**: Estratégias precisam coletar candles (~15-20 min)
2. **Validar Persistência**: Verificar se trades são salvos no banco
3. **Analisar Métricas**: Avaliar performance inicial
4. **Ajustar Parâmetros**: Se necessário, modificar estratégias
5. **Monte Carlo**: Implementar simulação estocástica (próxima fase)

## 📞 Suporte

Em caso de dúvidas ou problemas:

```bash
# Verificar status geral
./scripts/validate-platform.sh

# Verificar sessões
./scripts/check_sessions.sh

# Logs completos
docker compose logs execution-engine | tail -100
```

---

**Dashboard URL**: http://localhost:8081/history  
**APIs Base URL**: http://localhost:3008/api/history/  
**Documentação Completa**: `/docs` (FastAPI Swagger)
