#!/usr/bin/env python3
"""
Script para coletar dados históricos da Binance e popular TimescaleDB
Para uso com o Meta-Backtest - PASSO 14

DISCLAIMER: Este script é para fins educacionais e backtesting.
"""

import asyncio
import asyncpg
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BinanceHistoricalFetcher:
    """
    Coleta dados históricos da Binance API pública
    """
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3/klines"
        self.session = None
    
    async def fetch_klines(
        self, 
        symbol: str, 
        interval: str, 
        start_time: int, 
        end_time: int,
        limit: int = 1000
    ) -> List[List]:
        """
        Busca candles da Binance
        
        Args:
            symbol: Par de trading (ex: BTCUSDT)
            interval: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            start_time: Timestamp início em ms
            end_time: Timestamp fim em ms
            limit: Quantidade de candles por request (max 1000)
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': start_time,
            'endTime': end_time,
            'limit': limit
        }
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Erro na API: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Erro na request: {e}")
            return []
    
    async def fetch_range(
        self,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Busca range completo de dados
        
        Args:
            symbol: Par de trading
            interval: Timeframe
            start_date: Data início (YYYY-MM-DD)
            end_date: Data fim (YYYY-MM-DD)
        """
        # Converter para timestamps
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        
        # Calcular quantos ms por candle
        interval_ms_map = {
            '1m': 60_000,
            '5m': 300_000,
            '15m': 900_000,
            '1h': 3_600_000,
            '4h': 14_400_000,
            '1d': 86_400_000
        }
        
        interval_ms = interval_ms_map.get(interval, 3_600_000)
        
        all_data = []
        current_start = start_ms
        
        logger.info(f"📥 Coletando {symbol} {interval} de {start_date} até {end_date}")
        
        while current_start < end_ms:
            # Calcular fim do chunk (max 1000 candles)
            chunk_end = min(current_start + (1000 * interval_ms), end_ms)
            
            data = await self.fetch_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=chunk_end,
                limit=1000
            )
            
            if not data:
                logger.warning(f"Sem dados para {current_start}")
                break
            
            all_data.extend(data)
            
            # Próximo chunk
            current_start = chunk_end
            
            # Rate limit: 1200 requests/min = 20 req/s
            await asyncio.sleep(0.1)
            
            # Progress
            progress = ((current_start - start_ms) / (end_ms - start_ms)) * 100
            logger.info(f"   Progresso: {progress:.1f}% ({len(all_data)} candles)")
        
        # Converter para DataFrame
        if not all_data:
            logger.error("Nenhum dado coletado!")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Converter tipos
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        # Selecionar colunas relevantes
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df['symbol'] = symbol
        
        logger.info(f"✅ Coletados {len(df)} candles de {symbol}")
        
        return df
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()


async def save_to_timescaledb(df: pd.DataFrame, db_url: str):
    """
    Salva dados no TimescaleDB
    """
    if df.empty:
        logger.warning("DataFrame vazio, nada para salvar")
        return
    
    logger.info(f"💾 Salvando {len(df)} registros no TimescaleDB...")
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # Verificar se tabela existe
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'market_data'
            );
        """)
        
        if not table_exists:
            # Criar tabela
            await conn.execute("""
                CREATE TABLE market_data (
                    timestamp TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    PRIMARY KEY (timestamp, symbol)
                );
            """)
        
        # Criar hypertable se não existir
        try:
            await conn.execute("""
                SELECT create_hypertable('market_data', 'timestamp', 
                    if_not_exists => TRUE);
            """)
        except Exception as e:
            logger.debug(f"Hypertable já existe ou erro: {e}")
        
        # Inserir dados - primeiro limpar range para evitar duplicatas
        await conn.execute("""
            DELETE FROM market_data 
            WHERE symbol = $1 
            AND timestamp >= $2 
            AND timestamp <= $3;
        """, df['symbol'].iloc[0], df['timestamp'].min(), df['timestamp'].max())
        
        # Adaptar para schema existente: price (NOT NULL) + OHLCV
        insert_query = """
            INSERT INTO market_data 
            (timestamp, symbol, price, open, high, low, close, volume, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
        """
        
        records = [
            (
                row['timestamp'],
                row['symbol'],
                row['close'],  # price = close (campo obrigatório)
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                int(row['volume']),  # volume como bigint
                'binance_historical'  # source para identificar origem
            )
            for _, row in df.iterrows()
        ]
        
        await conn.executemany(insert_query, records)
        await conn.close()
        
        logger.info(f"✅ Dados salvos com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar no banco: {e}")
        raise


async def main():
    """
    Coleta dados históricos para os testes do PASSO 14
    """
    
    # Configuração
    SYMBOL = "BTCUSDT"
    INTERVAL = "1h"
    
    # Períodos críticos para teste
    periods = [
        # 4 anos completos (2021-2024)
        ("2021-01-01", "2021-12-31", "Bull Run 2021"),
        ("2022-01-01", "2022-12-31", "Bear Market 2022"),
        ("2023-01-01", "2023-12-31", "Recovery 2023"),
        ("2024-01-01", "2024-12-31", "Bull 2024"),
        
        # Período recente para validação
        ("2025-01-01", "2025-03-31", "Q1 2025"),
    ]
    
    # Database URL (quando executado dentro do container, usar hostname do docker)
    db_url = "postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market"
    
    logger.info("=" * 80)
    logger.info("🚀 INICIANDO COLETA DE DADOS HISTÓRICOS")
    logger.info("=" * 80)
    
    async with BinanceHistoricalFetcher() as fetcher:
        for start_date, end_date, description in periods:
            logger.info(f"\n📊 Período: {description}")
            logger.info(f"   Datas: {start_date} → {end_date}")
            
            # Fetch data
            df = await fetcher.fetch_range(
                symbol=SYMBOL,
                interval=INTERVAL,
                start_date=start_date,
                end_date=end_date
            )
            
            if not df.empty:
                # Save to database
                await save_to_timescaledb(df, db_url)
                
                # Estatísticas
                logger.info(f"   Range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
                logger.info(f"   Candles: {len(df)}")
            
            # Pausa entre períodos
            await asyncio.sleep(1)
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ COLETA COMPLETA!")
    logger.info("=" * 80)
    logger.info("\n🎯 PRÓXIMOS PASSOS:")
    logger.info("   1. Execute: python3 test_passo14.py")
    logger.info("   2. Verifique os resultados do position sizing dinâmico")
    logger.info("   3. Compare métricas: Win Rate, Sharpe, Max DD")


if __name__ == "__main__":
    asyncio.run(main())
