#!/usr/bin/env python3
"""
Script para baixar dados históricos de múltiplos símbolos e salvar no TimescaleDB
"""
import os
import sys
import argparse
import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time
import psycopg2
from psycopg2.extras import execute_values

# Configuração do banco TimescaleDB
TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "timescaledb")
TIMESCALE_PORT = os.getenv("TIMESCALE_PORT", "5432")
TIMESCALE_DB = os.getenv("TIMESCALE_DB", "crypto_market")
TIMESCALE_USER = os.getenv("TIMESCALE_USER", "crypto_user")
TIMESCALE_PASSWORD = os.getenv("TIMESCALE_PASSWORD", "crypto_pass")


def get_db_connection():
    """Conectar ao TimescaleDB"""
    try:
        conn = psycopg2.connect(
            host=TIMESCALE_HOST,
            port=TIMESCALE_PORT,
            database=TIMESCALE_DB,
            user=TIMESCALE_USER,
            password=TIMESCALE_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar TimescaleDB: {e}")
        sys.exit(1)


def download_ohlcv(exchange, symbol, timeframe, start_date, end_date):
    """
    Baixar dados OHLCV da Binance
    """
    print(f"📥 Baixando {symbol} {timeframe} de {start_date} até {end_date}...")
    
    # Converter datas para timestamps
    since = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
    
    all_ohlcv = []
    
    try:
        while since < end_ts:
            # Fetch data (max 1000 candles por request)
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            
            if not ohlcv:
                break
            
            all_ohlcv.extend(ohlcv)
            
            # Atualizar timestamp para próximo batch
            since = ohlcv[-1][0] + 1
            
            # Rate limiting (evitar ban)
            time.sleep(exchange.rateLimit / 1000)
            
            # Progress indicator
            current_date = datetime.fromtimestamp(ohlcv[-1][0] / 1000).strftime("%Y-%m-%d")
            print(f"  ⏳ Progresso: {current_date} ({len(all_ohlcv)} candles)")
            
            # Se chegou no fim do período
            if ohlcv[-1][0] >= end_ts:
                break
        
        print(f"  ✅ Total baixado: {len(all_ohlcv)} candles")
        return all_ohlcv
    
    except Exception as e:
        print(f"  ❌ Erro ao baixar {symbol}: {e}")
        return []


def save_to_timescale(conn, symbol, timeframe, ohlcv_data):
    """
    Salvar dados no TimescaleDB
    """
    if not ohlcv_data:
        print(f"  ⚠️  Nenhum dado para salvar")
        return 0
    
    # Converter para formato do banco
    source = f"binance_{timeframe}"
    
    # Preparar dados para INSERT
    values = []
    for candle in ohlcv_data:
        timestamp = datetime.fromtimestamp(candle[0] / 1000)
        values.append((
            symbol,
            source,
            timestamp,
            float(candle[1]),  # open
            float(candle[2]),  # high
            float(candle[3]),  # low
            float(candle[4]),  # close
            float(candle[5])   # volume
        ))
    
    try:
        cursor = conn.cursor()
        
        # INSERT com ON CONFLICT (usando o índice único symbol+timestamp)
        # Nota: O índice único é (symbol, timestamp), sem o campo source
        insert_query = """
            INSERT INTO market_data (symbol, source, timestamp, open, high, low, close, volume)
            VALUES %s
            ON CONFLICT (symbol, timestamp) 
            DO UPDATE SET 
                source = EXCLUDED.source,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """
        
        execute_values(cursor, insert_query, values, page_size=1000)
        conn.commit()
        
        print(f"  💾 Salvos {len(values)} candles no TimescaleDB")
        
        cursor.close()
        return len(values)
    
    except Exception as e:
        print(f"  ❌ Erro ao salvar no banco: {e}")
        conn.rollback()
        return 0


def main():
    parser = argparse.ArgumentParser(description="Download histórico multi-symbol para TimescaleDB")
    parser.add_argument("--symbols", required=True, help="Símbolos separados por vírgula (ex: BTCUSDT,ETHUSDT)")
    parser.add_argument("--start-date", required=True, help="Data inicial (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Data final (YYYY-MM-DD)")
    parser.add_argument("--timeframes", default="1h", help="Timeframes separados por vírgula (ex: 1h,4h,1d)")
    
    args = parser.parse_args()
    
    # Parse argumentos
    symbols = [s.strip() for s in args.symbols.split(",")]
    timeframes = [t.strip() for t in args.timeframes.split(",")]
    
    print("=" * 70)
    print("📊 DOWNLOAD HISTÓRICO MULTI-SYMBOL - TimescaleDB")
    print("=" * 70)
    print(f"Símbolos: {len(symbols)} ({', '.join(symbols[:3])}{'...' if len(symbols) > 3 else ''})")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Período: {args.start_date} até {args.end_date}")
    print("=" * 70)
    
    # Conectar à Binance
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    
    # Conectar ao TimescaleDB
    conn = get_db_connection()
    
    total_candles = 0
    total_symbols = len(symbols) * len(timeframes)
    current = 0
    
    # Download para cada símbolo e timeframe
    for symbol in symbols:
        for timeframe in timeframes:
            current += 1
            print(f"\n[{current}/{total_symbols}] {symbol} {timeframe}")
            print("-" * 70)
            
            # Download
            ohlcv = download_ohlcv(exchange, symbol, timeframe, args.start_date, args.end_date)
            
            # Salvar no banco
            saved = save_to_timescale(conn, symbol, timeframe, ohlcv)
            total_candles += saved
            
            # Pausa entre símbolos
            time.sleep(1)
    
    # Fechar conexão
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ DOWNLOAD CONCLUÍDO")
    print("=" * 70)
    print(f"Total de candles salvos: {total_candles}")
    print(f"Símbolos processados: {len(symbols)}")
    print(f"Timeframes processados: {len(timeframes)}")
    print("=" * 70)
    
    # Verificar dados no banco
    print("\n🔍 Verificando dados salvos no TimescaleDB...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for symbol in symbols[:3]:  # Verificar apenas os 3 primeiros
        cursor.execute("""
            SELECT 
                source,
                COUNT(*) as total,
                MIN(timestamp) as inicio,
                MAX(timestamp) as fim
            FROM market_data
            WHERE symbol = %s
            GROUP BY source
            ORDER BY source
        """, (symbol,))
        
        results = cursor.fetchall()
        if results:
            print(f"\n  {symbol}:")
            for row in results:
                print(f"    {row[0]}: {row[1]} candles ({row[2]} até {row[3]})")
    
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
