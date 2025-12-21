#!/usr/bin/env python3
"""
Script de Backfill de Dados Históricos
Preenche últimas 2 semanas de dados OHLCV para todos os símbolos monitorados
"""

import asyncio
import asyncpg
import ccxt.async_support as ccxt_async
from datetime import datetime, timedelta
import os
import sys
from typing import List, Dict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações
DB_CONFIG = {
    'host': os.getenv('TIMESCALE_HOST', 'timescaledb'),
    'port': int(os.getenv('TIMESCALE_PORT', '5432')),
    'database': os.getenv('TIMESCALE_DB', 'crypto_market'),
    'user': os.getenv('TIMESCALE_USER', 'crypto_user'),
    'password': os.getenv('TIMESCALE_PASSWORD', 'crypto_pass')
}

# Timeframes para backfill (em ordem de prioridade)
TIMEFRAMES = ['1h', '4h', '1d']  # 15m muito pesado, fazer opcional

# Período de backfill (últimas 2 semanas)
DAYS_TO_BACKFILL = 14


async def create_db_pool():
    """Cria connection pool com TimescaleDB"""
    return await asyncpg.create_pool(
        **DB_CONFIG,
        min_size=2,
        max_size=10,
        command_timeout=60
    )


async def get_active_symbols(pool) -> List[str]:
    """Busca símbolos ativos do banco"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT symbol FROM monitored_symbols 
            WHERE active = true 
            ORDER BY symbol
        """)
        return [row['symbol'] for row in rows]


async def check_existing_data(pool, symbol: str, timeframe: str, start_ts: datetime, end_ts: datetime) -> int:
    """Verifica quantos candles já existem no período"""
    async with pool.acquire() as conn:
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM market_data 
            WHERE symbol = $1 
            AND timestamp >= $2 
            AND timestamp <= $3
            AND source LIKE $4
        """, symbol, start_ts, end_ts, f'%{timeframe}%')
        return count


async def fetch_binance_ohlcv(exchange, symbol: str, timeframe: str, since: int, limit: int = 1000) -> List:
    """Busca dados OHLCV da Binance"""
    try:
        ccxt_symbol = symbol.replace('USDT', '/USDT')
        ohlcv = await exchange.fetch_ohlcv(ccxt_symbol, timeframe, since, limit)
        return ohlcv
    except Exception as e:
        logger.error(f"Erro ao buscar {symbol} {timeframe}: {e}")
        return []


async def insert_candles_bulk(pool, symbol: str, timeframe: str, candles: List):
    """Insere múltiplos candles de uma vez (bulk insert)"""
    if not candles:
        return 0
    
    records = []
    for candle in candles:
        timestamp_dt = datetime.fromtimestamp(candle[0] / 1000)
        records.append((
            symbol,
            timestamp_dt,
            float(candle[4]),  # price (close)
            float(candle[1]),  # open
            float(candle[2]),  # high
            float(candle[3]),  # low
            float(candle[4]),  # close
            int(candle[5]),    # volume
            f'binance_{timeframe}'  # source
        ))
    
    # Bulk insert com ON CONFLICT usando uma conexão do pool
    async with pool.acquire() as conn:
        await conn.executemany("""
            INSERT INTO market_data (symbol, timestamp, price, open, high, low, close, volume, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (symbol, timestamp) DO UPDATE SET
                price = EXCLUDED.price,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                source = EXCLUDED.source
        """, records)
    
    return len(records)


async def backfill_symbol(exchange, pool, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> Dict:
    """Backfill de um símbolo específico em um timeframe"""
    
    # Verificar dados existentes
    existing = await check_existing_data(pool, symbol, timeframe, start_date, end_date)
    
    # Calcular quantos candles esperamos
    timeframe_minutes = {
        '15m': 15,
        '1h': 60,
        '4h': 240,
        '1d': 1440
    }
    minutes_in_period = int((end_date - start_date).total_seconds() / 60)
    expected_candles = minutes_in_period // timeframe_minutes.get(timeframe, 60)
    
    # Se já tem mais de 90% dos dados, pular
    if existing > (expected_candles * 0.9):
        logger.info(f"✓ {symbol} {timeframe}: {existing}/{expected_candles} candles já existem (pulando)")
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'status': 'skipped',
            'existing': existing,
            'inserted': 0,
            'expected': expected_candles
        }
    
    logger.info(f"⏳ {symbol} {timeframe}: buscando {expected_candles - existing} candles...")
    
    # Buscar dados da Binance em chunks
    since = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    
    all_candles = []
    retries = 0
    max_retries = 3
    
    while since < end_ms and retries < max_retries:
        try:
            candles = await fetch_binance_ohlcv(exchange, symbol, timeframe, since, limit=1000)
            
            if not candles:
                break
            
            all_candles.extend(candles)
            
            # Próximo chunk
            last_ts = candles[-1][0]
            since = last_ts + 1
            
            # Rate limiting
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.warning(f"Erro ao buscar chunk de {symbol} {timeframe}: {e}")
            retries += 1
            await asyncio.sleep(1)
    
    # Filtrar candles dentro do período
    filtered_candles = [c for c in all_candles if start_date.timestamp() * 1000 <= c[0] <= end_date.timestamp() * 1000]
    
    # Inserir no banco
    if filtered_candles:
        inserted = await insert_candles_bulk(pool, symbol, timeframe, filtered_candles)
        logger.info(f"✅ {symbol} {timeframe}: {inserted} candles inseridos ({existing} já existiam)")
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'status': 'success',
            'existing': existing,
            'inserted': inserted,
            'expected': expected_candles
        }
    else:
        logger.warning(f"⚠️ {symbol} {timeframe}: nenhum dado retornado da Binance")
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'status': 'no_data',
            'existing': existing,
            'inserted': 0,
            'expected': expected_candles
        }


async def backfill_all_symbols(days: int = DAYS_TO_BACKFILL, timeframes: List[str] = TIMEFRAMES, symbols: List[str] = None):
    """Backfill completo para todos os símbolos"""
    
    # Criar connection pool
    pool = await create_db_pool()
    logger.info(f"✅ Conectado ao TimescaleDB ({DB_CONFIG['database']})")
    
    # Buscar símbolos ativos
    if symbols is None:
        symbols = await get_active_symbols(pool)
    logger.info(f"📊 {len(symbols)} símbolos para processar")
    
    # Criar exchange Binance
    exchange = ccxt_async.binance({
        'enableRateLimit': True,
        'rateLimit': 200,
        'options': {'defaultType': 'spot'}
    })
    logger.info("✅ Exchange Binance inicializada")
    
    # Calcular período
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    logger.info(f"📅 Período: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"⏱️  Timeframes: {', '.join(timeframes)}")
    
    # Estatísticas
    total_tasks = len(symbols) * len(timeframes)
    completed = 0
    results = {
        'success': 0,
        'skipped': 0,
        'failed': 0,
        'total_inserted': 0
    }
    
    logger.info(f"\n🚀 Iniciando backfill de {total_tasks} tarefas...")
    logger.info("=" * 80)
    
    try:
        # Processar cada timeframe
        for timeframe in timeframes:
            logger.info(f"\n📊 TIMEFRAME: {timeframe}")
            logger.info("-" * 80)
            
            # Processar símbolos com semáforo (máximo 5 paralelos)
            semaphore = asyncio.Semaphore(5)
            
            async def process_with_semaphore(symbol):
                async with semaphore:
                    result = await backfill_symbol(exchange, pool, symbol, timeframe, start_date, end_date)
                    return result
            
            # Executar em paralelo (limitado por semáforo)
            tasks = [process_with_semaphore(symbol) for symbol in symbols]
            symbol_results = await asyncio.gather(*tasks)
            
            # Consolidar resultados
            for result in symbol_results:
                completed += 1
                
                if result['status'] == 'success':
                    results['success'] += 1
                    results['total_inserted'] += result['inserted']
                elif result['status'] == 'skipped':
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
                
                # Progress
                progress = (completed / total_tasks) * 100
                logger.info(f"⏳ Progresso: {completed}/{total_tasks} ({progress:.1f}%)")
    
    finally:
        # Fechar conexões
        await exchange.close()
        await pool.close()
        logger.info("\n✅ Conexões fechadas")
    
    # Relatório final
    logger.info("\n" + "=" * 80)
    logger.info("📊 RELATÓRIO FINAL DE BACKFILL")
    logger.info("=" * 80)
    logger.info(f"✅ Sucesso:        {results['success']:>6} tarefas")
    logger.info(f"⏭️  Puladas:        {results['skipped']:>6} tarefas (já existiam)")
    logger.info(f"❌ Falhas:         {results['failed']:>6} tarefas")
    logger.info(f"📥 Total Inserido: {results['total_inserted']:>6} candles")
    logger.info("=" * 80)
    
    return results


async def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill de dados históricos')
    parser.add_argument('--days', type=int, default=14, help='Dias para trás (default: 14)')
    parser.add_argument('--timeframes', nargs='+', default=['1h', '4h', '1d'], 
                       help='Timeframes (default: 1h 4h 1d)')
    parser.add_argument('--symbols', nargs='+', help='Símbolos específicos (opcional)')
    parser.add_argument('--include-15m', action='store_true', help='Incluir 15m (muito pesado!)')
    
    args = parser.parse_args()
    
    timeframes = args.timeframes
    if args.include_15m and '15m' not in timeframes:
        timeframes.insert(0, '15m')
    
    logger.info("🚀 BACKFILL HISTÓRICO DE DADOS")
    logger.info(f"Configuração: {args.days} dias, timeframes: {timeframes}")
    
    await backfill_all_symbols(
        days=args.days,
        timeframes=timeframes,
        symbols=args.symbols
    )


if __name__ == '__main__':
    asyncio.run(main())
