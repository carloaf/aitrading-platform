#!/usr/bin/env python3
"""
Data Health Check - Verifica integridade dos dados históricos no TimescaleDB.

Valida:
1. Quantidade de candles por símbolo/timeframe
2. Gaps temporais (períodos sem dados)
3. Completude dos dados necessários para ML Training
"""

import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataHealthChecker:
    """Verifica saúde dos dados históricos no banco"""
    
    # Expectativas mínimas (últimos 2 anos)
    EXPECTED_CANDLES = {
        '1h': 17520,   # 24h * 365d * 2 anos
        '4h': 4380,    # 6 * 365 * 2
        '1d': 730,     # 365 * 2
    }
    
    # Símbolos principais que devem ter dados completos (formato do banco: sem barra)
    REQUIRED_SYMBOLS = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
        'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT'
    ]
    
    # Timeframes necessários para ML Training
    REQUIRED_TIMEFRAMES = ['1h', '4h', '1d']
    
    def __init__(self):
        self.db_host = os.getenv("POSTGRES_HOST", "postgres")
        self.db_port = int(os.getenv("POSTGRES_PORT", 5432))
        self.db_name = os.getenv("POSTGRES_DB", "aitrading_db")
        self.db_user = os.getenv("POSTGRES_USER", "aitrading_user")
        self.db_password = os.getenv("POSTGRES_PASSWORD", "aitrading_pass")
        self.conn: asyncpg.Connection = None
        
    async def connect(self):
        """Conecta ao banco"""
        try:
            self.conn = await asyncpg.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            logger.info(f"✅ Conectado ao TimescaleDB: {self.db_name}")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar: {e}")
            raise
    
    async def disconnect(self):
        """Desconecta do banco"""
        if self.conn:
            await self.conn.close()
    
    async def get_candle_count(self, symbol: str, timeframe: str, 
                              days: int = 730) -> Tuple[int, datetime, datetime]:
        """
        Retorna contagem de candles e período coberto
        
        Returns:
            (count, first_date, last_date)
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            result = await self.conn.fetchrow("""
                SELECT 
                    COUNT(*) as count,
                    MIN(time) as first_date,
                    MAX(time) as last_date
                FROM market_data
                WHERE symbol = $1
                    AND timeframe = $2
                    AND time >= $3
            """, symbol, timeframe, cutoff_date)
            
            return (
                result['count'] or 0,
                result['first_date'],
                result['last_date']
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao contar candles {symbol} {timeframe}: {e}")
            return (0, None, None)
    
    async def check_symbol_completeness(self, symbol: str, timeframe: str) -> Dict:
        """
        Verifica completude dos dados para um símbolo/timeframe
        
        Returns:
            {
                'symbol': str,
                'timeframe': str,
                'candle_count': int,
                'expected_count': int,
                'completeness_pct': float,
                'first_date': datetime,
                'last_date': datetime,
                'status': 'complete' | 'partial' | 'missing',
                'needs_download': bool
            }
        """
        count, first_date, last_date = await self.get_candle_count(symbol, timeframe)
        expected = self.EXPECTED_CANDLES.get(timeframe, 17520)
        
        completeness = (count / expected * 100) if expected > 0 else 0
        
        # Status baseado em completude
        if completeness >= 95:
            status = 'complete'
            needs_download = False
        elif completeness >= 50:
            status = 'partial'
            needs_download = True
        else:
            status = 'missing'
            needs_download = True
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'candle_count': count,
            'expected_count': expected,
            'completeness_pct': completeness,
            'first_date': first_date,
            'last_date': last_date,
            'status': status,
            'needs_download': needs_download
        }
    
    async def check_ml_training_readiness(self) -> Dict:
        """
        Verifica se há dados suficientes para treinar ML Filter
        
        Returns:
            {
                'ready': bool,
                'trades_count': int,
                'trades_needed': int,
                'recommendation': str
            }
        """
        try:
            # Verificar se tabela existe
            table_exists = await self.conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'autotrade_signals'
                )
            """)
            
            if not table_exists:
                return {
                    'ready': False,
                    'trades_count': 0,
                    'trades_needed': 50,
                    'total_executed': 0,
                    'winning_trades': 0,
                    'recommendation': '⚠️  Tabela autotrade_signals não existe. Execute populate_historical_trades.py'
                }
            
            result = await self.conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN t.pnl IS NOT NULL THEN 1 END) as trades_with_pnl,
                    COUNT(CASE WHEN t.pnl > 0 THEN 1 END) as winning_trades
                FROM autotrade_signals s
                LEFT JOIN paper_trading_trades t ON t.signal_id = s.signal_id
                WHERE s.executed = true
                    AND s.timestamp >= NOW() - INTERVAL '365 days'
            """)
            
            trades_count = result['trades_with_pnl'] or 0
            trades_needed = 50  # Mínimo para treinar ML
            
            ready = trades_count >= trades_needed
            
            if ready:
                recommendation = f"✅ Pronto para treinar ML! {trades_count} trades disponíveis."
            else:
                recommendation = f"⚠️  Faltam {trades_needed - trades_count} trades. Execute populate_historical_trades.py"
            
            return {
                'ready': ready,
                'trades_count': trades_count,
                'trades_needed': trades_needed,
                'total_executed': result['total_trades'] or 0,
                'winning_trades': result['winning_trades'] or 0,
                'recommendation': recommendation
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar ML readiness: {e}")
            return {
                'ready': False,
                'trades_count': 0,
                'trades_needed': 50,
                'recommendation': f"❌ Erro: {e}"
            }
    
    async def run_full_check(self) -> Dict:
        """
        Executa check completo de todos os símbolos/timeframes
        
        Returns:
            {
                'symbols_checked': int,
                'complete': List[Dict],
                'partial': List[Dict],
                'missing': List[Dict],
                'ml_readiness': Dict,
                'needs_action': bool
            }
        """
        logger.info("🔍 Iniciando Data Health Check...")
        
        results = {
            'complete': [],
            'partial': [],
            'missing': [],
            'ml_readiness': {},
            'needs_action': False
        }
        
        # Check cada símbolo/timeframe
        for symbol in self.REQUIRED_SYMBOLS:
            for timeframe in self.REQUIRED_TIMEFRAMES:
                check = await self.check_symbol_completeness(symbol, timeframe)
                
                if check['status'] == 'complete':
                    results['complete'].append(check)
                elif check['status'] == 'partial':
                    results['partial'].append(check)
                    results['needs_action'] = True
                else:
                    results['missing'].append(check)
                    results['needs_action'] = True
        
        # Check ML training readiness
        results['ml_readiness'] = await self.check_ml_training_readiness()
        if not results['ml_readiness']['ready']:
            results['needs_action'] = True
        
        results['symbols_checked'] = len(self.REQUIRED_SYMBOLS) * len(self.REQUIRED_TIMEFRAMES)
        
        # Log resumo
        self._log_summary(results)
        
        return results
    
    def _log_summary(self, results: Dict):
        """Imprime resumo do health check"""
        logger.info("=" * 80)
        logger.info("📊 DATA HEALTH CHECK - SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"✅ Complete: {len(results['complete'])}/{results['symbols_checked']}")
        logger.info(f"🟡 Partial:  {len(results['partial'])}/{results['symbols_checked']}")
        logger.info(f"❌ Missing:  {len(results['missing'])}/{results['symbols_checked']}")
        
        logger.info("\n📊 ML TRAINING READINESS:")
        ml = results['ml_readiness']
        logger.info(f"   Trades: {ml.get('trades_count', 0)}/{ml.get('trades_needed', 50)}")
        logger.info(f"   {ml.get('recommendation', 'Unknown')}")
        
        if results['partial']:
            logger.info("\n🟡 PARTIAL DATA (needs update):")
            for item in results['partial'][:5]:  # Top 5
                logger.info(f"   {item['symbol']:12} {item['timeframe']:4} - {item['completeness_pct']:.1f}% ({item['candle_count']:,} candles)")
        
        if results['missing']:
            logger.info("\n❌ MISSING DATA (needs download):")
            for item in results['missing'][:5]:  # Top 5
                logger.info(f"   {item['symbol']:12} {item['timeframe']:4} - {item['completeness_pct']:.1f}% ({item['candle_count']:,} candles)")
        
        logger.info("=" * 80)
        
        if results['needs_action']:
            logger.warning("⚠️  ACTION REQUIRED: Run auto_download_missing_data.py or populate_historical_trades.py")
        else:
            logger.info("✅ ALL SYSTEMS GREEN - Data is healthy!")


async def main():
    """Main execution"""
    checker = DataHealthChecker()
    
    try:
        await checker.connect()
        results = await checker.run_full_check()
        
        # Exit code baseado em status
        exit_code = 1 if results['needs_action'] else 0
        return exit_code
        
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        return 1
    finally:
        await checker.disconnect()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
