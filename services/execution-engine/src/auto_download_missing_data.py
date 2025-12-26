#!/usr/bin/env python3
"""
Auto Download Missing Data - Baixa automaticamente dados faltantes do Binance.

Integra com data_health_check.py para identificar gaps e popular TimescaleDB.
"""

import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from typing import List, Dict
import logging
import aiohttp
from time import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoDownloader:
    """Baixa automaticamente dados faltantes do Binance"""
    
    BINANCE_API = "https://api.binance.com/api/v3/klines"
    
    # Mapeamento timeframe -> milliseconds interval
    TIMEFRAME_MS = {
        '1h': 3600000,
        '4h': 14400000,
        '1d': 86400000,
    }
    
    # Binance limits
    MAX_CANDLES_PER_REQUEST = 1000
    REQUEST_DELAY = 0.5  # segundos entre requests
    
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
    
    def symbol_to_binance(self, symbol: str) -> str:
        """Converte BTC/USDT -> BTCUSDT (ou retorna se já estiver sem barra)"""
        return symbol.replace('/', '')
    
    async def fetch_binance_candles(self, symbol: str, timeframe: str,
                                   start_time: int, end_time: int) -> List[Dict]:
        """
        Baixa candles do Binance API
        
        Args:
            symbol: Par (BTCUSDT format)
            timeframe: '1h', '4h', '1d'
            start_time: Unix timestamp em milliseconds
            end_time: Unix timestamp em milliseconds
        
        Returns:
            Lista de candles OHLCV
        """
        candles = []
        
        try:
            async with aiohttp.ClientSession() as session:
                current_start = start_time
                
                while current_start < end_time:
                    params = {
                        'symbol': symbol,
                        'interval': timeframe,
                        'startTime': current_start,
                        'endTime': end_time,
                        'limit': self.MAX_CANDLES_PER_REQUEST
                    }
                    
                    async with session.get(self.BINANCE_API, params=params) as response:
                        if response.status != 200:
                            logger.error(f"❌ Binance API error: {response.status}")
                            break
                        
                        data = await response.json()
                        
                        if not data:
                            break
                        
                        for kline in data:
                            candles.append({
                                'timestamp': datetime.fromtimestamp(kline[0] / 1000),
                                'open': float(kline[1]),
                                'high': float(kline[2]),
                                'low': float(kline[3]),
                                'close': float(kline[4]),
                                'volume': float(kline[5])
                            })
                        
                        # Próximo batch
                        current_start = data[-1][0] + self.TIMEFRAME_MS[timeframe]
                        
                        # Rate limiting
                        await asyncio.sleep(self.REQUEST_DELAY)
                
                logger.info(f"✅ Binance: {len(candles)} candles baixados para {symbol} {timeframe}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar Binance {symbol}: {e}")
        
        return candles
    
    async def insert_candles(self, symbol: str, timeframe: str, candles: List[Dict]) -> int:
        """
        Insere candles no TimescaleDB
        
        Returns:
            Número de candles inseridos
        """
        inserted = 0
        
        try:
            # Símbolo já está no formato correto (BTCUSDT)
            db_symbol = symbol
            
            for candle in candles:
                try:
                    await self.conn.execute("""
                        INSERT INTO market_data (symbol, time, timeframe, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (time, symbol, timeframe) DO NOTHING
                    """,
                        db_symbol, candle['timestamp'], timeframe,
                        candle['open'], candle['high'], candle['low'],
                        candle['close'], candle['volume']
                    )
                    inserted += 1
                except Exception as e:
                    # Ignorar duplicatas
                    pass
            
            logger.info(f"✅ Inseridos {inserted}/{len(candles)} candles para {db_symbol} {timeframe}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inserir candles: {e}")
        
        return inserted
    
    async def download_missing_data(self, symbol: str, timeframe: str, days: int = 730):
        """
        Baixa dados faltantes para um símbolo/timeframe
        
        Args:
            symbol: Par no formato BTCUSDT (sem barra)
            timeframe: '1h', '4h', '1d'
            days: Quantos dias de histórico baixar (padrão: 2 anos)
        """
        logger.info(f"📥 Baixando {symbol} {timeframe} (últimos {days} dias)...")
        
        # Símbolo já está no formato Binance (BTCUSDT)
        binance_symbol = symbol
        
        # Calcular período
        end_time = int(time() * 1000)  # agora
        start_time = end_time - (days * 24 * 3600 * 1000)  # days atrás
        
        # Baixar do Binance
        candles = await self.fetch_binance_candles(
            binance_symbol, timeframe, start_time, end_time
        )
        
        if not candles:
            logger.warning(f"⚠️  Nenhum candle baixado para {symbol} {timeframe}")
            return 0
        
        # Inserir no banco
        inserted = await self.insert_candles(binance_symbol, timeframe, candles)
        
        return inserted
    
    async def auto_fix_missing_data(self, min_completeness: float = 90.0):
        """
        Identifica e corrige automaticamente dados faltantes
        
        Args:
            min_completeness: % mínimo de completude (padrão: 90%)
        
        Returns:
            Dict com estatísticas do processo
        """
        from data_health_check import DataHealthChecker
        
        logger.info("🔧 AUTO-FIX: Iniciando correção automática de dados...")
        
        # 1. Executar health check
        checker = DataHealthChecker()
        checker.conn = self.conn  # Reusar conexão
        
        results = await checker.run_full_check()
        
        # 2. Identificar o que precisa download
        to_download = []
        
        for item in results['partial'] + results['missing']:
            if item['completeness_pct'] < min_completeness:
                to_download.append(item)
        
        if not to_download:
            logger.info("✅ Nenhum dado faltante encontrado!")
            return {'downloads': 0, 'total_candles': 0}
        
        logger.info(f"📥 {len(to_download)} downloads necessários")
        
        # 3. Baixar dados faltantes
        stats = {
            'downloads': 0,
            'total_candles': 0,
            'failed': []
        }
        
        for item in to_download:
            try:
                inserted = await self.download_missing_data(
                    item['symbol'],
                    item['timeframe'],
                    days=730  # 2 anos
                )
                
                if inserted > 0:
                    stats['downloads'] += 1
                    stats['total_candles'] += inserted
                else:
                    stats['failed'].append(f"{item['symbol']} {item['timeframe']}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao baixar {item['symbol']} {item['timeframe']}: {e}")
                stats['failed'].append(f"{item['symbol']} {item['timeframe']}")
        
        # 4. Resumo final
        logger.info("=" * 80)
        logger.info("🎉 AUTO-FIX CONCLUÍDO!")
        logger.info(f"   Downloads: {stats['downloads']}")
        logger.info(f"   Candles inseridos: {stats['total_candles']:,}")
        if stats['failed']:
            logger.warning(f"   Falhas: {len(stats['failed'])} - {stats['failed']}")
        logger.info("=" * 80)
        
        return stats


async def main():
    """Main execution"""
    downloader = AutoDownloader()
    
    try:
        await downloader.connect()
        
        # Executar auto-fix (baixar dados faltantes)
        stats = await downloader.auto_fix_missing_data(min_completeness=90.0)
        
        # Exit code baseado em resultado
        exit_code = 0 if stats['downloads'] > 0 or not stats['failed'] else 1
        return exit_code
        
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        return 1
    finally:
        await downloader.disconnect()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
