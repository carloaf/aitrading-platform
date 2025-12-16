#!/usr/bin/env python3
"""
PARAMETER ADJUSTMENT CALCULATOR - PASSO 27.1
============================================
Calcula ajustes de parâmetros baseado em métricas WFO

Autor: CryptoDev Assistant
Data: 16/Dez/2025
"""

import argparse
import re
from typing import Dict, List, Tuple

# Regras de recalibração
RECALIBRATION_RULES = {
    'high_drawdown': {
        'condition': lambda dd: dd > 15,
        'params': {
            'risk_per_trade': -0.004,  # 2% → 1.6%
            'tp_multiplier_sideways': +0.5,  # 2.5x → 3.0x
        },
        'reason': 'Drawdown alto (>15%) - Reduzir risco'
    },
    'low_win_rate': {
        'condition': lambda wr: wr < 45,
        'params': {
            'min_quality_sideways': +10,  # 70 → 80
            'regime_confirmation_threshold': +2,  # 8 → 10
        },
        'reason': 'Win rate baixo (<45%) - Aumentar seletividade'
    },
    'low_sharpe': {
        'condition': lambda sharpe: sharpe < 0.5,
        'params': {
            'tp_multiplier_sideways': +0.5,  # Melhor R/R
            'break_even_atr_multiplier': -0.1,  # 0.5 → 0.4
        },
        'reason': 'Sharpe baixo (<0.5) - Melhorar Risk/Reward'
    },
    'few_trades': {
        'condition': lambda trades: trades < 5,
        'params': {
            'min_quality_sideways': -10,  # 70 → 60
            'rsi_divergence_lookback': -2,  # Relaxar filtros
        },
        'reason': 'Poucos trades (<5) - Relaxar filtros'
    },
    'negative_return': {
        'condition': lambda ret: ret < -5,
        'params': {
            'TRADING_PAUSED': True,  # Flag especial
        },
        'reason': '🚨 CRÍTICO: Return < -5% - PAUSAR TRADING'
    }
}

def analyze_metrics(return_pct: float, sharpe: float, max_dd: float, 
                    win_rate: float, trades: int) -> Dict[str, any]:
    """Analisa métricas e identifica problemas"""
    
    issues = []
    triggered_rules = []
    
    # Verificar cada regra
    for rule_name, rule in RECALIBRATION_RULES.items():
        if rule_name == 'high_drawdown' and rule['condition'](max_dd):
            issues.append(rule['reason'])
            triggered_rules.append(rule_name)
        elif rule_name == 'low_win_rate' and rule['condition'](win_rate):
            issues.append(rule['reason'])
            triggered_rules.append(rule_name)
        elif rule_name == 'low_sharpe' and rule['condition'](sharpe):
            issues.append(rule['reason'])
            triggered_rules.append(rule_name)
        elif rule_name == 'few_trades' and rule['condition'](trades):
            issues.append(rule['reason'])
            triggered_rules.append(rule_name)
        elif rule_name == 'negative_return' and rule['condition'](return_pct):
            issues.append(rule['reason'])
            triggered_rules.append(rule_name)
    
    return {
        'issues': issues,
        'triggered_rules': triggered_rules
    }

def calculate_adjustments(triggered_rules: List[str], severity: str) -> Dict[str, float]:
    """Calcula ajustes agregados de todos os rules triggered"""
    
    adjustments = {}
    
    for rule_name in triggered_rules:
        rule_params = RECALIBRATION_RULES[rule_name]['params']
        
        for param, delta in rule_params.items():
            if param == 'TRADING_PAUSED':
                adjustments[param] = True
                continue
            
            if param not in adjustments:
                adjustments[param] = 0
            
            # Agregar ajustes
            adjustments[param] += delta
    
    # Aplicar multiplicador de severidade
    if severity == 'critical':
        for param in adjustments:
            if param != 'TRADING_PAUSED':
                adjustments[param] *= 1.5
    
    return adjustments

def format_adjustments(adjustments: Dict[str, float]) -> str:
    """Formata ajustes para output legível"""
    
    if not adjustments:
        return "✅ Nenhum ajuste necessário"
    
    output = []
    output.append("🔧 Ajustes Calculados:")
    output.append("=" * 60)
    
    for param, delta in adjustments.items():
        if param == 'TRADING_PAUSED':
            output.append(f"🚨 {param}: ATIVAR")
        else:
            sign = "+" if delta > 0 else ""
            output.append(f"   {param}: {sign}{delta}")
    
    return "\n".join(output)

def apply_adjustments_to_file(adjustments: Dict[str, float], 
                              file_path: str = 'services/execution-engine/src/meta_simulation.py',
                              dry_run: bool = False) -> bool:
    """Aplica ajustes ao arquivo meta_simulation.py"""
    
    if dry_run:
        return True
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Aplicar cada ajuste
        for param, delta in adjustments.items():
            if param == 'TRADING_PAUSED':
                # Adicionar flag especial no topo do arquivo
                if 'TRADING_PAUSED = True' not in content:
                    content = '# AUTO-RECALIBRATION: TRADING PAUSED\nTRADING_PAUSED = True\n\n' + content
                continue
            
            # Procurar parâmetro no código
            # Padrões comuns:
            # self.param = value
            # param = value
            
            patterns = [
                rf'(self\.{param}\s*=\s*)([0-9.]+)',
                rf'({param}\s*=\s*)([0-9.]+)'
            ]
            
            found = False
            for pattern in patterns:
                matches = list(re.finditer(pattern, content))
                if matches:
                    found = True
                    # Pegar última ocorrência (geralmente é a definição)
                    match = matches[-1]
                    old_value = float(match.group(2))
                    new_value = old_value + delta
                    
                    # Substituir
                    old_full = match.group(0)
                    new_full = f"{match.group(1)}{new_value}"
                    content = content.replace(old_full, new_full, 1)
                    
                    print(f"   ✓ {param}: {old_value} → {new_value} (Δ{delta:+.3f})")
                    break
            
            if not found:
                print(f"   ⚠️  Parâmetro '{param}' não encontrado no arquivo")
        
        # Salvar arquivo modificado
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            return True
        else:
            print("⚠️  Nenhuma modificação aplicada")
            return False
    
    except Exception as e:
        print(f"❌ Erro ao aplicar ajustes: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Calculate parameter adjustments based on WFO results')
    parser.add_argument('--severity', choices=['moderate', 'critical'], required=True,
                       help='Severity level of recalibration')
    parser.add_argument('--return-pct', type=float, required=True, help='Return percentage')
    parser.add_argument('--sharpe', type=float, required=True, help='Sharpe ratio')
    parser.add_argument('--max-dd', type=float, required=True, help='Maximum drawdown percentage')
    parser.add_argument('--win-rate', type=float, required=True, help='Win rate percentage')
    parser.add_argument('--trades', type=int, default=10, help='Number of trades')
    parser.add_argument('--dry-run', action='store_true', help='Calculate but do not apply')
    
    args = parser.parse_args()
    
    # Análise
    analysis = analyze_metrics(
        return_pct=args.return_pct,
        sharpe=args.sharpe,
        max_dd=args.max_dd,
        win_rate=args.win_rate,
        trades=args.trades
    )
    
    if not analysis['triggered_rules']:
        print("✅ Nenhum problema detectado")
        return 0
    
    print("\n📊 Problemas Identificados:")
    for issue in analysis['issues']:
        print(f"   • {issue}")
    
    print("")
    
    # Calcular ajustes
    adjustments = calculate_adjustments(analysis['triggered_rules'], args.severity)
    
    # Output ajustes
    print(format_adjustments(adjustments))
    
    if not args.dry_run:
        print("\n🔧 Aplicando ajustes ao arquivo...")
        success = apply_adjustments_to_file(adjustments, dry_run=False)
        return 0 if success else 1
    
    return 0

if __name__ == '__main__':
    exit(main())
