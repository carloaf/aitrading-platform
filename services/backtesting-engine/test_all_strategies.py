"""
Script de teste rápido para validar todas as estratégias
Execute: python test_all_strategies.py
"""

import sys
import os

# Adicionar o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies import StrategyManager


def generate_test_data(periods=100):
    """Gera dados de teste simulados"""
    dates = pd.date_range(end=datetime.now(), periods=periods, freq='1H')
    
    # Preço com tendência + ruído
    base_price = 45000
    trend = np.linspace(0, 5000, periods)
    noise = np.random.normal(0, 500, periods)
    prices = base_price + trend + noise
    
    # OHLCV
    data = pd.DataFrame(index=dates)
    data['Open'] = prices
    data['High'] = prices * 1.02
    data['Low'] = prices * 0.98
    data['Close'] = prices + np.random.normal(0, 100, periods)
    data['Volume'] = np.random.randint(1000000, 10000000, periods)
    
    return data


def test_strategy(strategy_name):
    """Testa uma estratégia específica"""
    print(f"\n{'='*60}")
    print(f"Testando: {strategy_name.upper()}")
    print(f"{'='*60}")
    
    try:
        # Criar dados de teste
        df = generate_test_data(periods=200)
        
        # Obter estratégia
        strategy = StrategyManager.get_strategy(strategy_name)
        
        # Executar
        df_result = strategy.run(df)
        
        # Verificar resultados
        assert 'signal' in df_result.columns, "Coluna 'signal' não encontrada"
        assert 'position' in df_result.columns, "Coluna 'position' não encontrada"
        
        # Contar sinais
        buy_signals = (df_result['signal'] == 1).sum()
        sell_signals = (df_result['signal'] == -1).sum()
        
        # Calcular Sharpe
        sharpe = strategy.calculate_sharpe_ratio(df_result)
        
        print(f"✅ SUCESSO!")
        print(f"   • Sinais de COMPRA: {buy_signals}")
        print(f"   • Sinais de VENDA: {sell_signals}")
        print(f"   • Sharpe Ratio: {sharpe:.3f}")
        print(f"   • Último sinal: {df_result['signal'].iloc[-1]}")
        
        # Mostrar condições
        print(f"\n   Condições de Entrada:")
        for i, cond in enumerate(strategy.get_entry_conditions(), 1):
            print(f"      {i}. {cond}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_manager():
    """Testa o StrategyManager"""
    print(f"\n{'='*60}")
    print("Testando STRATEGY MANAGER")
    print(f"{'='*60}")
    
    try:
        # Listar estratégias
        strategies = StrategyManager.list_strategies()
        print(f"✅ {len(strategies)} estratégias disponíveis:")
        for s in strategies:
            print(f"   • {s['id']}: {s['name']}")
        
        # Comparar estratégias
        df = generate_test_data(periods=150)
        
        comparison = StrategyManager.compare_strategies(
            strategies=['trend_following', 'mean_reversion', 'momentum'],
            df=df,
            initial_capital=10000
        )
        
        print(f"\n✅ Comparação de estratégias:")
        for name, metrics in comparison.items():
            if 'error' not in metrics:
                print(f"   • {name}:")
                print(f"      - Sharpe: {metrics['sharpe_ratio']:.2f}")
                print(f"      - Retorno: {metrics['total_return']:.2f}%")
                print(f"      - Trades: {metrics['total_trades']}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_advanced_metrics():
    """Testa o módulo de métricas avançadas"""
    print(f"\n{'='*60}")
    print("Testando MÉTRICAS AVANÇADAS")
    print(f"{'='*60}")
    
    try:
        from advanced_metrics import AdvancedMetrics, format_metrics_report
        
        # Criar dados simulados de equity curve
        equity_curve = []
        capital = 10000
        
        for i in range(100):
            capital += np.random.normal(50, 200)
            equity_curve.append({
                'date': f"2024-01-{i%30+1:02d}",
                'equity': max(capital, 5000),
                'price': 45000 + i * 100
            })
        
        # Criar trades simulados
        class MockTrade:
            def __init__(self, pnl):
                self.pnl = pnl
                self.entry_date = "2024-01-01"
                self.exit_date = "2024-01-02"
        
        trades = [MockTrade(np.random.normal(100, 300)) for _ in range(30)]
        
        # Calcular métricas
        metrics = AdvancedMetrics.calculate_all_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=10000,
            risk_free_rate=0.02
        )
        
        print(f"✅ Métricas calculadas:")
        print(f"   • Sharpe Ratio: {metrics['sharpe_ratio']:.3f}")
        print(f"   • Sortino Ratio: {metrics['sortino_ratio']:.3f}")
        print(f"   • Calmar Ratio: {metrics['calmar_ratio']:.3f}")
        print(f"   • Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"   • Win Rate: {metrics['win_rate_pct']:.2f}%")
        print(f"   • Profit Factor: {metrics['profit_factor']:.2f}")
        
        # Testar formatação de relatório
        report = format_metrics_report(metrics)
        print(f"\n✅ Relatório formatado gerado ({len(report)} caracteres)")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Executa todos os testes"""
    print("\n" + "="*60)
    print("  TESTE COMPLETO DO SISTEMA DE ESTRATÉGIAS")
    print("="*60)
    
    results = {}
    
    # Testar Strategy Manager
    results['Strategy Manager'] = test_strategy_manager()
    
    # Testar cada estratégia
    strategies_to_test = [
        'trend_following',
        'mean_reversion',
        'volatility_breakout',
        'macd_rsi_combo',
        'bollinger_bands',
        'momentum',
        'volume_profile',
        'multi_timeframe',
        'dynamic_position_sizing'
    ]
    
    for strategy in strategies_to_test:
        results[strategy] = test_strategy(strategy)
    
    # Testar métricas avançadas
    results['Advanced Metrics'] = test_advanced_metrics()
    
    # Resumo final
    print("\n" + "="*60)
    print("  RESUMO DOS TESTES")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"{status} - {name}")
    
    print(f"\n{'='*60}")
    print(f"RESULTADO: {passed}/{total} testes passaram")
    print(f"{'='*60}\n")
    
    if passed == total:
        print("🎉 TODOS OS TESTES PASSARAM! Sistema funcionando corretamente.")
        return 0
    else:
        print("⚠️  ALGUNS TESTES FALHARAM. Verifique os erros acima.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
