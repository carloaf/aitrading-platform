"""
Auto Strategy Selector - Seleciona estratégia baseado no regime de mercado

Este módulo integra o Market Regime Detector ao paper trading para
seleção automática da estratégia mais apropriada.
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

from market_regime_detector import MarketRegimeDetector, MarketRegime

logger = logging.getLogger(__name__)


class AutoStrategySelector:
    """
    Selecionador automático de estratégia baseado em regime de mercado
    
    Analisa o mercado atual e recomenda a estratégia mais apropriada.
    """
    
    # Mapeamento de regimes para estratégias
    STRATEGY_MAP = {
        MarketRegime.BULL: {
            'primary': 'momentum',
            'alternatives': ['trend_following', 'macd_rsi_combo'],
            'description': 'Mercado em alta - estratégias de momentum'
        },
        MarketRegime.BEAR: {
            'primary': 'breakdown_momentum',
            'alternatives': ['bear_market_short', 'death_cross'],
            'description': 'Mercado em baixa - estratégias short'
        },
        MarketRegime.SIDEWAYS: {
            'primary': 'mean_reversion',
            'alternatives': ['bollinger_bands'],
            'description': 'Mercado lateral - estratégias de reversão'
        },
        MarketRegime.VOLATILE: {
            'primary': 'volatility_breakout',
            'alternatives': ['bollinger_bands'],
            'description': 'Mercado volátil - estratégias de breakout'
        }
    }
    
    def __init__(self, db_url: Optional[str] = None):
        """
        Inicializa o seletor automático
        
        Args:
            db_url: URL de conexão com TimescaleDB (opcional)
        """
        self.db_url = db_url or 'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market'
        self.detector = MarketRegimeDetector()
        self.last_analysis = None
        self.last_analysis_time = None
        
    async def select_strategy(self, 
                             symbol: str = "BTCUSDT",
                             interval: str = "1h",
                             lookback_days: int = 90,
                             force_refresh: bool = False) -> Dict:
        """
        Seleciona automaticamente a melhor estratégia para o mercado atual
        
        Args:
            symbol: Par de trading
            interval: Timeframe
            lookback_days: Dias de histórico para análise
            force_refresh: Forçar nova análise (ignorar cache)
            
        Returns:
            Dict com estratégia recomendada e análise completa
        """
        # Cache: reusar análise se foi feita há menos de 1 hora
        if not force_refresh and self.last_analysis and self.last_analysis_time:
            time_since_analysis = (datetime.utcnow() - self.last_analysis_time).total_seconds()
            if time_since_analysis < 3600:  # 1 hora
                logger.info(f"📋 Usando análise em cache ({time_since_analysis/60:.1f} min atrás)")
                return self.last_analysis
        
        logger.info(f"🔍 Analisando regime de mercado: {symbol} ({interval})")
        
        try:
            # 1. Buscar dados históricos
            conn = await asyncpg.connect(self.db_url)
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)
            
            query = """
                SELECT 
                    timestamp,
                    open_price as open,
                    high_price as high,
                    low_price as low,
                    close_price as close,
                    volume
                FROM market_data_realtime
                WHERE symbol = $1 
                AND interval_type = $2
                AND timestamp >= $3
                AND timestamp <= $4
                ORDER BY timestamp ASC
            """
            
            rows = await conn.fetch(query, symbol, interval, start_date, end_date)
            await conn.close()
            
            if len(rows) < 200:
                raise ValueError(f"Dados insuficientes: {len(rows)} candles")
            
            # 2. Converter para DataFrame
            import pandas as pd
            df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 3. Detectar regime
            analysis = self.detector.analyze(df)
            
            # 4. Selecionar estratégia baseado no regime
            regime_config = self.STRATEGY_MAP.get(analysis.regime)
            
            if not regime_config:
                raise ValueError(f"Regime desconhecido: {analysis.regime}")
            
            result = {
                'status': 'success',
                'timestamp': datetime.utcnow().isoformat(),
                'market_analysis': {
                    'regime': analysis.regime.value,
                    'confidence': analysis.confidence,
                    'trend_strength': analysis.trend_strength,
                    'volatility': analysis.volatility,
                    'description': analysis.description,
                    'signals': analysis.signals
                },
                'strategy_recommendation': {
                    'primary': regime_config['primary'],
                    'alternatives': regime_config['alternatives'],
                    'reason': regime_config['description']
                },
                'trading_advice': self._generate_trading_advice(analysis),
                'metadata': {
                    'symbol': symbol,
                    'interval': interval,
                    'lookback_days': lookback_days,
                    'candles_analyzed': len(df)
                }
            }
            
            # Cachear resultado
            self.last_analysis = result
            self.last_analysis_time = datetime.utcnow()
            
            logger.info(f"✅ Estratégia recomendada: {regime_config['primary']} (regime: {analysis.regime.value})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro ao selecionar estratégia: {e}")
            raise
    
    def _generate_trading_advice(self, analysis) -> Dict:
        """Gera conselhos de trading baseado na análise"""
        
        advice = {
            'should_trade': True,
            'risk_level': 'medium',
            'position_size_multiplier': 1.0,
            'warnings': []
        }
        
        # Análise de volatilidade
        if analysis.volatility > 10:
            advice['risk_level'] = 'high'
            advice['position_size_multiplier'] = 0.5
            advice['warnings'].append('Alta volatilidade detectada - reduzir tamanho de posição')
        elif analysis.volatility < 3:
            advice['risk_level'] = 'low'
            advice['position_size_multiplier'] = 1.2
        
        # Análise de confiança
        if analysis.confidence < 60:
            advice['should_trade'] = False
            advice['warnings'].append(f'Baixa confiança na análise ({analysis.confidence:.1f}%) - evitar trading')
        
        # Análise de regime
        if analysis.regime == MarketRegime.VOLATILE:
            advice['warnings'].append('Mercado muito volátil - aumentar stop loss')
        
        # Análise de sinais
        signals = analysis.signals
        if signals.get('volume') == 'LOW':
            advice['warnings'].append('Volume baixo - confirmação de sinais pode ser fraca')
        
        return advice
    
    async def should_change_strategy(self, 
                                    current_strategy: str,
                                    symbol: str = "BTCUSDT",
                                    interval: str = "1h") -> Dict:
        """
        Verifica se a estratégia atual ainda é apropriada
        
        Args:
            current_strategy: Estratégia atualmente em uso
            symbol: Par de trading
            interval: Timeframe
            
        Returns:
            Dict indicando se deve trocar e qual nova estratégia usar
        """
        result = await self.select_strategy(symbol, interval, force_refresh=True)
        
        recommended = result['strategy_recommendation']['primary']
        regime = result['market_analysis']['regime']
        confidence = result['market_analysis']['confidence']
        
        should_change = current_strategy != recommended
        
        return {
            'should_change': should_change,
            'current_strategy': current_strategy,
            'recommended_strategy': recommended,
            'regime': regime,
            'confidence': confidence,
            'reason': f"Regime mudou para {regime}" if should_change else f"Estratégia ainda apropriada para {regime}",
            'full_analysis': result
        }


# Função helper para uso direto
async def get_best_strategy(symbol: str = "BTCUSDT", 
                           interval: str = "1h",
                           lookback_days: int = 90) -> str:
    """
    Retorna a melhor estratégia para o mercado atual (uso simples)
    
    Args:
        symbol: Par de trading
        interval: Timeframe
        lookback_days: Dias de histórico
        
    Returns:
        Nome da estratégia recomendada
    """
    selector = AutoStrategySelector()
    result = await selector.select_strategy(symbol, interval, lookback_days)
    return result['strategy_recommendation']['primary']


if __name__ == "__main__":
    # Teste
    async def test():
        print("=" * 80)
        print("AUTO STRATEGY SELECTOR - Teste")
        print("=" * 80)
        
        selector = AutoStrategySelector()
        
        # Teste 1: Selecionar estratégia
        print("\n🔍 Teste 1: Seleção automática de estratégia")
        result = await selector.select_strategy("BTCUSDT", "1h", 90)
        
        print(f"\n📊 Regime: {result['market_analysis']['regime'].upper()}")
        print(f"📈 Confiança: {result['market_analysis']['confidence']:.1f}%")
        print(f"\n🎯 Estratégia Recomendada: {result['strategy_recommendation']['primary']}")
        print(f"💡 Motivo: {result['strategy_recommendation']['reason']}")
        
        print(f"\n⚠️  Avisos de Trading:")
        for warning in result['trading_advice']['warnings']:
            print(f"   • {warning}")
        
        print(f"\n🎲 Deve tradear? {result['trading_advice']['should_trade']}")
        print(f"📊 Nível de risco: {result['trading_advice']['risk_level']}")
        print(f"💰 Multiplicador de posição: {result['trading_advice']['position_size_multiplier']}x")
        
        # Teste 2: Verificar mudança de estratégia
        print("\n\n🔄 Teste 2: Verificar se deve mudar estratégia")
        change_result = await selector.should_change_strategy("momentum", "BTCUSDT", "1h")
        
        print(f"\n🔀 Deve mudar estratégia? {change_result['should_change']}")
        print(f"   Atual: {change_result['current_strategy']}")
        print(f"   Recomendada: {change_result['recommended_strategy']}")
        print(f"   Motivo: {change_result['reason']}")
        
        print("\n" + "=" * 80)
        print("✅ Testes concluídos!")
    
    asyncio.run(test())
