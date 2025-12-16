#!/usr/bin/env python3
"""
PASSO 25: Simulação Kelly vs Fixed Risk em Backtest Histórico
===============================================================

Simula o impacto do Kelly Criterion nos backtests 2021-2024
usando estatísticas reais dos resultados do PASSO 23.6
"""

def simulate_kelly_impact():
    """Simula crescimento de capital com Kelly vs Fixed Risk"""
    
    # Estatísticas reais do PASSO 23.6 (2021-2024, 4 anos)
    stats = {
        'initial_capital': 100000,
        'total_trades': 267,
        'win_rate': 0.524,  # 52.4%
        'avg_win': 1509,    # $1,509
        'avg_loss': 1333,   # $1,333
        'total_return_pct': 36.46,
        'max_drawdown_pct': 15.94
    }
    
    # Calcular Kelly
    p = stats['win_rate']
    q = 1 - p
    b = stats['avg_win'] / stats['avg_loss']  # 1.13x
    
    kelly_full = (p * b - q) / b
    kelly_fraction = kelly_full * 0.25  # 25% Kelly
    kelly_safe = max(0.005, min(kelly_fraction, 0.15))
    
    fixed_risk = 0.02  # 2% padrão
    
    print("="*90)
    print("PASSO 25: SIMULAÇÃO KELLY vs FIXED RISK (2021-2024)")
    print("="*90)
    
    print(f"\n📊 ESTATÍSTICAS HISTÓRICAS (Real):")
    print(f"  Período: 2021-2024 (4 anos)")
    print(f"  Total Trades: {stats['total_trades']}")
    print(f"  Win Rate: {stats['win_rate']:.1%}")
    print(f"  Avg Win: ${stats['avg_win']:,.0f}")
    print(f"  Avg Loss: ${stats['avg_loss']:,.0f}")
    print(f"  Payoff Ratio: {b:.2f}x")
    print(f"  Return Alcançado: {stats['total_return_pct']:+.2f}%")
    print(f"  Max Drawdown: {stats['max_drawdown_pct']:.2f}%")
    
    print(f"\n🎯 KELLY CRITERION:")
    print(f"  Kelly Full: {kelly_full:.4f} ({kelly_full*100:.2f}%)")
    print(f"  Kelly Fractional (25%): {kelly_fraction:.4f} ({kelly_fraction*100:.2f}%)")
    print(f"  Kelly Safe (limitado): {kelly_safe:.4f} ({kelly_safe*100:.2f}%)")
    print(f"  Fixed Risk (baseline): {fixed_risk:.4f} ({fixed_risk*100:.2f}%)")
    
    # Simulação simplificada (assumindo retorno proporcional ao risco)
    # NOTA: Isso é simplificação - na realidade Kelly ajusta dinamicamente
    
    # Calcular retorno esperado por trade
    wins = int(stats['total_trades'] * stats['win_rate'])
    losses = stats['total_trades'] - wins
    
    # Fixed Risk
    profit_fixed = (wins * stats['avg_win'] * fixed_risk) - (losses * stats['avg_loss'] * fixed_risk)
    final_capital_fixed = stats['initial_capital'] + profit_fixed
    return_fixed = (final_capital_fixed / stats['initial_capital'] - 1) * 100
    
    # Kelly Risk
    profit_kelly = (wins * stats['avg_win'] * kelly_safe) - (losses * stats['avg_loss'] * kelly_safe)
    final_capital_kelly = stats['initial_capital'] + profit_kelly
    return_kelly = (final_capital_kelly / stats['initial_capital'] - 1) * 100
    
    # Drawdown esperado (escala com risco)
    dd_ratio = kelly_safe / fixed_risk
    max_dd_kelly = stats['max_drawdown_pct'] * dd_ratio
    
    print(f"\n💰 SIMULAÇÃO DE CRESCIMENTO (Simplificada):")
    print(f"\n  FIXED RISK (2.0%):")
    print(f"    Capital Final: ${final_capital_fixed:,.0f}")
    print(f"    Return: {return_fixed:+.2f}%")
    print(f"    Max DD: ~{stats['max_drawdown_pct']:.2f}%")
    
    print(f"\n  KELLY RISK ({kelly_safe*100:.2f}%):")
    print(f"    Capital Final: ${final_capital_kelly:,.0f}")
    print(f"    Return: {return_kelly:+.2f}%")
    print(f"    Max DD estimado: ~{max_dd_kelly:.2f}%")
    
    if return_kelly > return_fixed:
        advantage = return_kelly - return_fixed
        dd_increase = max_dd_kelly - stats['max_drawdown_pct']
        print(f"\n  ✅ VANTAGEM KELLY: +{advantage:.2f}pp de retorno")
        print(f"  ⚠️  TRADE-OFF: +{dd_increase:.2f}pp de drawdown esperado")
        print(f"  📊 SHARPE ESPERADO: Similar ou levemente superior (mesma estratégia)")
    else:
        print(f"\n  ⚠️  Fixed Risk superior neste caso")
    
    print(f"\n🔬 ANÁLISE DE KELLY:")
    print(f"  Kelly Full {kelly_full*100:.2f}% sugere que o sistema tem EDGE positivo")
    print(f"  Fração 25% reduz volatilidade e drawdown")
    print(f"  Com WR {stats['win_rate']:.1%} e Payoff {b:.2f}x, Kelly é {kelly_safe/fixed_risk:.1f}x maior que fixed risk")
    
    print(f"\n💡 RECOMENDAÇÃO:")
    if kelly_safe > fixed_risk * 1.5:
        print(f"  ✅ Sistema forte o suficiente para usar Kelly Fractional")
        print(f"  ✅ Kelly sugere aumentar risco de {fixed_risk*100:.1f}% → {kelly_safe*100:.2f}%")
        print(f"  ⚠️  Monitorar drawdown de perto (pode aumentar {dd_increase:.1f}pp)")
    elif kelly_safe > fixed_risk:
        print(f"  🟡 Kelly sugere aumento MODERADO ({fixed_risk*100:.1f}% → {kelly_safe*100:.2f}%)")
        print(f"  🟡 Benefício marginal, manter fixed risk também é válido")
    else:
        print(f"  ⚠️  Kelly sugere MANTER ou REDUZIR risco atual")
        print(f"  ⚠️  Sistema pode não ter edge suficiente")
    
    print("\n" + "="*90)
    print("📌 NOTA: Esta é simulação simplificada.")
    print("   Para teste real, habilitar kelly_enabled=True no RiskManager")
    print("   e re-executar backtest completo 2021-2024.")
    print("="*90)

if __name__ == "__main__":
    simulate_kelly_impact()
