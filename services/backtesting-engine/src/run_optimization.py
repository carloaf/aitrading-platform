#!/usr/bin/env python3
"""
Script para otimização de parâmetros das estratégias top performers

Usage:
    python run_optimization.py --strategy volume_profile --symbol BTCUSDT
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from optimizer import ParameterOptimizer, create_optimizer_report
from data_providers import get_market_data
from strategies.volume_profile_strategy import VolumeProfileStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.macd_rsi_combo_strategy import MacdRsiComboStrategy
from strategies.multi_timeframe_strategy import MultiTimeframeStrategy
from strategies.volatility_breakout_strategy import VolatilityBreakoutStrategy
import argparse
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mapeamento de estratégias
STRATEGIES = {
    'volume_profile': VolumeProfileStrategy,
    'momentum': MomentumStrategy,
    'macd_rsi_combo': MacdRsiComboStrategy,
    'multi_timeframe': MultiTimeframeStrategy,
    'volatility_breakout': VolatilityBreakoutStrategy
}

# Definição de parameter ranges para cada estratégia
PARAMETER_RANGES = {
    'volume_profile': {
        'obv_period': [10, 15, 20, 25, 30],
        'obv_threshold': [0.5, 1.0, 1.5, 2.0]
    },
    'momentum': {
        'roc_period': [5, 10, 15, 20],
        'threshold': [-2.0, -1.0, 0.0, 1.0, 2.0]
    },
    'macd_rsi_combo': {
        'macd_fast': [8, 12, 16],
        'macd_slow': [21, 26, 31],
        'macd_signal': [7, 9, 11],
        'rsi_period': [10, 14, 18],
        'rsi_lower': [30, 35, 40],
        'rsi_upper': [65, 70, 75]
    },
    'multi_timeframe': {
        'trend_ema': [40, 50, 60],
        'entry_ema_fast': [15, 20, 25],
        'entry_ema_slow': [40, 50, 60],
        'rsi_period': [10, 14, 18]
    },
    'volatility_breakout': {
        'atr_period': [10, 14, 18, 21],
        'consolidation_period': [15, 20, 25],
        'breakout_multiplier': [1.0, 1.5, 2.0, 2.5],
        'volume_multiplier': [1.0, 1.5, 2.0]
    }
}


def data_provider_wrapper(symbol: str, start_date: str, end_date: str):
    """Wrapper para data provider"""
    return get_market_data(symbol, start_date, end_date, interval='1d')


def main():
    parser = argparse.ArgumentParser(description='Otimização de Parâmetros de Estratégias')
    parser.add_argument('--strategy', type=str, required=True, 
                       choices=list(STRATEGIES.keys()),
                       help='Nome da estratégia a otimizar')
    parser.add_argument('--symbol', type=str, default='BTCUSDT',
                       help='Símbolo a testar (padrão: BTCUSDT)')
    parser.add_argument('--start-date', type=str, default='2023-01-01',
                       help='Data inicial (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, 
                       default=datetime.now().strftime('%Y-%m-%d'),
                       help='Data final (YYYY-MM-DD)')
    parser.add_argument('--splits', type=int, default=5,
                       help='Número de splits para walk-forward (padrão: 5)')
    parser.add_argument('--train-ratio', type=float, default=0.7,
                       help='Proporção de dados para treino (padrão: 0.7)')
    parser.add_argument('--output', type=str, default=None,
                       help='Arquivo de saída para resultados JSON')
    
    args = parser.parse_args()
    
    # Obter classe da estratégia
    strategy_class = STRATEGIES[args.strategy]
    param_ranges = PARAMETER_RANGES[args.strategy]
    
    logger.info("=" * 80)
    logger.info("OTIMIZAÇÃO DE PARÂMETROS - AI TRADING PLATFORM")
    logger.info("=" * 80)
    logger.info(f"Estratégia: {args.strategy}")
    logger.info(f"Símbolo: {args.symbol}")
    logger.info(f"Período: {args.start_date} até {args.end_date}")
    logger.info(f"Ranges de parâmetros: {param_ranges}")
    logger.info(f"Walk-Forward: {args.splits} splits, {args.train_ratio*100:.0f}% treino")
    logger.info("=" * 80)
    logger.info("")
    
    # Criar otimizador
    optimizer = ParameterOptimizer(
        strategy_class=strategy_class,
        data_provider=data_provider_wrapper,
        n_splits=args.splits,
        train_ratio=args.train_ratio
    )
    
    # Executar otimização
    try:
        results = optimizer.optimize_grid_search(
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            param_ranges=param_ranges
        )
        
        if not results:
            logger.error("❌ Nenhum resultado obtido")
            return
        
        # Gerar relatório
        report = create_optimizer_report(results)
        print("\n" + report)
        
        # Salvar resultados
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"optimization_{args.strategy}_{args.symbol}_{timestamp}.json"
        
        optimizer.save_results(results, output_file)
        
        logger.info(f"\n✅ Otimização concluída com sucesso!")
        logger.info(f"📄 Resultados salvos em: {output_file}")
        
        # Mostrar melhores parâmetros
        best = results[0]
        logger.info("\n🏆 MELHORES PARÂMETROS:")
        logger.info(f"  {best.parameters}")
        logger.info(f"\n📊 PERFORMANCE:")
        logger.info(f"  Retorno Out-Sample: {best.out_sample_return:.2f}%")
        logger.info(f"  Sharpe Ratio Out-Sample: {best.out_sample_sharpe:.2f}")
        logger.info(f"  Win Rate Out-Sample: {best.out_sample_win_rate:.2f}%")
        logger.info(f"  Robustness Score: {best.robustness_score:.2f}")
        logger.info(f"  Max Drawdown: {best.max_drawdown:.2f}%")
        
    except Exception as e:
        logger.error(f"❌ Erro durante otimização: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
