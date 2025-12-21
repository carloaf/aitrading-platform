# 📊 GUIA COMPLETO: COMO USAR GRAFANA NO SISTEMA DE TRADING

**Data**: 21 de Dezembro de 2025  
**Autor**: Sistema AI Trading Platform  
**Versão**: 1.0

---

## 📑 ÍNDICE

1. [O que é Grafana?](#o-que-é-grafana)
2. [Setup Inicial (5 minutos)](#setup-inicial)
3. [Acessando o Dashboard](#acessando-o-dashboard)
4. [Entendendo as Métricas](#entendendo-as-métricas)
5. [Uso Prático Diário](#uso-prático-diário)
6. [Troubleshooting](#troubleshooting)
7. [Casos de Uso Avançados](#casos-de-uso-avançados)

---

## 🎯 O QUE É GRAFANA?

**Grafana** é uma plataforma de visualização de dados em tempo real que permite:

✅ **Monitorar performance** do sistema de trading 24/7  
✅ **Alertas automáticos** quando métricas ficam ruins  
✅ **Gráficos históricos** para análise de tendências  
✅ **Dashboards customizáveis** com múltiplos painéis  
✅ **Integração com Prometheus** (coleta de métricas)

### Stack de Monitoramento

```
┌─────────────────┐
│  WFO Execution  │  ← Você executa wfo_simple.sh
└────────┬────────┘
         │ gera
         ▼
┌─────────────────┐
│  history.csv    │  ← Armazena resultados WFO
└────────┬────────┘
         │ lê
         ▼
┌─────────────────┐
│ wfo_exporter.py │  ← Converte CSV → Prometheus
│   (porta 9090)  │
└────────┬────────┘
         │ scrape
         ▼
┌─────────────────┐
│   Prometheus    │  ← Coleta métricas a cada 10s
│   (porta 9091)  │
└────────┬────────┘
         │ query
         ▼
┌─────────────────┐
│     Grafana     │  ← Visualiza em dashboard
│   (porta 3001)  │  ← http://localhost:3001
└─────────────────┘
```

---

## 🚀 SETUP INICIAL

### Passo 1: Garantir que WFO tem dados

```bash
cd /home/dellno/worksapace/aitrading-platform

# Verificar se CSV de histórico existe
cat logs/wfo/history.csv | tail -5

# Se não existir, executar WFO primeiro:
bash scripts/wfo_simple.sh
```

**Output esperado**:
```csv
date,period,return,sharpe,max_dd,win_rate,trades
2025-05-01,may_2025,1.89,0.87,3.45,55.6,11
2025-04-01,apr_2025,2.72,0.92,4.12,50.0,12
```

### Passo 2: Iniciar Stack de Monitoramento

```bash
# Build e start (primeira vez demora ~30 segundos)
docker compose -f monitoring/docker-compose.monitoring.yml up -d

# Verificar status
docker compose -f monitoring/docker-compose.monitoring.yml ps
```

**Output esperado**:
```
NAME                    STATUS    PORTS
wfo-metrics-exporter    Up        0.0.0.0:9090->9090/tcp
wfo-prometheus          Up        0.0.0.0:9091->9090/tcp
wfo-grafana             Up        0.0.0.0:3001->3001/tcp
```

### Passo 3: Verificar que Métricas Estão Sendo Exportadas

```bash
# Health check do exporter
curl http://localhost:9090/health

# Ver métricas (deve mostrar 8 métricas)
curl http://localhost:9090/metrics | grep wfo_
```

**Output esperado**:
```
wfo_return_percent 0.37
wfo_sharpe_ratio 1.73
wfo_max_drawdown_percent 0.21
wfo_win_rate_percent 100.00
wfo_total_trades 1
wfo_robustness_score 90
wfo_runs_total 11
wfo_last_run_timestamp 1766351598
```

✅ **Pronto! Stack rodando com sucesso.**

---

## 🌐 ACESSANDO O DASHBOARD

### Passo 1: Abrir Grafana no Navegador

```bash
# Opção 1: Abrir automaticamente (Linux/Mac)
xdg-open http://localhost:3001   # Linux
open http://localhost:3001        # Mac

# Opção 2: Abrir manualmente
# Navegador → http://localhost:3001
```

### Passo 2: Fazer Login

**Tela de Login**:
- **Usuário**: `admin`
- **Senha**: `admin`

**Na primeira vez, será pedido para alterar a senha**:
- Você pode clicar em "Skip" ou definir uma nova senha

### Passo 3: Acessar Dashboard WFO

**Opções**:

1. **URL Direta**: http://localhost:3001/d/wfo-dashboard
2. **Menu**: Home → Dashboards → "WFO Performance Monitor"
3. **Search**: Clicar na lupa (🔍) e digitar "WFO"

---

## 📊 ENTENDENDO AS MÉTRICAS

O dashboard tem **9 painéis** organizados em 3 linhas:

### 📍 LINHA 1: INDICADORES PRINCIPAIS (Gauges)

#### 1. **Last Return %**
- **Verde** (>2%): Excelente performance
- **Amarelo** (0-2%): Performance moderada
- **Vermelho** (<0%): Performance negativa

**Exemplo**:
```
+0.37% ← Verde (positivo, mas abaixo de 2%)
```

#### 2. **Sharpe Ratio**
- **Verde** (>1.5): Qualidade excelente (risk-adjusted return)
- **Amarelo** (0.5-1.5): Qualidade boa
- **Vermelho** (<0.5): Qualidade ruim

**Exemplo**:
```
1.73 ← Verde (excelente risk/reward)
```

#### 3. **Robustness Score**
- **Verde** (<50): Sistema robusto, sem overfitting
- **Amarelo** (50-70): Atenção necessária
- **Vermelho** (>70): Possível overfitting, revisar parâmetros

**Cálculo**:
```python
# Heurística (0-100):
return_penalty = abs(return) if return < 0 else 0
sharpe_penalty = max(0, 1 - sharpe) * 30
dd_penalty = max(0, max_dd - 10) * 2
wr_penalty = max(0, 50 - win_rate) * 0.5

robustness = return_penalty*20 + sharpe_penalty + dd_penalty + wr_penalty
```

**Exemplo**:
```
90/100 ← Verde (sistema muito robusto!)
```

---

### 📈 LINHA 2: GRÁFICOS TEMPORAIS (Time Series)

#### 4. **Return Over Time**
- **Linha azul**: Evolução do retorno % ao longo do tempo
- **Eixo X**: Timestamp de cada execução WFO
- **Eixo Y**: Return %

**Como interpretar**:
- **Tendência ascendente** 📈: Sistema melhorando
- **Tendência descendente** 📉: Sistema degradando
- **Oscilações grandes**: Mercado volátil ou parâmetros instáveis
- **Linha estável**: Sistema consistente

**Exemplo visual**:
```
Return %
   4 |           ●
   3 |       ●       ●
   2 |   ●               ●
   1 | ●                     ●
   0 |_________________________
     Jan  Feb  Mar  Apr  May
```

#### 5. **Robustness Score Over Time**
- **Linha verde**: Evolução do score de robustez
- **Linha vermelha tracejada**: Threshold de 50 (limite aceitável)

**Como interpretar**:
- **Abaixo de 50** (zona verde): ✅ Sistema saudável
- **Entre 50-70** (zona amarela): ⚠️ Monitorar de perto
- **Acima de 70** (zona vermelha): 🚨 Recalibração necessária

---

### 📊 LINHA 3: ESTATÍSTICAS (Stat Panels)

#### 6. **Max Drawdown**
- **Verde** (<10%): Risco controlado
- **Amarelo** (10-15%): Risco moderado
- **Vermelho** (>15%): Risco elevado

**Exemplo**: `0.21%` ← Excelente controle de risco!

#### 7. **Win Rate**
- **Verde** (>55%): Alta taxa de acerto
- **Amarelo** (45-55%): Taxa normal
- **Vermelho** (<45%): Taxa baixa, revisar estratégia

**Exemplo**: `100.0%` ← Perfeito (mas pode ser overfitting se poucos trades)

#### 8. **Total Trades**
- **Indicador de atividade** do sistema
- **Muito baixo** (<5): Filtros muito rigorosos
- **Normal** (10-20): Sistema balanceado
- **Muito alto** (>30): Overtrading

**Exemplo**: `1` ← Poucos trades (período curto de teste)

#### 9. **Total WFO Runs**
- **Counter**: Total de execuções desde o início
- **Útil para**: Rastrear quantas vezes WFO foi executado

**Exemplo**: `11 runs` ← 11 validações WFO realizadas

---

## 💼 USO PRÁTICO DIÁRIO

### Cenário 1: Verificação Matinal (2 minutos)

**Objetivo**: Ver se sistema está saudável

```bash
# 1. Abrir dashboard
open http://localhost:3001/d/wfo-dashboard

# 2. Verificar 3 indicadores principais:
✅ Return verde/amarelo? → Sistema lucrativo
✅ Sharpe > 1.0? → Qualidade boa
✅ Robustness < 70? → Sem overfitting

# 3. Se tudo verde → Sistema OK
# 4. Se algo vermelho → Investigar detalhes
```

**Tempo**: ~2 minutos

---

### Cenário 2: Executar WFO e Ver Resultados (5 minutos)

**Objetivo**: Validar novo período e ver impacto no dashboard

```bash
# 1. Executar WFO para último mês
cd /home/dellno/worksapace/aitrading-platform
bash scripts/wfo_simple.sh

# Output:
# ✅ Return: +2.34%
# ✅ Sharpe: 1.25
# ✅ Win Rate: 69.2%
# 📝 Saved to logs/wfo/history.csv

# 2. Aguardar 10 segundos (Prometheus scrape)
sleep 10

# 3. Refresh dashboard no navegador
# F5 ou Ctrl+R

# 4. Ver métricas atualizadas:
# - Gauges atualizam para valores novos
# - Gráficos temporais adicionam novo ponto
# - Counter "Total Runs" incrementa +1
```

**Tempo**: ~5 minutos

---

### Cenário 3: Análise de Tendência (10 minutos)

**Objetivo**: Identificar se sistema está melhorando ou piorando

```bash
# 1. Abrir "Return Over Time" no dashboard

# 2. Ajustar time range (canto superior direito):
# - Last 7 days: Ver semana passada
# - Last 30 days: Ver mês passado
# - Last 90 days: Ver trimestre

# 3. Análise visual:
```

**Padrões a procurar**:

✅ **SAUDÁVEL**: Retorno oscila entre 0-5%, sem quedas bruscas
```
Return %
   5 |     ●   ●       ●
   3 | ●           ●       ●
   1 |                         ●
   0 |_________________________
```

⚠️ **ATENÇÃO**: Tendência descendente contínua
```
Return %
   5 | ●
   3 |     ●
   1 |         ●
  -1 |             ●
  -3 |                 ●  ← Degradação!
```

🚨 **CRÍTICO**: Múltiplos períodos negativos consecutivos
```
Return %
   0 |_________________________
  -2 |             ●   ●   ●  ← 3 negativos!
  -4 |         ●
```

---

### Cenário 4: Configurar Alerta (15 minutos)

**Objetivo**: Receber notificação quando Robustness Score > 70

```bash
# No Grafana:

# 1. Ir ao painel "Robustness Score"
# 2. Clicar no título → Edit
# 3. Aba "Alert" → Create alert rule
# 4. Configurar:
#    - Name: "High Robustness Alert"
#    - Condition: WHEN last() OF wfo_robustness_score IS ABOVE 70
#    - Evaluate every: 1m
#    - For: 5m (tolerar 5min acima antes de alertar)
# 5. Notification:
#    - Contact point: Email/Slack/Telegram
# 6. Save dashboard
```

**Resultado**: Você receberá alerta quando sistema precisar recalibração

---

## 🔧 TROUBLESHOOTING

### Problema 1: Dashboard não carrega

**Sintoma**: Página em branco ou erro "Dashboard not found"

**Solução**:
```bash
# 1. Verificar se container está up
docker compose -f monitoring/docker-compose.monitoring.yml ps

# 2. Ver logs do Grafana
docker logs wfo-grafana

# 3. Reiniciar stack
docker compose -f monitoring/docker-compose.monitoring.yml restart

# 4. Acessar novamente
open http://localhost:3001/d/wfo-dashboard
```

---

### Problema 2: Métricas não atualizam

**Sintoma**: Dashboard mostra valores antigos mesmo após executar WFO

**Solução**:
```bash
# 1. Verificar se CSV foi atualizado
tail -3 logs/wfo/history.csv

# 2. Verificar se exporter está lendo CSV
curl http://localhost:9090/metrics | grep wfo_return

# 3. Ver logs do exporter
docker logs wfo-metrics-exporter

# 4. Se necessário, reiniciar exporter
docker restart wfo-metrics-exporter

# 5. Aguardar 10s e refresh dashboard
```

---

### Problema 3: Erro "Connection refused"

**Sintoma**: Grafana não conecta ao Prometheus

**Solução**:
```bash
# 1. Verificar se Prometheus está up
docker ps | grep wfo-prometheus

# 2. Testar manualmente
curl http://localhost:9091/api/v1/query?query=wfo_return_percent

# 3. Ver configuração do datasource no Grafana:
#    Settings → Data Sources → Prometheus
#    URL deve ser: http://wfo-prometheus:9090

# 4. Test & Save
```

---

### Problema 4: Porta 3001 já em uso

**Sintoma**: `Error: port 3001 already in use`

**Solução**:
```bash
# Opção 1: Parar processo na porta 3001
sudo lsof -ti:3001 | xargs kill -9

# Opção 2: Alterar porta do Grafana
# Editar monitoring/docker-compose.monitoring.yml:
#   ports:
#     - "3001:3001"  ← Usar porta 3001

# Reiniciar
docker compose -f monitoring/docker-compose.monitoring.yml up -d

# Acessar em nova porta
open http://localhost:3001
```

---

## 🎓 CASOS DE USO AVANÇADOS

### Caso 1: Comparar Performance Multi-Asset

**Objetivo**: Ver BTC vs ETH vs SOL lado a lado

```bash
# 1. Executar WFO multi-asset
bash scripts/wfo_multi_asset.sh "dec_2025" "2025-12-01" "2025-12-21"

# 2. No Grafana, criar novo dashboard:
#    - Add panel
#    - Query: wfo_return_percent{symbol=~"BTC|ETH|SOL"}
#    - Visualization: Time series
#    - Legend: {{symbol}}

# 3. Ver 3 linhas (BTC azul, ETH verde, SOL amarelo)
```

---

### Caso 2: Criar Dashboard Customizado

**Objetivo**: Painel com métricas específicas do seu interesse

```bash
# No Grafana:

# 1. Dashboards → New Dashboard
# 2. Add visualization
# 3. Query editor:
#    - Metric: wfo_sharpe_ratio
#    - Visualization type: Gauge
#    - Thresholds: 0 (red), 0.5 (yellow), 1.5 (green)
# 4. Panel options:
#    - Title: "Sharpe Ratio Custom"
#    - Description: "Minha métrica favorita"
# 5. Save dashboard
```

---

### Caso 3: Exportar Relatório PDF

**Objetivo**: Gerar PDF do dashboard para compartilhar

```bash
# No Grafana:

# 1. Abrir dashboard WFO
# 2. Share dashboard (ícone 🔗 no canto superior direito)
# 3. Export → Snapshot
# 4. Create local snapshot
# 5. Download PDF

# Ou via CLI (requer plugin):
docker exec wfo-grafana grafana-cli plugins install grafana-image-renderer
docker restart wfo-grafana
```

---

## 📚 RECURSOS ADICIONAIS

### Links Úteis

- **Grafana Dashboard**: http://localhost:3001/d/wfo-dashboard
- **Prometheus UI**: http://localhost:9091
- **Métricas Raw**: http://localhost:9090/metrics
- **Health Check**: http://localhost:9090/health

### Documentação

- **Grafana Docs**: https://grafana.com/docs/
- **Prometheus Query**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **PromQL Examples**: https://prometheus.io/docs/prometheus/latest/querying/examples/

### Comandos Úteis

```bash
# Ver logs
docker compose -f monitoring/docker-compose.monitoring.yml logs -f

# Parar stack
docker compose -f monitoring/docker-compose.monitoring.yml down

# Rebuild (após mudanças)
docker compose -f monitoring/docker-compose.monitoring.yml up -d --build

# Limpar volumes (reset total)
docker compose -f monitoring/docker-compose.monitoring.yml down -v
```

---

## ✅ CHECKLIST RÁPIDO

**Setup Inicial** (apenas 1ª vez):
- [ ] Executar `wfo_simple.sh` para gerar history.csv
- [ ] Iniciar stack: `docker compose -f monitoring/docker-compose.monitoring.yml up -d`
- [ ] Acessar http://localhost:3001
- [ ] Login: admin/admin
- [ ] Dashboard WFO disponível

**Uso Diário**:
- [ ] Abrir dashboard WFO
- [ ] Verificar 3 gauges (return, sharpe, robustness)
- [ ] Se algo vermelho → investigar
- [ ] Se tudo verde → sistema OK

**Após Executar WFO**:
- [ ] Aguardar 10s (scrape interval)
- [ ] Refresh dashboard (F5)
- [ ] Ver valores atualizados
- [ ] Verificar gráfico temporal (nova linha adicionada)

---

## 🎯 RESUMO EXECUTIVO

**Grafana** te permite monitorar o sistema de trading **sem precisar abrir terminal**:

✅ **3 Gauges coloridos** mostram saúde do sistema de relance  
✅ **Gráficos temporais** revelam tendências ao longo do tempo  
✅ **Atualização automática** a cada 10 segundos  
✅ **Alertas** te notificam quando algo fica ruim  
✅ **Zero SQL/código** - tudo visual e intuitivo  

**Tempo de Setup**: 5 minutos  
**Uso Diário**: 2 minutos (verificação matinal)  
**ROI**: Detectar problemas **antes** de perder dinheiro 🚀

---

**Dúvidas?** Abra issue no GitHub ou consulte logs: `docker logs wfo-grafana`
