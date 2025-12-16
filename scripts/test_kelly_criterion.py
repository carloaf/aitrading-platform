#!/usr/bin/env python3
"""
PASSO 25: Teste do Kelly Criterion
===================================

Valida implementação do Kelly Criterion no RiskManager.

Exemplos de Teste:
1. Sistema lucrativo (WR 55%, R/R 1.5) → Kelly positivo
2. Sistema break-even (WR 50%, R/R 1.0) → Kelly zero
3. Sistema perdedor (WR 40%, R/R 1.0) → Kelly negativo
4. Poucos trades (< 30) → Usa fixed risk
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../services/execution-engine/src'))

from risk_manager import RiskManager, MarketPhase

def test_kelly_scenarios():
    """Testa diferentes cenários com Kelly Criterion"""
    
    rm = RiskManager(base_risk_per_trade=0.02)
    
    print("="*80)
    print("PASSO 25: TESTE KELLY CRITERION")
    print("="*80)
    
    scenarios = [
        {
            'name': '🟢 Sistema EXCELENTE (WR 60%, Avg Win $2000, Avg Loss $1000)',
            'win_rate': 0.60,
            'avg_win': 2000,
            'avg_loss': 1000,
            'num_trades': 50,
            'expected': 'Kelly alto, posição agressiva'
        },
        {
            'name': '🟢 Sistema BOM (WR 55%, Avg Win $1500, Avg Loss $1000)',
            'win_rate': 0.55,
            'avg_win': 1500,
            'avg_loss': 1000,
            'num_trades': 50,
            'expected': 'Kelly moderado'
        },
        {
            'name': '🟡 Sistema MARGINAL (WR 52%, Avg Win $1200, Avg Loss $1000)',
            'win_rate': 0.52,
            'avg_win': 1200,
            'avg_loss': 1000,
            'num_trades': 50,
            'expected': 'Kelly baixo'
        },
        {
            'name': '🟡 Sistema BREAK-EVEN (WR 50%, R/R 1.0)',
            'win_rate': 0.50,
            'avg_win': 1000,
            'avg_loss': 1000,
            'num_trades': 50,
            'expected': 'Kelly ~0 (sem edge)'
        },
        {
            'name': '🔴 Sistema PERDEDOR (WR 40%, R/R 1.0)',
            'win_rate': 0.40,
            'avg_win': 1000,
            'avg_loss': 1000,
            'num_trades': 50,
            'expected': 'Kelly NEGATIVO'
        },
        {
            'name': '⚠️  POUCOS TRADES (apenas 15 trades)',
            'win_rate': 0.60,
            'avg_win': 2000,
            'avg_loss': 1000,
            'num_trades': 15,
            'expected': 'Usa fixed risk (insuficiente)'
        },
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print(f"   Win Rate: {scenario['win_rate']:.1%}")
        print(f"   Avg Win: ${scenario['avg_win']:,.0f}")
        print(f"   Avg Loss: ${scenario['avg_loss']:,.0f}")
        print(f"   Trades: {scenario['num_trades']}")
        print(f"   Expected: {scenario['expected']}")
        
        kelly_risk = rm.calculate_kelly_criterion(
            win_rate=scenario['win_rate'],
            avg_win=scenario['avg_win'],
            avg_loss=scenario['avg_loss'],
            num_trades=scenario['num_trades']
        )
        
        # Calcular Kelly Full para comparação
        p = scenario['win_rate']
        q = 1 - p
        b = scenario['avg_win'] / scenario['avg_loss']
        kelly_full = (p * b - q) / b if b > 0 else 0
        kelly_fractional = kelly_full * rm.kelly_fraction
        
        print(f"   → Kelly Full: {kelly_full:.4f} ({kelly_full*100:.2f}%)")
        print(f"   → Kelly Fractional ({rm.kelly_fraction:.0%}): {kelly_fractional:.4f} ({kelly_fractional*100:.2f}%)")
        print(f"   → Kelly Safe (limitado): {kelly_risk:.4f} ({kelly_risk*100:.2f}%)")
        print(f"   → Fixed Risk (baseline): {rm.base_risk_per_trade:.4f} ({rm.base_risk_per_trade*100:.2f}%)")
        
        if kelly_risk > rm.base_risk_per_trade:
            diff = kelly_risk - rm.base_risk_per_trade
            print(f"   ✅ Kelly sugere AUMENTAR risco em {diff*100:.2f}pp")
        elif kelly_risk < rm.base_risk_per_trade:
            diff = rm.base_risk_per_trade - kelly_risk
            print(f"   ⚠️  Kelly sugere REDUZIR risco em {diff*100:.2f}pp")
        else:
            print(f"   ➡️  Kelly = Fixed Risk (sem ajuste)")
    
    print("\n" + "="*80)
    print("📊 COMPARAÇÃO KELLY vs FIXED RISK")
    print("="*80)
    
    # Calcular crescimento esperado (exemplo simplificado)
    capital = 100000
    num_trades = 100
    
    for scenario in scenarios[:3]:  # Apenas sistemas lucrativos
        print(f"\n{scenario['name'][:50]}")
        
        # Fixed Risk
        fixed_risk = rm.base_risk_per_trade
        trades_won = int(num_trades * scenario['win_rate'])
        trades_lost = num_trades - trades_won
        
        # Simplificado: assumindo risco fixo
        total_profit_fixed = (trades_won * scenario['avg_win'] * fixed_risk) - \
                            (trades_lost * scenario['avg_loss'] * fixed_risk)
        final_capital_fixed = capital + total_profit_fixed
        
        # Kelly Risk
        kelly_risk = rm.calculate_kelly_criterion(
            scenario['win_rate'], scenario['avg_win'], scenario['avg_loss'], 50
        )
        total_profit_kelly = (trades_won * scenario['avg_win'] * kelly_risk) - \
                            (trades_lost * scenario['avg_loss'] * kelly_risk)
        final_capital_kelly = capital + total_profit_kelly
        
        print(f"  Fixed Risk (2%): ${final_capital_fixed:,.0f} ({(final_capital_fixed/capital-1)*100:+.2f}%)")
        print(f"  Kelly Risk ({kelly_risk*100:.2f}%): ${final_capital_kelly:,.0f} ({(final_capital_kelly/capital-1)*100:+.2f}%)")
        
        if final_capital_kelly > final_capital_fixed:
            advantage = (final_capital_kelly / final_capital_fixed - 1) * 100
            print(f"  ✅ Kelly performance: +{advantage:.2f}% melhor")
        else:
            print(f"  ⚠️  Fixed risk performance superior (Kelly conservador demais)")
    
    print("\n" + "="*80)
    print("✅ TESTE CONCLUÍDO")
    print("="*80)

if __name__ == "__main__":
    test_kelly_scenarios()
