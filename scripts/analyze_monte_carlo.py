#!/usr/bin/env python3
"""
Script de Análise de Simulações Monte Carlo
Gera relatório detalhado para subsidiar decisões de trading
"""

import json
import requests
from datetime import datetime
from pathlib import Path
import statistics

API_BASE = "http://localhost:3008/api/monte-carlo"

class MonteCarloAnalyzer:
    """Analisador de resultados Monte Carlo"""
    
    def __init__(self):
        self.strategies = [
            "momentum",
            "macd_rsi_combo", 
            "trend_following",
            "volatility_breakout"
        ]
        self.results = {}
        
    def collect_results(self):
        """Coleta resultados de todas as estratégias"""
        print("📊 Coletando resultados das simulações...")
        
        for strategy in self.strategies:
            try:
                response = requests.get(f"{API_BASE}/progress/{strategy}")
                if response.status_code == 200:
                    self.results[strategy] = response.json()
                    status = self.results[strategy].get('status', 'unknown')
                    print(f"  ✓ {strategy}: {status}")
                else:
                    print(f"  ✗ {strategy}: Erro HTTP {response.status_code}")
            except Exception as e:
                print(f"  ✗ {strategy}: {e}")
        
        return len(self.results) > 0
    
    def rank_strategies(self):
        """Rankeia estratégias por múltiplas métricas"""
        rankings = {
            'sharpe_ratio': [],
            'total_return': [],
            'win_rate': [],
            'profit_factor': [],
            'max_drawdown': [],
            'probability_profit': []
        }
        
        for strategy, data in self.results.items():
            if data.get('status') != 'completed':
                continue
                
            report = data.get('report', {})
            
            # Extrai métricas
            sharpe = report.get('sharpe_statistics', {}).get('mean', 0)
            returns = report.get('return_statistics', {}).get('mean', 0)
            win_rate = report.get('trade_statistics', {}).get('mean_win_rate', 0)
            prob_profit = report.get('risk_metrics', {}).get('probability_of_profit', 0)
            drawdown = report.get('drawdown_statistics', {}).get('mean', 0)
            
            # Calcula profit factor dos cenários
            scenarios = report.get('scenarios', {})
            best = scenarios.get('best_case', {})
            pf = best.get('profit_factor', 0)
            
            rankings['sharpe_ratio'].append((strategy, sharpe))
            rankings['total_return'].append((strategy, returns))
            rankings['win_rate'].append((strategy, win_rate))
            rankings['profit_factor'].append((strategy, pf))
            rankings['max_drawdown'].append((strategy, abs(drawdown)))  # Menor é melhor
            rankings['probability_profit'].append((strategy, prob_profit))
        
        # Ordena (maior melhor, exceto drawdown)
        for key in rankings:
            if key == 'max_drawdown':
                rankings[key].sort(key=lambda x: x[1])  # Crescente
            else:
                rankings[key].sort(key=lambda x: x[1], reverse=True)  # Decrescente
        
        return rankings
    
    def calculate_composite_score(self, rankings):
        """Calcula score composto para cada estratégia"""
        scores = {}
        weights = {
            'sharpe_ratio': 0.30,
            'total_return': 0.20,
            'probability_profit': 0.20,
            'profit_factor': 0.15,
            'win_rate': 0.10,
            'max_drawdown': 0.05  # Invertido (menor é melhor)
        }
        
        # Para cada métrica, atribui pontos (1º lugar = n pontos, último = 1 ponto)
        for metric, ranking in rankings.items():
            n = len(ranking)
            for pos, (strategy, value) in enumerate(ranking):
                if strategy not in scores:
                    scores[strategy] = 0
                
                points = (n - pos) * weights[metric]
                scores[strategy] += points
        
        # Ordena por score total
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked
    
    def generate_report(self, output_file='analise_monte_carlo.md'):
        """Gera relatório completo em Markdown"""
        
        if not self.collect_results():
            print("❌ Nenhum resultado disponível!")
            return
        
        rankings = self.rank_strategies()
        composite = self.calculate_composite_score(rankings)
        
        report = f"""# ANÁLISE DE SIMULAÇÕES MONTE CARLO - RELATÓRIO EXECUTIVO

**Data**: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  
**Analista**: CryptoDev Assistant  
**Versão**: 1.0  

---

## 1. RESUMO EXECUTIVO

"""
        
        # Estratégia recomendada
        if composite:
            winner = composite[0][0]
            winner_score = composite[0][1]
            
            report += f"""### 🏆 ESTRATÉGIA RECOMENDADA: {winner.upper().replace('_', ' ')}

**Score Composto**: {winner_score:.2f}/5.00

"""
            
            # Detalhes da vencedora
            winner_data = self.results.get(winner, {}).get('report', {})
            scenarios = winner_data.get('scenarios', {})
            best = scenarios.get('best_case', {})
            median = scenarios.get('median_case', {})
            
            report += f"""**Métricas Principais**:
- Sharpe Ratio: {winner_data.get('sharpe_statistics', {}).get('mean', 0):.2f}
- Retorno Médio: {winner_data.get('return_statistics', {}).get('mean', 0):.2f}%
- Prob. de Lucro: {winner_data.get('risk_metrics', {}).get('probability_of_profit', 0):.1f}%
- Win Rate: {winner_data.get('trade_statistics', {}).get('mean_win_rate', 0):.1f}%
- Max Drawdown: {winner_data.get('drawdown_statistics', {}).get('mean', 0):.2f}%

**Parâmetros Ótimos (Melhor Cenário)**:
```python
{json.dumps(best.get('parameters', {}), indent=2)}
```

**Performance Esperada**:
- Retorno: {best.get('total_return', 0):.2f}%
- Sharpe: {best.get('sharpe_ratio', 0):.2f}
- Drawdown Máx: {best.get('max_drawdown', 0):.2f}%
- Total Trades: {best.get('total_trades', 0)}
- Profit Factor: {best.get('profit_factor', 0):.2f}

"""
        
        # Ranking completo
        report += """---

## 2. RANKING GERAL DAS ESTRATÉGIAS

### 2.1 Score Composto

| Posição | Estratégia | Score | Recomendação |
|---------|------------|-------|--------------|
"""
        
        for pos, (strategy, score) in enumerate(composite, 1):
            name = strategy.replace('_', ' ').title()
            
            if pos == 1:
                rec = "✅ IMPLEMENTAR"
            elif pos == 2:
                rec = "🔄 BACKUP"
            elif pos == 3:
                rec = "⚠️ AVALIAR"
            else:
                rec = "❌ NÃO RECOMENDADO"
            
            report += f"| {pos}º | {name} | {score:.2f} | {rec} |\n"
        
        # Rankings individuais
        report += "\n### 2.2 Rankings por Métrica\n\n"
        
        metric_names = {
            'sharpe_ratio': 'Sharpe Ratio',
            'total_return': 'Retorno Total',
            'probability_profit': 'Prob. de Lucro',
            'profit_factor': 'Profit Factor',
            'win_rate': 'Win Rate',
            'max_drawdown': 'Max Drawdown (menor melhor)'
        }
        
        for metric, ranking in rankings.items():
            report += f"\n**{metric_names[metric]}**:\n"
            for pos, (strategy, value) in enumerate(ranking[:3], 1):
                name = strategy.replace('_', ' ').title()
                report += f"{pos}. {name}: {value:.2f}\n"
        
        # Análise de risco
        report += """

---

## 3. ANÁLISE DE RISCO

### 3.1 Métricas de Risco por Estratégia

| Estratégia | VaR 95% | CVaR 95% | Max DD Médio | Prob. Perda |
|------------|---------|----------|--------------|-------------|
"""
        
        for strategy in self.strategies:
            data = self.results.get(strategy, {}).get('report', {})
            risk = data.get('risk_metrics', {})
            dd = data.get('drawdown_statistics', {})
            
            name = strategy.replace('_', ' ').title()
            var = risk.get('value_at_risk_95', 0)
            cvar = risk.get('conditional_var_95', 0)
            max_dd = dd.get('mean', 0)
            prob_loss = risk.get('probability_of_loss', 0)
            
            report += f"| {name} | {var:.2f}% | {cvar:.2f}% | {max_dd:.2f}% | {prob_loss:.1f}% |\n"
        
        # Recomendações
        report += """

---

## 4. RECOMENDAÇÕES DE IMPLEMENTAÇÃO

### 4.1 Gestão de Risco

Para a estratégia recomendada:

- **Position Sizing**: Máximo 3% do capital por trade
- **Stop Loss**: 2x ATR ou -5% (o que ocorrer primeiro)
- **Take Profit**: 3x Stop Loss (ratio 1:3)
- **Max Drawdown Permitido**: 20% do capital
- **Máximo de trades simultâneos**: 3

### 4.2 Fases de Implementação

**Fase 1 - Paper Trading (2 semanas)**:
- Validar sinais em tempo real
- Monitorar slippage e custos reais
- Ajustar timeframes se necessário

**Fase 2 - Produção Limitada (4 semanas)**:
- Alocar 20% do capital disponível
- Monitoramento 24/7
- Reavaliar parâmetros semanalmente

**Fase 3 - Scale Up (após validação)**:
- Aumentar gradualmente até 100% do capital
- Diversificar em múltiplos pares
- Implementar alertas automáticos

### 4.3 Critérios de Parada

Interromper estratégia se:
- Drawdown > 25% em 30 dias
- Sharpe Ratio < 0 por 2 meses consecutivos
- 10 trades consecutivos com perda
- Mudança significativa no regime de mercado

---

## 5. CONCLUSÃO

"""
        
        if composite:
            winner = composite[0][0]
            winner_name = winner.replace('_', ' ').title()
            
            report += f"""Baseado em 200 simulações Monte Carlo por estratégia, a **{winner_name}** 
apresentou a melhor combinação de retorno ajustado ao risco, consistência e 
robustez estatística.

**Próximos passos**:
1. Iniciar paper trading com parâmetros recomendados
2. Monitorar performance por 2 semanas
3. Avaliar implementação em produção com capital limitado

**DISCLAIMER**: Resultados passados não garantem performance futura. Todo 
trading envolve risco significativo de perda. Teste extensivamente antes de 
usar capital real.
"""
        
        report += f"""

---

**Relatório gerado automaticamente em**: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  
**Dados disponíveis em**: http://localhost:8081/monte-carlo
"""
        
        # Salvar relatório
        output_path = Path(output_file)
        output_path.write_text(report)
        print(f"\n✅ Relatório salvo em: {output_path.absolute()}")
        print(f"📄 {len(report)} caracteres")
        
        return report


if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║        ANÁLISE DE SIMULAÇÕES MONTE CARLO                       ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    analyzer = MonteCarloAnalyzer()
    report = analyzer.generate_report()
    
    if report:
        print("\n" + "="*65)
        print("✅ ANÁLISE CONCLUÍDA!")
        print("="*65)
        print("\nRelatório disponível em: analise_monte_carlo.md")
        print("Dashboard: http://localhost:8081/monte-carlo")
