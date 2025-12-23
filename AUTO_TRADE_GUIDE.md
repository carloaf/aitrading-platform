# 🤖 Auto-Trade Guide - Execução Automática de Sinais

## Visão Geral

O sistema de **Auto-Trade** permite que sinais detectados pelo Scanner RSI Divergence sejam **automaticamente executados** como paper trades, criando um sistema de backtesting em tempo real.

### Fluxo Completo

```
Scanner RSI Divergence
    ↓
Detecta Divergência (força ≥ 40%)
    ↓
Salva no banco: autotrade_signals
    ↓
Auto-executa paper trade
    ↓
Salva em: paper_trading_trades
    ↓
Calcula performance: Win Rate, PnL, Profit Factor
```

---

## 📋 Arquitetura

### 1. Banco de Dados

#### Tabela: `autotrade_signals`
```sql
CREATE TABLE autotrade_signals (
    signal_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    signal_type VARCHAR(20) NOT NULL,  -- 'BULLISH' ou 'BEARISH'
    strength DECIMAL(5,4),              -- 0.0000 a 1.0000
    rsi_current DECIMAL(5,2),
    price_current DECIMAL(20,8),
    entry_price DECIMAL(20,8),
    stop_loss DECIMAL(20,8),
    take_profit DECIMAL(20,8),
    risk_reward_ratio DECIMAL(5,2),
    
    -- AUTO-TRADE FIELDS
    executed BOOLEAN DEFAULT FALSE,
    execution_reason TEXT,
    paper_trading_trade_id INTEGER REFERENCES paper_trading_trades(id)
);
```

#### Tabela: `paper_trading_trades`
```sql
CREATE TABLE paper_trading_trades (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,          -- 'BUY' ou 'SELL'
    entry_price DECIMAL(20,8) NOT NULL,
    exit_price DECIMAL(20,8),
    quantity DECIMAL(20,8) NOT NULL,
    stop_loss DECIMAL(20,8),
    take_profit DECIMAL(20,8),
    status VARCHAR(20) DEFAULT 'OPEN',  -- 'OPEN', 'CLOSED'
    pnl DECIMAL(20,8),
    pnl_percent DECIMAL(10,4),
    entry_time TIMESTAMPTZ DEFAULT NOW(),
    exit_time TIMESTAMPTZ,
    
    -- SIGNAL INTEGRATION
    signal_source VARCHAR(50),          -- 'RSI_DIVERGENCE'
    signal_strength DECIMAL(5,4),       -- Link para força do sinal
    timeframe VARCHAR(10)
);
```

---

## 🚀 Como Funcionar

### 1. Habilitar Auto-Trade

**Via API:**
```bash
curl -X POST http://localhost:3008/api/scanner/enable-auto-trade?min_strength=0.4
```

**Resposta:**
```json
{
  "success": true,
  "message": "Auto-trade enabled",
  "min_signal_strength": 0.4,
  "note": "Signals with strength >= threshold will be auto-executed"
}
```

### 2. Desabilitar Auto-Trade

```bash
curl -X POST http://localhost:3008/api/scanner/disable-auto-trade
```

### 3. Consultar Performance

```bash
curl http://localhost:3008/api/scanner/auto-trade-performance
```

**Resposta Exemplo:**
```json
{
  "success": true,
  "enabled": true,
  "session_id": "auto_scanner_20250128_143052",
  "initial_capital": 10000.00,
  "current_capital": 10245.67,
  "total_trades": 15,
  "closed_trades": 10,
  "open_trades": 5,
  "wins": 7,
  "losses": 3,
  "win_rate": 70.0,
  "total_pnl": 245.67,
  "avg_win": 85.23,
  "avg_loss": -42.15,
  "profit_factor": 2.02,
  "return_pct": 2.46,
  "recent_trades": [
    {
      "id": 123,
      "symbol": "BTCUSDT",
      "side": "BUY",
      "entry_price": 42350.50,
      "quantity": 0.0024,
      "pnl": 12.45,
      "signal_strength": 0.72,
      "entry_time": "2025-01-28T14:30:52Z"
    }
  ]
}
```

---

## ⚙️ Lógica de Auto-Execução

### Critérios para Executar Trade

1. **Auto-trade habilitado**: `scanner.auto_trade_enabled = True`
2. **Força do sinal**: `signal.strength >= 0.4` (40% mínimo)
3. **Divergência válida**: RSI confirmado + Price confirmado

### Cálculo de Posição (Position Sizing)

```python
# Parâmetros
initial_capital = 10000.00  # $10,000 inicial
risk_per_trade = 0.02       # 2% por trade

# Cálculo
risk_amount = capital * risk_per_trade  # $200 por trade
stop_distance = abs(entry_price - stop_loss)
position_size = risk_amount / stop_distance

# Exemplo:
# Entry: $42,350.50
# Stop: $42,100.00
# Stop Distance: $250.50
# Position Size: $200 / $250.50 = 0.799 BTC
```

### Stop Loss e Take Profit

- **Stop Loss**: Calculado pelo scanner com base no ATR e níveis de suporte/resistência
- **Take Profit**: Risk/Reward ratio de 2:1 ou 3:1 dependendo da força do sinal
- **Trailing Stop**: Pode ser habilitado para proteger lucros

---

## 📊 Métricas de Performance

### Win Rate (Taxa de Acerto)
```python
win_rate = (wins / closed_trades) * 100
# Exemplo: (7 / 10) * 100 = 70%
```

### Profit Factor (Fator de Lucro)
```python
total_wins = sum(pnl for pnl in wins)
total_losses = abs(sum(pnl for pnl in losses))
profit_factor = total_wins / total_losses

# Interpretação:
# > 2.0 = Excelente
# 1.5 - 2.0 = Bom
# 1.0 - 1.5 = Aceitável
# < 1.0 = Perdedor
```

### Return % (Retorno Percentual)
```python
return_pct = ((current_capital / initial_capital) - 1) * 100
# Exemplo: ((10245.67 / 10000) - 1) * 100 = 2.46%
```

### Average Win vs Average Loss
```python
avg_win = sum(wins) / len(wins)
avg_loss = sum(losses) / len(losses)

# Ideal: avg_win > abs(avg_loss) * 2
```

---

## 🎯 Visualização no Dashboard

### Seção "Performance Paper Trading"

**Cartões de Estatísticas:**
- ✅ **Total Trades**: Número total de trades executados
- 📊 **Win Rate**: Taxa de acerto em %
- 💰 **P&L Total**: Lucro/Prejuízo acumulado
- 📈 **Profit Factor**: Razão entre lucros e perdas

**Tabela de Trades Recentes:**
| ID | Símbolo | Tipo | Preço | Quantidade | Valor | P&L | Confiança | Data |
|----|---------|------|-------|------------|-------|-----|-----------|------|
| #123 | BTCUSDT | BUY | $42,350.50 | 0.0024 | $101.64 | +$12.45 | 72% | 28/01 14:30 |

**Atualização Automática:**
- Refresh a cada 60 segundos
- Botão manual "Atualizar"

---

## 🔧 Configuração Avançada

### Modificar Força Mínima do Sinal

```python
# No scanner
scanner.min_signal_strength_for_trade = 0.5  # 50% mínimo
```

### Modificar Capital Inicial

```python
# Em paper_trading_sessions
UPDATE paper_trading_sessions
SET initial_capital = 50000.00
WHERE session_id = 'auto_scanner_20250128_143052';
```

### Modificar Risk per Trade

```python
# Ajustar no código multi_symbol_scanner.py
risk_amount = current_capital * 0.01  # 1% risk ao invés de 2%
```

---

## 📝 Código Fonte

### Backend: `multi_symbol_scanner.py`

**Métodos Principais:**

1. **`_save_signal_to_db()`** (linha 753)
   - Salva sinal no banco
   - Verifica se auto-trade está habilitado
   - Chama `_create_paper_trade_from_signal()`

2. **`_create_paper_trade_from_signal()`** (linha 808)
   - Cria sessão de paper trading se não existir
   - Calcula position size com 2% risk
   - Insere trade na tabela `paper_trading_trades`
   - Atualiza sinal com `paper_trading_trade_id`

3. **`get_auto_trade_performance()`** (linha 895)
   - Busca trades da sessão
   - Calcula estatísticas: win rate, PnL, profit factor
   - Retorna últimos 10 trades

### Frontend: `scanner-dashboard.ejs`

**Função Principal:**

```javascript
async function loadPaperTradingStats() {
    const response = await fetch(API_BASE + '/api/scanner/auto-trade-performance');
    const result = await response.json();
    
    // Atualiza UI com estatísticas
    document.getElementById('statsTotalTrades').textContent = result.total_trades;
    document.getElementById('statsWinRate').textContent = result.win_rate.toFixed(1) + '%';
    // ...
}

// Auto-refresh a cada 60 segundos
setInterval(loadPaperTradingStats, 60000);
```

---

## 🐛 Troubleshooting

### "Auto-trade not enabled"
- Execute: `POST /api/scanner/enable-auto-trade`
- Verifique: `scanner.auto_trade_enabled == True`

### "No trades auto-executed"
- Verifique se sinais têm `strength >= 0.4`
- Confirme se scanner está rodando: `/api/scanner/start`
- Check logs: `docker logs -f execution-engine`

### "PnL sempre zero"
- Trades ainda estão OPEN (não fechados)
- Apenas trades CLOSED têm PnL calculado
- Aguarde take profit ou stop loss serem atingidos

---

## 📈 Exemplos de Uso

### Caso 1: Backtest de Estratégia
```bash
# 1. Habilitar auto-trade
curl -X POST http://localhost:3008/api/scanner/enable-auto-trade?min_strength=0.5

# 2. Iniciar scanner contínuo
curl -X POST http://localhost:3008/api/scanner/start

# 3. Aguardar 24 horas

# 4. Ver performance
curl http://localhost:3008/api/scanner/auto-trade-performance
```

### Caso 2: Teste de Parâmetros
```bash
# Testar com força mínima 60%
curl -X POST http://localhost:3008/api/scanner/enable-auto-trade?min_strength=0.6

# Comparar com força mínima 40%
curl -X POST http://localhost:3008/api/scanner/enable-auto-trade?min_strength=0.4
```

---

## 🔮 Próximos Passos

- [ ] Adicionar trailing stop automático
- [ ] Implementar scale-in / scale-out
- [ ] Adicionar filtros de mercado (bull/bear)
- [ ] Exportar relatórios em PDF
- [ ] Comparação com buy & hold
- [ ] Integração com Telegram para notificações

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique logs: `docker logs -f execution-engine`
2. Consulte `SIGNAL_PERSISTENCE_GUIDE.md` para persistência
3. Revise `PAPER_TRADING_GUIDE.md` para detalhes de paper trading

---

**Última atualização**: 2025-01-28  
**Versão**: 1.0.0
