#!/usr/bin/env python3
"""
Análise Detalhada Q3/2025 - Identificar causas da perda
"""

import json

# Dados do backtest Q3/2025
data = {
    "success": True,
    "symbol": "BTCUSDT",
    "period": "2025-07-01 to 2025-09-30",
    "candles_analyzed": 2185,
    "performance": {
        "initial_capital": 100000.0,
        "final_capital": 98287.35,
        "total_return": -1712.65,
        "total_return_pct": -1.71,
        "max_drawdown_pct": 7.12
    },
    "risk_metrics": {
        "sharpe_ratio": -0.88,
        "sortino_ratio": -0.53,
        "profit_factor": 0.8
    },
    "trade_stats": {
        "total_trades": 15,
        "winning_trades": 8,
        "losing_trades": 7,
        "win_rate": 53.3,
        "avg_win": 748.68,
        "avg_loss": 1070.85
    },
    "adaptability": {
        "regime_changes": 17,
        "strategy_switches": 9
    },
    "exit_reasons": {
        "TAKE_PROFIT": 6,
        "STOP_LOSS": 9
    },
    "debug": {
        "entry_accepted": {
            "rsi_divergence_bearish:SHORT:sideways": 3,
            "bear_market_short:SHORT:bear": 1,
            "momentum:LONG:bull": 3,
            "trend_following:LONG:bull": 5,
            "rsi_divergence_bullish:LONG:sideways": 2,
            "liquidity_grab:LONG:sideways": 1
        }
    }
}

print("="*80)
print("🔍 ANÁLISE DETALHADA Q3/2025 (Jul-Set)")
print("="*80)

print("\n📊 RESUMO DO PERÍODO:")
print(f"   Candles analisados: {data['candles_analyzed']:,}")
print(f"   Capital inicial: ${data['performance']['initial_capital']:,.2f}")
print(f"   Capital final: ${data['performance']['final_capital']:,.2f}")
print(f"   Perda total: ${data['performance']['total_return']:,.2f} ({data['performance']['total_return_pct']:+.2f}%)")
print(f"   Max Drawdown: {data['performance']['max_drawdown_pct']:.2f}%")

print("\n📈 MÉTRICAS DE RISCO:")
print(f"   Sharpe Ratio: {data['risk_metrics']['sharpe_ratio']:.2f} (NEGATIVO)")
print(f"   Sortino Ratio: {data['risk_metrics']['sortino_ratio']:.2f}")
print(f"   Profit Factor: {data['risk_metrics']['profit_factor']:.2f} (<1.0 = perda)")

print("\n📊 ESTATÍSTICAS DE TRADES:")
print(f"   Total de trades: {data['trade_stats']['total_trades']}")
print(f"   Trades vencedores: {data['trade_stats']['winning_trades']} ({data['trade_stats']['win_rate']:.1f}%)")
print(f"   Trades perdedores: {data['trade_stats']['losing_trades']}")
print(f"   Lucro médio: ${data['trade_stats']['avg_win']:.2f}")
print(f"   Perda média: ${data['trade_stats']['avg_loss']:.2f}")
print(f"   Ratio L/P: {data['trade_stats']['avg_win']/data['trade_stats']['avg_loss']:.2f}x (ruim se <1.5)")

print("\n🔄 ADAPTABILIDADE:")
print(f"   Mudanças de regime: {data['adaptability']['regime_changes']} (muito alto!)")
print(f"   Trocas de estratégia: {data['adaptability']['strategy_switches']}")
print(f"   Frequência regime: {data['candles_analyzed']/data['adaptability']['regime_changes']:.0f} candles/mudança")

print("\n🚪 RAZÕES DE SAÍDA:")
tp = data['exit_reasons']['TAKE_PROFIT']
sl = data['exit_reasons']['STOP_LOSS']
total = tp + sl
print(f"   Take Profit: {tp} ({100*tp/total:.0f}%)")
print(f"   Stop Loss: {sl} ({100*sl/total:.0f}%) ⚠️ MAIORIA")
print(f"   Ratio TP/SL: {tp/sl:.2f}x (ideal >1.5)")

print("\n📍 DISTRIBUIÇÃO DE ENTRADAS:")
entries = data['debug']['entry_accepted']
total_entries = sum(entries.values())
print(f"   Total de entradas: {total_entries}")
for strategy, count in sorted(entries.items(), key=lambda x: x[1], reverse=True):
    strat_name, direction, regime = strategy.split(':')
    pct = 100*count/total_entries
    print(f"   - {strat_name} ({direction}, {regime}): {count} ({pct:.0f}%)")

print("\n" + "="*80)
print("🔴 PROBLEMAS IDENTIFICADOS:")
print("="*80)

print("\n1. ⚠️ PROFIT FACTOR < 1.0")
print("   - 0.8 significa que perdas > lucros")
print("   - Avg Loss ($1,071) > Avg Win ($749)")
print("   - Ratio L/P de apenas 0.70x (muito baixo)")

print("\n2. ⚠️ STOP LOSSES EXCESSIVOS")
print("   - 9 stops vs 6 take profits (60% vs 40%)")
print("   - Sistema saindo cedo demais em perdas")
print("   - Stops podem estar muito apertados")

print("\n3. ⚠️ REGIME CHANGES EXCESSIVOS")
print("   - 17 mudanças em ~2,185 candles")
print("   - 1 mudança a cada 128 candles (~5 dias)")
print("   - Provável mercado choppy/lateral instável")
print("   - Trades fechados prematuramente por regime_change")

print("\n4. ⚠️ DESBALANCEAMENTO LONG/SHORT")
entries_long = sum(v for k, v in entries.items() if 'LONG' in k)
entries_short = sum(v for k, v in entries.items() if 'SHORT' in k)
print(f"   - Entradas LONG: {entries_long} ({100*entries_long/total_entries:.0f}%)")
print(f"   - Entradas SHORT: {entries_short} ({100*entries_short/total_entries:.0f}%)")
print("   - Predomínio LONG em mercado que pode ter sido baixista")

print("\n5. ⚠️ WIN RATE BOM MAS INSUFICIENTE")
print("   - 53.3% de acerto é bom")
print("   - Mas losses maiores que wins anulam vantagem")
print("   - Problema não é entrada, é gestão de risco")

print("\n" + "="*80)
print("💡 RECOMENDAÇÕES:")
print("="*80)

print("\n1. 🔧 AJUSTAR STOPS E TARGETS")
print("   - Aumentar TP target: SIDEWAYS 1.5x → 2.0x ATR")
print("   - Considerar trailing stop mais agressivo")
print("   - Proteger lucros melhor (move stop to break-even)")

print("\n2. 🔧 REDUZIR REGIME OSCILLATION")
print("   - Aumentar hysteresis: 6 → 8 candles")
print("   - Exigir confirmação mais forte de mudança")
print("   - Evitar fechar trades vencedores por regime_change")

print("\n3. 🔧 FILTROS MAIS RIGOROSOS")
print("   - Aumentar min_quality em SIDEWAYS: 60 → 70")
print("   - Adicionar filtro de volatilidade (evitar chop)")
print("   - Reduzir número de trades em períodos instáveis")

print("\n4. 🔧 MELHORAR RISK/REWARD")
print("   - Atual: 0.70x (muito ruim)")
print("   - Target: >1.5x")
print("   - Usar Kelly sizing para otimizar position size")

print("\n5. 📊 VALIDAR EM OUTROS PARES")
print("   - Testar ETH/SOL em Q3/2025")
print("   - Verificar se problema é específico de BTC")
print("   - Pode ser mercado geral em 2025")

print("\n✅ Análise concluída!")
print("💾 Próximo passo: Comparar com ETH/SOL em Q3/2025")
