# 🚀 Guia de Uso Rápido - Sistema de Estratégias de Trading

## ⚡ Quick Start

### 1. Testar uma Estratégia (Backend Direto)

```bash
# No diretório do backtesting-engine
cd services/backtesting-engine

# Instalar dependências
pip install -r requirements.txt

# Executar servidor
python src/main.py
```

Servidor rodando em: `http://localhost:8000`

---

### 2. Testar Via API (com cURL)

```bash
# Listar estratégias disponíveis
curl http://localhost:8000/strategies/examples | jq

# Executar backtest com Trend Following
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USD",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "initial_capital": 10000,
    "commission": 0.001,
    "strategy": {
      "name": "Trend Following",
      "description": "EMA Crossover with volume confirmation",
      "parameters": {
        "fast_ema": 21,
        "slow_ema": 55
      },
      "entry_conditions": ["EMA_fast > EMA_slow", "volume_confirmed == 1"],
      "exit_conditions": ["EMA_fast < EMA_slow"]
    }
  }' | jq
```

---

### 3. Uso Programático (Python)

```python
from strategies import StrategyManager
import pandas as pd
import yfinance as yf

# 1. Carregar dados
df = yf.download('BTC-USD', start='2023-01-01', end='2024-01-01')

# 2. Escolher estratégia
strategy = StrategyManager.get_strategy('trend_following')

# 3. Executar
df_result = strategy.run(df)

# 4. Ver sinais
print(df_result[['Close', 'signal', 'position', 'stop_loss']].tail(10))

# 5. Análise de tendência
analysis = strategy.analyze_trend_strength(df_result)
print(f"Tendência: {analysis['direction']}")
print(f"Força: {analysis['strength']}")
print(f"ADX: {analysis['adx_value']:.2f}")
```

---

### 4. Comparar Múltiplas Estratégias

```python
from strategies import StrategyManager

# Comparar 3 estratégias
strategies = ['trend_following', 'mean_reversion', 'macd_rsi_combo']

results = StrategyManager.compare_strategies(
    strategies=strategies,
    df=df,
    initial_capital=10000
)

# Ver resultados
for name, metrics in results.items():
    print(f"\n{name}:")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"  Retorno Total: {metrics['total_return']:.2f}%")
    print(f"  Total Trades: {metrics['total_trades']}")
```

---

### 5. Otimizar Parâmetros

```python
from strategies import StrategyManager

# Definir ranges para testar
param_ranges = {
    'fast_ema': [9, 12, 21],
    'slow_ema': [34, 50, 55],
    'rsi_lower': [30, 35, 40],
    'rsi_upper': [70, 75, 80]
}

# Criar estratégia
strategy = StrategyManager.get_strategy('trend_following')

# Otimizar
best_params = strategy.optimize_parameters(df, param_ranges)

print(f"Melhores parâmetros encontrados:")
print(best_params)

# Usar os melhores parâmetros
optimized_strategy = StrategyManager.get_strategy(
    'trend_following', 
    parameters=best_params
)
df_optimized = optimized_strategy.run(df)
```

---

### 6. Backtesting Completo com Métricas

```python
from advanced_metrics import AdvancedMetrics, format_metrics_report

# Executar estratégia
strategy = StrategyManager.get_strategy('trend_following')
df_result = strategy.run(df)

# Simular trades (simplificado para exemplo)
equity_curve = []
trades = []
capital = 10000

for i, row in df_result.iterrows():
    if row['signal'] == 1:  # Compra
        # Lógica de trade aqui...
        pass
    
    equity_curve.append({
        'date': str(i),
        'equity': capital,  # capital atualizado
        'price': row['Close']
    })

# Calcular todas as métricas
metrics = AdvancedMetrics.calculate_all_metrics(
    equity_curve=equity_curve,
    trades=trades,
    initial_capital=10000,
    risk_free_rate=0.02
)

# Imprimir relatório formatado
print(format_metrics_report(metrics))
```

---

### 7. Detectar Condição de Mercado

```python
from strategies import get_recommended_strategy, StrategyManager

# Analisar se mercado está lateral
mean_rev_strategy = StrategyManager.get_strategy('mean_reversion')
is_ranging = mean_rev_strategy.is_ranging_market(df, periods=50)

if is_ranging:
    print("Mercado LATERAL detectado")
    recommended = ['mean_reversion', 'bollinger_bands', 'volatility_breakout']
else:
    print("Mercado em TENDÊNCIA detectado")
    recommended = ['trend_following', 'momentum', 'multi_timeframe']

print(f"Estratégias recomendadas: {recommended}")

# Usar a primeira recomendada
best_strategy = StrategyManager.get_strategy(recommended[0])
df_result = best_strategy.run(df)
```

---

### 8. Gestão de Risco Dinâmica

```python
from strategies import StrategyManager

# Usar estratégia de position sizing dinâmico
risk_strategy = StrategyManager.get_strategy('dynamic_position_sizing', parameters={
    'risk_per_trade': 0.02,  # 2% de risco por trade
    'atr_multiplier': 2.0,
    'max_position_size': 0.25  # Máximo 25% do capital
})

df_result = risk_strategy.run(df)

# Analisar risco atual
risk_analysis = risk_strategy.analyze_risk(df_result, account_balance=10000)

print(f"Preço atual: ${risk_analysis['current_price']:.2f}")
print(f"ATR: ${risk_analysis['atr']:.2f} ({risk_analysis['atr_pct']:.2f}%)")
print(f"Tamanho de posição recomendado: {risk_analysis['recommended_position_size_pct']:.2f}%")
print(f"Valor da posição: ${risk_analysis['position_value_usd']:.2f}")
print(f"Risco por trade: ${risk_analysis['risk_per_trade_usd']:.2f}")
print(f"Stop-loss: ${risk_analysis['stop_loss']:.2f}")
print(f"Take-profit: ${risk_analysis['take_profit']:.2f}")
print(f"Risk/Reward: {risk_analysis['risk_reward_ratio']:.2f}")
```

---

### 9. Multi-Timeframe Analysis

```python
from strategies import StrategyManager
import yfinance as yf

# Carregar dados em diferentes timeframes
df_1h = yf.download('BTC-USD', interval='1h', period='30d')
df_4h = yf.download('BTC-USD', interval='4h', period='60d')
df_1d = yf.download('BTC-USD', interval='1d', period='180d')

# Estratégia multi-timeframe
mtf_strategy = StrategyManager.get_strategy('multi_timeframe')

# Analisar timeframe diário (tendência principal)
df_1d_result = mtf_strategy.run(df_1d)
daily_trend = df_1d_result['trend_direction'].iloc[-1]

print(f"Tendência Diária: {'ALTA' if daily_trend == 1 else 'BAIXA'}")

# Se tendência de alta no diário, buscar entrada no 1h
if daily_trend == 1:
    df_1h_result = mtf_strategy.run(df_1h)
    
    # Ver últimos sinais
    recent_signals = df_1h_result[df_1h_result['signal'] != 0].tail(5)
    print("\nÚltimos sinais (1h):")
    print(recent_signals[['Close', 'signal', 'RSI', 'EMA_fast', 'EMA_slow']])
```

---

### 10. Visualização Simples (com Matplotlib)

```python
import matplotlib.pyplot as plt

# Executar estratégia
strategy = StrategyManager.get_strategy('trend_following')
df_result = strategy.run(df)

# Criar gráfico
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# Gráfico 1: Preço e EMAs
ax1.plot(df_result.index, df_result['Close'], label='Preço', linewidth=2)
ax1.plot(df_result.index, df_result['EMA_fast'], label='EMA Rápida', alpha=0.7)
ax1.plot(df_result.index, df_result['EMA_slow'], label='EMA Lenta', alpha=0.7)

# Marcar sinais de compra/venda
buy_signals = df_result[df_result['signal'] == 1]
sell_signals = df_result[df_result['signal'] == -1]

ax1.scatter(buy_signals.index, buy_signals['Close'], marker='^', color='green', s=100, label='Compra')
ax1.scatter(sell_signals.index, sell_signals['Close'], marker='v', color='red', s=100, label='Venda')
ax1.set_ylabel('Preço (USD)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Gráfico 2: RSI
ax2.plot(df_result.index, df_result['RSI'], label='RSI', color='purple')
ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5)
ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5)
ax2.set_ylabel('RSI')
ax2.legend()
ax2.grid(True, alpha=0.3)

# Gráfico 3: Volume
ax3.bar(df_result.index, df_result['Volume'], label='Volume', alpha=0.5)
ax3.plot(df_result.index, df_result['Volume_SMA'], label='Volume SMA', color='orange', linewidth=2)
ax3.set_ylabel('Volume')
ax3.set_xlabel('Data')
ax3.legend()
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('strategy_analysis.png', dpi=150)
plt.show()

print("Gráfico salvo como 'strategy_analysis.png'")
```

---

## 📊 Métricas Disponíveis

Todas as estratégias fornecem estas métricas:

```python
metrics = {
    # Retorno
    'total_return_pct': 45.2,
    'sharpe_ratio': 1.85,
    'sortino_ratio': 2.14,
    'calmar_ratio': 1.23,
    
    # Risco
    'max_drawdown_pct': 12.5,
    'volatility_annual': 28.3,
    
    # Trades
    'total_trades': 42,
    'win_rate_pct': 55.0,
    'profit_factor': 1.8,
    'expectancy': 125.50,
    
    # Outros
    'avg_win': 450.00,
    'avg_loss': -250.00,
    'risk_reward_ratio': 1.8
}
```

---

## 🎯 Dicas Importantes

### ✅ DO (Faça)
- Teste em múltiplos períodos históricos
- Use stop-loss SEMPRE
- Combine múltiplos indicadores
- Otimize parâmetros com walk-forward
- Paper trading antes de usar capital real
- Diversifique estratégias

### ❌ DON'T (Não Faça)
- Confiar em um único indicador
- Over-optimizar (overfitting)
- Ignorar custos de transação
- Trading sem stop-loss
- Arriscar mais de 2% por trade
- Fazer decisões emocionais

---

## 📚 Documentação Completa

Para mais detalhes, consulte:
- `services/backtesting-engine/src/strategies/README.md` - Guia completo de estratégias
- `PROJECT_STATUS.md` - Status do projeto
- `INSTRUCOES.md` - Instruções originais do sistema

---

## 🆘 Troubleshooting

### Erro: "Dados insuficientes"
```python
# Certifique-se de ter pelo menos 50 períodos
df = yf.download('BTC-USD', period='3mo')  # 3 meses de dados
```

### Erro: "Estratégia não encontrada"
```python
# Listar todas as estratégias disponíveis
strategies = StrategyManager.list_strategies()
for s in strategies:
    print(s['id'])
```

### Performance lenta
```python
# Use menos dados para testes rápidos
df = df.tail(500)  # Últimos 500 candles apenas
```

---

**Happy Trading! 🚀📈**
