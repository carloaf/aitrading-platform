#!/usr/bin/env python3
"""
Download de dados históricos ETH/USDT e SOL/USDT para 2025
Para executar: python3 scripts/download_eth_sol_2025.py
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
import ccxt.async_support as ccxt
import sys
from typing import List, Dict

# Configuração
SYMBOLS = ['ETH/USDT', 'SOL/USDT']
START_DATE = '2025-01-01'
END_DATE = '2025-12-15'
TIMEFRAME = '1h'

# Conexão TimescaleDB
DB_CONFIG = {
    'host': 'timescaledb',
    'port': 5432,
    'database': 'crypto_market',
    'user': 'crypto_user',
    'password': 'crypto_pass'
}


async def fetch_binance_data(symbol: str, start_date: str, end_date: str) -> List[Dict]:
    """Baixa dados do Binance via ccxt"""
    print(f"\n📥 Baixando {symbol} de {start_date} até {end_date}...")
    
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    
    try:
        # Converter datas
        since = exchange.parse8601(f'{start_date}T00:00:00Z')
        until = exchange.parse8601(f'{end_date}T23:59:59Z')
        
        all_candles = []
        current_since = since
        
        while current_since < until:
            try:
                candles = await exchange.fetch_ohlcv(
                    symbol,
                    timeframe=TIMEFRAME,
                    since=current_since,
                    limit=1000
                )
                
                if not candles:
                    break
                
                all_candles.extend(candles)
                
                # Atualizar timestamp para próxima página
                current_since = candles[-1][0] + 1
                
                # Feedback progressivo
                last_date = datetime.fromtimestamp(candles[-1][0] / 1000)
                print(f"   ⏳ Baixados {len(all_candles)} candles até {last_date.strftime('%Y-%m-%d %H:%M')}", end='\r')
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"\n   ⚠️ Erro ao baixar página: {e}")
                await asyncio.sleep(2)
                continue
        
        print(f"\n   ✅ Total: {len(all_candles)} candles baixados")
        
        return all_candles
        
    finally:
        await exchange.close()


async def insert_to_timescale(conn, symbol: str, candles: List[Dict]):
    """Insere dados no TimescaleDB"""
    print(f"\n💾 Inserindo {len(candles)} candles de {symbol} no banco...")
    
    # Normalizar símbolo (ETHUSDT sem /)
    symbol_normalized = symbol.replace('/', '')
    
    inserted = 0
    duplicates = 0
    errors = 0
    
    for candle in candles:
        timestamp = datetime.fromtimestamp(candle[0] / 1000)
        open_price = float(candle[1])
        high = float(candle[2])
        low = float(candle[3])
        close = float(candle[4])
        volume = float(candle[5])
        
        try:
            # Verificar se já existe antes de inserir
            exists = await conn.fetchval('''
                SELECT 1 FROM market_data 
                WHERE symbol = $1 AND timestamp = $2
                LIMIT 1
            ''', symbol_normalized, timestamp)
            
            if exists:
                duplicates += 1
                continue
            
            # Insert direto (sem ON CONFLICT pois não há constraint)
            # Nota: price = close (compatibilidade com schema)
            await conn.execute('''
                INSERT INTO market_data (
                    symbol, timestamp, open, high, low, close, price, volume, source
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ''', symbol_normalized, timestamp, open_price, high, low, close, 
                close, volume, 'binance')
            
            inserted += 1
            
            if inserted % 500 == 0:
                print(f"   ⏳ Inseridos {inserted}/{len(candles)} candles...", end='\r')
                
        except Exception as e:
            errors += 1
            if errors < 5:  # Mostrar só primeiros 5 erros
                print(f"\n   ⚠️ Erro ao inserir candle {timestamp}: {e}")
    
    print(f"\n   ✅ Inseridos: {inserted} | Duplicatas: {duplicates} | Erros: {errors}")
    
    return inserted, duplicates, errors


async def validate_data(conn, symbol: str):
    """Valida dados inseridos"""
    symbol_normalized = symbol.replace('/', '')
    
    result = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total,
            MIN(timestamp) as primeira_data,
            MAX(timestamp) as ultima_data,
            MIN(close) as min_price,
            MAX(close) as max_price
        FROM market_data
        WHERE symbol = $1
        AND timestamp >= $2
        AND timestamp <= $3
    ''', symbol_normalized, datetime.strptime(START_DATE, '%Y-%m-%d'),
        datetime.strptime(END_DATE, '%Y-%m-%d'))
    
    print(f"\n📊 VALIDAÇÃO {symbol}:")
    print(f"   Total candles: {result['total']}")
    
    if result['total'] > 0:
        print(f"   Período: {result['primeira_data']} → {result['ultima_data']}")
        print(f"   Preço: ${result['min_price']:.2f} → ${result['max_price']:.2f}")
    else:
        print(f"   ⚠️ Nenhum dado encontrado no banco")
    
    # Verificar gaps (esperado: ~1 candle/hora)
    days = (datetime.strptime(END_DATE, '%Y-%m-%d') - datetime.strptime(START_DATE, '%Y-%m-%d')).days
    expected_candles = days * 24
    coverage = (result['total'] / expected_candles) * 100 if expected_candles > 0 else 0
    
    print(f"   Cobertura: {coverage:.1f}% (esperado: {expected_candles} candles)")
    
    if coverage < 95:
        print(f"   ⚠️ ATENÇÃO: Cobertura abaixo de 95%")
    else:
        print(f"   ✅ Cobertura adequada")
    
    return result['total']


async def main():
    """Execução principal"""
    print("="*80)
    print("🚀 DOWNLOAD DE DADOS HISTÓRICOS ETH/SOL 2025")
    print("="*80)
    print(f"\n⚙️ Configuração:")
    print(f"   Símbolos: {', '.join(SYMBOLS)}")
    print(f"   Período: {START_DATE} → {END_DATE}")
    print(f"   Timeframe: {TIMEFRAME}")
    print(f"   Destino: TimescaleDB (crypto_market)")
    
    # Conectar ao banco
    print(f"\n🔌 Conectando ao TimescaleDB...")
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("   ✅ Conectado!")
    except Exception as e:
        print(f"   ❌ Erro ao conectar: {e}")
        print("\n💡 Dica: Este script deve ser executado DENTRO do container:")
        print("   docker cp scripts/download_eth_sol_2025.py aitrading-execution-engine:/tmp/")
        print("   docker exec aitrading-execution-engine python3 /tmp/download_eth_sol_2025.py")
        return 1
    
    summary = []
    
    try:
        for symbol in SYMBOLS:
            print(f"\n{'='*80}")
            print(f"📈 PROCESSANDO: {symbol}")
            print(f"{'='*80}")
            
            # 1. Download
            candles = await fetch_binance_data(symbol, START_DATE, END_DATE)
            
            if not candles:
                print(f"   ❌ Nenhum dado baixado para {symbol}")
                summary.append({
                    'symbol': symbol,
                    'downloaded': 0,
                    'inserted': 0,
                    'status': 'FALHOU'
                })
                continue
            
            # 2. Inserir
            inserted, duplicates, errors = await insert_to_timescale(conn, symbol, candles)
            
            # 3. Validar
            total_db = await validate_data(conn, symbol)
            
            summary.append({
                'symbol': symbol,
                'downloaded': len(candles),
                'inserted': inserted,
                'duplicates': duplicates,
                'errors': errors,
                'total_db': total_db,
                'status': '✅ OK' if total_db > 0 else '❌ FALHOU'
            })
            
            # Pausa entre símbolos
            if symbol != SYMBOLS[-1]:
                print(f"\n⏸️  Pausa de 2 segundos...")
                await asyncio.sleep(2)
        
        # Resumo final
        print(f"\n\n{'='*80}")
        print("📊 RESUMO FINAL")
        print(f"{'='*80}")
        print(f"\n| Símbolo | Baixados | Inseridos | Duplicatas | Erros | Total DB | Status |")
        print(f"|---------|----------|-----------|------------|-------|----------|--------|")
        
        for s in summary:
            print(f"| {s['symbol']:7} | {s['downloaded']:8} | {s['inserted']:9} | "
                  f"{s.get('duplicates', 0):10} | {s.get('errors', 0):5} | "
                  f"{s.get('total_db', 0):8} | {s['status']:6} |")
        
        print(f"\n✅ Download concluído!")
        print(f"\n💡 Próximo passo: Executar Walk-Forward Multi-Par")
        print(f"   python3 scripts/walk_forward_optimization.py ETHUSDT")
        print(f"   python3 scripts/walk_forward_optimization.py SOLUSDT")
        
    finally:
        await conn.close()
        print(f"\n🔌 Conexão fechada")
    
    return 0


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️ Download cancelado pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
