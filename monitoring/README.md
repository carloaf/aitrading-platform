# PASSO 27.4: Grafana Dashboard WFO

Monitoramento em tempo real de Walk-Forward Optimization com Prometheus + Grafana.

## 📊 Arquitetura

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  wfo_simple.sh  │ ───▶ │  history.csv    │ ───▶ │  wfo_exporter   │
│  (executa WFO)  │      │  (logs/wfo/)    │      │  (Prometheus)   │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                                            │
                                                            ▼
                         ┌─────────────────┐      ┌─────────────────┐
                         │   Prometheus    │ ───▶ │     Grafana     │
                         │  (scrape 10s)   │      │  (dashboard)    │
                         └─────────────────┘      └─────────────────┘
                                                   http://localhost:3000
```

## 🚀 Setup Rápido

### 1. Iniciar Stack de Monitoramento

```bash
cd /home/dellno/worksapace/aitrading-platform

# Build e start
docker compose -f monitoring/docker-compose.monitoring.yml up -d

# Verificar status
docker compose -f monitoring/docker-compose.monitoring.yml ps

# Deve mostrar 3 containers:
# - wfo-metrics-exporter (porta 9090)
# - wfo-prometheus (porta 9091)
# - wfo-grafana (porta 3000)
```

### 2. Acessar Grafana

1. Abrir navegador: **http://localhost:3000**
2. Login:
   - Usuário: `admin`
   - Senha: `admin`
3. Dashboard WFO já configurado automaticamente

### 3. Testar Métricas

```bash
# Verificar métricas exportadas
curl http://localhost:9090/metrics

# Health check
curl http://localhost:9090/health

# Prometheus UI
open http://localhost:9091

# Grafana Dashboard
open http://localhost:3000/d/wfo-dashboard
```

## 📈 Métricas Disponíveis

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `wfo_return_percent` | Gauge | Retorno % do último WFO |
| `wfo_sharpe_ratio` | Gauge | Sharpe ratio do último WFO |
| `wfo_max_drawdown_percent` | Gauge | Max drawdown % do último WFO |
| `wfo_win_rate_percent` | Gauge | Win rate % do último WFO |
| `wfo_total_trades` | Gauge | Total de trades do último WFO |
| `wfo_robustness_score` | Gauge | Score de robustez (0-100) |
| `wfo_runs_total` | Counter | Total de execuções WFO |
| `wfo_last_run_timestamp` | Gauge | Timestamp última execução |

## 📊 Dashboard

O dashboard inclui:

### Row 1: Indicadores Principais
- **Return %**: Gauge com thresholds (red<0%, yellow 0-2%, green>2%)
- **Sharpe Ratio**: Gauge com thresholds (red<0.5, yellow 0.5-1.5, green>1.5)
- **Robustness Score**: Gauge (green<50, yellow 50-70, red>70)

### Row 2: Gráficos Temporais
- **Return Over Time**: Line chart com histórico de retornos
- **Robustness Score Over Time**: Line chart com threshold em 50

### Row 3: Estatísticas
- **Max Drawdown**: Stat panel (green<10%, yellow 10-15%, red>15%)
- **Win Rate**: Stat panel (red<45%, yellow 45-55%, green>55%)
- **Total Trades**: Stat panel
- **Total WFO Runs**: Counter

## 🔧 Configuração

### Alterar Porta do Exporter

Editar `monitoring/docker-compose.monitoring.yml`:

```yaml
wfo-exporter:
  ports:
    - "9090:9090"  # Alterar porta host
```

### Ajustar Scrape Interval

Editar `monitoring/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'wfo_metrics'
    scrape_interval: 10s  # Alterar intervalo
```

### Adicionar Alertas

Criar `monitoring/alerts.yml`:

```yaml
groups:
  - name: wfo_alerts
    interval: 30s
    rules:
      - alert: WFOLowReturn
        expr: wfo_return_percent < -5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "WFO return < -5%"
          description: "Last WFO return is {{ $value }}%"
      
      - alert: WFOLowRobustness
        expr: wfo_robustness_score < 50
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "WFO robustness < 50"
          description: "Robustness score is {{ $value }}"
```

Descomentar em `prometheus.yml`:

```yaml
rule_files:
  - "alerts.yml"
```

## 🔍 Troubleshooting

### Exporter não inicia

```bash
# Verificar logs
docker compose -f monitoring/docker-compose.monitoring.yml logs wfo-exporter

# Testar manualmente
python3 monitoring/wfo_exporter.py --csv logs/wfo/history.csv --port 9090
```

### Métricas não aparecem no Grafana

1. Verificar se CSV existe: `ls logs/wfo/history.csv`
2. Verificar exporter: `curl http://localhost:9090/metrics`
3. Verificar Prometheus targets: http://localhost:9091/targets
4. Verificar datasource Grafana: Settings → Data Sources → Prometheus

### Dashboard não carrega

```bash
# Verificar permissões
chmod -R 755 monitoring/grafana/

# Restart Grafana
docker compose -f monitoring/docker-compose.monitoring.yml restart grafana
```

## 📝 Manutenção

### Backup de Dados

```bash
# Backup Prometheus data
docker run --rm -v wfo_prometheus_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/prometheus_backup.tar.gz -C /data .

# Backup Grafana data
docker run --rm -v wfo_grafana_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/grafana_backup.tar.gz -C /data .
```

### Limpeza

```bash
# Parar e remover containers
docker compose -f monitoring/docker-compose.monitoring.yml down

# Remover volumes (CUIDADO: apaga dados históricos)
docker compose -f monitoring/docker-compose.monitoring.yml down -v
```

## 🎯 Próximos Passos

- [ ] Configurar Alertmanager para notificações
- [ ] Adicionar dashboard para multi-asset WFO
- [ ] Integrar métricas do MetaBacktester via /metrics endpoint
- [ ] Setup Grafana Cloud para acesso remoto
- [ ] Criar alerts para Slack/Telegram

## 📚 Referências

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
