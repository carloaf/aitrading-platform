#!/usr/bin/env python3
"""
Download Historical Data from Binance
Executes inside the execution-engine container
Downloads OHLCV data and saves directly to TimescaleDB
"""

import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import asyncpg
import os
import sys
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration (TimescaleDB)
DB_HOST = os.getenv('TIMESCALE_HOST', 'timescaledb')
DB_PORT = int(os.getenv('TIMESCALE_PORT', '5432'))
DB_NAME = os.getenv('TIMESCALE_DB', 'crypto_market')
DB_USER = os.getenv('TIMESCALE_USER', 'crypto_user')
DB_PASSWORD = os.getenv('TIMESCALE_PASSWORD', os.getenv('TIMESCALE_PASS', 'crypto_pass'))


async def download_binance_data(
    symbol: str = 'BTC/USDT',
    timeframe: str = '1h',
    start_date: str = '2021-01-01',
    end_date: str = '2024-12-31'
):
    """
    Download historical data from Binance and save to TimescaleDB
    Uses batch requests to minimize API calls
    """
    
    logger.info(f"🚀 Starting download: {symbol} {timeframe} from {start_date} to {end_date}")
    
    # Initialize exchange
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    
    # Connect to database
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        logger.info(f"✅ Connected to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        await exchange.close()
        return False
    
    try:
        # Table already exists in TimescaleDB, just verify schema
        table_check = await conn.fetchval('''
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'market_data'
        ''')
        
        if table_check == 0:
            logger.error("❌ market_data table does not exist in TimescaleDB!")
            return False
        
        logger.info(f"✅ market_data table exists")
        
        # Convert symbol format
        binance_symbol = symbol.replace('/', '')
        db_symbol = binance_symbol
        
        # Source name (binance_1h, binance_4h, binance_1d)
        source_name = f"binance_{timeframe}"
        
        # Parse dates
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        
        # Binance returns max 1000 candles per request
        # 1h timeframe = 1000 hours = ~41 days per batch
        batch_size = 1000
        current_ts = start_ts
        total_candles = 0
        batch_num = 0
        
        while current_ts < end_ts:
            batch_num += 1
            
            try:
                # Fetch OHLCV data
                ohlcv = await exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=current_ts,
                    limit=batch_size
                )
                
                if not ohlcv:
                    logger.warning(f"⚠️ No data returned for batch {batch_num}")
                    break
                
                # Process and insert data
                rows_inserted = 0
                for candle in ohlcv:
                    timestamp, open_p, high_p, low_p, close_p, volume = candle
                    
                    # Convert timestamp to datetime
                    dt = datetime.utcfromtimestamp(timestamp / 1000)
                    
                    # Upsert data (TimescaleDB schema)
                    await conn.execute('''
                        INSERT INTO market_data (symbol, timestamp, open, high, low, close, price, volume, source)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (symbol, timestamp) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            price = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            source = EXCLUDED.source
                    ''', db_symbol, dt, open_p, high_p, low_p, close_p, close_p, volume, source_name)
                    rows_inserted += 1
                
                total_candles += rows_inserted
                
                # Get last timestamp for next batch
                last_ts = ohlcv[-1][0]
                current_ts = last_ts + 1  # Start from next candle
                
                # Calculate progress
                progress = (current_ts - start_ts) / (end_ts - start_ts) * 100
                
                logger.info(f"📊 Batch {batch_num}: {rows_inserted} candles | Total: {total_candles:,} | Progress: {progress:.1f}%")
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Error in batch {batch_num}: {e}")
                await asyncio.sleep(1)  # Wait and retry
                continue
        
        logger.info(f"✅ Download complete! Total candles: {total_candles:,}")
        
        # Verify data
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data WHERE symbol = $1 AND source = $2",
            db_symbol, source_name
        )
        logger.info(f"📈 Database now has {count:,} candles for {db_symbol} ({source_name})")
        
        # Show date range
        result = await conn.fetchrow('''
            SELECT MIN(timestamp) as min_time, MAX(timestamp) as max_time
            FROM market_data WHERE symbol = $1 AND source = $2
        ''', db_symbol, source_name)
        logger.info(f"📅 Date range: {result['min_time']} to {result['max_time']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
        
    finally:
        await conn.close()
        await exchange.close()


async def main():
    """Main entry point"""
    
    # Parse command line arguments
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'BTC/USDT'
    timeframe = sys.argv[2] if len(sys.argv) > 2 else '1h'
    start_date = sys.argv[3] if len(sys.argv) > 3 else '2021-01-01'
    end_date = sys.argv[4] if len(sys.argv) > 4 else '2024-12-31'
    
    success = await download_binance_data(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if success:
        logger.info("🎉 Data download completed successfully!")
    else:
        logger.error("💥 Data download failed!")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
