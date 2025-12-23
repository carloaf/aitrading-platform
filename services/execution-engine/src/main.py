"""
FastAPI Main - REST API para Execution Engine
Endpoints para controlar paper trading e monitorar performance
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import asyncio
import os
import numpy as np
import asyncpg
import json

from order_manager import OrderManager, OrderSide, OrderType
from strategy_executor import StrategyExecutor
from auto_strategy_selector import AutoStrategySelector
from autotrade_manager import AutoTradeManager, AutoTradeSignalData
import ccxt.async_support as ccxt_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# MARKET DATA CACHE SYSTEM (Database-backed)
# ==========================================

# Pool de conexões global para market data cache
_market_data_pool: Optional[asyncpg.Pool] = None
_market_data_worker_task: Optional[asyncio.Task] = None
_market_data_worker_running = False

# Timeframes para coleta automática (1h para cache, demais para histórico)
WORKER_TIMEFRAMES = ['1h', '4h', '1d']  # 15m opcional (muito pesado)

# Lista de símbolos para monitorar (pode ser configurada)
DEFAULT_MARKET_SYMBOLS = [
    # Top 10 - Major Assets
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    
    # Top 20 - Large Cap
    "TRXUSDT", "TONUSDT", "BCHUSDT", "ETCUSDT", "ICPUSDT",
    "FILUSDT", "VETUSDT", "HBARUSDT", "MATICUSDT", "SHIBUSDT",
    
    # Top 40 - Mid Cap + Layer 2
    "LTCUSDT", "ATOMUSDT", "UNIUSDT", "XLMUSDT", "NEARUSDT",
    "IMXUSDT", "STXUSDT", "MANTAUSDT", "METISUSDT", "ZKUSDT",
    "STRKUSDT", "LOOMUSDT", "SKLUSDT", "CELOUSDT", "ZETAUSDT",
    "CYBERUSDT", "GLMUSDT", "CELRUSDT", "CTSIUSDT",
    
    # DeFi Protocol Tokens
    "AAVEUSDT", "MKRUSDT", "CRVUSDT", "SNXUSDT", "COMPUSDT",
    "LDOUSDT", "SUSHIUSDT", "1INCHUSDT", "DYDXUSDT", "GMXUSDT",
    "PENDLEUSDT", "JUPUSDT", "RUNEUSDT", "YFIUSDT", "BALUSDT",
    
    # AI / Oracle / Data
    "FETUSDT", "AGIXUSDT", "OCEANUSDT", "TAOUSDT", "WLDUSDT",
    "ARKMUSDT", "GRTUSDT", "NMRUSDT", "IOTXUSDT", "RENDERUSDT",
    "THETAUSDT", "ARUSDT",
    
    # Alt Layer-1 / Infrastructure
    "KASUSDT", "ROSEUSDT", "FTMUSDT", "EGLDUSDT", "FLOWUSDT",
    
    # Hot / Trending
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT",
    "SEIUSDT", "TIAUSDT", "ALGOUSDT", "WIFUSDT", "BONKUSDT",
    "PEPEUSDT", "FLOKIUSDT"
]

async def get_market_data_pool():
    """Retorna pool de conexões para market data cache"""
    global _market_data_pool
    if _market_data_pool is None:
        db_url = f"postgresql://{os.getenv('TIMESCALE_USER', 'crypto_user')}:{os.getenv('TIMESCALE_PASSWORD', 'crypto_pass')}@{os.getenv('TIMESCALE_HOST', 'timescaledb')}:{os.getenv('TIMESCALE_PORT', '5432')}/{os.getenv('TIMESCALE_DB', 'crypto_market')}"
        _market_data_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
        logger.info("[MarketDataCache] Pool de conexões criado")
    return _market_data_pool

async def init_market_data_cache_table():
    """Cria tabelas de market data se não existirem"""
    pool = await get_market_data_pool()
    async with pool.acquire() as conn:
        # Tabela de cache (tempo real)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS market_data_cache (
                symbol VARCHAR(20) PRIMARY KEY,
                price DECIMAL(20, 8),
                change_24h DECIMAL(10, 4),
                rsi DECIMAL(5, 2),
                proximity INTEGER,
                trend VARCHAR(30),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_data_updated 
            ON market_data_cache(updated_at DESC)
        """)
        
        # Tabela de símbolos monitorados (dinâmicos)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS monitored_symbols (
                symbol VARCHAR(20) PRIMARY KEY,
                active BOOLEAN NOT NULL DEFAULT true,
                added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                notes TEXT
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_monitored_symbols_active 
            ON monitored_symbols(active) WHERE active = true
        """)
        
        # Verificar se há símbolos - se não, inserir os padrão
        count = await conn.fetchval("SELECT COUNT(*) FROM monitored_symbols")
        if count == 0:
            logger.info("[MarketDataCache] Inserindo símbolos padrão...")
            for symbol in DEFAULT_MARKET_SYMBOLS:
                await conn.execute("""
                    INSERT INTO monitored_symbols (symbol, active, notes)
                    VALUES ($1, true, 'Default symbol')
                    ON CONFLICT (symbol) DO NOTHING
                """, symbol)
            logger.info(f"[MarketDataCache] {len(DEFAULT_MARKET_SYMBOLS)} símbolos padrão inseridos")
        
        logger.info("[MarketDataCache] Tabelas criadas/verificadas")

async def get_active_symbols() -> List[str]:
    """Busca lista de símbolos ativos do banco de dados"""
    try:
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol FROM monitored_symbols 
                WHERE active = true 
                ORDER BY symbol
            """)
            symbols = [row['symbol'] for row in rows]
            return symbols if symbols else DEFAULT_MARKET_SYMBOLS
    except Exception as e:
        logger.warning(f"[MarketDataCache] Erro ao buscar símbolos ativos: {e}. Usando DEFAULT.")
        return DEFAULT_MARKET_SYMBOLS

async def update_market_data_cache(symbols: List[str] = None):
    """
    Background worker: busca dados da Binance e atualiza o banco.
    Salva em market_data_cache (tempo real) E market_data (histórico).
    Chamado periodicamente pelo worker.
    """
    import ta
    import pandas as pd
    from datetime import datetime
    
    if symbols is None:
        symbols = await get_active_symbols()
    
    try:
        exchange = await get_market_data_exchange()
        pool = await get_market_data_pool()
        
        # Semáforo para limitar chamadas paralelas à Binance (reduzido de 3 para 2)
        # Com 80 símbolos e delay de 0.2s, ciclo completo = ~8s
        semaphore = asyncio.Semaphore(2)
        
        async def fetch_single_symbol(symbol):
            async with semaphore:
                try:
                    # Rate limiting adicional: delay entre requisições
                    await asyncio.sleep(0.2)  # 200ms delay = 5 req/s máximo
                    
                    ccxt_symbol = symbol.replace('USDT', '/USDT')
                    
                    # Buscar 1h para cache (RSI, trend)
                    ohlcv_1h = await exchange.fetch_ohlcv(ccxt_symbol, '1h', limit=30)
                    
                    if not ohlcv_1h or len(ohlcv_1h) == 0:
                        logger.warning(f"[MarketDataCache] Sem dados OHLCV para {symbol}")
                        return None
                    
                    df = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
                    current_rsi = float(df['rsi'].iloc[-1])
                    current_price = float(df['close'].iloc[-1])
                    price_24h_ago = float(df['close'].iloc[-24]) if len(df) >= 24 else float(df['close'].iloc[0])
                    change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
                    
                    # Calcular proximidade de alerta
                    proximity = 0
                    trend = 'neutral'
                    
                    if current_rsi <= 30:
                        proximity = min(100, int((30 - current_rsi) * 5 + 50))
                        trend = 'forming_bullish'
                    elif current_rsi >= 70:
                        proximity = min(100, int((current_rsi - 70) * 5 + 50))
                        trend = 'forming_bearish'
                    elif current_rsi <= 35:
                        proximity = int((35 - current_rsi) * 8)
                        trend = 'watching_bullish'
                    elif current_rsi >= 65:
                        proximity = int((current_rsi - 65) * 8)
                        trend = 'watching_bearish'
                    
                    # Buscar outros timeframes para histórico (4h, 1d)
                    multi_timeframe_data = {}
                    for tf in ['4h', '1d']:
                        try:
                            ohlcv_tf = await exchange.fetch_ohlcv(ccxt_symbol, tf, limit=2)
                            if ohlcv_tf and len(ohlcv_tf) > 0:
                                multi_timeframe_data[tf] = ohlcv_tf[-1]  # Último candle
                        except Exception as e:
                            logger.debug(f"[MarketDataCache] Erro ao buscar {symbol} {tf}: {e}")
                    
                    # Retornar dados completos (cache + histórico multi-timeframe)
                    return {
                        'symbol': ccxt_symbol,
                        'db_symbol': symbol,  # Formato para banco (BTCUSDT)
                        'price': round(current_price, 2 if current_price >= 1 else 6),
                        'change_24h': round(change_24h, 2),
                        'rsi': round(current_rsi, 1),
                        'proximity': proximity,
                        'trend': trend,
                        # Dados históricos do último candle (1h para compatibilidade)
                        'ohlcv': {
                            'timestamp': ohlcv_1h[-1][0],  # Timestamp em ms
                            'open': float(ohlcv_1h[-1][1]),
                            'high': float(ohlcv_1h[-1][2]),
                            'low': float(ohlcv_1h[-1][3]),
                            'close': float(ohlcv_1h[-1][4]),
                            'volume': float(ohlcv_1h[-1][5])
                        },
                        # Dados multi-timeframe
                        'multi_timeframe': multi_timeframe_data
                    }
                except Exception as e:
                    logger.warning(f"[MarketDataCache] Erro ao buscar {symbol}: {e}")
                    # Retornar erro para processar depois (sem bloquear semaphore)
                    return {'error': True, 'symbol': symbol, 'exception': str(e)}
        
        # Buscar todos os símbolos em paralelo (com limite de 3)
        tasks = [fetch_single_symbol(s) for s in symbols]
        results = await asyncio.gather(*tasks)
        
        # Separar resultados válidos de erros
        valid_results = []
        failed_symbols = []
        
        for r in results:
            if r is None:
                continue
            elif isinstance(r, dict) and r.get('error'):
                failed_symbols.append(r)
            else:
                valid_results.append(r)
        
        # Criar alertas para símbolos que falharam (fora do semaphore)
        # TEMPORARIAMENTE DESABILITADO - pode causar deadlock
        # if failed_symbols:
        #     for failed in failed_symbols:
        #         try:
        #             await create_symbol_alert(
        #                 symbol=failed['symbol'],
        #                 event_type='failed',
        #                 message=f"Falha ao buscar dados: {failed['exception']}",
        #                 severity='error',
        #                 metadata={'error': failed['exception'], 'timeframe': '1h'}
        #             )
        #         except Exception as alert_error:
        #             logger.debug(f"Erro ao criar alerta: {alert_error}")
        
        # Salvar no banco (cache + histórico) - valid_results já foi filtrado acima
        async with pool.acquire() as conn:
            cache_count = 0
            historical_count = 0
            
            for data in valid_results:
                # 1. Salvar no cache (tempo real)
                await conn.execute("""
                    INSERT INTO market_data_cache (symbol, price, change_24h, rsi, proximity, trend, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    ON CONFLICT (symbol) DO UPDATE SET
                        price = EXCLUDED.price,
                        change_24h = EXCLUDED.change_24h,
                        rsi = EXCLUDED.rsi,
                        proximity = EXCLUDED.proximity,
                        trend = EXCLUDED.trend,
                        updated_at = NOW()
                """, data['symbol'], data['price'], data['change_24h'], 
                    data['rsi'], data['proximity'], data['trend'])
                cache_count += 1
                
                # 2. Salvar dados históricos (OHLCV 1h) na tabela market_data
                if 'ohlcv' in data:
                    ohlcv = data['ohlcv']
                    timestamp_dt = datetime.fromtimestamp(ohlcv['timestamp'] / 1000)
                    
                    await conn.execute("""
                        INSERT INTO market_data (symbol, timestamp, price, open, high, low, close, volume, source)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (symbol, timestamp) DO UPDATE SET
                            price = EXCLUDED.price,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """, data['db_symbol'], timestamp_dt, ohlcv['close'],
                        ohlcv['open'], ohlcv['high'], ohlcv['low'], 
                        ohlcv['close'], ohlcv['volume'], 'binance_1h')
                    historical_count += 1
                
                # 3. Salvar dados multi-timeframe (4h, 1d)
                if 'multi_timeframe' in data:
                    for tf, candle_data in data['multi_timeframe'].items():
                        try:
                            tf_timestamp_dt = datetime.fromtimestamp(candle_data[0] / 1000)
                            await conn.execute("""
                                INSERT INTO market_data (symbol, timestamp, price, open, high, low, close, volume, source)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                                ON CONFLICT (symbol, timestamp) DO UPDATE SET
                                    price = EXCLUDED.price,
                                    open = EXCLUDED.open,
                                    high = EXCLUDED.high,
                                    low = EXCLUDED.low,
                                    close = EXCLUDED.close,
                                    volume = EXCLUDED.volume
                            """, data['db_symbol'], tf_timestamp_dt, float(candle_data[4]),
                                float(candle_data[1]), float(candle_data[2]), float(candle_data[3]),
                                float(candle_data[4]), float(candle_data[5]), f'binance_{tf}')
                            historical_count += 1
                        except Exception as e:
                            logger.debug(f"[MarketDataCache] Erro ao salvar {data['db_symbol']} {tf}: {e}")
        
        logger.info(f"[MarketDataCache] Atualizado {cache_count}/{len(symbols)} símbolos (cache) + {historical_count} candles históricos")
        return cache_count
        
    except Exception as e:
        logger.error(f"[MarketDataCache] Erro no update: {e}")
        return 0

async def market_data_worker():
    """
    Background worker que atualiza market data cache a cada 120 segundos.
    Executado como task assíncrona no startup.
    
    RATE LIMITING:
    - Binance API: 1200 weight/min
    - fetch_ohlcv: ~5 weight cada
    - Com 80 símbolos + 3 timeframes = ~400 weight/ciclo
    - Intervalo de 120s = ~200 weight/min (margem de segurança)
    """
    global _market_data_worker_running
    _market_data_worker_running = True
    
    logger.info("[MarketDataWorker] Iniciando worker de atualização de market data...")
    
    # Primeira atualização imediata
    await update_market_data_cache()
    
    while _market_data_worker_running:
        try:
            await asyncio.sleep(120)  # Atualiza a cada 120 segundos (era 60s - aumentado para evitar rate limit)
            if _market_data_worker_running:
                await update_market_data_cache()
        except asyncio.CancelledError:
            logger.info("[MarketDataWorker] Worker cancelado")
            break
        except Exception as e:
            logger.error(f"[MarketDataWorker] Erro: {e}")
            await asyncio.sleep(30)  # Espera 30s antes de tentar novamente (era 10s)

async def start_market_data_worker():
    """Inicia o background worker de market data"""
    global _market_data_worker_task
    
    # Inicializar tabela
    await init_market_data_cache_table()
    
    # Iniciar worker
    _market_data_worker_task = asyncio.create_task(market_data_worker())
    logger.info("[MarketDataWorker] Worker iniciado como background task")

async def stop_market_data_worker():
    """Para o background worker de market data"""
    global _market_data_worker_running, _market_data_worker_task
    
    _market_data_worker_running = False
    if _market_data_worker_task:
        _market_data_worker_task.cancel()
        try:
            await _market_data_worker_task
        except asyncio.CancelledError:
            pass
    logger.info("[MarketDataWorker] Worker parado")

# AutoTrade Manager (global instance)
autotrade_manager: Optional[AutoTradeManager] = None

# Exchange singleton para market-data (evita criar múltiplas conexões)
_market_data_exchange = None
_market_data_lock = asyncio.Lock()

# Mutex global para fila de requisições de market-data (previne paralelismo entre chamadas)
_market_data_handler_lock = asyncio.Lock()

async def get_market_data_exchange():
    """Retorna singleton do exchange para market-data com lock para thread-safety"""
    global _market_data_exchange
    
    async with _market_data_lock:
        if _market_data_exchange is None:
            import ccxt.async_support as ccxt_async
            _market_data_exchange = ccxt_async.binance({
                'enableRateLimit': True,
                'rateLimit': 500,
                'options': {'defaultType': 'spot'}
            })
            logger.info("[MarketData] Exchange singleton criado")
        return _market_data_exchange


# Função para converter tipos numpy para tipos Python nativos
def convert_numpy_types(obj: Any) -> Any:
    """Converte tipos numpy para tipos Python nativos para serialização JSON"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj


# FastAPI app
app = FastAPI(
    title="Execution Engine - Paper Trading",
    description="Motor de execução para paper trading com estratégias em tempo real",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global
executors: Dict[str, StrategyExecutor] = {}
order_managers: Dict[str, OrderManager] = {}


async def get_autotrade_manager():
    """Get or initialize AutoTradeManager (lazy initialization)"""
    global autotrade_manager
    
    logger.info("🔍 get_autotrade_manager() chamado")
    
    if autotrade_manager is None:
        logger.info("🔄 Inicializando AutoTradeManager...")
        autotrade_manager = AutoTradeManager(
            db_host=os.getenv("TIMESCALE_HOST", "timescaledb"),
            db_port=int(os.getenv("TIMESCALE_PORT", 5432)),
            db_name=os.getenv("TIMESCALE_DB", "crypto_market"),
            db_user=os.getenv("TIMESCALE_USER", "crypto_user"),
            db_password=os.getenv("TIMESCALE_PASSWORD", "crypto_pass")
        )
        
        try:
            await autotrade_manager.connect()
            logger.info("✅ AutoTradeManager inicializado e conectado")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar AutoTradeManager: {e}", exc_info=True)
            autotrade_manager = None
    else:
        logger.info("♻️ AutoTradeManager já inicializado - reutilizando")
    
    return autotrade_manager


# Lifecycle events
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Execution Engine startup event")
    # Iniciar background worker de market data cache
    await start_market_data_worker()
    logger.info("✅ Market Data Worker iniciado")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Execution Engine shutdown event")
    await stop_market_data_worker()
    logger.info("✅ Market Data Worker parado")


# ==========================================
# SYMBOLS MANAGEMENT API (Dynamic Symbols)
# ==========================================

class AddSymbolRequest(BaseModel):
    symbol: str = Field(..., description="Symbol to add (e.g., BTCUSDT)")
    notes: Optional[str] = Field(None, description="Optional notes about the symbol")

class SymbolResponse(BaseModel):
    symbol: str
    active: bool
    added_at: datetime
    updated_at: datetime
    notes: Optional[str] = None

@app.get("/api/symbols", response_model=List[SymbolResponse])
async def get_monitored_symbols(active_only: bool = True):
    """
    Lista todos os símbolos monitorados.
    
    Query params:
    - active_only: Se True, retorna apenas símbolos ativos (default: True)
    """
    try:
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            if active_only:
                query = """
                    SELECT symbol, active, added_at, updated_at, notes 
                    FROM monitored_symbols 
                    WHERE active = true 
                    ORDER BY symbol
                """
            else:
                query = """
                    SELECT symbol, active, added_at, updated_at, notes 
                    FROM monitored_symbols 
                    ORDER BY active DESC, symbol
                """
            
            rows = await conn.fetch(query)
            
            symbols = [
                SymbolResponse(
                    symbol=row['symbol'],
                    active=row['active'],
                    added_at=row['added_at'],
                    updated_at=row['updated_at'],
                    notes=row['notes']
                )
                for row in rows
            ]
            
            return symbols
    except Exception as e:
        logger.error(f"Erro ao buscar símbolos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/symbols", response_model=SymbolResponse)
async def add_monitored_symbol(request: AddSymbolRequest):
    """
    Adiciona um novo símbolo para monitoramento.
    
    Body:
    - symbol: Símbolo a adicionar (ex: BTCUSDT)
    - notes: Notas opcionais sobre o símbolo
    """
    try:
        # Validar formato do símbolo (deve terminar com USDT)
        if not request.symbol.endswith('USDT'):
            raise HTTPException(
                status_code=400, 
                detail="Símbolo deve terminar com USDT (ex: BTCUSDT)"
            )
        
        # Validar se símbolo existe na Binance
        try:
            exchange = await get_market_data_exchange()
            ccxt_symbol = request.symbol.replace('USDT', '/USDT')
            await exchange.fetch_ticker(ccxt_symbol)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Símbolo {request.symbol} não encontrado na Binance: {str(e)}"
            )
        
        # Inserir no banco
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO monitored_symbols (symbol, active, notes, added_at, updated_at)
                VALUES ($1, true, $2, NOW(), NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                    active = true,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                RETURNING symbol, active, added_at, updated_at, notes
            """, request.symbol, request.notes)
            
            logger.info(f"✅ Símbolo {request.symbol} adicionado ao monitoramento")
            
            # Criar alerta de novo símbolo adicionado
            await create_symbol_alert(
                symbol=request.symbol,
                event_type='added',
                message=f'Novo símbolo adicionado ao monitoramento',
                severity='success',
                metadata={'notes': request.notes}
            )
            
            return SymbolResponse(
                symbol=row['symbol'],
                active=row['active'],
                added_at=row['added_at'],
                updated_at=row['updated_at'],
                notes=row['notes']
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao adicionar símbolo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/symbols/{symbol}")
async def remove_monitored_symbol(symbol: str, permanent: bool = False):
    """
    Remove um símbolo do monitoramento.
    
    Path params:
    - symbol: Símbolo a remover (ex: BTCUSDT)
    
    Query params:
    - permanent: Se True, deleta do banco. Se False, apenas desativa (default: False)
    """
    try:
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            if permanent:
                # Deletar permanentemente
                result = await conn.execute("""
                    DELETE FROM monitored_symbols WHERE symbol = $1
                """, symbol)
                
                if result == "DELETE 0":
                    raise HTTPException(status_code=404, detail=f"Símbolo {symbol} não encontrado")
                
                logger.info(f"🗑️ Símbolo {symbol} deletado permanentemente")
                
                # Criar alerta de remoção permanente
                await create_symbol_alert(
                    symbol=symbol,
                    event_type='removed',
                    message=f'Símbolo removido permanentemente do monitoramento',
                    severity='warning',
                    metadata={'permanent': True}
                )
                
                return {"status": "deleted", "symbol": symbol}
            else:
                # Apenas desativar
                row = await conn.fetchrow("""
                    UPDATE monitored_symbols 
                    SET active = false, updated_at = NOW()
                    WHERE symbol = $1
                    RETURNING symbol
                """, symbol)
                
                if not row:
                    raise HTTPException(status_code=404, detail=f"Símbolo {symbol} não encontrado")
                
                logger.info(f"⏸️ Símbolo {symbol} desativado")
                
                # Criar alerta de desativação
                await create_symbol_alert(
                    symbol=symbol,
                    event_type='removed',
                    message=f'Símbolo desativado (não deletado)',
                    severity='info',
                    metadata={'permanent': False}
                )
                
                return {"status": "deactivated", "symbol": symbol}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao remover símbolo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/symbols/stats")
async def get_symbols_stats():
    """
    Retorna estatísticas dos símbolos monitorados.
    """
    try:
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_symbols,
                    COUNT(*) FILTER (WHERE active = true) as active_symbols,
                    COUNT(*) FILTER (WHERE active = false) as inactive_symbols,
                    MIN(added_at) as first_added,
                    MAX(added_at) as last_added
                FROM monitored_symbols
            """)
            
            # Buscar símbolos com mais dados históricos
            top_symbols = await conn.fetch("""
                SELECT 
                    md.symbol,
                    COUNT(*) as candle_count,
                    MIN(md.timestamp) as oldest_data,
                    MAX(md.timestamp) as latest_data
                FROM market_data md
                JOIN monitored_symbols ms ON md.symbol = ms.symbol
                WHERE ms.active = true
                GROUP BY md.symbol
                ORDER BY candle_count DESC
                LIMIT 10
            """)
            
            return {
                "total_symbols": stats['total_symbols'],
                "active_symbols": stats['active_symbols'],
                "inactive_symbols": stats['inactive_symbols'],
                "first_added": stats['first_added'],
                "last_added": stats['last_added'],
                "top_symbols_by_data": [
                    {
                        "symbol": row['symbol'],
                        "candle_count": row['candle_count'],
                        "oldest_data": row['oldest_data'],
                        "latest_data": row['latest_data']
                    }
                    for row in top_symbols
                ]
            }
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/candles")
async def get_historical_candles(
    symbol: str,
    timeframe: str = "1h",
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 100
):
    """
    Consultar dados históricos OHLCV por símbolo e timeframe.
    
    Parâmetros:
    - symbol: Símbolo (ex: BTCUSDT)
    - timeframe: Timeframe (1h, 4h, 1d)
    - start: Data inicial (ISO 8601, ex: 2025-01-01T00:00:00Z)
    - end: Data final (ISO 8601)
    - limit: Máximo de candles (default: 100)
    """
    try:
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            # Construir query dinâmica
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM market_data
                WHERE symbol = $1 AND source = $2
            """
            params = [symbol, f'binance_{timeframe}']
            param_count = 2
            
            if start:
                param_count += 1
                query += f" AND timestamp >= ${param_count}"
                params.append(datetime.fromisoformat(start.replace('Z', '+00:00')))
            
            if end:
                param_count += 1
                query += f" AND timestamp <= ${param_count}"
                params.append(datetime.fromisoformat(end.replace('Z', '+00:00')))
            
            query += f" ORDER BY timestamp DESC LIMIT ${param_count + 1}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(rows),
                "candles": [
                    {
                        "timestamp": row['timestamp'].isoformat(),
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "close": float(row['close']),
                        "volume": float(row['volume'])
                    }
                    for row in rows
                ]
            }
    except Exception as e:
        logger.error(f"Erro ao buscar candles históricos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/symbols/coverage-dashboard")
async def get_coverage_dashboard():
    """
    Dashboard de cobertura de dados: visualizar em tempo real quais símbolos têm dados atualizados.
    
    Retorna:
    - Métricas globais (total_symbols, active, with_data, coverage %)
    - Cobertura por timeframe (1h, 4h, 1d)
    - Lista de símbolos com status (last_update, update_frequency, data_gaps)
    """
    try:
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            # Métricas globais
            global_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT ms.symbol) as total_symbols,
                    COUNT(DISTINCT ms.symbol) FILTER (WHERE ms.active = true) as active_symbols,
                    COUNT(DISTINCT md.symbol) as symbols_with_data
                FROM monitored_symbols ms
                LEFT JOIN market_data md ON ms.symbol = md.symbol
            """)
            
            coverage_pct = (global_stats['symbols_with_data'] / global_stats['active_symbols'] * 100) if global_stats['active_symbols'] > 0 else 0
            
            # Cobertura por timeframe
            timeframe_coverage = await conn.fetch("""
                SELECT 
                    source,
                    COUNT(DISTINCT symbol) as symbol_count,
                    COUNT(*) as total_candles,
                    MAX(timestamp) as latest_data
                FROM market_data
                WHERE source IN ('binance_1h', 'binance_4h', 'binance_1d')
                GROUP BY source
            """)
            
            # Status por símbolo (últimos 7 dias)
            symbol_status = await conn.fetch("""
                SELECT 
                    ms.symbol,
                    ms.active,
                    COUNT(DISTINCT md.timestamp) FILTER (WHERE md.source = 'binance_1h') as candles_1h,
                    COUNT(DISTINCT md.timestamp) FILTER (WHERE md.source = 'binance_4h') as candles_4h,
                    COUNT(DISTINCT md.timestamp) FILTER (WHERE md.source = 'binance_1d') as candles_1d,
                    MAX(md.timestamp) FILTER (WHERE md.source = 'binance_1h') as last_update_1h,
                    MAX(md.timestamp) FILTER (WHERE md.source = 'binance_4h') as last_update_4h,
                    MAX(md.timestamp) FILTER (WHERE md.source = 'binance_1d') as last_update_1d
                FROM monitored_symbols ms
                LEFT JOIN market_data md ON ms.symbol = md.symbol 
                    AND md.timestamp >= NOW() - INTERVAL '7 days'
                WHERE ms.active = true
                GROUP BY ms.symbol, ms.active
                ORDER BY ms.symbol
            """)
            
            return {
                "global_metrics": {
                    "total_symbols": global_stats['total_symbols'],
                    "active_symbols": global_stats['active_symbols'],
                    "symbols_with_data": global_stats['symbols_with_data'],
                    "coverage_percentage": round(coverage_pct, 2)
                },
                "timeframe_coverage": [
                    {
                        "timeframe": row['source'].replace('binance_', ''),
                        "symbol_count": row['symbol_count'],
                        "total_candles": row['total_candles'],
                        "latest_data": row['latest_data'].isoformat() if row['latest_data'] else None
                    }
                    for row in timeframe_coverage
                ],
                "symbol_status": [
                    {
                        "symbol": row['symbol'],
                        "active": row['active'],
                        "candles": {
                            "1h": row['candles_1h'],
                            "4h": row['candles_4h'],
                            "1d": row['candles_1d']
                        },
                        "last_update": {
                            "1h": row['last_update_1h'].isoformat() if row['last_update_1h'] else None,
                            "4h": row['last_update_4h'].isoformat() if row['last_update_4h'] else None,
                            "1d": row['last_update_1d'].isoformat() if row['last_update_1d'] else None
                        }
                    }
                    for row in symbol_status
                ]
            }
    except Exception as e:
        logger.error(f"Erro ao buscar dashboard de cobertura: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# PAPER TRADING REQUEST MODELS
# ==========================================

class StartPaperTradingRequest(BaseModel):
    session_id: str
    strategy_name: str
    strategy_parameters: Dict
    symbol: str = "BTCUSDT"
    timeframe: str = "1m"
    initial_balance: float = 10000.0
    commission_rate: float = 0.001
    slippage_rate: float = 0.0005


@app.get("/api/symbols/alerts")
async def get_symbol_alerts(
    symbol: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50
):
    """
    Consultar alertas de símbolos.
    
    Parâmetros:
    - symbol: Filtrar por símbolo específico (opcional)
    - event_type: Filtrar por tipo de evento (added, failed, recovered, removed, no_data)
    - severity: Filtrar por severidade (info, warning, error, success)
    - limit: Máximo de resultados (default: 50)
    """
    try:
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            query = "SELECT * FROM symbol_alerts WHERE 1=1"
            params = []
            param_count = 0
            
            if symbol:
                param_count += 1
                query += f" AND symbol = ${param_count}"
                params.append(symbol)
            
            if event_type:
                param_count += 1
                query += f" AND event_type = ${param_count}"
                params.append(event_type)
            
            if severity:
                param_count += 1
                query += f" AND severity = ${param_count}"
                params.append(severity)
            
            query += f" ORDER BY created_at DESC LIMIT ${param_count + 1}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return {
                "count": len(rows),
                "alerts": [
                    {
                        "id": row['id'],
                        "symbol": row['symbol'],
                        "event_type": row['event_type'],
                        "message": row['message'],
                        "severity": row['severity'],
                        "metadata": row['metadata'],
                        "created_at": row['created_at'].isoformat()
                    }
                    for row in rows
                ]
            }
    except Exception as e:
        logger.error(f"Erro ao buscar alertas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def create_symbol_alert(
    symbol: str,
    event_type: str,
    message: str,
    severity: str = "info",
    metadata: Optional[Dict] = None
):
    """
    Helper function para criar alertas de símbolos.
    """
    try:
        pool = await get_market_data_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO symbol_alerts (symbol, event_type, message, severity, metadata)
                VALUES ($1, $2, $3, $4, $5)
            """, symbol, event_type, message, severity, json.dumps(metadata) if metadata else None)
            
            logger.info(f"[Alert] {severity.upper()} - {symbol}: {message}")
    except Exception as e:
        logger.error(f"Erro ao criar alerta: {e}")


class ManualOrderRequest(BaseModel):
    session_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str  # "MARKET", "LIMIT", etc
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None


# ==========================================
# AUTO STRATEGY SELECTOR
# ==========================================

class StrategySelectionRequest(BaseModel):
    """Requisição para seleção automática de estratégia"""
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    lookback_days: int = 90
    force_refresh: bool = False


class StrategyChangeCheckRequest(BaseModel):
    """Requisição para verificar se deve mudar estratégia"""
    current_strategy: str
    symbol: str = "BTCUSDT"
    interval: str = "1h"


@app.post("/api/strategy/auto-select")
async def auto_select_strategy(request: StrategySelectionRequest):
    """
    🤖 Seleção AUTOMÁTICA de estratégia baseada no regime de mercado
    
    Analisa o mercado atual e retorna:
    - Estratégia primária recomendada
    - Estratégias alternativas
    - Análise completa do regime
    - Conselhos de trading (risco, tamanho de posição, avisos)
    
    Exemplo de uso:
    ```bash
    curl -X POST "http://localhost:3008/api/strategy/auto-select" \\
      -H "Content-Type: application/json" \\
      -d '{"symbol": "BTCUSDT", "interval": "1h", "lookback_days": 90}'
    ```
    """
    try:
        selector = AutoStrategySelector()
        
        result = await selector.select_strategy(
            symbol=request.symbol,
            interval=request.interval,
            lookback_days=request.lookback_days,
            force_refresh=request.force_refresh
        )
        
        logger.info(f"🎯 Estratégia selecionada: {result['strategy_recommendation']['primary']} " +
                   f"(regime: {result['market_analysis']['regime']})")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erro na seleção automática: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/strategy/should-change")
async def should_change_strategy(request: StrategyChangeCheckRequest):
    """
    🔄 Verifica se deve TROCAR a estratégia atual
    
    Compara a estratégia em uso com a recomendação atual do mercado.
    Útil para sistemas que já estão rodando e precisam se adaptar.
    
    Retorna:
    - should_change: true/false
    - current_strategy: estratégia atual
    - recommended_strategy: estratégia recomendada
    - reason: motivo da recomendação
    - full_analysis: análise completa
    
    Exemplo de uso:
    ```bash
    curl -X POST "http://localhost:3008/api/strategy/should-change" \\
      -H "Content-Type: application/json" \\
      -d '{"current_strategy": "momentum", "symbol": "BTCUSDT"}'
    ```
    """
    try:
        selector = AutoStrategySelector()
        
        result = await selector.should_change_strategy(
            current_strategy=request.current_strategy,
            symbol=request.symbol,
            interval=request.interval
        )
        
        if result['should_change']:
            logger.warning(f"⚠️  RECOMENDAÇÃO DE MUDANÇA: {request.current_strategy} → {result['recommended_strategy']}")
        else:
            logger.info(f"✅ Estratégia {request.current_strategy} ainda é apropriada")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar mudança de estratégia: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategy/best")
async def get_best_strategy(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    lookback_days: int = 90
):
    """
    🎯 Retorna APENAS o nome da melhor estratégia (uso simplificado)
    
    Endpoint minimalista para obter rapidamente a estratégia recomendada.
    
    Exemplo:
    ```bash
    curl "http://localhost:3008/api/strategy/best?symbol=BTCUSDT&interval=1h"
    # Resposta: {"strategy": "breakdown_momentum"}
    ```
    """
    try:
        from auto_strategy_selector import get_best_strategy
        
        strategy = await get_best_strategy(symbol, interval, lookback_days)
        
        return {
            "strategy": strategy,
            "symbol": symbol,
            "interval": interval
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter melhor estratégia: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# META-BACKTESTER (BLUE_PRINT v1.0)
# ==========================================

class MetaBacktestRequest(BaseModel):
    """Requisição para Meta-Backtest"""
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    start_date: str = "2021-01-01"
    end_date: str = "2023-12-31"
    initial_capital: float = 100000.0
    slippage: float = 0.001
    commission: float = 0.001
    risk_per_trade: float = 0.02
    include_trades: bool = False
    include_equity_curve: bool = False
    max_trades: int = 200
    max_regime_history: int = 10

    # OPÇÃO B (cirúrgica): Chop-protection só para entradas de momentum em BULL recém-detectado
    # DESABILITADO por padrão; habilitar via API para tuning específico
    bull_momentum_chop_protection: bool = False
    bull_momentum_min_regime_age_candles: int = 12
    bull_momentum_cooldown_hours: int = 12
    bull_momentum_min_adx: float = 18.0
    bull_momentum_adx_window_candles: int = 24
    bull_momentum_max_prev_sideways_candles: int = 1000000
    bull_momentum_min_ema_separation: float = 0.03

    # Kelly Position Sizing (PASSO 25)
    use_kelly_sizing: bool = False  # Desabilitado por padrão
    kelly_fraction: float = 0.25  # 25% do full Kelly (conservador)
    kelly_min_trades: int = 30  # Mínimo de trades para habilitar Kelly

    # PASSO 28: Sentiment filter (opt-in)
    use_sentiment_filter: bool = False
    sentiment_hours: int = 24
    sentiment_limit: int = 50
    sentiment_min_score: float = -0.2
    sentiment_use_precomputed: bool = True

    # PASSO 29: Multi-Timeframe confirmation (opt-in)
    use_multi_timeframe_filter: bool = False
    mtf_timeframes: List[str] = Field(default_factory=lambda: ["4h", "1d"])
    mtf_min_candles: int = 20  # Realista: 1 ano 1h (~8760h) → 2190 candles 4h, 365 candles 1d

    # PASSO 34: ML Signal Filter (opt-in)
    use_ml_filter: bool = False
    ml_min_score: float = 0.6  # Score mínimo do ML (0-1) para aceitar trade
    ml_retrain_enabled: bool = False  # Auto-retrain quando performance degrada


class RiskCalculationRequest(BaseModel):
    """Requisição para cálculo de risco"""
    capital: float = 100000.0
    entry_price: float
    stop_loss_price: float
    regime: str = "BULL"
    regime_confidence: float = 80.0
    volume_profile: str = "NORMAL"
    volatility_atr_ratio: float = 1.0


@app.post("/api/meta-backtest/run")
async def run_meta_backtest(request: MetaBacktestRequest):
    """
    🚀 Executa Meta-Backtest Adaptativo
    
    BLUE_PRINT v1.0 - Testa a capacidade do sistema de trocar de estratégia
    dinamicamente baseado no regime de mercado.
    
    Características:
    - Itera candle a candle
    - Recalcula regime em tempo real
    - Troca estratégia automaticamente
    - Aplica slippage e taxas
    """
    try:
        import asyncpg
        import pandas as pd
        from meta_simulation import MetaBacktester, print_results
        
        # Conectar ao banco
        db_url = os.getenv('DATABASE_URL', 'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
        
        df = None
        
        try:
            conn = await asyncpg.connect(db_url)
            
            # Tentar buscar da tabela market_data (dados históricos da Binance)
            query = """
                SELECT 
                    timestamp,
                    symbol,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM market_data
                WHERE symbol = $1
                    AND timestamp >= $2::timestamptz
                    AND timestamp <= $3::timestamptz
                ORDER BY timestamp
            """
            
            # FIX: Converter strings para datetime
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(request.start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(request.end_date, '%Y-%m-%d') + timedelta(days=1)
            
            logger.info(f"🔍 Buscando dados: {request.symbol} de {start_dt} até {end_dt}")
            
            rows = await conn.fetch(
                query,
                request.symbol,
                start_dt,
                end_dt
            )
            
            logger.info(f"📊 Encontrados {len(rows)} candles para {request.symbol}")
            
            await conn.close()
            
            if rows and len(rows) > 100:
                df = pd.DataFrame([dict(row) for row in rows])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                df = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low', 
                    'close': 'Close', 'volume': 'Volume'
                })
        except Exception as db_error:
            logger.warning(f"⚠️ Erro ao buscar dados do banco: {db_error}")
        
        # USAR DADOS REAIS DO BANCO (baixados da Binance)
        # df = None  # Removido: agora usamos dados reais!
        
        # Se não há dados no banco, gerar dados sintéticos para demonstração
        if df is None or len(df) < 100:
            logger.info(f"📊 Gerando dados sintéticos para {request.symbol} (demonstração)")
            
            # FIX: Usar symbol como seed para gerar dados diferentes por par
            symbol_hash = hash(request.symbol) % 10000
            np.random.seed(42 + symbol_hash)
            
            start = pd.to_datetime(request.start_date)
            end = pd.to_datetime(request.end_date)
            dates = pd.date_range(start=start, end=end, freq='1h')
            
            n = len(dates)
            
            # Simular diferentes fases de mercado com base no símbolo
            base_price = 40000 if 'BTC' in request.symbol else (2500 if 'ETH' in request.symbol else 100)
            prices = [base_price]
            
            # Volatility multiplier por símbolo (SOL > ETH > BTC)
            vol_mult = 1.5 if 'SOL' in request.symbol else (1.2 if 'ETH' in request.symbol else 1.0)
            
            for i in range(1, n):
                # Adicionar tendências sazonais
                day_of_year = dates[i].dayofyear
                
                # Bull market Jan-Abr, Crash Nov-Jan, Recovery depois
                if day_of_year < 120:  # Bull
                    drift = 0.0003
                    vol = 0.015 * vol_mult
                elif day_of_year < 210:  # Chop
                    drift = 0.0
                    vol = 0.025 * vol_mult
                elif day_of_year < 330:  # Bear/Crash
                    drift = -0.0002
                    vol = 0.03 * vol_mult
                else:  # Recovery
                    drift = 0.0002
                    vol = 0.02 * vol_mult
                
                ret = np.random.normal(drift, vol)
                prices.append(prices[-1] * (1 + ret))
            
            prices = np.array(prices)
            
            df = pd.DataFrame({
                'Open': prices * (1 + np.random.uniform(-0.005, 0.005, n)),
                'High': prices * (1 + np.random.uniform(0, 0.015, n)),
                'Low': prices * (1 - np.random.uniform(0, 0.015, n)),
                'Close': prices,
                'Volume': np.random.uniform(100, 1000, n) * 1e6
            }, index=dates)
            
            logger.info(f"📈 Dados sintéticos gerados: {len(df)} candles")
        
        logger.info(f"📊 Dados carregados: {len(df)} candles de {request.start_date} a {request.end_date}")
        
        # PASSO 28: Buscar sentimento agregado (opt-in)
        sentiment_payload = None
        sentiment_score = 0.0
        if request.use_sentiment_filter:
            sentiment_url = os.getenv('SENTIMENT_SERVICE_URL', 'http://sentiment-analyzer:8000')
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(
                        f"{sentiment_url}/sentiment/symbol",
                        params={
                            "symbol": request.symbol,
                            "hours": request.sentiment_hours,
                            "limit": request.sentiment_limit,
                            "use_precomputed": request.sentiment_use_precomputed,
                        },
                    )
                    if r.status_code == 200:
                        sentiment_payload = r.json()
                        sentiment_score = float(sentiment_payload.get('sentiment_score', 0.0) or 0.0)
                    else:
                        logger.warning(f"⚠️ Sentiment service respondeu {r.status_code}: {r.text[:200]}")
            except Exception as e:
                logger.warning(f"⚠️ Falha ao buscar sentiment (seguindo com 0.0): {e}")

        # Executar Meta-Backtest
        backtester = MetaBacktester(
            initial_capital=request.initial_capital,
            slippage=request.slippage,
            commission=request.commission,
            risk_per_trade=request.risk_per_trade,
            regime_lookback=100,  # FIX: Reduzido de 250 para 100
            bull_momentum_chop_protection=request.bull_momentum_chop_protection,
            bull_momentum_min_regime_age_candles=request.bull_momentum_min_regime_age_candles,
            bull_momentum_cooldown_hours=request.bull_momentum_cooldown_hours,
            bull_momentum_min_adx=request.bull_momentum_min_adx,
            bull_momentum_adx_window_candles=request.bull_momentum_adx_window_candles,
            bull_momentum_max_prev_sideways_candles=request.bull_momentum_max_prev_sideways_candles,
            bull_momentum_min_ema_separation=request.bull_momentum_min_ema_separation,
            # PASSO 25: Kelly Position Sizing
            use_kelly_sizing=request.use_kelly_sizing,
            kelly_fraction=request.kelly_fraction,
            kelly_min_trades=request.kelly_min_trades,
            # PASSO 28: Sentiment filter
            use_sentiment_filter=request.use_sentiment_filter,
            sentiment_score=sentiment_score,
            sentiment_min_score=request.sentiment_min_score,
            # PASSO 29: Multi-Timeframe confirmation
            use_multi_timeframe_filter=request.use_multi_timeframe_filter,
            mtf_timeframes=request.mtf_timeframes,
            mtf_min_candles=request.mtf_min_candles,
            # PASSO 34: ML Signal Filter
            use_ml_filter=request.use_ml_filter,
            ml_min_score=request.ml_min_score,
            ml_retrain_enabled=request.ml_retrain_enabled,
        )
        
        result = backtester.run_simulation(df)
        
        # Helper para converter valores numéricos (tratando inf/nan)
        def safe_float(val, default=0.0):
            """Converte para float tratando inf/nan"""
            if val is None or (isinstance(val, float) and (float('inf') == val or float('-inf') == val or val != val)):
                return default
            return float(val)
        
        def safe_round(val, decimals=2, default=0.0):
            """Round seguro tratando inf/nan"""
            safe_val = safe_float(val, default)
            return round(safe_val, decimals)

        def serialize_trade(trade):
            """Serializa Trade (dataclass) para JSON-safe."""
            def dt(v):
                return v.isoformat() if hasattr(v, 'isoformat') else v

            return {
                "entry_time": dt(getattr(trade, 'entry_time', None)),
                "exit_time": dt(getattr(trade, 'exit_time', None)),
                "direction": getattr(trade, 'direction', None),
                "strategy": getattr(trade, 'strategy', None),
                "regime": getattr(trade, 'regime', None),
                "size": safe_round(getattr(trade, 'size', None), 6),
                "entry_price": safe_round(getattr(trade, 'entry_price', None)),
                "exit_price": safe_round(getattr(trade, 'exit_price', None)),
                "pnl": safe_round(getattr(trade, 'pnl', None)),
                "pnl_pct": safe_round(getattr(trade, 'pnl_pct', None)),
                "status": getattr(trade, 'status', None),
                "exit_reason": getattr(trade, 'exit_reason', ''),
            }
        
        # Validação BLUE_PRINT
        passed_sharpe = safe_float(result.sharpe_ratio, 0) >= 1.5
        passed_drawdown = safe_float(result.max_drawdown_pct, 100) <= 20
        
        response = {
            "success": True,
            "symbol": request.symbol,
            "period": f"{request.start_date} to {request.end_date}",
            "candles_analyzed": len(df),
            
            "performance": {
                "initial_capital": safe_round(result.initial_capital),
                "final_capital": safe_round(result.final_capital),
                "total_return": safe_round(result.total_return),
                "total_return_pct": safe_round(result.total_return_pct),
                "max_drawdown_pct": safe_round(result.max_drawdown_pct)
            },
            
            "risk_metrics": {
                "sharpe_ratio": safe_round(result.sharpe_ratio),
                "sortino_ratio": safe_round(result.sortino_ratio),
                "profit_factor": safe_round(result.profit_factor)
            },
            
            "trade_stats": {
                "total_trades": int(result.total_trades) if result.total_trades else 0,
                "winning_trades": int(result.winning_trades) if result.winning_trades else 0,
                "losing_trades": int(result.losing_trades) if result.losing_trades else 0,
                "win_rate": safe_round(result.win_rate, 1),
                "avg_win": safe_round(result.avg_win),
                "avg_loss": safe_round(result.avg_loss)
            },

            "sentiment": {
                "enabled": bool(request.use_sentiment_filter),
                "min_score": request.sentiment_min_score,
                "score": round(float(sentiment_score), 4),
                "details": sentiment_payload,
            },

            "multi_timeframe": {
                "enabled": bool(request.use_multi_timeframe_filter),
                "timeframes": list(request.mtf_timeframes or []),
                "min_candles": int(request.mtf_min_candles),
            },
            
            "adaptability": {
                "regime_changes": int(result.regime_changes) if result.regime_changes else 0,
                "strategy_switches": int(result.strategy_switches) if result.strategy_switches else 0
            },
            
            "exit_reasons": result.exit_reasons if hasattr(result, 'exit_reasons') and result.exit_reasons else {},

            "debug": result.debug_stats if hasattr(result, 'debug_stats') and result.debug_stats else {},
            
            "blueprint_validation": {
                "sharpe_gte_1_5": {
                    "target": 1.5,
                    "actual": safe_round(result.sharpe_ratio),
                    "passed": bool(passed_sharpe)
                },
                "max_dd_lte_20": {
                    "target": 20,
                    "actual": safe_round(result.max_drawdown_pct),
                    "passed": bool(passed_drawdown)
                },
                "overall_pass": bool(passed_sharpe and passed_drawdown)
            },
            
            "regime_history": [
                {k: (str(v) if hasattr(v, 'isoformat') else v) for k, v in item.items()}
                for item in (result.regime_history[:max(0, int(request.max_regime_history))] if result.regime_history else [])
            ]
        }

        if request.include_trades:
            max_trades = max(0, int(request.max_trades))
            response["trades"] = [serialize_trade(t) for t in (result.trades[:max_trades] if result.trades else [])]

        if request.include_equity_curve:
            response["equity_curve"] = [safe_round(x, 2) for x in (result.equity_curve if result.equity_curve else [])]

        return response
        
    except Exception as e:
        logger.error(f"❌ Erro no Meta-Backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/meta-backtest/scenarios")
async def get_stress_test_scenarios():
    """
    📋 Lista cenários de stress test disponíveis (BLUE_PRINT)
    
    Retorna os 4 cenários obrigatórios de stress test:
    1. The Bull Run: Jan 2021 - Abr 2021
    2. The Chop: Mai 2021 - Jul 2021
    3. The Crash: Nov 2021 - Jan 2022
    4. The Recovery: Jan 2023 - Mar 2023
    """
    from meta_simulation import STRESS_TEST_PERIODS
    
    return {
        "scenarios": STRESS_TEST_PERIODS,
        "validation_targets": {
            "sharpe_ratio": ">= 1.5",
            "max_drawdown": "<= 20%"
        }
    }


@app.post("/api/meta-backtest/stress-test")
async def run_stress_tests(scenario: Optional[str] = None):
    """
    🔬 Executa Stress Tests do BLUE_PRINT
    
    Cenários:
    - bull_run: Jan 2021 - Abr 2021 (Deve lucrar muito)
    - chop: Mai 2021 - Jul 2021 (Deve perder pouco)
    - crash: Nov 2021 - Jan 2022 (Deve virar para Short)
    - recovery: Jan 2023 - Mar 2023 (Deve capturar o fundo)
    
    Se não especificar cenário, executa todos.
    """
    try:
        from meta_simulation import STRESS_TEST_PERIODS, MetaBacktester
        import asyncpg
        import pandas as pd
        
        # Filtrar cenários
        if scenario and scenario in STRESS_TEST_PERIODS:
            scenarios_to_run = {scenario: STRESS_TEST_PERIODS[scenario]}
        else:
            scenarios_to_run = STRESS_TEST_PERIODS
        
        # Conectar ao banco
        db_url = os.getenv('DATABASE_URL', 'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
        conn = await asyncpg.connect(db_url)
        
        results = {}
        
        for key, config in scenarios_to_run.items():
            logger.info(f"🔬 Executando stress test: {config['name']}")
            
            # Buscar dados do período
            # FIX: Usar BTCUSDT (formato dos dados históricos) e BTC/USDT (live)
            query = """
                SELECT 
                    timestamp,
                    symbol,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM market_data
                WHERE symbol IN ('BTCUSDT', 'BTC/USDT')
                    AND timestamp >= $1::timestamp
                    AND timestamp <= $2::timestamp
                ORDER BY timestamp
            """
            
            from datetime import datetime
            start_dt = datetime.fromisoformat(config['start']) if isinstance(config['start'], str) else config['start']
            end_dt = datetime.fromisoformat(config['end']) if isinstance(config['end'], str) else config['end']
            
            rows = await conn.fetch(query, start_dt, end_dt)
            
            if not rows or len(rows) < 100:
                results[key] = {
                    "name": config['name'],
                    "error": f"Dados insuficientes: {len(rows) if rows else 0} candles"
                }
                continue
            
            # Converter para DataFrame
            df = pd.DataFrame([dict(row) for row in rows])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.rename(columns={
                'open': 'Open', 'high': 'High', 'low': 'Low', 
                'close': 'Close', 'volume': 'Volume'
            })
            
            # Executar backtest
            backtester = MetaBacktester(initial_capital=100000, regime_lookback=100)
            result = backtester.run_simulation(df)
            
            # Helper para converter valores com safe_float
            def safe_float_stress(val, default=0.0):
                if val is None or (isinstance(val, float) and (float('inf') == val or float('-inf') == val or val != val)):
                    return default
                return float(val)
            
            results[key] = {
                "name": config['name'],
                "period": f"{config['start']} to {config['end']}",
                "expected": config['expected'],
                "candles": len(df),
                "return_pct": round(safe_float_stress(result.total_return_pct), 2),
                "max_drawdown_pct": round(safe_float_stress(result.max_drawdown_pct), 2),
                "sharpe_ratio": round(safe_float_stress(result.sharpe_ratio), 2),
                "trades": int(result.total_trades) if result.total_trades else 0,
                "regime_changes": int(result.regime_changes) if result.regime_changes else 0
            }
        
        await conn.close()
        
        return {
            "stress_tests": results,
            "summary": {
                "total_scenarios": len(results),
                "passed_sharpe": sum(1 for r in results.values() if isinstance(r.get('sharpe_ratio'), (int, float)) and r.get('sharpe_ratio', 0) >= 1.5),
                "passed_drawdown": sum(1 for r in results.values() if isinstance(r.get('max_drawdown_pct'), (int, float)) and r.get('max_drawdown_pct', 100) <= 20)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro nos Stress Tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RSIDivergenceBacktestRequest(BaseModel):
    """Request para backtest da estratégia RSI Divergence v2.1"""
    symbol: str = "BTCUSDT"
    start_date: str = "2023-01-01"
    end_date: str = "2024-01-01"
    initial_capital: float = 100000.0
    timeframe: str = "1h"  # Suporte multi-timeframe: 15m, 1h, 4h, 1d
    # Parâmetros da estratégia v2.0 OTIMIZADOS
    rsi_period: int = 14
    lookback_periods: int = 15          # ALTERADO: 20 → 15
    min_adx_trend: int = 18             # ALTERADO: 20 → 18
    stop_loss_atr_mult: float = 2.0
    take_profit_atr_mult: float = 4.0
    min_signal_strength: float = 0.50   # ALTERADO: 0.5 → 0.50 (mesmo)
    # NOVO v2.0: Filtros adicionais
    rsi_overbought: int = 75            # NOVO: zona extrema de venda
    rsi_oversold: int = 25              # NOVO: zona extrema de compra
    volume_multiplier: float = 1.5      # NOVO: confirmação de volume
    use_ema_filter: bool = True         # NOVO: filtro EMA 50/200
    use_mtf_filter: bool = False        # NOVO v2.1: Multi-timeframe (desabilitado por padrão)


@app.post("/api/backtest/rsi-divergence")
async def backtest_rsi_divergence(request: RSIDivergenceBacktestRequest):
    """
    🎯 Backtest da estratégia RSI Divergence com dados reais do PostgreSQL
    
    Detecta divergências entre preço e RSI:
    - Divergência de Alta (Bullish)
    - Divergência de Baixa (Bearish)
    - Divergência Oculta de Alta (Hidden Bullish)
    - Divergência Oculta de Baixa (Hidden Bearish)
    """
    try:
        import asyncpg
        import pandas as pd
        from strategies.rsi_divergence import RSIDivergenceStrategy
        
        logger.info(f"🎯 Iniciando backtest RSI Divergence para {request.symbol} ({request.timeframe})")
        
        # Conectar ao banco
        db_url = os.getenv('DATABASE_URL', 'postgresql://aitrading_user:aitrading_pass@postgres:5432/aitrading_db')
        conn = await asyncpg.connect(db_url)
        
        # Buscar dados históricos
        query = """
            SELECT 
                time as timestamp,
                symbol,
                open,
                high,
                low,
                close,
                volume
            FROM market_data
            WHERE symbol = $1
                AND time >= $2::timestamptz
                AND time <= $3::timestamptz
                AND timeframe = $4
            ORDER BY time
        """
        
        from datetime import datetime
        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)
        
        rows = await conn.fetch(query, request.symbol, start_dt, end_dt, request.timeframe)
        await conn.close()
        
        if not rows or len(rows) < 200:
            raise HTTPException(
                status_code=400, 
                detail=f"Dados insuficientes: {len(rows) if rows else 0} candles (mínimo: 200)"
            )
        
        # Converter para DataFrame
        df = pd.DataFrame([dict(row) for row in rows])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        logger.info(f"📊 Dados carregados: {len(df)} candles de {df.index.min()} a {df.index.max()}")
        
        # Criar estratégia com parâmetros v2.1
        strategy_params = {
            'rsi_period': request.rsi_period,
            'lookback_periods': request.lookback_periods,
            'min_adx_trend': request.min_adx_trend,
            'stop_loss_atr_mult': request.stop_loss_atr_mult,
            'take_profit_atr_mult': request.take_profit_atr_mult,
            'min_signal_strength': request.min_signal_strength,
            # NOVO v2.0
            'rsi_overbought': request.rsi_overbought,
            'rsi_oversold': request.rsi_oversold,
            'volume_multiplier': request.volume_multiplier,
            'use_ema_filter': request.use_ema_filter,
            # NOVO v2.1
            'use_mtf_filter': request.use_mtf_filter,
        }
        
        strategy = RSIDivergenceStrategy(parameters=strategy_params)
        
        # Calcular indicadores
        df = strategy.calculate_indicators(df)
        
        # Gerar sinais
        df = strategy.generate_signals(df)
        
        # Obter estatísticas dos padrões
        pattern_stats = strategy.get_pattern_statistics(df)
        
        # Simular trades
        trades = []
        capital = request.initial_capital
        position = None
        equity_curve = []
        
        for i, row in df.iterrows():
            if row['signal'] != 0 and position is None:
                # Abrir posição
                position = {
                    'entry_date': str(i),
                    'entry_price': float(row['close']),
                    'signal': int(row['signal']),
                    'signal_type': row['signal_type'],
                    'signal_strength': float(row['signal_strength']),
                    'stop_loss': float(row['stop_loss']),
                    'take_profit': float(row['take_profit'])
                }
            elif position is not None:
                # Verificar saída
                current_price = float(row['close'])
                
                # Stop Loss
                if position['signal'] == 1:  # Long
                    if current_price <= position['stop_loss']:
                        pnl = (position['stop_loss'] - position['entry_price']) / position['entry_price']
                        position['exit_date'] = str(i)
                        position['exit_price'] = position['stop_loss']
                        position['exit_reason'] = 'STOP_LOSS'
                        position['pnl'] = float(pnl)
                        trades.append(position)
                        capital *= (1 + pnl)
                        position = None
                    elif current_price >= position['take_profit']:
                        pnl = (position['take_profit'] - position['entry_price']) / position['entry_price']
                        position['exit_date'] = str(i)
                        position['exit_price'] = position['take_profit']
                        position['exit_reason'] = 'TAKE_PROFIT'
                        position['pnl'] = float(pnl)
                        trades.append(position)
                        capital *= (1 + pnl)
                        position = None
                else:  # Short
                    if current_price >= position['stop_loss']:
                        pnl = (position['entry_price'] - position['stop_loss']) / position['entry_price']
                        position['exit_date'] = str(i)
                        position['exit_price'] = position['stop_loss']
                        position['exit_reason'] = 'STOP_LOSS'
                        position['pnl'] = float(pnl)
                        trades.append(position)
                        capital *= (1 + pnl)
                        position = None
                    elif current_price <= position['take_profit']:
                        pnl = (position['entry_price'] - position['take_profit']) / position['entry_price']
                        position['exit_date'] = str(i)
                        position['exit_price'] = position['take_profit']
                        position['exit_reason'] = 'TAKE_PROFIT'
                        position['pnl'] = float(pnl)
                        trades.append(position)
                        capital *= (1 + pnl)
                        position = None
                        
            equity_curve.append({'date': str(i), 'equity': float(capital)})
        
        # Fechar posição aberta se houver
        if position is not None:
            current_price = float(df['close'].iloc[-1])
            if position['signal'] == 1:
                pnl = (current_price - position['entry_price']) / position['entry_price']
            else:
                pnl = (position['entry_price'] - current_price) / position['entry_price']
            position['exit_date'] = str(df.index[-1])
            position['exit_price'] = current_price
            position['exit_reason'] = 'END_OF_DATA'
            position['pnl'] = float(pnl)
            trades.append(position)
        
        # Calcular métricas
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['pnl'] > 0)
        losing_trades = sum(1 for t in trades if t['pnl'] < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_return = ((capital - request.initial_capital) / request.initial_capital) * 100
        
        # Max Drawdown
        equity_values = [e['equity'] for e in equity_curve]
        max_equity = equity_values[0]
        max_drawdown = 0
        for eq in equity_values:
            if eq > max_equity:
                max_equity = eq
            drawdown = (max_equity - eq) / max_equity * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Exit reasons
        exit_reasons = {}
        for t in trades:
            reason = t.get('exit_reason', 'UNKNOWN')
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        logger.info(f"✅ Backtest concluído: {total_trades} trades, {win_rate:.1f}% win rate, {total_return:.2f}% retorno")
        
        return {
            "strategy_name": "RSI Divergence Strategy",
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "period": f"{request.start_date} to {request.end_date}",
            "candles": len(df),
            "parameters": strategy_params,
            "pattern_statistics": pattern_stats,
            "results": {
                "initial_capital": float(request.initial_capital),
                "final_capital": float(capital),
                "total_return_pct": round(total_return, 2),
                "max_drawdown_pct": round(max_drawdown, 2),
                "total_trades": int(total_trades),
                "winning_trades": int(winning_trades),
                "losing_trades": int(losing_trades),
                "win_rate": round(win_rate, 2),
                "avg_profit": round(sum(t['pnl'] for t in trades if t['pnl'] > 0) / winning_trades * 100, 2) if winning_trades > 0 else 0,
                "avg_loss": round(sum(t['pnl'] for t in trades if t['pnl'] < 0) / losing_trades * 100, 2) if losing_trades > 0 else 0,
                "exit_reasons": exit_reasons
            },
            "trades": trades[-20:],  # Últimos 20 trades
            "equity_curve": equity_curve[::max(1, len(equity_curve)//100)]  # 100 pontos máximo
        }
        
    except asyncpg.PostgresError as e:
        logger.error(f"❌ Erro no banco de dados: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no banco de dados: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Erro no backtest RSI Divergence: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/risk/calculate")
async def calculate_position_risk(request: RiskCalculationRequest):
    """
    💰 Calcula tamanho de posição com Risk Manager (BLUE_PRINT)
    
    Usa multiplicadores dinâmicos baseados em:
    - Confiança do regime de mercado
    - Qualidade do volume
    - Volatilidade (ATR relativo)
    
    Fórmula: Position_Size = (Capital * Risk) / Stop_Distance * Multipliers
    """
    try:
        from risk_manager import (
            RiskManager, MarketPhase, VolumeProfile, 
            regime_to_phase, get_volume_profile
        )
        
        # Criar Risk Manager
        rm = RiskManager(
            base_risk_per_trade=0.02,
            max_position_size=0.25,
            max_drawdown=0.20
        )
        
        # Converter strings para enums
        regime_phase = regime_to_phase(request.regime)
        
        volume_map = {
            'HIGH': VolumeProfile.HIGH,
            'NORMAL': VolumeProfile.NORMAL,
            'LOW': VolumeProfile.LOW
        }
        vol_profile = volume_map.get(request.volume_profile.upper(), VolumeProfile.NORMAL)
        
        # Calcular
        params = rm.calculate_position_size(
            capital=request.capital,
            entry_price=request.entry_price,
            stop_loss_price=request.stop_loss_price,
            regime=regime_phase,
            regime_confidence=request.regime_confidence,
            volume_profile=vol_profile,
            volatility_atr_ratio=request.volatility_atr_ratio
        )
        
        return {
            "success": True,
            "inputs": {
                "capital": request.capital,
                "entry_price": request.entry_price,
                "stop_loss_price": request.stop_loss_price,
                "regime": request.regime,
                "regime_confidence": request.regime_confidence,
                "volume_profile": request.volume_profile,
                "volatility_atr_ratio": request.volatility_atr_ratio
            },
            "calculation": {
                "position_size_pct": round(params.position_size * 100, 2),
                "position_size_usd": round(request.capital * params.position_size, 2),
                "risk_per_trade_pct": round(params.risk_per_trade, 2),
                "stop_loss_distance_pct": round(params.stop_loss_distance, 2),
                "take_profit_distance_pct": round(params.take_profit_distance, 2)
            },
            "multipliers": {
                "confidence": round(params.confidence_multiplier, 3),
                "volume": round(params.volume_multiplier, 3),
                "atr": round(params.atr_multiplier, 3),
                "final": round(params.final_multiplier, 3)
            },
            "recommendation": params.recommendation
        }
        
    except Exception as e:
        logger.error(f"❌ Erro no cálculo de risco: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Documentação da API"""
    return {
        "service": "Execution Engine - Paper Trading",
        "version": "2.0.0",
        "endpoints": {
            "GET /health": "Health check",
            
            "📊 MARKET REGIME & STRATEGY SELECTION": {
                "POST /api/market-regime/detect": "🔍 Detecta regime de mercado (Bull/Bear/Sideways/Volatile)",
                "POST /api/strategy/auto-select": "🤖 Seleciona automaticamente a melhor estratégia",
                "POST /api/strategy/should-change": "🔄 Verifica se deve trocar estratégia atual",
                "GET /api/strategy/best": "🎯 Retorna apenas o nome da melhor estratégia"
            },
            
            "🎮 PAPER TRADING": {
                "POST /paper-trading/start": "Iniciar paper trading",
                "POST /paper-trading/{session_id}/stop": "Parar paper trading",
                "GET /paper-trading/{session_id}/status": "Status da sessão",
                "GET /paper-trading/{session_id}/account": "Resumo da conta",
                "GET /paper-trading/{session_id}/positions": "Posições abertas",
                "GET /paper-trading/{session_id}/orders": "Ordens ativas",
                "GET /paper-trading/{session_id}/trades": "Histórico de trades",
                "POST /paper-trading/{session_id}/order": "Criar ordem manual",
                "DELETE /paper-trading/{session_id}/order/{order_id}": "Cancelar ordem",
                "GET /paper-trading/sessions": "Listar sessões ativas"
            },
            
            "🧪 META-BACKTESTER (BLUE_PRINT v1.0)": {
                "POST /api/meta-backtest/run": "🚀 Executa backtest adaptativo com troca de estratégias",
                "POST /api/meta-backtest/stress-test": "🔬 Executa stress tests (Bull Run, Chop, Crash, Recovery)",
                "GET /api/meta-backtest/scenarios": "📋 Lista cenários de stress test disponíveis",
                "POST /api/risk/calculate": "💰 Calcula tamanho de posição com Risk Manager"
            }
        },
        "new_features": [
            "✅ Market Regime Detector - Identifica automaticamente Bull/Bear market",
            "✅ Auto Strategy Selector - Escolhe melhor estratégia para o regime",
            "✅ Strategy Change Advisor - Recomenda quando trocar estratégia",
            "✅ Meta-Backtester - Simula troca adaptativa de estratégias (BLUE_PRINT)",
            "✅ Risk Manager - Dimensionamento de posição institucional",
            "✅ Liquidity Grab Strategy - Wyckoff Spring para capturar stop hunts"
        ]
    }


@app.post("/paper-trading/start")
async def start_paper_trading(request: StartPaperTradingRequest, background_tasks: BackgroundTasks):
    """
    Inicia uma sessão de paper trading
    """
    
    if request.session_id in executors:
        raise HTTPException(status_code=400, detail=f"Sessão {request.session_id} já existe")
        
    try:
        # Importar estratégia dinamicamente
        import importlib
        import sys
        
        # Adicionar caminho do src ao PYTHONPATH
        sys.path.insert(0, '/app/src')
        
        strategy_map = {
            'momentum': ('strategies.momentum', 'MomentumStrategy'),
            'macd_rsi_combo': ('strategies.macd_rsi_combo', 'MacdRsiComboStrategy'),
            'trend_following': ('strategies.trend_following', 'TrendFollowingStrategy'),
            'mean_reversion': ('strategies.mean_reversion', 'MeanReversionStrategy'),
            'volatility_breakout': ('strategies.volatility_breakout', 'VolatilityBreakoutStrategy'),
            'bollinger_bands': ('strategies.bollinger_bands', 'BollingerBandsStrategy'),
            'volume_profile': ('strategies.volume_profile', 'VolumeProfileStrategy'),
            'multi_timeframe': ('strategies.multi_timeframe', 'MultiTimeframeStrategy'),
            'dynamic_position_sizing': ('strategies.dynamic_position_sizing', 'DynamicPositionSizing'),
            'liquidity_grab': ('strategies.liquidity_grab', 'LiquidityGrabStrategy')  # BLUE_PRINT
        }
        
        if request.strategy_name not in strategy_map:
            raise HTTPException(
                status_code=400, 
                detail=f"Estratégia '{request.strategy_name}' não encontrada. Disponíveis: {list(strategy_map.keys())}"
            )
            
        # Importar classe da estratégia
        module_path, class_name = strategy_map[request.strategy_name]
        logger.info(f"Importando estratégia: {module_path}.{class_name}")
        module = importlib.import_module(module_path)
        strategy_class = getattr(module, class_name)
        
        # Criar Order Manager
        order_manager = OrderManager(
            initial_balance=request.initial_balance,
            commission_rate=request.commission_rate,
            slippage_rate=request.slippage_rate,
            session_id=request.session_id,
            symbol=request.symbol,
            strategy_name=request.strategy_name
        )
        
        # Inicializar banco de dados
        await order_manager.initialize_database()
        
        order_managers[request.session_id] = order_manager
        
        # Criar Strategy Executor
        executor = StrategyExecutor(
            strategy_class=strategy_class,
            strategy_parameters=request.strategy_parameters,
            order_manager=order_manager,
            symbol=request.symbol,
            timeframe=request.timeframe
        )
        
        executors[request.session_id] = executor
        
        # Iniciar em background
        background_tasks.add_task(executor.start)
        
        logger.info(f"🚀 Paper trading iniciado: {request.session_id}")
        
        return {
            "message": "Paper trading iniciado com sucesso",
            "session_id": request.session_id,
            "strategy": request.strategy_name,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "initial_balance": request.initial_balance
        }
        
    except Exception as e:
        logger.error(f"Erro ao iniciar paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/paper-trading/{session_id}/stop")
async def stop_paper_trading(session_id: str):
    """Para uma sessão de paper trading"""
    
    if session_id not in executors:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
    executor = executors[session_id]
    
    try:
        await executor.stop()
        
        # Remover da lista ativa
        del executors[session_id]
        
        # Manter order_manager para consulta de histórico
        
        logger.info(f"⏹️ Paper trading parado: {session_id}")
        
        return {
            "message": "Paper trading parado com sucesso",
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Erro ao parar paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/paper-trading/{session_id}/status")
async def get_status(session_id: str):
    """Retorna status da sessão"""
    
    if session_id not in executors:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
    executor = executors[session_id]
    status = executor.get_status()
    return convert_numpy_types(status)


@app.get("/paper-trading/{session_id}/account")
async def get_account_summary(session_id: str):
    """Retorna resumo da conta"""
    
    if session_id not in order_managers:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
    order_manager = order_managers[session_id]
    return order_manager.get_account_summary()


@app.get("/paper-trading/{session_id}/positions")
async def get_positions(session_id: str):
    """Retorna posições abertas"""
    
    if session_id not in order_managers:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
    order_manager = order_managers[session_id]
    return order_manager.get_all_positions()


@app.get("/paper-trading/{session_id}/orders")
async def get_orders(session_id: str):
    """Retorna ordens ativas"""
    
    if session_id not in order_managers:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
    order_manager = order_managers[session_id]
    return order_manager.get_all_orders()


@app.get("/paper-trading/{session_id}/trades")
async def get_trades(session_id: str, limit: int = 50):
    """Retorna histórico de trades"""
    
    if session_id not in order_managers:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
    order_manager = order_managers[session_id]
    return order_manager.get_trade_history(limit=limit)


@app.post("/paper-trading/{session_id}/order")
async def create_manual_order(session_id: str, request: ManualOrderRequest):
    """Cria uma ordem manual (para intervenção do usuário)"""
    
    if session_id not in order_managers:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
    order_manager = order_managers[session_id]
    
    try:
        order = await order_manager.create_order(
            symbol=request.symbol,
            side=OrderSide(request.side),
            order_type=OrderType(request.order_type),
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price
        )
        
        return order.to_dict()
        
    except Exception as e:
        logger.error(f"Erro ao criar ordem: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/paper-trading/{session_id}/order/{order_id}")
async def cancel_order(session_id: str, order_id: str):
    """Cancela uma ordem pendente"""
    
    if session_id not in order_managers:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
    order_manager = order_managers[session_id]
    
    success = await order_manager.cancel_order(order_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Ordem {order_id} não encontrada")
        
    return {"message": "Ordem cancelada", "order_id": order_id}


@app.get("/paper-trading/sessions")
async def list_sessions():
    """Lista todas as sessões ativas"""
    
    sessions = []
    for session_id, executor in executors.items():
        status = executor.get_status()
        sessions.append({
            "session_id": session_id,
            "strategy": status['strategy_name'],
            "symbol": status['symbol'],
            "is_running": status['is_running'],
            "uptime_seconds": status['uptime_seconds'],
            "trades_executed": status['trades_executed'],
            "total_pnl": status['account_summary']['total_pnl']
        })
        
    return {
        "total_sessions": len(sessions),
        "sessions": sessions
    }


# ==========================================
# ENDPOINTS DE HISTÓRICO
# ==========================================

@app.get("/api/history/candles")
async def get_historical_candles(
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    limit: int = 100
):
    """
    Consulta candles históricos do TimescaleDB
    
    Parâmetros:
    - symbol: Par de trading (ex: BTCUSDT, ETHUSDT)
    - interval: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
    - limit: Número de candles (máx 1000)
    """
    import asyncpg
    
    try:
        # Conectar ao TimescaleDB
        conn_string = os.getenv('TIMESCALE_URL', 
            'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
        
        conn = await asyncpg.connect(conn_string)
        
        # Query otimizada
        query = """
            SELECT 
                timestamp,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                quote_volume,
                trades_count
            FROM market_data_realtime
            WHERE symbol = $1 AND interval_type = $2
            ORDER BY timestamp DESC
            LIMIT $3
        """
        
        rows = await conn.fetch(query, symbol, interval, min(limit, 1000))
        await conn.close()
        
        candles = []
        for row in rows:
            candles.append({
                'timestamp': row['timestamp'].isoformat(),
                'open': float(row['open_price']),
                'high': float(row['high_price']),
                'low': float(row['low_price']),
                'close': float(row['close_price']),
                'volume': float(row['volume']),
                'quote_volume': float(row['quote_volume']) if row['quote_volume'] else None,
                'trades': row['trades_count']
            })
        
        return {
            "symbol": symbol,
            "interval": interval,
            "total_candles": len(candles),
            "candles": list(reversed(candles))  # Ordem cronológica
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar candles históricos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/trades/{session_id}")
async def get_session_trade_history(
    session_id: str,
    limit: int = 100
):
    """
    Consulta histórico de trades de uma sessão específica do banco
    
    Parâmetros:
    - session_id: ID da sessão
    - limit: Número de trades (máx 500)
    """
    import asyncpg
    
    try:
        conn_string = os.getenv('TIMESCALE_URL', 
            'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
        
        conn = await asyncpg.connect(conn_string)
        
        query = """
            SELECT 
                id,
                session_id,
                symbol,
                strategy_name,
                trade_type,
                timestamp,
                price,
                quantity,
                value,
                fee,
                balance_before,
                balance_after,
                pnl,
                pnl_percent,
                cumulative_pnl,
                signal_confidence,
                indicators_snapshot,
                position_side,
                position_size
            FROM paper_trading_trades
            WHERE session_id = $1
            ORDER BY timestamp DESC
            LIMIT $2
        """
        
        rows = await conn.fetch(query, session_id, min(limit, 500))
        await conn.close()
        
        trades = []
        for row in rows:
            trades.append({
                'id': row['id'],
                'session_id': row['session_id'],
                'symbol': row['symbol'],
                'strategy': row['strategy_name'],
                'type': row['trade_type'],
                'timestamp': row['timestamp'].isoformat(),
                'price': float(row['price']),
                'quantity': float(row['quantity']),
                'value': float(row['value']),
                'fee': float(row['fee']) if row['fee'] else 0,
                'balance_before': float(row['balance_before']) if row['balance_before'] else None,
                'balance_after': float(row['balance_after']) if row['balance_after'] else None,
                'pnl': float(row['pnl']) if row['pnl'] else 0,
                'pnl_percent': float(row['pnl_percent']) if row['pnl_percent'] else 0,
                'cumulative_pnl': float(row['cumulative_pnl']) if row['cumulative_pnl'] else 0,
                'signal_confidence': float(row['signal_confidence']) if row['signal_confidence'] else None,
                'indicators': row['indicators_snapshot'],
                'position_side': row['position_side'],
                'position_size': float(row['position_size']) if row['position_size'] else 0
            })
        
        return {
            "session_id": session_id,
            "total_trades": len(trades),
            "trades": list(reversed(trades))
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar trades históricos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/performance/{session_id}")
async def get_session_performance(session_id: str):
    """
    Calcula métricas de performance de uma sessão
    
    Retorna:
    - Equity curve
    - Win rate
    - Sharpe ratio
    - Max drawdown
    - Profit factor
    """
    import asyncpg
    import numpy as np
    
    try:
        conn_string = os.getenv('TIMESCALE_URL', 
            'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
        
        conn = await asyncpg.connect(conn_string)
        
        # Buscar dados da sessão
        session_query = """
            SELECT * FROM paper_trading_sessions WHERE session_id = $1
        """
        session = await conn.fetchrow(session_query, session_id)
        
        if not session:
            await conn.close()
            raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
        
        # Buscar todos os trades
        trades_query = """
            SELECT 
                timestamp,
                balance_after,
                pnl,
                pnl_percent,
                cumulative_pnl,
                trade_type
            FROM paper_trading_trades
            WHERE session_id = $1
            ORDER BY timestamp ASC
        """
        trades = await conn.fetch(trades_query, session_id)
        await conn.close()
        
        if len(trades) == 0:
            return {
                "session_id": session_id,
                "total_trades": 0,
                "message": "Nenhum trade executado ainda"
            }
        
        # Calcular métricas
        pnls = [float(t['pnl']) for t in trades if t['pnl'] is not None]
        returns = [float(t['pnl_percent']) for t in trades if t['pnl_percent'] is not None]
        
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]
        
        # Equity curve
        equity_curve = []
        for trade in trades:
            equity_curve.append({
                'timestamp': trade['timestamp'].isoformat(),
                'balance': float(trade['balance_after']),
                'cumulative_pnl': float(trade['cumulative_pnl']) if trade['cumulative_pnl'] else 0
            })
        
        # Métricas básicas
        total_pnl = sum(pnls)
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0
        win_rate = (len(winning_trades) / len(pnls)) * 100 if pnls else 0
        
        # Profit Factor
        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 0
        # When no losses, use large but finite number for JSON serialization
        profit_factor = total_wins / total_losses if total_losses > 0 else 999.99
        
        # Sharpe Ratio (anualizado)
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        else:
            sharpe = 0
        
        # Max Drawdown
        balances = [float(t['balance_after']) for t in trades]
        peak = balances[0]
        max_dd = 0
        for balance in balances:
            if balance > peak:
                peak = balance
            dd = ((peak - balance) / peak) * 100
            if dd > max_dd:
                max_dd = dd
        
        # ROI
        initial_balance = float(session['initial_balance'])
        current_balance = float(session['current_balance'])
        roi = ((current_balance - initial_balance) / initial_balance) * 100
        
        return {
            "session_id": session_id,
            "symbol": session['symbol'],
            "strategy": session['strategy_name'],
            "summary": {
                "initial_balance": initial_balance,
                "current_balance": current_balance,
                "total_pnl": total_pnl,
                "roi_percent": round(roi, 2),
                "total_trades": len(pnls),
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades)
            },
            "metrics": {
                "win_rate": round(win_rate, 2),
                "profit_factor": round(profit_factor, 2),
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown": round(max_dd, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "avg_trade": round(np.mean(pnls), 2) if pnls else 0
            },
            "equity_curve": equity_curve
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao calcular performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/all-sessions")
async def get_all_sessions_summary():
    """
    Retorna resumo de todas as sessões (ativas e históricas)
    """
    import asyncpg
    
    try:
        conn_string = os.getenv('TIMESCALE_URL', 
            'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
        
        conn = await asyncpg.connect(conn_string)
        
        query = """
            SELECT * FROM vw_session_performance
            ORDER BY started_at DESC
        """
        
        rows = await conn.fetch(query)
        await conn.close()
        
        sessions = []
        for row in rows:
            sessions.append({
                'session_id': row['session_id'],
                'symbol': row['symbol'],
                'strategy': row['strategy_name'],
                'initial_balance': float(row['initial_balance']),
                'current_balance': float(row['current_balance']),
                'total_trades': row['total_trades'],
                'winning_trades': row['winning_trades'],
                'losing_trades': row['losing_trades'],
                'win_rate': float(row['win_rate_percent']),
                'total_pnl': float(row['total_pnl']),
                'roi_percent': float(row['roi_percent']),
                'is_running': row['is_running'],
                'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                'runtime_hours': float(row['runtime_hours']) if row['runtime_hours'] else 0
            })
        
        return {
            "total_sessions": len(sessions),
            "sessions": sessions
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar sessões: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# MONTE CARLO SIMULATION
# ==========================================

class MonteCarloRequest(BaseModel):
    """Requisição para simulação Monte Carlo"""
    strategy_name: str
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    timeframe: str = "1h"  # Alias para interval
    lookback_days: int = 180  # 6 meses para período balanceado (bull + bear)
    iterations: int = 10000
    initial_balance: float = 10000.0
    start_capital: float = 10000.0  # Alias para initial_balance
    parameter_ranges: Dict[str, List[float]] = {}  # OPCIONAL - usa defaults se vazio
    parallel: bool = True


# Global state for simulation progress tracking
simulation_progress: Dict[str, Dict] = {}


@app.get("/api/monte-carlo/progress/{strategy_name}")
async def get_simulation_progress(strategy_name: str):
    """
    Retorna o progresso atual da simulação Monte Carlo
    """
    if strategy_name in simulation_progress:
        return simulation_progress[strategy_name]
    return {
        "status": "not_found",
        "progress": 0,
        "current_iteration": 0,
        "total_iterations": 0
    }


@app.post("/api/monte-carlo/simulate")
async def run_monte_carlo_simulation(request: MonteCarloRequest, background_tasks: BackgroundTasks):
    """
    Executa simulação Monte Carlo em uma estratégia
    
    Parâmetros:
    - strategy_name: Nome da estratégia (momentum, macd_rsi_combo, etc.)
    - symbol: Par de trading
    - interval: Timeframe dos dados
    - lookback_days: Dias de histórico para simular
    - iterations: Número de simulações (recomendado: 10000)
    - initial_balance: Capital inicial
    - parameter_ranges: Ranges dos parâmetros para variar
    - parallel: Usar processamento paralelo
    
    Retorna:
    - Estatísticas completas da simulação
    - Distribuições de retorno
    - Cenários de melhor/pior caso
    - Métricas de risco (VaR, CVaR)
    """
    import asyncpg
    from monte_carlo import MonteCarloSimulator
    import importlib
    import time as time_module
    
    try:
        logger.info(f"🎲 Iniciando Monte Carlo: {request.strategy_name}, {request.iterations} iterações")
        
        # Initialize progress tracking
        simulation_progress[request.strategy_name] = {
            "status": "loading_data",
            "progress": 0,
            "current_iteration": 0,
            "total_iterations": request.iterations,
            "start_time": time_module.time(),
            "message": "Carregando dados históricos..."
        }
        
        # 1. Buscar dados históricos do TimescaleDB
        conn_string = os.getenv('TIMESCALE_URL', 
            'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
        
        conn = await asyncpg.connect(conn_string)
        
        # Calcular data inicial
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=request.lookback_days)
        
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
        
        rows = await conn.fetch(query, request.symbol, request.interval, start_date, end_date)
        await conn.close()
        
        # Se dados insuficientes no banco, buscar do CCXT
        if len(rows) < 1000:
            logger.warning(f"⚠️  Apenas {len(rows)} candles no banco. Buscando dados históricos do CCXT...")
            
            import ccxt
            import pandas as pd
            
            exchange = ccxt.binance()
            
            # Converter símbolo BTCUSDT -> BTC/USDT
            symbol_ccxt = request.symbol[:3] + '/' + request.symbol[3:]
            
            # Buscar dados em lotes (CCXT tem limite de 1000 por requisição)
            all_ohlcv = []
            since_ts = int(start_date.timestamp() * 1000)
            end_ts = int(end_date.timestamp() * 1000)
            
            while since_ts < end_ts:
                try:
                    ohlcv = exchange.fetch_ohlcv(symbol_ccxt, request.interval, since=since_ts, limit=1000)
                    if not ohlcv:
                        break
                    all_ohlcv.extend(ohlcv)
                    since_ts = ohlcv[-1][0] + 1  # Próximo timestamp
                    
                    # Update progress
                    progress_pct = min(100, int((since_ts - int(start_date.timestamp() * 1000)) / 
                                               (end_ts - int(start_date.timestamp() * 1000)) * 100))
                    simulation_progress[request.strategy_name]['message'] = f"Carregando dados: {progress_pct}%"
                    
                except Exception as e:
                    logger.error(f"Erro ao buscar dados CCXT: {e}")
                    break
            
            # Converter para DataFrame
            df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            logger.info(f"✅ {len(df)} candles carregados do CCXT ({df['timestamp'].min()} até {df['timestamp'].max()})")
        else:
            # Converter para DataFrame
            import pandas as pd
            df = pd.DataFrame([dict(row) for row in rows])
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            logger.info(f"📊 {len(df)} candles carregados do banco ({start_date.date()} a {end_date.date()})")
        
        # Validar dados mínimos
        if len(df) < 100:
            raise HTTPException(
                status_code=400, 
                detail=f"Dados insuficientes: {len(df)} candles. Mínimo: 100"
            )
        
        # 2. Carregar função da estratégia dos adapters
        from strategies.monte_carlo_adapters import (
            momentum_strategy_func,
            macd_rsi_strategy_func,
            trend_following_strategy_func,
            volatility_breakout_strategy_func,
            bollinger_bands_strategy_func,
            mean_reversion_strategy_func,
            bear_market_short_strategy_func,
            breakdown_momentum_strategy_func,
            death_cross_strategy_func
        )
        
        strategy_map = {
            'momentum': momentum_strategy_func,
            'macd_rsi_combo': macd_rsi_strategy_func,
            'trend_following': trend_following_strategy_func,
            'volatility_breakout': volatility_breakout_strategy_func,
            'bollinger_bands': bollinger_bands_strategy_func,
            'mean_reversion': mean_reversion_strategy_func,
            'bear_market_short': bear_market_short_strategy_func,
            'breakdown_momentum': breakdown_momentum_strategy_func,
            'death_cross': death_cross_strategy_func
        }
        
        if request.strategy_name not in strategy_map:
            raise HTTPException(
                status_code=400,
                detail=f"Estratégia não encontrada: {request.strategy_name}. Disponíveis: {list(strategy_map.keys())}"
            )
        
        strategy_func = strategy_map[request.strategy_name]
        
        # 3. Converter parameter_ranges para tuplas (ou usar defaults)
        from strategies.monte_carlo_adapters import get_default_param_ranges
        
        if not request.parameter_ranges:
            # Usar ranges padrão da estratégia
            default_ranges = get_default_param_ranges(request.strategy_name)
            logger.info(f"📐 Usando parameter ranges padrão para '{request.strategy_name}'")
            param_ranges = default_ranges
        else:
            # Converter os ranges fornecidos
            param_ranges = {}
            for param_name, values in request.parameter_ranges.items():
                if len(values) != 2:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Parâmetro {param_name} deve ter exatamente 2 valores [min, max]"
                    )
                param_ranges[param_name] = (values[0], values[1])
        
        logger.info(f"📐 Parameter ranges: {param_ranges}")
        
        # Update progress - starting simulation
        simulation_progress[request.strategy_name] = {
            "status": "running",
            "progress": 5,
            "current_iteration": 0,
            "total_iterations": request.iterations,
            "start_time": time_module.time(),
            "message": "Iniciando simulações..."
        }
        
        # 4. Executar simulação com callback de progresso
        def progress_callback(current: int, total: int):
            progress_pct = (current / total) * 90 + 5  # 5-95%
            simulation_progress[request.strategy_name] = {
                "status": "running",
                "progress": progress_pct,
                "current_iteration": current,
                "total_iterations": total,
                "start_time": simulation_progress[request.strategy_name]["start_time"],
                "message": f"Executando iteração {current}/{total}..."
            }
        
        simulator = MonteCarloSimulator(
            initial_balance=request.initial_balance,
            iterations=request.iterations,
            random_seed=None  # Random para cada execução
        )
        
        # Run simulation in a thread to avoid blocking the event loop
        import asyncio
        
        def run_simulation_sync():
            return simulator.run_simulation(
                strategy_name=request.strategy_name,
                historical_data=df,
                strategy_func=strategy_func,
                param_ranges=param_ranges,
                parallel=request.parallel,
                progress_callback=progress_callback
            )
        
        report = await asyncio.to_thread(run_simulation_sync)
        
        # Update progress - completing
        simulation_progress[request.strategy_name] = {
            "status": "saving",
            "progress": 98,
            "current_iteration": request.iterations,
            "total_iterations": request.iterations,
            "start_time": simulation_progress[request.strategy_name]["start_time"],
            "message": "Salvando relatório..."
        }
        
        # 5. Salvar relatório
        os.makedirs("/app/logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"/app/logs/monte_carlo_{request.strategy_name}_{timestamp}.json"
        simulator.save_report(report, report_path)
        
        # Update progress - completed
        simulation_progress[request.strategy_name] = {
            "status": "completed",
            "progress": 100,
            "current_iteration": request.iterations,
            "total_iterations": request.iterations,
            "start_time": simulation_progress[request.strategy_name]["start_time"],
            "elapsed_time": time_module.time() - simulation_progress[request.strategy_name]["start_time"],
            "message": "Simulação concluída!"
        }
        
        logger.info(f"✅ Simulação concluída: {report.successful_runs}/{request.iterations} runs")
        logger.info(f"📊 Mean Return: {report.mean_return:.2f}%")
        logger.info(f"🎯 Probability of Profit: {report.probability_of_profit:.1f}%")
        
        # 6. Retornar resumo
        return {
            "status": "completed",
            "report": report.to_dict(),
            "report_file": report_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro na simulação Monte Carlo: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monte-carlo/reports")
async def list_monte_carlo_reports():
    """Lista relatórios de Monte Carlo salvos"""
    import glob
    import json
    
    try:
        report_files = glob.glob("/app/logs/monte_carlo_*.json")
        reports = []
        
        for filepath in sorted(report_files, reverse=True)[:20]:  # Últimos 20
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    
                    # Extract metrics with fallbacks
                    return_stats = data.get('return_statistics', {})
                    risk_metrics = data.get('risk_metrics', {})
                    sharpe_stats = data.get('sharpe_statistics', {})
                    
                    reports.append({
                        'filename': filepath.split('/')[-1],
                        'strategy': data.get('strategy_name', 'unknown'),
                        'iterations': data.get('total_iterations', 0),
                        'mean_return': return_stats.get('mean', 0),
                        'probability_of_profit': risk_metrics.get('probability_of_profit', 0),
                        'mean_sharpe': sharpe_stats.get('mean', 0),
                        'sharpe': sharpe_stats.get('mean', 0),  # Alias for compatibility
                        'value_at_risk': risk_metrics.get('value_at_risk_95', 0),
                        'execution_time': data.get('execution_time', 0),
                        'timestamp': filepath.split('_')[-1].replace('.json', '')
                    })
            except Exception as e:
                logger.warning(f"Erro ao ler {filepath}: {e}")
        
        return {
            "total_reports": len(reports),
            "reports": reports
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar relatórios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monte-carlo/report/{filename}")
async def get_monte_carlo_report(filename: str):
    """Retorna relatório completo de Monte Carlo"""
    import json
    
    try:
        filepath = f"/app/logs/{filename}"
        
        with open(filepath, 'r') as f:
            raw_report = json.load(f)
        
        # Map to frontend-expected format
        return_stats = raw_report.get('return_statistics', {})
        risk_metrics = raw_report.get('risk_metrics', {})
        sharpe_stats = raw_report.get('sharpe_statistics', {})
        drawdown_stats = raw_report.get('drawdown_statistics', {})
        trade_stats = raw_report.get('trade_statistics', {})
        
        mapped_report = {
            'strategy': raw_report.get('strategy_name', 'unknown'),
            'iterations': raw_report.get('total_iterations', 0),
            'successful_runs': raw_report.get('successful_runs', 0),
            'failed_runs': raw_report.get('failed_runs', 0),
            'execution_time': raw_report.get('execution_time', 0),
            
            # Return metrics
            'mean_return': return_stats.get('mean', 0),
            'median_return': return_stats.get('median', 0),
            'std_return': return_stats.get('std', 0),
            'percentile_5': return_stats.get('percentile_5', 0),
            'percentile_95': return_stats.get('percentile_95', 0),
            
            # Risk metrics
            'probability_of_profit': risk_metrics.get('probability_of_profit', 0),
            'probability_of_loss': risk_metrics.get('probability_of_loss', 0),
            'value_at_risk_95': risk_metrics.get('value_at_risk_95', 0),
            'value_at_risk': risk_metrics.get('value_at_risk_95', 0),  # Alias
            'conditional_var_95': risk_metrics.get('conditional_var_95', 0),
            
            # Sharpe metrics
            'mean_sharpe_ratio': sharpe_stats.get('mean', 0),
            'mean_sharpe': sharpe_stats.get('mean', 0),  # Alias
            'median_sharpe': sharpe_stats.get('median', 0),
            
            # Drawdown metrics
            'mean_drawdown': drawdown_stats.get('mean', 0),
            'worst_drawdown': drawdown_stats.get('worst', 0),
            'drawdown_percentile_95': drawdown_stats.get('percentile_95', 0),
            
            # Trade metrics
            'mean_trades': trade_stats.get('mean_trades', 0),
            'mean_win_rate': trade_stats.get('mean_win_rate', 0),
            
            # Scenarios
            'scenarios': raw_report.get('scenarios', {}),
            
            # Raw results for charts
            'all_results': raw_report.get('all_results', [])
        }
        
        return {'report': mapped_report}
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    except Exception as e:
        logger.error(f"Erro ao ler relatório: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LIVE TRADING TEST MODE (PASSO 31)
# ==========================================

from live_trading_test import (
    BinanceTestnetClient, 
    TradingMode, 
    OrderSide as LiveOrderSide,
    OrderType as LiveOrderType,
    get_live_trading_client,
    initialize_live_trading
)

# Estado global do cliente de live trading
live_trading_client: Optional[BinanceTestnetClient] = None


class LiveTradingInitRequest(BaseModel):
    """Requisição para inicializar live trading test"""
    mode: str = "dry_run"  # dry_run, testnet, paper
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


class LiveTestOrderRequest(BaseModel):
    """Requisição para testar uma ordem"""
    symbol: str = "BTCUSDT"
    side: str = "BUY"  # BUY ou SELL
    order_type: str = "MARKET"  # MARKET, LIMIT, etc
    quantity: float = 0.001
    price: Optional[float] = None
    stop_price: Optional[float] = None


class KillSwitchRequest(BaseModel):
    """Requisição para controlar kill switch"""
    action: str = "status"  # activate, deactivate, status
    reason: Optional[str] = None


@app.post("/api/live-trading/init")
async def initialize_live_trading_endpoint(request: LiveTradingInitRequest):
    """
    Inicializa cliente de Live Trading em modo de teste
    
    Modos disponíveis:
    - dry_run: Simulação local sem conexão (default)
    - testnet: Conecta ao Binance Testnet (requer API keys)
    - paper: Paper trading com dados reais da Binance
    """
    global live_trading_client
    
    try:
        # Mapear modo
        mode_map = {
            'dry_run': TradingMode.DRY_RUN,
            'testnet': TradingMode.TESTNET,
            'paper': TradingMode.PAPER
        }
        mode = mode_map.get(request.mode, TradingMode.DRY_RUN)
        
        # Inicializar cliente
        live_trading_client = BinanceTestnetClient(
            api_key=request.api_key,
            api_secret=request.api_secret,
            mode=mode
        )
        
        # Conectar
        connected = await live_trading_client.connect()
        
        return {
            'success': connected,
            'mode': mode.value,
            'status': live_trading_client.get_status(),
            'message': f"Live trading inicializado em modo {mode.value}" if connected else "Falha na conexão"
        }
        
    except Exception as e:
        logger.error(f"Erro ao inicializar live trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/live-trading/status")
async def get_live_trading_status():
    """Retorna status do cliente de live trading"""
    global live_trading_client
    
    if live_trading_client is None:
        return {
            'initialized': False,
            'message': 'Live trading não inicializado. Use POST /api/live-trading/init primeiro.'
        }
    
    return {
        'initialized': True,
        **live_trading_client.get_status()
    }


@app.post("/api/live-trading/test-order")
async def test_live_order(request: LiveTestOrderRequest):
    """
    Testa uma ordem sem executar de verdade
    
    Valida:
    - Conectividade
    - Parâmetros da ordem
    - Limites de risco
    - Executa no modo configurado (dry_run/testnet/paper)
    """
    global live_trading_client
    
    if live_trading_client is None:
        # Auto-inicializar em modo dry_run
        live_trading_client = BinanceTestnetClient(mode=TradingMode.DRY_RUN)
        await live_trading_client.connect()
    
    try:
        # Mapear side e type
        side = LiveOrderSide.BUY if request.side.upper() == "BUY" else LiveOrderSide.SELL
        order_type = LiveOrderType[request.order_type.upper()]
        
        # Executar teste
        result = await live_trading_client.test_order(
            symbol=request.symbol,
            side=side,
            order_type=order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price
        )
        
        return {
            'success': result.success,
            'order': result.to_dict(),
            'client_status': live_trading_client.get_status()
        }
        
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Tipo de ordem inválido: {request.order_type}")
    except Exception as e:
        logger.error(f"Erro ao testar ordem: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/live-trading/kill-switch")
async def control_kill_switch(request: KillSwitchRequest):
    """
    Controla o kill switch de emergência
    
    Ações:
    - activate: Ativa kill switch (bloqueia todas as ordens)
    - deactivate: Desativa kill switch
    - status: Retorna status atual
    """
    global live_trading_client
    
    if live_trading_client is None:
        raise HTTPException(status_code=400, detail="Live trading não inicializado")
    
    if request.action == "activate":
        reason = request.reason or "Manual activation via API"
        live_trading_client.activate_kill_switch(reason)
        return {
            'action': 'activated',
            'reason': reason,
            'status': live_trading_client.get_status()
        }
    
    elif request.action == "deactivate":
        live_trading_client.deactivate_kill_switch()
        return {
            'action': 'deactivated',
            'status': live_trading_client.get_status()
        }
    
    else:  # status
        return {
            'action': 'status',
            'kill_switch': {
                'active': live_trading_client.kill_switch_active,
                'reason': live_trading_client.kill_switch_reason
            }
        }


@app.get("/api/live-trading/audit-log")
async def get_audit_log(limit: int = 100):
    """Retorna log de auditoria das últimas operações"""
    global live_trading_client
    
    if live_trading_client is None:
        return {'entries': [], 'message': 'Live trading não inicializado'}
    
    return {
        'entries': live_trading_client.get_audit_log(limit),
        'total_entries': len(live_trading_client.audit_log)
    }


@app.get("/api/live-trading/connectivity-test")
async def run_connectivity_test():
    """
    Executa teste completo de conectividade com Binance
    
    Testa:
    - Ping/latência
    - Sincronização de tempo
    - Ticker prices
    - Exchange info
    - Credenciais (se configuradas)
    """
    global live_trading_client
    
    if live_trading_client is None:
        # Auto-inicializar para teste
        live_trading_client = BinanceTestnetClient(mode=TradingMode.DRY_RUN)
        await live_trading_client.connect()
    
    results = await live_trading_client.run_connectivity_test()
    return results


@app.post("/api/live-trading/disconnect")
async def disconnect_live_trading():
    """Desconecta cliente de live trading"""
    global live_trading_client
    
    if live_trading_client is None:
        return {'success': True, 'message': 'Já desconectado'}
    
    await live_trading_client.disconnect()
    live_trading_client = None
    
    return {'success': True, 'message': 'Desconectado com sucesso'}


# ==========================================
# MULTI-SYMBOL RSI DIVERGENCE SCANNER (PASSO 32)
# ==========================================

from multi_symbol_scanner import (
    MultiSymbolScanner,
    ScannerConfig,
    DivergenceSignal,
    SignalType,
    quick_scan
)

# Estado global do scanner
rsi_scanner: Optional[MultiSymbolScanner] = None


class ScannerConfigRequest(BaseModel):
    """Configuração do scanner de múltiplos símbolos (v2.1 - alinhado com Backtest Visual)"""
    symbols: Optional[List[str]] = None  # Ex: ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    timeframes: Optional[List[str]] = None  # Ex: ["1h", "4h"]
    rsi_period: int = 14
    min_signal_strength: float = 0.35  # Atualizado: 0.3 → 0.35 (validado no Backtest Visual)
    lookback_periods: int = 15  # Atualizado: 10 → 15 (alinhado com Backtest Visual)
    stop_loss_atr_mult: float = 2.0
    take_profit_atr_mult: float = 3.5  # Atualizado: 4.0 → 3.5 (validado no Backtest Visual)
    use_ema_filter: bool = True  # NOVO v2.1: Filtro EMA 50/200 para alinhamento com tendência


class ScanRequest(BaseModel):
    """Requisição de scan imediato"""
    symbols: Optional[List[str]] = None
    timeframes: Optional[List[str]] = None


@app.post("/api/scanner/init")
async def init_rsi_scanner(request: ScannerConfigRequest):
    """
    Inicializa o scanner de múltiplos símbolos para RSI Divergence v2.1
    
    Parâmetros alinhados com Backtest Visual (validado com +42.47% em SOLUSDT):
    - min_signal_strength: 0.35 (mais qualidade)
    - lookback_periods: 15 (mais contexto)
    - take_profit_atr_mult: 3.5 (mais realista)
    - use_ema_filter: true (filtro EMA 50/200)
    
    Exemplo:
    ```json
    {
      "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"],
      "timeframes": ["1h", "4h"],
      "min_signal_strength": 0.35,
      "use_ema_filter": true
    }
    ```
    """
    global rsi_scanner
    
    try:
        config = ScannerConfig()
        
        if request.symbols:
            config.symbols = request.symbols
        if request.timeframes:
            config.timeframes = request.timeframes
        
        config.rsi_period = request.rsi_period
        config.min_signal_strength = request.min_signal_strength
        config.lookback_periods = request.lookback_periods
        config.stop_loss_atr_mult = request.stop_loss_atr_mult
        config.take_profit_atr_mult = request.take_profit_atr_mult
        config.use_ema_filter = request.use_ema_filter  # NOVO v2.1
        
        # Pass database pool for signal persistence
        pool = await get_market_data_pool()
        rsi_scanner = MultiSymbolScanner(config, db_pool=pool)
        
        return {
            'success': True,
            'message': f'Scanner v2.1 inicializado com {len(config.symbols)} símbolos',
            'config': {
                'symbols': config.symbols,
                'timeframes': config.timeframes,
                'rsi_period': config.rsi_period,
                'min_signal_strength': config.min_signal_strength,
                'lookback_periods': config.lookback_periods,
                'stop_loss_atr_mult': config.stop_loss_atr_mult,
                'take_profit_atr_mult': config.take_profit_atr_mult,
                'use_ema_filter': config.use_ema_filter  # NOVO v2.1
            }
        }
        
    except Exception as e:
        logger.error(f"Erro ao inicializar scanner: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scanner/scan")
async def run_scan(request: ScanRequest = None):
    """
    VERSÃO OTIMIZADA: Retorna status do cache sem fazer scan completo
    
    O scan completo de 80 símbolos leva >60s. Esta versão retorna
    apenas o status atual do cache de forma instantânea.
    
    Para scan completo, use /api/scanner/scan-full (background task).
    """
    global rsi_scanner
    
    try:
        # Retornar status rápido do cache ao invés de fazer scan completo
        if rsi_scanner is None:
            return {
                'success': True,
                'scan_count': 0,
                'last_scan_time': None,
                'symbols_scanned': 0,
                'timeframes': [],
                'signals_found': 0,
                'signals': [],
                'note': 'Scanner não inicializado. Use /api/scanner/init primeiro.'
            }
        
        # Retornar último resultado do cache (instantâneo)
        return {
            'success': True,
            'scan_count': rsi_scanner.scan_count if hasattr(rsi_scanner, 'scan_count') else 0,
            'last_scan_time': rsi_scanner.last_scan_time if hasattr(rsi_scanner, 'last_scan_time') else None,
            'symbols_scanned': len(rsi_scanner.config.symbols) if rsi_scanner.config else 0,
            'timeframes': rsi_scanner.config.timeframes if rsi_scanner.config else [],
            'signals_found': len(rsi_scanner.active_signals) if hasattr(rsi_scanner, 'active_signals') else 0,
            'signals': rsi_scanner.active_signals[:10] if hasattr(rsi_scanner, 'active_signals') else [],
            'note': 'Dados do cache (último scan). Para scan completo use /api/scanner/scan-full'
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar status do scan: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scanner/scan-full")
async def run_full_scan(request: ScanRequest = None, background_tasks: BackgroundTasks = None):
    """
    Executa um scan completo em todos os símbolos (LENTO - >60s)
    
    Esta versão faz scan de 80 símbolos na Binance e pode demorar >60s.
    Use /api/scanner/scan para obter status instantâneo do cache.
    """
    global rsi_scanner
    
    try:
        # Usar scanner existente ou criar temporário
        if rsi_scanner is None:
            config = ScannerConfig()
            if request and request.symbols:
                config.symbols = request.symbols
            if request and request.timeframes:
                config.timeframes = request.timeframes
            # Pass database pool for signal persistence
            pool = await get_market_data_pool()
            rsi_scanner = MultiSymbolScanner(config, db_pool=pool)
        
        # Executar scan completo
        result = await rsi_scanner.scan_once()
        
        return {
            'success': True,
            'scan_count': result['scan_count'],
            'last_scan_time': result['last_scan_time'],
            'symbols_scanned': result['symbols_monitored'],
            'timeframes': result['timeframes'],
            'signals_found': result['active_signals'],
            'signals': result['signals']
        }
        
    except Exception as e:
        logger.error(f"Erro no scan: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scanner/quick-scan")
async def quick_scan_endpoint(
    symbols: str = "BTC/USDT,ETH/USDT,SOL/USDT",
    timeframes: str = "1h"
):
    """
    Scan rápido para símbolos específicos
    
    Parâmetros via query string:
    - symbols: Lista separada por vírgula (ex: BTC/USDT,ETH/USDT)
    - timeframes: Lista separada por vírgula (ex: 1h,4h)
    
    Exemplo:
    GET /api/scanner/quick-scan?symbols=BTC/USDT,ETH/USDT&timeframes=1h,4h
    """
    try:
        symbol_list = [s.strip() for s in symbols.split(',')]
        tf_list = [t.strip() for t in timeframes.split(',')]
        
        result = await quick_scan(symbol_list, tf_list)
        
        return {
            'success': True,
            'symbols': symbol_list,
            'timeframes': tf_list,
            'signals_found': result['active_signals'],
            'signals': result['signals']
        }
        
    except Exception as e:
        logger.error(f"Erro no quick scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scanner/status")
async def get_scanner_status():
    """
    Retorna status atual do scanner
    """
    global rsi_scanner
    
    if rsi_scanner is None:
        return {
            'initialized': False,
            'message': 'Scanner não inicializado. Use POST /api/scanner/init'
        }
    
    return {
        'initialized': True,
        'is_running': rsi_scanner.is_running,
        'scan_count': rsi_scanner.scan_count,
        'last_scan_time': rsi_scanner.last_scan_time.isoformat() if rsi_scanner.last_scan_time else None,
        'symbols': rsi_scanner.config.symbols,
        'timeframes': rsi_scanner.config.timeframes,
        'active_signals': len(rsi_scanner.active_signals)
    }


@app.get("/api/scanner/signals")
async def get_active_signals():
    """
    Retorna sinais ativos do último scan
    """
    global rsi_scanner
    
    if rsi_scanner is None:
        return {'signals': [], 'message': 'Scanner não inicializado'}
    
    return {
        'signals': [
            {
                "symbol": s.symbol,
                "type": s.signal_type.value,
                "direction": "BUY" if s.direction == 1 else "SELL",
                "strength": round(s.strength, 3),
                "strength_level": s.strength_level.value,
                "price": s.current_price,
                "rsi": round(s.rsi_value, 1),
                "timeframe": s.timeframe,
                "entry": s.entry_price,
                "stop_loss": round(s.stop_loss, 2),
                "take_profit": round(s.take_profit, 2),
                "risk_reward": round(s.risk_reward, 2),
                "confirmations": {
                    "volume": s.volume_confirmed,
                    "macd": s.macd_confirmed,
                    "trend": s.trend_aligned
                },
                "timestamp": s.timestamp.isoformat()
            }
            for s in rsi_scanner.active_signals
        ],
        'total': len(rsi_scanner.active_signals),
        'last_scan': rsi_scanner.last_scan_time.isoformat() if rsi_scanner.last_scan_time else None
    }


@app.post("/api/scanner/start-continuous")
async def start_continuous_scanning(background_tasks: BackgroundTasks, interval_seconds: int = 60):
    """
    Inicia scanning contínuo em background
    
    O scanner irá verificar todos os símbolos configurados a cada X segundos.
    """
    global rsi_scanner
    
    if rsi_scanner is None:
        # Pass database pool for signal persistence
        pool = await get_market_data_pool()
        rsi_scanner = MultiSymbolScanner(ScannerConfig(), db_pool=pool)
    
    if rsi_scanner.is_running:
        return {'success': False, 'message': 'Scanner já está rodando'}
    
    rsi_scanner.config.scan_interval = interval_seconds
    
    # Iniciar em background
    background_tasks.add_task(rsi_scanner.start)
    
    return {
        'success': True,
        'message': f'Scanner iniciado com intervalo de {interval_seconds}s',
        'symbols': rsi_scanner.config.symbols,
        'timeframes': rsi_scanner.config.timeframes
    }


@app.post("/api/scanner/stop")
async def stop_continuous_scanning():
    """
    Para o scanning contínuo
    """
    global rsi_scanner
    
    if rsi_scanner is None or not rsi_scanner.is_running:
        return {'success': True, 'message': 'Scanner não está rodando'}
    
    rsi_scanner.stop()
    
    return {
        'success': True,
        'message': 'Scanner parado',
        'total_scans': rsi_scanner.scan_count
    }


@app.get("/api/scanner/history")
async def get_scanner_history(limit: int = 50, hours: int = 24):
    """
    Retorna histórico de sinais do banco de dados
    
    Query params:
    - limit: Número máximo de sinais (default: 50)
    - hours: Janela de tempo em horas (default: 24)
    
    Retorna sinais persistidos no banco, mesmo após restart do container.
    """
    global rsi_scanner
    
    try:
        # Se scanner existir e tiver db_pool, usar ele
        if rsi_scanner and rsi_scanner.db_pool:
            signals = await rsi_scanner.get_recent_signals_from_db(limit, hours)
        else:
            # Criar conexão temporária
            pool = await get_market_data_pool()
            async with pool.acquire() as conn:
                query = """
                SELECT 
                    signal_id, timestamp, symbol, timeframe, signal_type, direction,
                    strength, entry_price, stop_loss, take_profit, current_price,
                    rsi, adx, reason, executed, execution_reason
                FROM autotrade_signals
                WHERE timestamp >= NOW() - INTERVAL '%s hours'
                  AND signal_type LIKE '%%divergence%%'
                ORDER BY timestamp DESC
                LIMIT $1
                """
                
                rows = await conn.fetch(query % hours, limit)
                
                signals = []
                for row in rows:
                    signals.append({
                        'signal_id': row['signal_id'],
                        'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None,
                        'symbol': row['symbol'],
                        'timeframe': row['timeframe'],
                        'type': row['signal_type'],
                        'direction': row['direction'],
                        'strength': float(row['strength']) if row['strength'] else 0.0,
                        'entry': float(row['entry_price']) if row['entry_price'] else 0.0,
                        'stop_loss': float(row['stop_loss']) if row['stop_loss'] else 0.0,
                        'take_profit': float(row['take_profit']) if row['take_profit'] else 0.0,
                        'price': float(row['current_price']) if row['current_price'] else 0.0,
                        'rsi': float(row['rsi']) if row['rsi'] else 0.0,
                        'adx': float(row['adx']) if row['adx'] else 0.0,
                        'reason': row['reason'],
                        'executed': row['executed'],
                        'execution_reason': row['execution_reason']
                    })
        
        return {
            'success': True,
            'total': len(signals),
            'signals': signals,
            'period_hours': hours
        }
        
    except Exception as e:
        logger.error(f"Error fetching signal history: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scanner/market-data")
async def get_scanner_market_data(symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"):
    """
    Retorna dados de mercado do cache do banco de dados.
    
    ARQUITETURA v3 (Database-backed):
    - Background worker atualiza dados da Binance a cada 60s
    - Este endpoint apenas lê do banco (< 10ms)
    - Elimina problemas de timeout/AbortError no frontend
    - Suporta múltiplos clientes simultâneos sem sobrecarga
    
    Parâmetros:
    - symbols: Lista de símbolos separados por vírgula
    """
    try:
        pool = await get_market_data_pool()
        symbol_list = [s.strip().replace('USDT', '/USDT') for s in symbols.split(',')]
        
        async with pool.acquire() as conn:
            # Buscar dados do cache
            rows = await conn.fetch("""
                SELECT symbol, price, change_24h, rsi, proximity, trend, updated_at
                FROM market_data_cache
                WHERE symbol = ANY($1)
                ORDER BY proximity DESC
            """, symbol_list)
            
            if not rows:
                # Se não houver dados no cache, retornar vazio (worker ainda não rodou)
                return {
                    'success': True,
                    'timestamp': datetime.utcnow().isoformat(),
                    'data': [],
                    'count': 0,
                    'requested': len(symbol_list),
                    'success_rate': 0,
                    'source': 'database',
                    'message': 'Cache ainda não populado. Aguarde ~60s para primeira atualização.'
                }
            
            # Converter para formato esperado pelo frontend
            market_data = []
            for row in rows:
                market_data.append({
                    'symbol': row['symbol'],
                    'price': float(row['price']) if row['price'] else 0,
                    'change_24h': float(row['change_24h']) if row['change_24h'] else 0,
                    'rsi': float(row['rsi']) if row['rsi'] else 50,
                    'proximity': int(row['proximity']) if row['proximity'] else 0,
                    'trend': row['trend'] or 'neutral'
                })
            
            # Calcular idade do cache mais antigo
            oldest_update = min(row['updated_at'] for row in rows) if rows else datetime.utcnow()
            cache_age_seconds = (datetime.utcnow().replace(tzinfo=oldest_update.tzinfo) - oldest_update).total_seconds() if oldest_update.tzinfo else (datetime.utcnow() - oldest_update).total_seconds()
            
            success_rate = len(market_data) / len(symbol_list) * 100 if symbol_list else 0
            
            logger.info(f"[MarketData] Retornando {len(market_data)}/{len(symbol_list)} símbolos do banco (cache age: {cache_age_seconds:.0f}s)")
            
            return {
                'success': True,
                'timestamp': datetime.utcnow().isoformat(),
                'data': market_data,
                'count': len(market_data),
                'requested': len(symbol_list),
                'success_rate': round(success_rate, 1),
                'source': 'database',
                'cache_age_seconds': round(cache_age_seconds, 0)
            }
            
    except Exception as e:
        logger.error(f"[MarketData] Erro ao ler do banco: {e}")
        return {
            'success': False,
            'error': str(e),
            'data': [],
            'source': 'database'
        }


@app.post("/api/scanner/market-data/refresh")
async def refresh_market_data_cache():
    """
    Força atualização imediata do cache de market data.
    Útil quando o usuário quer dados frescos sem esperar o ciclo de 60s.
    """
    try:
        count = await update_market_data_cache()
        return {
            'success': True,
            'message': f'Cache atualizado com {count} símbolos',
            'updated_count': count
        }
    except Exception as e:
        logger.error(f"[MarketData] Erro ao atualizar cache: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/api/scanner/market-data/status")
async def get_market_data_cache_status():
    """
    Retorna status do sistema de cache de market data.
    """
    try:
        pool = await get_market_data_pool()
        
        async with pool.acquire() as conn:
            # Contar símbolos no cache
            count = await conn.fetchval("SELECT COUNT(*) FROM market_data_cache")
            
            # Data da última atualização
            last_update = await conn.fetchval("SELECT MAX(updated_at) FROM market_data_cache")
            
            # Símbolos disponíveis
            symbols = await conn.fetch("SELECT symbol FROM market_data_cache ORDER BY symbol")
            
        return {
            'success': True,
            'worker_running': _market_data_worker_running,
            'symbols_cached': count,
            'last_update': last_update.isoformat() if last_update else None,
            'available_symbols': [row['symbol'] for row in symbols],
            'update_interval_seconds': 60
        }
        
    except Exception as e:
        logger.error(f"[MarketData] Erro ao obter status: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ==========================================
# MULTI-SYMBOL PAPER TRADING
# ==========================================

class MultiSymbolPaperTradingRequest(BaseModel):
    """Requisição para iniciar paper trading em múltiplos símbolos"""
    session_prefix: str = "rsi-div"
    symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    strategy_name: str = "rsi_divergence"
    timeframe: str = "1h"
    initial_balance_per_symbol: float = 10000.0
    auto_trade_signals: bool = False  # Se True, executa ordens automaticamente
    min_signal_strength: float = 0.5


@app.post("/api/paper-trading/multi-symbol/start")
async def start_multi_symbol_paper_trading(request: MultiSymbolPaperTradingRequest):
    """
    Inicia sessões de Paper Trading para múltiplos símbolos simultaneamente
    
    Cada símbolo terá sua própria sessão de paper trading, permitindo
    testar a estratégia RSI Divergence em várias criptos ao mesmo tempo.
    
    Exemplo:
    ```json
    {
      "session_prefix": "rsi-test",
      "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
      "strategy_name": "rsi_divergence",
      "timeframe": "1h",
      "initial_balance_per_symbol": 10000.0,
      "auto_trade_signals": false,
      "min_signal_strength": 0.5
    }
    ```
    """
    global executors, order_managers
    
    sessions_created = []
    errors = []
    
    for symbol in request.symbols:
        session_id = f"{request.session_prefix}-{symbol.lower()}"
        
        try:
            # Criar order manager
            order_manager = OrderManager(
                initial_balance=request.initial_balance_per_symbol,
                commission_rate=0.001,
                slippage_rate=0.0005
            )
            
            # Criar executor
            executor = StrategyExecutor(
                order_manager=order_manager,
                strategy_name=request.strategy_name,
                strategy_parameters={
                    "min_signal_strength": request.min_signal_strength,
                    "lookback_periods": 10,
                    "stop_loss_atr_mult": 2.0,
                    "take_profit_atr_mult": 4.0
                },
                symbol=symbol,
                timeframe=request.timeframe
            )
            
            # Iniciar executor
            await executor.start()
            
            # Armazenar
            executors[session_id] = executor
            order_managers[session_id] = order_manager
            
            sessions_created.append({
                "session_id": session_id,
                "symbol": symbol,
                "balance": request.initial_balance_per_symbol,
                "status": "running"
            })
            
        except Exception as e:
            errors.append({
                "symbol": symbol,
                "error": str(e)
            })
    
    return {
        "success": len(errors) == 0,
        "sessions_created": len(sessions_created),
        "sessions": sessions_created,
        "errors": errors,
        "config": {
            "strategy": request.strategy_name,
            "timeframe": request.timeframe,
            "auto_trade": request.auto_trade_signals,
            "min_strength": request.min_signal_strength
        }
    }


@app.get("/api/paper-trading/multi-symbol/status")
async def get_multi_symbol_status(prefix: str = ""):
    """
    Retorna status de todas as sessões de paper trading multi-symbol
    
    Parâmetros:
    - prefix: Filtrar por prefixo do session_id (ex: "rsi-test")
    """
    global executors, order_managers
    
    sessions = []
    
    for session_id, executor in executors.items():
        if prefix and not session_id.startswith(prefix):
            continue
        
        order_manager = order_managers.get(session_id)
        
        session_info = {
            "session_id": session_id,
            "symbol": executor.symbol if hasattr(executor, 'symbol') else "N/A",
            "is_running": executor.is_running if hasattr(executor, 'is_running') else False,
            "strategy": executor.strategy_name if hasattr(executor, 'strategy_name') else "N/A"
        }
        
        if order_manager:
            account = order_manager.get_account_summary()
            session_info.update({
                "balance": account.get("balance", 0),
                "equity": account.get("equity", 0),
                "total_pnl": account.get("total_pnl", 0),
                "total_pnl_percent": account.get("total_pnl_percent", 0),
                "open_positions": account.get("open_positions", 0),
                "total_trades": account.get("total_trades", 0)
            })
        
        sessions.append(session_info)
    
    # Calcular totais
    total_balance = sum(s.get("balance", 0) for s in sessions)
    total_equity = sum(s.get("equity", 0) for s in sessions)
    total_pnl = sum(s.get("total_pnl", 0) for s in sessions)
    total_trades = sum(s.get("total_trades", 0) for s in sessions)
    
    return {
        "sessions": sessions,
        "total_sessions": len(sessions),
        "summary": {
            "total_balance": round(total_balance, 2),
            "total_equity": round(total_equity, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percent": round((total_pnl / total_balance * 100) if total_balance > 0 else 0, 2),
            "total_trades": total_trades
        }
    }


@app.post("/api/paper-trading/multi-symbol/stop-all")
async def stop_all_multi_symbol_sessions(prefix: str = ""):
    """
    Para todas as sessões de paper trading multi-symbol
    """
    global executors, order_managers
    
    stopped = []
    
    session_ids = list(executors.keys())
    
    for session_id in session_ids:
        if prefix and not session_id.startswith(prefix):
            continue
        
        try:
            executor = executors.get(session_id)
            if executor and hasattr(executor, 'stop'):
                await executor.stop()
            
            del executors[session_id]
            if session_id in order_managers:
                del order_managers[session_id]
            
            stopped.append(session_id)
            
        except Exception as e:
            logger.error(f"Erro ao parar {session_id}: {e}")
    
    return {
        "success": True,
        "stopped_sessions": len(stopped),
        "sessions": stopped
    }


# ==========================================
# AUTO-TRADE: Scanner → Paper Trading Connection
# ==========================================

# Estado global do AutoTrade
autotrade_state = {
    "active": False,
    "dry_run": True,  # Por padrão, não executa trades reais
    "session_id": None,
    "min_signal_strength": 0.5,
    "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "signals_processed": 0,
    "trades_executed": 0,
    "last_signal": None,
    "signals_log": []
}


class AutoTradeConfigRequest(BaseModel):
    """Configuração do AutoTrade"""
    min_signal_strength: float = 0.5
    symbols: Optional[List[str]] = None  # Se None, usa símbolos do Scanner
    dry_run: bool = True
    initial_balance: float = 10000.0
    risk_per_trade: float = 0.02  # 2% do capital por trade


class AutoTradeSignal(BaseModel):
    """Sinal recebido do Scanner para execução"""
    symbol: str
    direction: int  # 1 = BUY, -1 = SELL
    signal_type: str
    strength: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timeframe: str = "1h"


@app.post("/api/autotrade/start")
async def start_autotrade(config: AutoTradeConfigRequest):
    """
    🤖 Inicia o modo AutoTrade - conecta Scanner ao Paper Trading
    
    - Quando Scanner detecta sinal forte → envia para Paper Trading
    - dry_run=True por padrão (simula trades, não executa)
    - Registra todos os sinais e trades NO BANCO DE DADOS
    - Se symbols não for especificado, usa os símbolos do Scanner ativo
    """
    global autotrade_state, rsi_scanner
    
    # Garantir que AutoTradeManager está inicializado
    manager = await get_autotrade_manager()
    
    if autotrade_state["active"]:
        return {
            "success": False,
            "message": "AutoTrade já está ativo",
            "state": autotrade_state
        }
    
    # Determinar símbolos: usa os passados na requisição ou os do Scanner
    symbols_to_use = config.symbols
    if not symbols_to_use or len(symbols_to_use) == 0:
        # Tentar usar símbolos do Scanner ativo
        if rsi_scanner and hasattr(rsi_scanner, 'config') and rsi_scanner.config.symbols:
            symbols_to_use = [s.replace('/', '') for s in rsi_scanner.config.symbols]
            logger.info(f"🤖 AutoTrade usando {len(symbols_to_use)} símbolos do Scanner ativo")
        else:
            # Fallback para símbolos padrão
            symbols_to_use = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
            logger.warning("🤖 AutoTrade usando símbolos padrão (Scanner não inicializado)")
    
    # Gerar session_id único
    session_id = f"autotrade_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Criar sessão no banco de dados
    if manager:
        mode = 'DRY_RUN' if config.dry_run else 'LIVE'
        success = await manager.create_session(
            session_id=session_id,
            mode=mode,
            initial_capital=config.initial_balance,
            min_strength=config.min_signal_strength,
            symbols=symbols_to_use,
            timeframe='1h'
        )
        
        if not success:
            logger.warning(f"⚠️ Não foi possível criar sessão no banco (pode já existir)")
    else:
        logger.warning("⚠️ AutoTradeManager não disponível - dados não serão salvos no banco")
    
    autotrade_state.update({
        "active": True,
        "dry_run": config.dry_run,
        "session_id": session_id,
        "min_signal_strength": config.min_signal_strength,
        "symbols": symbols_to_use,
        "initial_balance": config.initial_balance,
        "risk_per_trade": config.risk_per_trade,
        "signals_processed": 0,
        "trades_executed": 0,
        "last_signal": None,
        "signals_log": [],
        "started_at": datetime.now().isoformat()
    })
    
    mode = "🔴 DRY RUN (simulação)" if config.dry_run else "🟢 LIVE (execução real)"
    logger.info(f"🤖 AutoTrade STARTED - Session: {session_id} - Mode: {mode} - Símbolos: {len(symbols_to_use)}")
    logger.info(f"💾 Todos os sinais e trades serão salvos no banco de dados!")
    
    return {
        "success": True,
        "message": f"AutoTrade iniciado em modo {'DRY RUN' if config.dry_run else 'LIVE'} com {len(symbols_to_use)} símbolos",
        "session_id": session_id,
        "symbols_count": len(symbols_to_use),
        "database_enabled": manager is not None,
        "state": autotrade_state
    }


@app.post("/api/autotrade/stop")
async def stop_autotrade():
    """
    ⏹️ Para o modo AutoTrade e finaliza a sessão no banco
    """
    global autotrade_state, autotrade_manager
    
    if not autotrade_state["active"]:
        return {
            "success": False,
            "message": "AutoTrade não está ativo"
        }
    
    session_id = autotrade_state["session_id"]
    trades = autotrade_state["trades_executed"]
    signals = autotrade_state["signals_processed"]
    
    # Finalizar sessão no banco
    if autotrade_manager:
        await autotrade_manager.stop_session(session_id)
        
        # Obter estatísticas finais
        stats = await autotrade_manager.get_session_stats(session_id)
        logger.info(f"📊 Estatísticas finais da sessão salvas no banco")
    
    autotrade_state.update({
        "active": False,
        "stopped_at": datetime.now().isoformat()
    })
    
    logger.info(f"⏹️ AutoTrade STOPPED - Session: {session_id} - Trades: {trades} - Signals: {signals}")
    
    return {
        "success": True,
        "message": "AutoTrade parado e sessão finalizada",
        "session_summary": {
            "session_id": session_id,
            "signals_processed": signals,
            "trades_executed": trades,
            "database_stats": stats if autotrade_manager else None
        }
    }


@app.get("/api/autotrade/status")
async def get_autotrade_status():
    """
    📊 Retorna o status atual do AutoTrade
    
    Se AutoTrade está inativo, mostra os símbolos que seriam usados
    (do Scanner ativo, se disponível)
    """
    global rsi_scanner
    
    # Determinar símbolos a mostrar
    if autotrade_state["active"]:
        # Se ativo, usa os símbolos da sessão atual
        symbols_to_show = autotrade_state["symbols"]
    else:
        # Se inativo, mostra os símbolos que seriam usados ao iniciar
        if rsi_scanner and hasattr(rsi_scanner, 'config') and rsi_scanner.config.symbols:
            symbols_to_show = [s.replace('/', '') for s in rsi_scanner.config.symbols]
        else:
            symbols_to_show = autotrade_state["symbols"]
    
    return {
        "active": autotrade_state["active"],
        "dry_run": autotrade_state["dry_run"],
        "session_id": autotrade_state.get("session_id"),
        "min_signal_strength": autotrade_state["min_signal_strength"],
        "symbols": symbols_to_show,
        "symbols_source": "scanner" if (rsi_scanner and hasattr(rsi_scanner, 'config') and rsi_scanner.config.symbols) else "default",
        "stats": {
            "signals_processed": autotrade_state["signals_processed"],
            "trades_executed": autotrade_state["trades_executed"],
            "last_signal": autotrade_state.get("last_signal")
        },
        "recent_signals": autotrade_state.get("signals_log", [])[-5:]
    }


@app.post("/api/autotrade/process-signal")
async def process_autotrade_signal(signal: AutoTradeSignal):
    """
    🔔 Processa um sinal do Scanner para execução no AutoTrade
    
    Este endpoint é chamado pelo Scanner quando detecta uma divergência.
    Se AutoTrade estiver ativo e o sinal passar nos filtros, executa o trade.
    VERSÃO MELHORADA: Salva TUDO no banco de dados.
    """
    global autotrade_state
    
    # Garantir que AutoTradeManager está inicializado
    manager = await get_autotrade_manager()
    
    # Preparar dados do sinal
    signal_data = AutoTradeSignalData(
        symbol=signal.symbol,
        direction="BUY" if signal.direction == 1 else "SELL",
        signal_type=signal.signal_type,
        strength=signal.strength,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        current_price=signal.entry_price,
        timeframe=signal.timeframe
    )
    
    # Verificar se AutoTrade está ativo
    if not autotrade_state["active"]:
        signal_data.reason = "AutoTrade não está ativo"
        
        # Salvar sinal mesmo que não processado
        if manager:
            await manager.save_signal(
                session_id=autotrade_state.get("session_id", "unknown"),
                signal_data=signal_data,
                processed=False,
                executed=False
            )
        
        return {
            "success": False,
            "message": "AutoTrade não está ativo",
            "action": "none"
        }
    
    session_id = autotrade_state["session_id"]
    autotrade_state["signals_processed"] += 1
    
    # Verificar se símbolo está na lista
    if signal.symbol not in autotrade_state["symbols"]:
        signal_data.reason = f"Símbolo {signal.symbol} não está na lista de monitoramento"
        
        if manager:
            await manager.save_signal(
                session_id=session_id,
                signal_data=signal_data,
                processed=True,
                executed=False
            )
        
        return {
            "success": False,
            "message": f"Símbolo {signal.symbol} não está na lista",
            "action": "ignored"
        }
    
    # Verificar força mínima do sinal
    if signal.strength < autotrade_state["min_signal_strength"]:
        signal_data.reason = f"Força ({signal.strength:.2f}) abaixo do mínimo ({autotrade_state['min_signal_strength']})"
        
        if manager:
            await manager.save_signal(
                session_id=session_id,
                signal_data=signal_data,
                processed=True,
                executed=False
            )
        
        return {
            "success": False,
            "message": f"Força do sinal ({signal.strength:.2f}) abaixo do mínimo",
            "action": "ignored"
        }
    
    # Sinal passou nos filtros!
    signal_data.reason = "Sinal passou nos filtros"
    
    # Salvar sinal no banco ANTES de processar
    signal_id = None
    if manager:
        signal_id = await manager.save_signal(
            session_id=session_id,
            signal_data=signal_data,
            processed=True,
            executed=False  # Ainda não executado
        )
    
    # Executar trade (ou simular em dry_run)
    if autotrade_state["dry_run"]:
        # Modo simulação - registra mas não executa
        autotrade_state["trades_executed"] += 1
        
        # Atualizar status do sinal
        if manager and signal_id:
            await manager.update_signal_execution(
                signal_id=signal_id,
                executed=True,
                reason="✅ DRY RUN - Trade simulado"
            )
        
        logger.info(f"🔴 DRY RUN - Trade simulado: {signal.symbol} {signal_data.direction} @ {signal.entry_price}")
        
        return {
            "success": True,
            "message": "Trade simulado (dry_run)",
            "action": "simulated",
            "signal_id": signal_id,
            "trade": {
                "symbol": signal.symbol,
                "side": signal_data.direction,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "signal_strength": signal.strength,
                "mode": "dry_run"
            }
        }
    else:
        # Modo LIVE - executa trade real via Paper Trading
        try:
            # Calcular quantidade baseada no risco
            balance = autotrade_state.get("initial_balance", 10000)
            risk_per_trade = autotrade_state.get("risk_per_trade", 0.02)
            risk_amount = balance * risk_per_trade
            
            # Calcular stop em % 
            stop_distance = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
            quantity = risk_amount / (signal.entry_price * stop_distance) if stop_distance > 0 else 0
            
            # Criar ordem via Paper Trading
            order_request = ManualOrderRequest(
                session_id=session_id,
                symbol=signal.symbol,
                side=signal_data.direction,
                order_type="MARKET",
                quantity=quantity
            )
            
            autotrade_state["trades_executed"] += 1
            
            # Atualizar status do sinal
            if manager and signal_id:
                await manager.update_signal_execution(
                    signal_id=signal_id,
                    executed=True,
                    reason="✅ Trade executado em modo LIVE"
                )
            
            logger.info(f"🟢 LIVE - Trade executado: {signal.symbol} {signal_data.direction} qty={quantity:.6f} @ {signal.entry_price}")
            
            return {
                "success": True,
                "message": "Trade executado",
                "action": "executed",
                "signal_id": signal_id,
                "trade": {
                    "symbol": signal.symbol,
                    "side": signal_data.direction,
                    "quantity": quantity,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "signal_strength": signal.strength,
                    "mode": "live"
                }
            }
            
        except Exception as e:
            error_reason = f"❌ Erro na execução: {str(e)}"
            
            # Atualizar status do sinal com erro
            if manager and signal_id:
                await manager.update_signal_execution(
                    signal_id=signal_id,
                    executed=False,
                    reason=error_reason
                )
            
            logger.error(f"Erro no AutoTrade: {e}")
            
            return {
                "success": False,
                "message": error_reason,
                "action": "error",
                "signal_id": signal_id
            }


@app.get("/api/autotrade/signals-log")
async def get_autotrade_signals_log(limit: int = 50):
    """
    📋 Retorna o log de sinais processados pelo AutoTrade (do banco)
    """
    global autotrade_state, autotrade_manager
    
    if not autotrade_manager:
        # Fallback para dados em memória
        return {
            "total_signals": len(autotrade_state.get("signals_log", [])),
            "signals": autotrade_state.get("signals_log", [])[-limit:],
            "source": "memory"
        }
    
    # Buscar do banco
    session_id = autotrade_state.get("session_id", "unknown")
    signals = await autotrade_manager.get_recent_signals(session_id, limit)
    
    return {
        "total_signals": len(signals),
        "signals": signals,
        "source": "database"
    }


@app.get("/api/autotrade/analytics/session/{session_id}")
async def get_session_analytics(session_id: str):
    """
    📊 Retorna análise completa de uma sessão do AutoTrade
    """
    global autotrade_manager
    
    if not autotrade_manager:
        raise HTTPException(status_code=503, detail="AutoTradeManager não disponível")
    
    # Estatísticas gerais
    stats = await autotrade_manager.get_session_stats(session_id)
    
    if not stats:
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada")
    
    # Performance por símbolo
    by_symbol = await autotrade_manager.get_performance_by_symbol(session_id)
    
    # Performance por tipo de sinal
    by_signal_type = await autotrade_manager.get_performance_by_signal_type(session_id)
    
    # Sinais recentes
    recent_signals = await autotrade_manager.get_recent_signals(session_id, limit=20)
    
    return {
        "session_stats": stats,
        "performance_by_symbol": by_symbol,
        "performance_by_signal_type": by_signal_type,
        "recent_signals": recent_signals
    }


@app.get("/api/autotrade/analytics/symbols")
async def get_symbols_analytics():
    """
    📈 Retorna performance agregada por símbolo (todas as sessões)
    """
    global autotrade_manager
    
    if not autotrade_manager:
        raise HTTPException(status_code=503, detail="AutoTradeManager não disponível")
    
    try:
        query = """
            SELECT 
                symbol,
                COUNT(DISTINCT session_id) as sessions_count,
                SUM(total_signals) as total_signals,
                SUM(trades_executed) as total_trades,
                SUM(winning_trades) as winning_trades,
                SUM(losing_trades) as losing_trades,
                ROUND(AVG(win_rate), 2) as avg_win_rate,
                ROUND(SUM(total_pnl), 2) as total_pnl,
                ROUND(AVG(avg_pnl_percent), 2) as avg_pnl_percent
            FROM autotrade_performance_by_symbol
            GROUP BY symbol
            ORDER BY total_pnl DESC
        """
        
        rows = await autotrade_manager.db_conn.fetch(query)
        return {
            "symbols": [dict(row) for row in rows]
        }
    except Exception as e:
        logger.error(f"❌ Erro ao buscar analytics por símbolo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/autotrade/analytics/signal-types")
async def get_signal_types_analytics():
    """
    🎯 Retorna performance agregada por tipo de sinal (todas as sessões)
    """
    global autotrade_manager
    
    if not autotrade_manager:
        raise HTTPException(status_code=503, detail="AutoTradeManager não disponível")
    
    try:
        query = """
            SELECT 
                signal_type,
                direction,
                COUNT(DISTINCT session_id) as sessions_count,
                SUM(total_signals) as total_signals,
                SUM(trades_executed) as total_trades,
                SUM(winning_trades) as winning_trades,
                SUM(losing_trades) as losing_trades,
                ROUND(AVG(win_rate), 2) as avg_win_rate,
                ROUND(SUM(total_pnl), 2) as total_pnl,
                ROUND(AVG(avg_pnl_percent), 2) as avg_pnl_percent
            FROM autotrade_performance_by_signal_type
            GROUP BY signal_type, direction
            ORDER BY total_pnl DESC
        """
        
        rows = await autotrade_manager.db_conn.fetch(query)
        return {
            "signal_types": [dict(row) for row in rows]
        }
    except Exception as e:
        logger.error(f"❌ Erro ao buscar analytics por tipo de sinal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/autotrade/sessions")
async def list_autotrade_sessions(active_only: bool = False, limit: int = 10):
    """
    📋 Lista todas as sessões do AutoTrade
    """
    global autotrade_manager
    
    if not autotrade_manager:
        raise HTTPException(status_code=503, detail="AutoTradeManager não disponível")
    
    try:
        query = """
            SELECT * FROM autotrade_performance_summary
            WHERE ($1 = FALSE OR is_active = TRUE)
            ORDER BY started_at DESC
            LIMIT $2
        """
        
        rows = await autotrade_manager.db_conn.fetch(query, active_only, limit)
        return {
            "sessions": [dict(row) for row in rows]
        }
    except Exception as e:
        logger.error(f"❌ Erro ao listar sessões: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8001))
    
    logger.info(f"🚀 Iniciando Execution Engine na porta {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        workers=1,  # Single worker (estado compartilhado)
        timeout_keep_alive=30,  # Manter conexões vivas
        limit_concurrency=50  # Limitar requisições simultâneas
    )
