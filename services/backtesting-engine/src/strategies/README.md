# 📊 Módulo de Estratégias de Trading

Sistema completo com 9 estratégias profissionais para trading de criptomoedas e ativos financeiros.

## 🚀 Estratégias Disponíveis

### 1. **Trend Following** (Seguimento de Tendência)
- **Indicadores**: EMA21, EMA55, RSI, Volume, ADX
- **Melhor para**: Mercados em tendência forte
- **Timeframe**: 1h, 4h, diário
- **Win Rate esperado**: 40-50% com R:R 2:1

**Condições de Entrada:**
```python
✓ EMA21 > EMA55 (tendência de alta)
✓ Volume > 1.5x média
✓ RSI entre 40-80
✓ ADX > 25 (tendência forte)
```

---

### 2. **Mean Reversion** (Reversão à Média)
- **Indicadores**: Bollinger Bands, RSI, Stochastic
- **Melhor para**: Mercados laterais, alta volatilidade
- **Timeframe**: 15m, 1h
- **Win Rate esperado**: 60-70% com R:R 1:1.5

**Condições de Entrada:**
```python
✓ Preço toca banda inferior de Bollinger
✓ RSI < 30 (sobrevenda)
✓ Stochastic < 20
```

---

### 3. **Volatility Breakout** (Rompimento de Volatilidade)
- **Indicadores**: ATR, Canais de preço
- **Melhor para**: Início de tendências fortes
- **Timeframe**: 1h, 4h
- **Win Rate esperado**: 35-45% com R:R 3:1

**Condições de Entrada:**
```python
✓ Preço rompe máxima de 20 períodos
✓ ATR em expansão
✓ Volume > 1.5x média
```

---

### 4. **MACD + RSI Combo** (Combinação)
- **Indicadores**: MACD, RSI
- **Melhor para**: Uso geral, qualquer mercado
- **Timeframe**: 1h, 4h
- **Win Rate esperado**: 50-55% com R:R 1.5:1

---

### 5. **Bollinger Bands** (Simples)
- **Indicadores**: Bollinger Bands
- **Melhor para**: Iniciantes
- **Timeframe**: 1h
- **Win Rate esperado**: 55-60% com R:R 1:1

---

### 6. **Momentum**
- **Indicadores**: ROC (Rate of Change)
- **Melhor para**: Tendências explosivas
- **Timeframe**: 4h, diário
- **Win Rate esperado**: 40-45% com R:R 2.5:1

---

### 7. **Volume Profile** (Análise de Volume)
- **Indicadores**: OBV (On-Balance Volume)
- **Melhor para**: Confirmação de tendências
- **Timeframe**: 1h, 4h
- **Win Rate esperado**: 45-50% com R:R 2:1

---

### 8. **Multi-Timeframe** (Confirmação MTF)
- **Indicadores**: EMAs, MACD, RSI em múltiplos timeframes
- **Melhor para**: Alta precisão, traders experientes
- **Timeframe**: 15m com análise em 1h e 4h
- **Win Rate esperado**: 60-65% com R:R 1.5:1

---

### 9. **Dynamic Position Sizing** (Gestão de Risco)
- **Indicadores**: ATR, Kelly Criterion
- **Melhor para**: Proteção de capital
- **Timeframe**: Qualquer
- **Foco**: Preservação de capital e gestão de risco

---

## 📖 Como Usar

### Uso Básico

```python
from strategies import StrategyManager
import pandas as pd

# Carregar dados
df = pd.read_csv('seu_arquivo.csv')

# Criar estratégia
strategy = StrategyManager.get_strategy('trend_following')

# Executar
df_result = strategy.run(df)

# Ver sinais
print(df_result[['Close', 'signal', 'position']].tail())
```

### Com Parâmetros Customizados

```python
# Parâmetros customizados
params = {
    'fast_ema': 10,
    'slow_ema': 30,
    'rsi_lower': 35,
    'rsi_upper': 75
}

strategy = StrategyManager.get_strategy('trend_following', parameters=params)
df_result = strategy.run(df)
```

### Listar Todas as Estratégias

```python
strategies = StrategyManager.list_strategies()

for s in strategies:
    print(f"Nome: {s['name']}")
    print(f"ID: {s['id']}")
    print(f"Parâmetros: {s['default_parameters']}")
    print()
```

### Comparar Estratégias

```python
# Comparar 3 estratégias
comparison = StrategyManager.compare_strategies(
    strategies=['trend_following', 'mean_reversion', 'macd_rsi_combo'],
    df=df,
    initial_capital=10000
)

for name, metrics in comparison.items():
    print(f"{name}:")
    print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}")
    print(f"  Retorno: {metrics['total_return']:.2f}%")
```

---

## 🎯 Recomendações por Condição de Mercado

### 📈 Mercado em Tendência de Alta
```python
- Trend Following ⭐⭐⭐⭐⭐
- Momentum ⭐⭐⭐⭐
- Multi-Timeframe ⭐⭐⭐⭐
```

### 📉 Mercado em Tendência de Baixa
```python
- Mean Reversion ⭐⭐⭐⭐
- Dynamic Position Sizing ⭐⭐⭐⭐⭐
```

### ➡️ Mercado Lateral (Ranging)
```python
- Mean Reversion ⭐⭐⭐⭐⭐
- Bollinger Bands ⭐⭐⭐⭐
- Volatility Breakout ⭐⭐⭐
```

### 💥 Mercado Volátil
```python
- Volatility Breakout ⭐⭐⭐⭐⭐
- Dynamic Position Sizing ⭐⭐⭐⭐⭐
- Bollinger Bands ⭐⭐⭐⭐
```

---

## 🔧 Otimização de Parâmetros

```python
# Definir ranges de parâmetros para testar
param_ranges = {
    'fast_ema': [9, 12, 21],
    'slow_ema': [34, 50, 55],
    'rsi_lower': [30, 35, 40]
}

# Otimizar
strategy = StrategyManager.get_strategy('trend_following')
best_params = strategy.optimize_parameters(df, param_ranges)

print(f"Melhores parâmetros: {best_params}")
```

---

## 📊 Métricas Avançadas

Todas as estratégias incluem:

- ✅ **Sharpe Ratio**: Retorno ajustado por risco
- ✅ **Sortino Ratio**: Sharpe considerando apenas downside
- ✅ **Calmar Ratio**: Retorno / Max Drawdown
- ✅ **Omega Ratio**: Probabilidade ganho/perda
- ✅ **Maximum Drawdown**: Maior perda consecutiva
- ✅ **Win Rate**: Taxa de acerto
- ✅ **Profit Factor**: Lucro bruto / Prejuízo bruto
- ✅ **Expectancy**: Valor esperado por trade

---

## ⚠️ Gestão de Risco

### Stop-Loss Dinâmico
Todas as estratégias incluem stop-loss baseado em ATR:

```python
Stop Loss = Preço Entrada - (2 × ATR)
Take Profit = Preço Entrada + (3 × ATR)
```

### Position Sizing
Use a estratégia **Dynamic Position Sizing** para calcular tamanho ótimo:

```python
strategy = StrategyManager.get_strategy('dynamic_position_sizing')
df_result = strategy.run(df)

# Ver tamanho recomendado de posição
print(df_result['position_size'].tail())
```

---

## 🧪 Backtesting

```python
from advanced_metrics import AdvancedMetrics, format_metrics_report

# Executar estratégia
strategy = StrategyManager.get_strategy('trend_following')
df_result = strategy.run(df)

# Simular trades (simplificado)
# ... código de simulação ...

# Calcular métricas
metrics = AdvancedMetrics.calculate_all_metrics(
    equity_curve=equity_curve,
    trades=trades,
    initial_capital=10000
)

# Imprimir relatório
print(format_metrics_report(metrics))
```

---

## 📚 Exemplos Práticos

### Exemplo 1: Trading BTC/USD
```python
# Carregar dados do Bitcoin
df = get_bitcoin_data('2023-01-01', '2024-01-01')

# Usar estratégia de tendência
strategy = StrategyManager.get_strategy('trend_following')
df_result = strategy.run(df)

# Analisar força da tendência
analysis = strategy.analyze_trend_strength(df_result)
print(analysis)
```

### Exemplo 2: Detectar Mercado Lateral
```python
# Usar Mean Reversion
strategy = StrategyManager.get_strategy('mean_reversion')

# Detectar se mercado está lateral
is_ranging = strategy.is_ranging_market(df, periods=50)

if is_ranging:
    print("Mercado lateral detectado - Mean Reversion é ideal!")
    df_result = strategy.run(df)
```

### Exemplo 3: Multi-Estratégia
```python
# Combinar múltiplas estratégias
strategies = ['trend_following', 'mean_reversion', 'momentum']

votes = []
for strat_name in strategies:
    strategy = StrategyManager.get_strategy(strat_name)
    df_temp = strategy.run(df)
    votes.append(df_temp['signal'].iloc[-1])

# Sinal final = maioria
final_signal = 1 if sum(votes) > 0 else -1 if sum(votes) < 0 else 0
```

---

## 🎓 Dicas para Melhores Resultados

1. **Combine Indicadores**: Nunca confie em um único indicador
2. **Use Stop-Loss**: Sempre defina stop-loss antes de entrar
3. **Gestão de Risco**: Nunca arrisque mais de 2% por trade
4. **Backtest Extenso**: Teste em múltiplos períodos e condições
5. **Walk-Forward**: Otimize em dados passados, valide em dados futuros
6. **Paper Trading**: Teste em conta demo antes de usar capital real

---

## 📞 Suporte

Para dúvidas ou sugestões:
- Documentação completa: `/docs`
- Exemplos: `/examples`
- Issues: GitHub Issues

---

## 🔄 Atualizações

**Versão 1.0.0**
- ✅ 9 estratégias implementadas
- ✅ Métricas avançadas (Sortino, Calmar, Omega)
- ✅ Sistema de otimização de parâmetros
- ✅ Gestão de risco dinâmica
- ✅ Suporte a múltiplos timeframes

---

## ⚖️ Disclaimer

**AVISO IMPORTANTE**: 
- Estas estratégias são para fins educacionais
- Performance passada não garante resultados futuros
- Sempre teste extensivamente antes de usar capital real
- Trading envolve risco de perda de capital
- Nunca invista mais do que pode perder

---

**Happy Trading! 📈💰**
