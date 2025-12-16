#!/usr/bin/env python3
"""
AI Trading Platform - Indicator Calculator Service
=================================================

Serviço responsável por calcular indicadores técnicos usando pandas e numpy.
Suporta tanto gRPC quanto REST API para máxima flexibilidade.

Indicadores Implementados:
- Médias Móveis (SMA, EMA, WMA)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Stochastic Oscillator
- ADX (Average Directional Index)
- Williams %R
- CCI (Commodity Channel Index)
- E muito mais...
"""

import asyncio
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import grpc
from grpc_reflection.v1alpha import reflection
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import redis
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from loguru import logger
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
import schedule
import time
from indicators import TechnicalIndicators

# Carregar variáveis de ambiente
load_dotenv()

# Configuração de logs
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/indicator_calculator.log",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

# ==========================================
# CONFIGURAÇÕES
# ==========================================

class Config:
    """Configurações do serviço"""
    
    # Servidor
    GRPC_PORT = int(os.getenv('GRPC_PORT', 50051))
    HTTP_PORT = int(os.getenv('HTTP_PORT', 8000))
    HOST = os.getenv('HOST', '0.0.0.0')
    
    # Banco de dados
    TIMESCALE_URL = os.getenv('TIMESCALE_URL', 'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
    
    # Cache
    CACHE_TTL = int(os.getenv('CACHE_TTL', 300))  # 5 minutos
    
    # Processamento
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', 4))
    
    # Indicadores
    DEFAULT_PERIODS = {
        'sma': [9, 21, 50, 200],
        'ema': [12, 26, 50],
        'rsi': [14],
        'macd': [(12, 26, 9)],
        'bb': [(20, 2)],
        'stoch': [(14, 3, 3)]
    }

config = Config()

# ==========================================
# CONEXÕES
# ==========================================

class DatabaseManager:
    """Gerenciador de conexões com banco de dados"""
    
    def __init__(self):
        self.engine = None
        self.redis_client = None
        
    async def connect(self):
        """Conectar aos bancos de dados com retry"""
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Tentativa {attempt + 1}/{max_retries} de conexão aos bancos...")
                
                # PostgreSQL/TimescaleDB
                self.engine = create_engine(config.TIMESCALE_URL, pool_pre_ping=True)
                
                # Testar conexão
                with self.engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    logger.info("✅ Conectado ao TimescaleDB")
                
                # Redis
                self.redis_client = redis.from_url(config.REDIS_URL, decode_responses=True)
                self.redis_client.ping()  # Remover await aqui
                logger.info("✅ Conectado ao Redis")
                
                return  # Sucesso, sair do loop
                
            except Exception as e:
                logger.error(f"❌ Erro na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Aguardando {retry_delay}s antes da próxima tentativa...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("❌ Esgotadas todas as tentativas de conexão")
                    raise
    
    def get_market_data(self, symbol: str, timeframe: str = '1m', limit: int = 500) -> pd.DataFrame:
        """Buscar dados de mercado para cálculo de indicadores"""
        try:
            query = """
            SELECT 
                timestamp,
                open_price as open,
                high_price as high,
                low_price as low,
                close_price as close,
                volume
            FROM market_data_realtime 
            WHERE symbol = %s 
            AND interval_type = %s
            ORDER BY timestamp DESC
            LIMIT %s
            """
            
            df = pd.read_sql_query(
                query, 
                self.engine, 
                params=[symbol, timeframe, limit]
            )
            
            if df.empty:
                logger.warning(f"Nenhum dado encontrado para {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Inverter para ordem cronológica
            df = df.sort_values('timestamp')
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            logger.debug(f"Dados carregados: {symbol} {timeframe} - {len(df)} registros")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados de mercado: {e}")
            return pd.DataFrame()
    
    async def cache_set(self, key: str, value: dict, ttl: int = None):
        """Salvar no cache Redis"""
        try:
            ttl = ttl or config.CACHE_TTL
            await self.redis_client.setex(
                key, 
                ttl, 
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")
    
    async def cache_get(self, key: str) -> Optional[dict]:
        """Buscar do cache Redis"""
        try:
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar cache: {e}")
            return None

# Instância global do gerenciador
db_manager = DatabaseManager()

# ==========================================
# CALCULADORA DE INDICADORES
# ==========================================

class IndicatorCalculator:
    """Calculadora de indicadores técnicos usando implementação personalizada"""
    
    @staticmethod
    def sma(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Simple Moving Average"""
        result = TechnicalIndicators.sma(data['close'], period)
        return result.values
    
    @staticmethod
    def ema(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Exponential Moving Average"""
        result = TechnicalIndicators.ema(data['close'], period)
        return result.values
    
    @staticmethod
    def wma(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Weighted Moving Average"""
        result = TechnicalIndicators.wma(data['close'], period)
        return result.values
    
    @staticmethod
    def rsi(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Relative Strength Index"""
        result = TechnicalIndicators.rsi(data['close'], period)
        return result.values
    
    @staticmethod
    def macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """MACD (Moving Average Convergence Divergence)"""
        result = TechnicalIndicators.macd(data['close'], fast, slow, signal)
        return result['macd'].values, result['signal'].values, result['histogram'].values
    
    @staticmethod
    def bollinger_bands(data: pd.DataFrame, period: int = 20, std_dev: float = 2) -> tuple:
        """Bollinger Bands"""
        result = TechnicalIndicators.bollinger_bands(data['close'], period, std_dev)
        return result['upper'].values, result['middle'].values, result['lower'].values
    
    @staticmethod
    def stochastic(data: pd.DataFrame, k_period: int = 14, d_period: int = 3, d_smooth: int = 3) -> tuple:
        """Stochastic Oscillator"""
        result = TechnicalIndicators.stochastic(data['high'], data['low'], data['close'], k_period, d_period)
        return result['k_percent'].values, result['d_percent'].values
    
    @staticmethod
    def adx(data: pd.DataFrame, period: int = 14) -> tuple:
        """Average Directional Index"""
        result = TechnicalIndicators.adx(data['high'], data['low'], data['close'], period)
        return result['adx'].values, result['di_plus'].values, result['di_minus'].values
    
    @staticmethod
    def williams_r(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Williams %R"""
        result = TechnicalIndicators.williams_r(data['high'], data['low'], data['close'], period)
        return result.values
    
    @staticmethod
    def cci(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Commodity Channel Index"""
        result = TechnicalIndicators.cci(data['high'], data['low'], data['close'], period)
        return result.values
    
    @staticmethod
    def atr(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Average True Range"""
        result = TechnicalIndicators.atr(data['high'], data['low'], data['close'], period)
        return result.values
    
    @staticmethod
    def obv(data: pd.DataFrame) -> np.ndarray:
        """On-Balance Volume"""
        result = TechnicalIndicators.obv(data['close'], data['volume'])
        return result.values

    @staticmethod
    def calculate_all_indicators(data: pd.DataFrame) -> dict:
        """Calcular todos os indicadores disponíveis"""
        if len(data) < 200:  # Precisamos de dados suficientes
            logger.warning(f"Dados insuficientes para cálculo de indicadores: {len(data)} registros")
            return {}
        
        try:
            indicators = {
                'timestamp': data.index[-1].isoformat(),
                'symbol': None,  # Será preenchido externamente
                'moving_averages': {
                    'sma_9': float(IndicatorCalculator.sma(data, 9)[-1]) if not np.isnan(IndicatorCalculator.sma(data, 9)[-1]) else None,
                    'sma_21': float(IndicatorCalculator.sma(data, 21)[-1]) if not np.isnan(IndicatorCalculator.sma(data, 21)[-1]) else None,
                    'sma_50': float(IndicatorCalculator.sma(data, 50)[-1]) if not np.isnan(IndicatorCalculator.sma(data, 50)[-1]) else None,
                    'sma_200': float(IndicatorCalculator.sma(data, 200)[-1]) if not np.isnan(IndicatorCalculator.sma(data, 200)[-1]) else None,
                    'ema_12': float(IndicatorCalculator.ema(data, 12)[-1]) if not np.isnan(IndicatorCalculator.ema(data, 12)[-1]) else None,
                    'ema_26': float(IndicatorCalculator.ema(data, 26)[-1]) if not np.isnan(IndicatorCalculator.ema(data, 26)[-1]) else None,
                    'ema_50': float(IndicatorCalculator.ema(data, 50)[-1]) if not np.isnan(IndicatorCalculator.ema(data, 50)[-1]) else None,
                },
                'oscillators': {
                    'rsi_14': float(IndicatorCalculator.rsi(data, 14)[-1]) if not np.isnan(IndicatorCalculator.rsi(data, 14)[-1]) else None,
                    'williams_r_14': float(IndicatorCalculator.williams_r(data, 14)[-1]) if not np.isnan(IndicatorCalculator.williams_r(data, 14)[-1]) else None,
                    'cci_20': float(IndicatorCalculator.cci(data, 20)[-1]) if not np.isnan(IndicatorCalculator.cci(data, 20)[-1]) else None,
                },
                'trend': {
                    'adx_14': float(IndicatorCalculator.adx(data, 14)[-1]) if not np.isnan(IndicatorCalculator.adx(data, 14)[-1]) else None,
                },
                'volatility': {
                    'atr_14': float(IndicatorCalculator.atr(data, 14)[-1]) if not np.isnan(IndicatorCalculator.atr(data, 14)[-1]) else None,
                },
                'volume': {
                    'obv': float(IndicatorCalculator.obv(data)[-1]) if not np.isnan(IndicatorCalculator.obv(data)[-1]) else None,
                }
            }
            
            # MACD
            macd_line, signal_line, histogram = IndicatorCalculator.macd(data)
            indicators['macd'] = {
                'macd_line': float(macd_line[-1]) if not np.isnan(macd_line[-1]) else None,
                'signal_line': float(signal_line[-1]) if not np.isnan(signal_line[-1]) else None,
                'histogram': float(histogram[-1]) if not np.isnan(histogram[-1]) else None,
            }
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = IndicatorCalculator.bollinger_bands(data)
            indicators['bollinger_bands'] = {
                'upper': float(bb_upper[-1]) if not np.isnan(bb_upper[-1]) else None,
                'middle': float(bb_middle[-1]) if not np.isnan(bb_middle[-1]) else None,
                'lower': float(bb_lower[-1]) if not np.isnan(bb_lower[-1]) else None,
            }
            
            # Stochastic
            stoch_k, stoch_d = IndicatorCalculator.stochastic(data)
            indicators['stochastic'] = {
                'k': float(stoch_k[-1]) if not np.isnan(stoch_k[-1]) else None,
                'd': float(stoch_d[-1]) if not np.isnan(stoch_d[-1]) else None,
            }
            
            return indicators
            
        except Exception as e:
            logger.error(f"Erro ao calcular indicadores: {e}")
            return {}

calc = IndicatorCalculator()

# ==========================================
# SERVIÇO PRINCIPAL
# ==========================================

class IndicatorService:
    """Serviço principal de indicadores técnicos"""
    
    def __init__(self):
        self.is_running = False
        self.symbols = ['BTCUSDT', 'ETHUSDT']  # Símbolos padrão
        
    async def start(self):
        """Inicializar o serviço"""
        logger.info("🚀 Iniciando Indicator Calculator Service...")
        
        # Conectar aos bancos
        await db_manager.connect()
        
        # Iniciar cálculo agendado
        self.start_scheduled_calculations()
        
        self.is_running = True
        logger.info("✅ Indicator Calculator Service iniciado com sucesso!")
    
    def start_scheduled_calculations(self):
        """Iniciar cálculos agendados de indicadores"""
        
        def run_calculations():
            """Executar cálculos em thread separada"""
            schedule.every(1).minutes.do(self.calculate_all_symbols)
            
            while self.is_running:
                schedule.run_pending()
                time.sleep(30)
        
        # Iniciar em thread separada
        calculation_thread = threading.Thread(target=run_calculations, daemon=True)
        calculation_thread.start()
        
        logger.info("📊 Cálculos agendados iniciados (1 minuto)")
    
    async def calculate_all_symbols(self):
        """Calcular indicadores para todos os símbolos"""
        logger.info("📈 Calculando indicadores para todos os símbolos...")
        
        for symbol in self.symbols:
            try:
                await self.calculate_indicators_for_symbol(symbol)
            except Exception as e:
                logger.error(f"Erro ao calcular indicadores para {symbol}: {e}")
    
    async def calculate_indicators_for_symbol(self, symbol: str, timeframe: str = '1m'):
        """Calcular indicadores para um símbolo específico"""
        try:
            # Verificar cache primeiro
            cache_key = f"indicators:{symbol}:{timeframe}"
            cached = await db_manager.cache_get(cache_key)
            
            if cached:
                logger.debug(f"Indicadores encontrados no cache: {symbol}")
                return cached
            
            # Buscar dados de mercado
            data = db_manager.get_market_data(symbol, timeframe, 500)
            
            if data.empty:
                logger.warning(f"Sem dados para calcular indicadores: {symbol}")
                return None
            
            # Calcular indicadores
            indicators = calc.calculate_all_indicators(data)
            
            if not indicators:
                logger.warning(f"Falha no cálculo de indicadores: {symbol}")
                return None
            
            indicators['symbol'] = symbol
            indicators['timeframe'] = timeframe
            
            # Salvar no cache
            await db_manager.cache_set(cache_key, indicators, 60)  # Cache de 1 minuto
            
            # Publicar no Redis para outros serviços
            await db_manager.redis_client.publish(
                f'indicators:{symbol}', 
                json.dumps(indicators, default=str)
            )
            
            logger.info(f"✅ Indicadores calculados: {symbol} {timeframe}")
            return indicators
            
        except Exception as e:
            logger.error(f"Erro ao calcular indicadores para {symbol}: {e}")
            return None
    
    async def get_indicators(self, symbol: str, timeframe: str = '1m') -> Optional[dict]:
        """Obter indicadores (com cache)"""
        cache_key = f"indicators:{symbol}:{timeframe}"
        
        # Tentar cache primeiro
        cached = await db_manager.cache_get(cache_key)
        if cached:
            return cached
        
        # Se não houver cache, calcular
        return await self.calculate_indicators_for_symbol(symbol, timeframe)
    
    async def health_check(self) -> dict:
        """Health check do serviço"""
        return {
            'status': 'healthy' if self.is_running else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'symbols_monitored': len(self.symbols),
            'database_connected': db_manager.engine is not None,
            'redis_connected': db_manager.redis_client is not None,
            'indicators_library': 'custom_pandas_numpy'
        }

# Instância global do serviço
service = IndicatorService()

# ==========================================
# API REST (FASTAPI)
# ==========================================

app = FastAPI(
    title="AI Trading Platform - Indicator Calculator",
    description="Serviço de cálculo de indicadores técnicos usando TA-Lib",
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

@app.on_event("startup")
async def startup_event():
    """Inicializar serviço ao iniciar FastAPI"""
    await service.start()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await service.health_check()

@app.get("/indicators/{symbol}")
async def get_indicators(symbol: str, timeframe: str = "1m"):
    """Obter indicadores para um símbolo"""
    try:
        indicators = await service.get_indicators(symbol.upper(), timeframe)
        
        if not indicators:
            raise HTTPException(
                status_code=404, 
                detail=f"Indicadores não encontrados para {symbol}"
            )
        
        return indicators
        
    except Exception as e:
        logger.error(f"Erro na API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/indicators/calculate")
async def calculate_indicators(request: dict):
    """Calcular indicadores sob demanda"""
    try:
        symbol = request.get('symbol', '').upper()
        timeframe = request.get('timeframe', '1m')
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required")
        
        indicators = await service.calculate_indicators_for_symbol(symbol, timeframe)
        
        if not indicators:
            raise HTTPException(
                status_code=404, 
                detail=f"Não foi possível calcular indicadores para {symbol}"
            )
        
        return indicators
        
    except Exception as e:
        logger.error(f"Erro no cálculo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/indicators")
async def list_available_symbols():
    """Listar símbolos disponíveis"""
    return {
        'symbols': service.symbols,
        'supported_timeframes': ['1m', '5m', '15m', '1h', '4h', '1d'],
        'available_indicators': [
            'moving_averages', 'oscillators', 'trend', 
            'volatility', 'volume', 'macd', 'bollinger_bands', 'stochastic'
        ]
    }

# ==========================================
# MAIN
# ==========================================

async def run_rest_api():
    """Executar API REST"""
    config_uvicorn = uvicorn.Config(
        app, 
        host=config.HOST, 
        port=config.HTTP_PORT,
        log_level="info"
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()

async def main():
    """Função principal"""
    logger.info("🔧 Iniciando AI Trading Platform - Indicator Calculator")
    
    try:
        # Executar API REST
        await run_rest_api()
        
    except KeyboardInterrupt:
        logger.info("🛑 Parando serviço...")
        service.is_running = False
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
