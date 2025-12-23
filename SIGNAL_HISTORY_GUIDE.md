# Guia do Histórico de Sinais - Scanner Dashboard

## 📋 Visão Geral

O **Histórico de Sinais (Últimas 24h)** foi completamente reformulado para oferecer uma experiência superior de monitoramento e análise de divergências RSI detectadas.

## ✨ Funcionalidades Implementadas

### 1. **Filtros de Direção** 
Botões de filtro no cabeçalho permitem visualizar sinais específicos:
- **Todos**: Exibe todos os sinais detectados
- **Compra**: Filtra apenas sinais de compra (BUY)
- **Venda**: Filtra apenas sinais de venda (SELL)
- **Limpar**: Remove todo o histórico (persiste no localStorage)

### 2. **Barra de Estatísticas**
Painel com 6 métricas em tempo real:
- **Total**: Quantidade total de sinais nas últimas 24h
- **Compras**: Número de sinais de compra
- **Vendas**: Número de sinais de venda
- **Força Média**: Média percentual da força dos sinais
- **Símbolos Únicos**: Quantidade de criptomoedas diferentes com sinais
- **Último Sinal**: Tempo decorrido desde o último sinal detectado

### 3. **Tabela Melhorada**
Aprimoramentos visuais e funcionais:

#### Colunas:
1. **Hora**: Horário exato da detecção
2. **Símbolo**: Par cripto (ex: BTC/USDT)
3. **Tipo**: Tipo de divergência (Regular/Hidden)
4. **Direção**: Badge colorido (verde=compra, vermelho=venda)
5. **Força**: Percentual com ícone indicador
6. **Preço**: Preço no momento da detecção
7. **RSI**: Valor do RSI com cor baseada em nível
8. **Tempo**: Tempo relativo ("5min atrás", "2h atrás")

#### Indicadores Visuais:
- **Linhas coloridas**: 
  - Verde suave para sinais de COMPRA
  - Vermelho suave para sinais de VENDA
  - Borda esquerda colorida para fácil identificação
  
- **Força do Sinal**:
  - ● (círculo cheio) + negrito verde: Força ≥ 70% 
  - ● (círculo cheio) + negrito amarelo: Força 50-69%
  - ◐ (círculo meio) + azul: Força 30-49%
  - ○ (círculo vazio) + cinza: Força < 30%

- **RSI Colorido**:
  - Verde negrito: RSI ≤ 30 (oversold - bullish)
  - Verde: RSI 30-40
  - Cinza: RSI 40-60 (neutro)
  - Vermelho: RSI 60-70  
  - Vermelho negrito: RSI ≥ 70 (overbought - bearish)

### 4. **Persistência de Dados**
- Histórico salvo automaticamente no **localStorage**
- Expira após **24 horas**
- Restaurado automaticamente ao recarregar a página
- Sobrevive a recarregamentos e fechamentos do navegador

### 5. **Tempo Relativo**
Exibição humanizada do tempo decorrido:
- "agora" - menos de 1 minuto
- "5min atrás" - minutos (até 59min)
- "2h atrás" - horas (60min ou mais)

## 🎨 Melhorias de UX/UI

### Efeitos Visuais:
- **Hover nas linhas**: Destaque com leve deslocamento e sombra
- **Botões ativos**: Elevação e sombra para indicar filtro ativo
- **Ícones Bootstrap**: Icons intuitivos para todas as ações
- **Cores Bootstrap**: Paleta consistente com o resto do dashboard

### Acessibilidade:
- Larguras fixas nas colunas para melhor alinhamento
- Scroll vertical para histórico extenso (max-height: 400px)
- Cabeçalho sticky mantém colunas visíveis ao rolar
- Estado vazio claro com ícone e mensagem descritiva

## 🔧 Implementação Técnica

### Funções JavaScript:

#### `updateHistoryTable()`
```javascript
// Atualiza a tabela HTML com os sinais filtrados
// - Aplica filtro de direção (all/BUY/SELL)
// - Gera HTML com cores e ícones
// - Calcula força e RSI com formatação condicional
```

#### `updateHistoryStats()`
```javascript
// Calcula e exibe estatísticas em tempo real
// - Total, Buy/Sell counts
// - Força média
// - Símbolos únicos
// - Tempo do último sinal
```

#### `filterHistoryByDirection(direction)`
```javascript
// Filtra sinais por direção
// Parâmetros: 'all', 'BUY', 'SELL'
// Atualiza botões ativos e rerender tabela
```

#### `getTimeAgo(timestamp)`
```javascript
// Converte timestamp Unix para tempo relativo
// Retorna: "agora", "5min atrás", "2h atrás"
```

#### `saveSignalHistory()`
```javascript
// Salva array signalHistory no localStorage
// Key: 'signalHistoryCache'
// Inclui timestamps para expiração
```

#### `restoreSignalHistory()`
```javascript
// Restaura sinais do localStorage
// Filtra sinais > 24h
// Chamado no DOMContentLoaded
```

### localStorage Structure:
```javascript
{
  key: 'signalHistoryCache',
  value: [
    {
      symbol: 'BTC/USDT',
      type: 'regular_bullish',
      direction: 'BUY',
      strength: 0.85,
      price: 45000,
      rsi: 28.5,
      time: '14:32:15',
      timestamp: 1704123135000
    },
    // ...mais sinais
  ]
}
```

## 📊 Como Usar

### Monitoramento Básico:
1. Acesse `http://localhost:8081/scanner`
2. Clique em **"Iniciar Scan"** para buscar divergências
3. Sinais detectados aparecem na tabela automaticamente
4. Histórico persiste por 24 horas

### Filtragem Avançada:
1. Use botões **Compra/Venda** para focar em um tipo de sinal
2. Clique **Todos** para ver novamente todos os sinais
3. Observe as **estatísticas** no topo para análise rápida

### Limpeza:
1. Clique **Limpar** para remover todo o histórico
2. Confirme que deseja apagar permanentemente
3. localStorage será limpo junto

## 🐛 Troubleshooting

### Histórico vazio após recarregar:
- Verifique se há sinais com menos de 24h
- Abra console do navegador (F12) e busque por `[History]`
- Sinais expirados (>24h) são automaticamente removidos

### Filtros não funcionam:
- Certifique-se de que há sinais na tabela
- Verifique console para erros JavaScript
- Recarregue a página (Ctrl+F5) para limpar cache

### Estatísticas incorretas:
- As estatísticas são recalculadas a cada atualização
- Se persistir, limpe o histórico e aguarde novos sinais
- Verifique se `signalHistory` array está correto no console

## 🔄 Fluxo de Dados

```
Scan API Response
    ↓
addToHistory()
    ↓
saveSignalHistory() ← localStorage
    ↓
updateHistoryTable()
    ↓
updateHistoryStats()
```

## 📝 Commit History

### Commit 1262a63 (Latest)
```
feat(scanner): Enhance signal history with filters, statistics, and better UX

- Add filter buttons (All/Buy/Sell/Clear)
- Add statistics bar (6 metrics)
- Improve table formatting (color-coded rows)
- Add strength indicators with icons
- Add RSI color coding
- Add relative time display
- Increase table height to 400px
- Improve empty state
```

### Commit f0cbc18 (Previous)
```
fix(scanner): Corrige exibição de Proximidade de Alerta e persistência de histórico

- Fixed symbol format (BTC/USDT → BTCUSDT)
- Implemented localStorage persistence
- Added 24h expiration filter
```

## 🎯 Próximos Passos Sugeridos

1. **Exportação CSV**: Permitir download do histórico
2. **Gráficos**: Adicionar visualizações (chart.js)
3. **Alertas Sonoros**: Notificar novos sinais importantes
4. **Filtro por Símbolo**: Buscar histórico de cripto específica
5. **Ordenação**: Clicar em colunas para ordenar
6. **Paginação**: Para históricos muito extensos (>100 sinais)

## 📚 Referências

- [Bootstrap 5 Badges](https://getbootstrap.com/docs/5.0/components/badge/)
- [Bootstrap Icons](https://icons.getbootstrap.com/)
- [MDN localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)
- [JavaScript Date](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date)

---

**Autor**: AI Trading Platform Team  
**Data**: 2025-01-16  
**Versão**: 2.0  
**Status**: ✅ Implementado e testado
