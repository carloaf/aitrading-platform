"""
WebSocket Client para Binance - Dados em Tempo Real
Conecta-se aos streams da Binance para receber:
- Ticker (preço atual)
- Trades (execuções)
- Klines (candles em tempo real)
- Order Book updates
"""

import asyncio
import json
import logging
from typing import Callable, Optional, Dict, List
from datetime import datetime
import websockets
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TickerData:
    """Dados de ticker em tempo real"""
    symbol: str
    price: float
    bid: float
    ask: float
    volume_24h: float
    timestamp: datetime
    
    def to_dict(self):
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TradeData:
    """Dados de trade executado"""
    symbol: str
    price: float
    quantity: float
    time: datetime
    is_buyer_maker: bool
    
    def to_dict(self):
        return {
            **asdict(self),
            'time': self.time.isoformat()
        }


@dataclass
class KlineData:
    """Dados de candlestick em tempo real"""
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool
    
    def to_dict(self):
        return {
            **asdict(self),
            'open_time': self.open_time.isoformat(),
            'close_time': self.close_time.isoformat()
        }


class BinanceWebSocketClient:
    """
    Cliente WebSocket para Binance Spot
    
    Streams disponíveis:
    - <symbol>@ticker - Ticker 24h
    - <symbol>@trade - Trades em tempo real
    - <symbol>@kline_<interval> - Candlesticks
    - <symbol>@depth - Order book updates
    """
    
    BASE_URL = "wss://stream.binance.com:9443/ws"
    
    def __init__(self):
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.callbacks: Dict[str, List[Callable]] = {
            'ticker': [],
            'trade': [],
            'kline': [],
            'depth': []
        }
        self.running = False
        
    async def connect_ticker(self, symbol: str, callback: Callable):
        """
        Conectar ao stream de ticker
        
        Args:
            symbol: Par de trading (ex: 'btcusdt')
            callback: Função async a chamar com TickerData
        """
        stream = f"{symbol.lower()}@ticker"
        self.callbacks['ticker'].append(callback)
        await self._connect_stream(stream, self._handle_ticker)
        
    async def connect_trades(self, symbol: str, callback: Callable):
        """
        Conectar ao stream de trades
        
        Args:
            symbol: Par de trading
            callback: Função async a chamar com TradeData
        """
        stream = f"{symbol.lower()}@trade"
        self.callbacks['trade'].append(callback)
        await self._connect_stream(stream, self._handle_trade)
        
    async def connect_klines(self, symbol: str, interval: str, callback: Callable):
        """
        Conectar ao stream de klines/candlesticks
        
        Args:
            symbol: Par de trading
            interval: Intervalo (1m, 5m, 15m, 1h, 4h, 1d, etc)
            callback: Função async a chamar com KlineData
        """
        stream = f"{symbol.lower()}@kline_{interval}"
        self.callbacks['kline'].append(callback)
        await self._connect_stream(stream, self._handle_kline)
        
    async def _connect_stream(self, stream: str, handler: Callable):
        """Conecta a um stream específico"""
        url = f"{self.BASE_URL}/{stream}"
        
        try:
            logger.info(f"📡 Conectando ao stream: {stream}")
            ws = await websockets.connect(url)
            self.connections[stream] = ws
            self.running = True
            
            # Iniciar listener em background
            asyncio.create_task(self._listen_stream(stream, ws, handler))
            
            logger.info(f"✅ Conectado ao stream: {stream}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar stream {stream}: {e}")
            raise
            
    async def _listen_stream(self, stream: str, ws: websockets.WebSocketClientProtocol, handler: Callable):
        """Loop de escuta para um stream"""
        try:
            while self.running:
                message = await ws.recv()
                data = json.loads(message)
                await handler(data)
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"⚠️ Conexão fechada: {stream}")
            # Tentar reconectar
            await asyncio.sleep(5)
            if self.running:
                logger.info(f"🔄 Reconectando: {stream}")
                await self._connect_stream(stream, handler)
                
        except Exception as e:
            logger.error(f"❌ Erro no stream {stream}: {e}")
            
    async def _handle_ticker(self, data: dict):
        """Processa dados de ticker"""
        try:
            ticker = TickerData(
                symbol=data['s'],
                price=float(data['c']),
                bid=float(data['b']),
                ask=float(data['a']),
                volume_24h=float(data['v']),
                timestamp=datetime.fromtimestamp(data['E'] / 1000)
            )
            
            # Chamar todos os callbacks registrados
            for callback in self.callbacks['ticker']:
                await callback(ticker)
                
        except Exception as e:
            logger.error(f"Erro ao processar ticker: {e}")
            
    async def _handle_trade(self, data: dict):
        """Processa dados de trade"""
        try:
            trade = TradeData(
                symbol=data['s'],
                price=float(data['p']),
                quantity=float(data['q']),
                time=datetime.fromtimestamp(data['T'] / 1000),
                is_buyer_maker=data['m']
            )
            
            for callback in self.callbacks['trade']:
                await callback(trade)
                
        except Exception as e:
            logger.error(f"Erro ao processar trade: {e}")
            
    async def _handle_kline(self, data: dict):
        """Processa dados de kline"""
        try:
            k = data['k']
            kline = KlineData(
                symbol=k['s'],
                interval=k['i'],
                open_time=datetime.fromtimestamp(k['t'] / 1000),
                close_time=datetime.fromtimestamp(k['T'] / 1000),
                open=float(k['o']),
                high=float(k['h']),
                low=float(k['l']),
                close=float(k['c']),
                volume=float(k['v']),
                is_closed=k['x']
            )
            
            for callback in self.callbacks['kline']:
                await callback(kline)
                
        except Exception as e:
            logger.error(f"Erro ao processar kline: {e}")
            
    async def disconnect_all(self):
        """Desconecta todos os streams"""
        self.running = False
        
        for stream, ws in self.connections.items():
            try:
                await ws.close()
                logger.info(f"🔌 Desconectado: {stream}")
            except Exception as e:
                logger.error(f"Erro ao desconectar {stream}: {e}")
                
        self.connections.clear()
        logger.info("✅ Todos os streams desconectados")


# Exemplo de uso
async def example_usage():
    """Exemplo de como usar o WebSocket Client"""
    
    async def on_ticker(ticker: TickerData):
        print(f"💰 {ticker.symbol}: ${ticker.price:.2f} | Bid: ${ticker.bid:.2f} | Ask: ${ticker.ask:.2f}")
        
    async def on_trade(trade: TradeData):
        side = "SELL" if trade.is_buyer_maker else "BUY"
        print(f"📊 Trade {trade.symbol}: {side} {trade.quantity:.6f} @ ${trade.price:.2f}")
        
    async def on_kline(kline: KlineData):
        if kline.is_closed:
            print(f"🕯️ {kline.symbol} {kline.interval} fechado: O:{kline.open:.2f} H:{kline.high:.2f} L:{kline.low:.2f} C:{kline.close:.2f}")
    
    # Criar cliente
    client = BinanceWebSocketClient()
    
    # Conectar aos streams
    await client.connect_ticker('btcusdt', on_ticker)
    await client.connect_trades('btcusdt', on_trade)
    await client.connect_klines('btcusdt', '1m', on_kline)
    
    # Manter rodando
    try:
        await asyncio.sleep(60)  # Rodar por 60 segundos
    except KeyboardInterrupt:
        print("\n⏹️ Parando...")
    finally:
        await client.disconnect_all()


if __name__ == "__main__":
    print("🚀 Testando WebSocket Client...")
    asyncio.run(example_usage())
