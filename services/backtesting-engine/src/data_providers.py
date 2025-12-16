"""
Data Providers para obter dados de mercado de diferentes fontes
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import requests
from typing import Optional
import os

logger = logging.getLogger(__name__)

class DataProvider:
    """Classe base para provedores de dados"""
    
    def get_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> pd.DataFrame:
        raise NotImplementedError

class BinanceDataProvider(DataProvider):
    """Provedor de dados usando Binance API diretamente"""
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        
    def get_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> pd.DataFrame:
        """
        Obtém dados históricos da Binance
        
        Args:
            symbol: Par de trading (ex: BTCUSDT, ETHUSDT)
            start_date: Data inicial (YYYY-MM-DD)
            end_date: Data final (YYYY-MM-DD)
            interval: Intervalo (1m, 5m, 15m, 1h, 4h, 1d)
        """
        try:
            # Converter símbolo (BTC-USD -> BTCUSDT)
            if '-' in symbol:
                base, quote = symbol.split('-')
                symbol = f"{base}{quote}T" if quote == 'USD' else f"{base}{quote}"
            
            # Converter datas para timestamp
            start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
            
            # Mapear intervalos
            interval_map = {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w'
            }
            binance_interval = interval_map.get(interval, '1d')
            
            logger.info(f"Buscando dados da Binance: {symbol} de {start_date} até {end_date}")
            
            # Fazer requisição
            url = f"{self.base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': binance_interval,
                'startTime': start_ts,
                'endTime': end_ts,
                'limit': 1000
            }
            
            all_data = []
            while True:
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code != 200:
                    logger.error(f"Erro na API Binance: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                if not data:
                    break
                
                all_data.extend(data)
                
                # Se recebeu menos que o limite, terminou
                if len(data) < 1000:
                    break
                
                # Atualizar startTime para próxima requisição
                params['startTime'] = data[-1][0] + 1
            
            if not all_data:
                logger.warning(f"Nenhum dado retornado da Binance para {symbol}")
                return pd.DataFrame()
            
            # Converter para DataFrame
            df = pd.DataFrame(all_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Converter tipos
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Converter para float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            # Remover colunas não necessárias
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            logger.info(f"✅ Dados da Binance carregados: {len(df)} candles")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados da Binance: {e}", exc_info=True)
            return pd.DataFrame()

class TimescaleDBDataProvider(DataProvider):
    """Provedor de dados usando TimescaleDB (dados coletados pelo market-data-collector)"""
    
    def __init__(self):
        self.db_url = os.getenv('TIMESCALE_URL', 'postgresql://trader:trader123@timescaledb:5432/aitrading')
        
    def get_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> pd.DataFrame:
        """
        Obtém dados do TimescaleDB
        """
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Converter símbolo
            if '-' in symbol:
                base, quote = symbol.split('-')
                symbol = f"{base}{quote}T" if quote == 'USD' else f"{base}{quote}"
            
            logger.info(f"Buscando dados do TimescaleDB: {symbol} de {start_date} até {end_date}")
            
            # Conectar ao banco
            conn = psycopg2.connect(self.db_url)
            
            # Query para buscar dados agregados
            query = """
                SELECT 
                    time_bucket(%s, ts) as timestamp,
                    first(price, ts) as open,
                    max(price) as high,
                    min(price) as low,
                    last(price, ts) as close,
                    sum(volume) as volume
                FROM market_data
                WHERE symbol = %s
                AND ts BETWEEN %s AND %s
                GROUP BY timestamp
                ORDER BY timestamp
            """
            
            # Mapear intervalos para time_bucket
            interval_map = {
                '1m': '1 minute', '5m': '5 minutes', '15m': '15 minutes',
                '1h': '1 hour', '4h': '4 hours', '1d': '1 day'
            }
            bucket_interval = interval_map.get(interval, '1 day')
            
            df = pd.read_sql_query(
                query, 
                conn,
                params=(bucket_interval, symbol, start_date, end_date)
            )
            
            conn.close()
            
            if df.empty:
                logger.warning(f"Nenhum dado no TimescaleDB para {symbol}")
                return pd.DataFrame()
            
            # Configurar index
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"✅ Dados do TimescaleDB carregados: {len(df)} candles")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados do TimescaleDB: {e}", exc_info=True)
            return pd.DataFrame()

class MarketDataCollectorProvider(DataProvider):
    """Provedor que usa o market-data-collector service"""
    
    def __init__(self):
        self.base_url = os.getenv('MARKET_DATA_URL', 'http://market-data-collector:3001')
        
    def get_data(self, symbol: str, start_date: str, end_date: str, interval: str = '1d') -> pd.DataFrame:
        """
        Obtém dados via market-data-collector service
        """
        try:
            # Converter símbolo
            if '-' in symbol:
                base, quote = symbol.split('-')
                symbol = f"{base}{quote}T" if quote == 'USD' else f"{base}{quote}"
            
            logger.info(f"Buscando dados do market-data-collector: {symbol}")
            
            url = f"{self.base_url}/api/historical"
            params = {
                'symbol': symbol,
                'start': start_date,
                'end': end_date,
                'interval': interval
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"market-data-collector retornou {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            
            if not data or 'data' not in data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data['data'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"✅ Dados do market-data-collector: {len(df)} candles")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados do market-data-collector: {e}")
            return pd.DataFrame()

def get_market_data(symbol: str, start_date: str, end_date: str, interval: str = '1d') -> pd.DataFrame:
    """
    Obtém dados de mercado tentando múltiplos provedores em ordem de prioridade
    
    1. TimescaleDB (se tiver dados coletados)
    2. Binance API (direto)
    3. Market Data Collector service
    """
    providers = [
        ('Binance API', BinanceDataProvider()),
        ('TimescaleDB', TimescaleDBDataProvider()),
        ('Market Data Collector', MarketDataCollectorProvider()),
    ]
    
    for provider_name, provider in providers:
        try:
            logger.info(f"Tentando provedor: {provider_name}")
            df = provider.get_data(symbol, start_date, end_date, interval)
            
            if not df.empty and len(df) > 0:
                logger.info(f"✅ Sucesso com {provider_name}: {len(df)} candles")
                return df
            else:
                logger.warning(f"⚠️ {provider_name} retornou dados vazios")
        except Exception as e:
            logger.warning(f"❌ Falha com {provider_name}: {e}")
            continue
    
    logger.error(f"❌ Nenhum provedor conseguiu obter dados para {symbol}")
    return pd.DataFrame()
