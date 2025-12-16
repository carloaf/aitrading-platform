# PASSO 26: Walk-Forward Optimization Automation (2026)

**Data**: 16 de Dezembro de 2025  
**Objetivo**: Automatizar WFO mensal com alertas de degradação e pipeline de recalibração

---

## 📋 VISÃO GERAL

Sistema de monitoramento automático que:
1. ✅ Executa backtest do mês anterior automaticamente
2. ✅ Detecta degradação de performance vs mês anterior
3. ✅ Gera alertas baseados em thresholds críticos
4. ✅ Recomenda recalibração quando necessário
5. ✅ Mantém histórico em CSV para análise de tendências

---

## 🚀 COMO USAR

### Execução Manual

```bash
# Executar WFO do mês anterior
./scripts/wfo_monthly_automation.sh

# Com parâmetros customizados
API_URL=http://localhost:3008 \
SYMBOL=ETHUSDT \
TIMEFRAME=4h \
./scripts/wfo_monthly_automation.sh
```

### Automação via Cron

```bash
# Executar no dia 5 de cada mês às 02:00
0 2 5 * * /home/user/aitrading-platform/scripts/wfo_monthly_automation.sh >> /var/log/wfo_cron.log 2>&1

# Com notificação por email em caso de falha
0 2 5 * * /home/user/aitrading-platform/scripts/wfo_monthly_automation.sh || mail -s "WFO Alert" admin@example.com < /var/log/wfo_cron.log
```

---

## ⚙️ CONFIGURAÇÃO

### Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `API_URL` | `http://localhost:3008` | URL do execution-engine |
| `SYMBOL` | `BTCUSDT` | Par a ser testado |
| `TIMEFRAME` | `1h` | Timeframe dos candles |
| `INITIAL_CAPITAL` | `100000` | Capital inicial do backtest |

### Thresholds de Alerta

| Threshold | Valor | Descrição |
|-----------|-------|-----------|
| `ALERT_SHARPE_MIN` | 0.5 | Sharpe < 0.5 = alerta |
| `ALERT_DD_MAX` | 10.0 | Max DD > 10% = alerta |
| `ALERT_WIN_RATE_MIN` | 45.0 | Win rate < 45% = alerta |
| `ALERT_RETURN_MIN` | -2.0 | Return < -2% = alerta crítico |
| `DEGRADATION_THRESHOLD` | -20 | -20% vs mês anterior = crítico |

Edite diretamente em `wfo_monthly_automation.sh` para ajustar.

---

## 📊 OUTPUTS

### 1. Log Console

```
[2026-01-05 02:00:15] ==========================================
[2026-01-05 02:00:15] WALK-FORWARD OPTIMIZATION - 2026
[2026-01-05 02:00:15] ==========================================
[2026-01-05 02:00:15] 
[2026-01-05 02:00:15] 📅 Período: 2025-12-01 → 2025-12-31
[2026-01-05 02:00:15] 
[2026-01-05 02:00:18] 📊 RESULTADOS:
[2026-01-05 02:00:18]    Return: +3.45%
[2026-01-05 02:00:18]    Sharpe: 1.82
[2026-01-05 02:00:18]    Max DD: 4.23%
[2026-01-05 02:00:18]    Win Rate: 62.5%
[2026-01-05 02:00:18]    Trades: 16
[2026-01-05 02:00:18] 
[2026-01-05 02:00:18] 📉 ANÁLISE DE DEGRADAÇÃO:
[2026-01-05 02:00:18]    OK: -12.5% vs mês anterior
[2026-01-05 02:00:18] 
[2026-01-05 02:00:18] 🔔 ALERTAS:
[2026-01-05 02:00:18] ✅ Todas as métricas dentro dos limites
[2026-01-05 02:00:18] 
[2026-01-05 02:00:18] 🎯 RECOMENDAÇÃO:
[2026-01-05 02:00:18] ✅ SISTEMA OPERANDO NORMALMENTE
[2026-01-05 02:00:18]    → Sem necessidade de recalibração
[2026-01-05 02:00:18] 
[2026-01-05 02:00:18] ✅ WFO concluído com sucesso
```

### 2. Arquivo de Log

Local: `logs/wfo/wfo_YYYYMM.log`

Contém histórico completo de todas as execuções do mês.

### 3. Histórico CSV

Local: `logs/wfo/history.csv`

```csv
date,start_date,end_date,return,sharpe,sortino,pf,dd,wr,trades
2026-01-05,2025-12-01,2025-12-31,3.45,1.82,1.45,1.85,4.23,62.5,16
2026-02-05,2026-01-01,2026-01-31,1.23,0.92,0.68,1.12,6.78,51.2,14
```

Use para análise de tendências:

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('logs/wfo/history.csv')
df.plot(x='date', y=['return', 'sharpe', 'dd'], subplots=True, figsize=(12, 8))
plt.savefig('wfo_trends.png')
```

---

## 🔔 SISTEMA DE ALERTAS

### Níveis de Alerta

#### ✅ **OK** (Exit code 0)
- Todas as métricas dentro dos limites
- Degradação < 20% vs mês anterior
- Return > -2%

**Ação**: Nenhuma

---

#### ⚠️ **WARNING** (Exit code 1)
Gatilhos:
- Sharpe < 0.5
- Win Rate < 45%
- Degradação entre -20% e -40%

**Ação**: Monitoramento ativo, preparar ajustes

---

#### 🔴 **CRITICAL** (Exit code 2)
Gatilhos:
- Return < -2%
- Max DD > 10%
- Degradação > 40%

**Ação**: Recalibração urgente ou pausar trading

---

## 🎯 RECOMENDAÇÕES DE RECALIBRAÇÃO

O script analisa métricas e sugere ações:

### 🚨 **RECALIBRAÇÃO URGENTE** (Score ≥ 5)
```
Condições:
- Return negativo
- Sharpe < 1.0
- Max DD > 10%
- Win Rate < 50%

Ações sugeridas:
1. Pausar trading imediatamente
2. Revisar estratégias ativas
3. Ajustar risk_per_trade (reduzir para 1%)
4. Aumentar hysteresis (8 → 10)
5. Aumentar min_quality (70 → 80)
```

---

### ⚠️ **RECALIBRAÇÃO RECOMENDADA** (Score 3-4)
```
Condições:
- Sharpe < 1.0 ou Win Rate < 50%
- DD elevado mas < 10%

Ações sugeridas:
1. Ajustar TP multipliers (2.5x → 3.0x)
2. Revisar chop-protection (ativar se OFF)
3. Testar Kelly Position Sizing
4. Aumentar regime_confirmation_threshold
```

---

### 🟡 **MONITORAMENTO ATIVO** (Score 1-2)
```
Condições:
- Uma ou duas métricas levemente abaixo do ideal

Ações sugeridas:
1. Continuar operação normal
2. Monitorar próximo mês
3. Preparar ajustes preventivos
```

---

### ✅ **OPERAÇÃO NORMAL** (Score 0)
```
Todas as métricas saudáveis

Ações:
- Manter parâmetros atuais
- Documentar configuração bem-sucedida
```

---

## 📈 ANÁLISE DE TENDÊNCIAS

### Detectar Degradação Gradual

```python
import pandas as pd

df = pd.read_csv('logs/wfo/history.csv')

# Calcular média móvel de 3 meses
df['return_ma3'] = df['return'].rolling(3).mean()
df['sharpe_ma3'] = df['sharpe'].rolling(3).mean()

# Detectar tendência negativa
if df['return_ma3'].iloc[-1] < df['return_ma3'].iloc[-4]:
    print("⚠️ Degradação gradual detectada nos últimos 3 meses")
```

### Visualizar Performance Histórica

```bash
# Gerar gráfico de tendências
python3 << EOF
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('logs/wfo/history.csv')
df['date'] = pd.to_datetime(df['date'])

fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Return
axes[0, 0].plot(df['date'], df['return'], marker='o')
axes[0, 0].axhline(y=0, color='r', linestyle='--')
axes[0, 0].set_title('Monthly Return (%)')
axes[0, 0].grid(True)

# Sharpe
axes[0, 1].plot(df['date'], df['sharpe'], marker='o', color='green')
axes[0, 1].axhline(y=1.0, color='r', linestyle='--')
axes[0, 1].set_title('Sharpe Ratio')
axes[0, 1].grid(True)

# Max DD
axes[1, 0].plot(df['date'], df['dd'], marker='o', color='red')
axes[1, 0].axhline(y=10, color='orange', linestyle='--')
axes[1, 0].set_title('Max Drawdown (%)')
axes[1, 0].grid(True)

# Win Rate
axes[1, 1].plot(df['date'], df['wr'], marker='o', color='blue')
axes[1, 1].axhline(y=50, color='r', linestyle='--')
axes[1, 1].set_title('Win Rate (%)')
axes[1, 1].grid(True)

plt.tight_layout()
plt.savefig('logs/wfo/trends.png', dpi=150)
print("✅ Gráfico salvo em logs/wfo/trends.png")
EOF
```

---

## 🔧 AJUSTES BASEADOS EM ALERTAS

### Degradação de Return

```bash
# Testar com Kelly Position Sizing habilitado
curl -X POST http://localhost:3008/api/meta-backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "use_kelly_sizing": true,
    "kelly_fraction": 0.25
  }'
```

### Sharpe Baixo

```bash
# Aumentar TP multiplier para melhorar risk/reward
curl -X POST http://localhost:3008/api/meta-backtest/run \
  -d '{
    "risk_per_trade": 0.015  # Reduzir de 2% para 1.5%
  }'
```

### Max DD Alto

```bash
# Aumentar hysteresis para reduzir whipsaws
# Editar meta_simulation.py:
# regime_confirmation_threshold: 8 → 10
```

---

## 🚦 INTEGRAÇÃO COM MONITORAMENTO

### Prometheus Metrics (futuro)

```python
# Adicionar ao execution-engine
from prometheus_client import Gauge

wfo_return = Gauge('wfo_monthly_return', 'WFO Monthly Return (%)')
wfo_sharpe = Gauge('wfo_monthly_sharpe', 'WFO Monthly Sharpe Ratio')
wfo_dd = Gauge('wfo_monthly_max_dd', 'WFO Monthly Max Drawdown (%)')

# Atualizar após cada WFO
wfo_return.set(3.45)
wfo_sharpe.set(1.82)
wfo_dd.set(4.23)
```

### Alertmanager (futuro)

```yaml
# alertmanager.yml
route:
  receiver: 'wfo-alerts'
  
receivers:
  - name: 'wfo-alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#trading-alerts'
        text: 'WFO Alert: {{ .CommonAnnotations.summary }}'
```

---

## 📝 CHECKLIST MENSAL

- [ ] Executar `wfo_monthly_automation.sh`
- [ ] Revisar alertas no log
- [ ] Analisar histórico CSV
- [ ] Gerar gráfico de tendências
- [ ] Aplicar ajustes se recomendado
- [ ] Documentar mudanças em `CHANGELOG.md`
- [ ] Re-testar com novos parâmetros
- [ ] Atualizar `PLANO_DE_MELHORAMENTO.md`

---

## 🎯 PRÓXIMOS PASSOS

1. **Automação de Recalibração**
   - Script que aplica ajustes automaticamente baseado em recomendações
   - Testar múltiplas configurações em paralelo
   - Selecionar melhor configuração via WFO

2. **Multi-Asset WFO**
   - Executar WFO para BTC, ETH, SOL simultaneamente
   - Comparar performance entre pares
   - Detectar qual par está performando melhor

3. **Adaptive Parameters**
   - Machine learning para ajustar parâmetros automaticamente
   - Usar histórico CSV como dataset de treinamento
   - Prever melhores parâmetros para próximo mês

4. **Real-Time Monitoring**
   - Dashboard Grafana com métricas WFO
   - Alertas automáticos via Telegram/Slack
   - API para consultar status WFO

---

## 📚 REFERÊNCIAS

- PASSO 24: Walk-Forward Optimization 2025
- PASSO 24.3: Ajustes de Gestão de Risco
- PASSO 25: Kelly Position Sizing
- `PLANO_DE_MELHORAMENTO.md`: Lições Aprendidas 2025
