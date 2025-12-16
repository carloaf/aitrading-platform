"""
Strategy Executor - Executa estratégias em tempo real
Conecta WebSocket -> Estratégia -> Order Manager
"""

import asyncio
import logging
from typing import Dict, Optional, Callable
from datetime import datetime
import pandas as pd
import numpy as np

from websocket_client import BinanceWebSocketClient, TickerData, KlineData
from order_manager import OrderManager, OrderSide, OrderType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StrategyExecutor:
    """
    Executa estratégias de trading em tempo real
    """
    
    def __init__(self, 
                 strategy_class,
                 strategy_parameters: Dict,
                 order_manager: OrderManager,
                 symbol: str = 'BTCUSDT',
                 timeframe: str = '1m'):
        
        self.strategy_class = strategy_class
        self.strategy_parameters = strategy_parameters
        self.order_manager = order_manager
        self.symbol = symbol
        self.timeframe = timeframe
        
        # Criar instância da estratégia
        self.strategy = strategy_class(parameters=strategy_parameters)
        
        # WebSocket client
        self.ws_client = BinanceWebSocketClient()
        
        # Buffer de candles para análise
        self.candles_buffer = []
        self.max_buffer_size = 500  # Manter últimos 500 candles
        
        # Estado
        self.is_running = False
        self.last_signal = 0
        self.position_open = False
        
        # Performance tracking
        self.start_time = None
        self.signals_generated = 0
        self.trades_executed = 0
        
        logger.info(f"🎯 Strategy Executor criado: {self.strategy.name}")
        logger.info(f"   Símbolo: {symbol} | Timeframe: {timeframe}")
        
    async def start(self):
        """Inicia execução da estratégia"""
        
        if self.is_running:
            logger.warning("⚠️ Executor já está rodando")
            return
            
        self.is_running = True
        self.start_time = datetime.now()
        
        logger.info(f"🚀 Iniciando execução ao vivo...")
        
        try:
            # Conectar aos streams necessários
            await self.ws_client.connect_ticker(self.symbol, self._on_ticker)
            await self.ws_client.connect_klines(self.symbol, self.timeframe, self._on_kline)
            
            logger.info(f"✅ Executor ativo e monitorando {self.symbol}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar executor: {e}")
            self.is_running = False
            raise
            
    async def stop(self):
        """Para execução da estratégia"""
        
        if not self.is_running:
            logger.warning("⚠️ Executor já está parado")
            return
            
        self.is_running = False
        
        logger.info(f"⏹️ Parando executor...")
        
        # Fechar posições abertas se configurado
        if self.position_open:
            await self._close_all_positions()
            
        # Desconectar WebSocket
        await self.ws_client.disconnect_all()
        
        # Relatório final
        duration = (datetime.now() - self.start_time).total_seconds() / 60
        logger.info(f"✅ Executor parado")
        logger.info(f"   Duração: {duration:.1f} minutos")
        logger.info(f"   Sinais gerados: {self.signals_generated}")
        logger.info(f"   Trades executados: {self.trades_executed}")
        
    async def _on_ticker(self, ticker: TickerData):
        """Callback para atualizações de ticker"""
        
        # Atualizar preço no order manager
        self.order_manager.update_market_price(ticker.symbol, ticker.price)
        
    async def _on_kline(self, kline: KlineData):
        """Callback para novos candles"""
        
        # Só processar candles fechados
        if not kline.is_closed:
            return
            
        # Adicionar ao buffer
        candle_dict = {
            'timestamp': kline.close_time,
            'Open': kline.open,
            'High': kline.high,
            'Low': kline.low,
            'Close': kline.close,
            'Volume': kline.volume
        }
        
        self.candles_buffer.append(candle_dict)
        
        # Limitar tamanho do buffer
        if len(self.candles_buffer) > self.max_buffer_size:
            self.candles_buffer.pop(0)
            
        # Precisa de dados mínimos para calcular indicadores
        if len(self.candles_buffer) < 50:
            logger.debug(f"📊 Coletando dados... {len(self.candles_buffer)}/50")
            return
            
        # Executar estratégia
        await self._execute_strategy()
        
    async def _execute_strategy(self):
        """Executa lógica da estratégia"""
        
        try:
            # Converter buffer para DataFrame
            df = pd.DataFrame(self.candles_buffer)
            df.set_index('timestamp', inplace=True)
            
            # Executar estratégia (calcula indicadores e gera sinais)
            df_with_signals = self.strategy.run(df.copy())
            
            # Pegar último sinal
            current_signal = df_with_signals['signal'].iloc[-1]
            
            # Detectar mudança de sinal
            if current_signal != self.last_signal:
                self.signals_generated += 1
                logger.info(f"📡 Novo sinal detectado: {current_signal} (anterior: {self.last_signal})")
                
                # Executar trade baseado no sinal
                await self._handle_signal(current_signal, df_with_signals.iloc[-1])
                
                self.last_signal = current_signal
                
        except Exception as e:
            logger.error(f"❌ Erro ao executar estratégia: {e}")
            
    async def _handle_signal(self, signal: int, candle_data: pd.Series):
        """Processa sinal e executa trades"""
        
        current_price = candle_data['Close']
        
        # Sinal de COMPRA (1)
        if signal == 1 and not self.position_open:
            logger.info(f"🟢 SINAL DE COMPRA @ ${current_price:.2f}")
            
            # Calcular quantidade baseada no saldo disponível
            account = self.order_manager.get_account_summary()
            risk_per_trade = account['balance'] * 0.95  # Usar 95% do saldo
            quantity = risk_per_trade / current_price
            
            # Criar ordem de compra
            order = await self.order_manager.create_order(
                symbol=self.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=quantity
            )
            
            if order.status.value == "FILLED":
                self.position_open = True
                self.trades_executed += 1
                logger.info(f"✅ Compra executada: {quantity:.6f} @ ${current_price:.2f}")
                
        # Sinal de VENDA (-1)
        elif signal == -1 and self.position_open:
            logger.info(f"🔴 SINAL DE VENDA @ ${current_price:.2f}")
            
            # Pegar posição atual
            positions = self.order_manager.get_all_positions()
            if positions and positions[0]['symbol'] == self.symbol:
                quantity = positions[0]['quantity']
                
                # Criar ordem de venda
                order = await self.order_manager.create_order(
                    symbol=self.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=quantity
                )
                
                if order.status.value == "FILLED":
                    self.position_open = False
                    self.trades_executed += 1
                    
                    # Calcular PnL do trade
                    account = self.order_manager.get_account_summary()
                    logger.info(f"✅ Venda executada: {quantity:.6f} @ ${current_price:.2f}")
                    logger.info(f"💰 PnL Total: ${account['total_pnl']:.2f} ({account['total_pnl_percent']:.2f}%)")
                    
    async def _close_all_positions(self):
        """Fecha todas as posições abertas"""
        
        positions = self.order_manager.get_all_positions()
        
        for pos in positions:
            logger.info(f"🔄 Fechando posição: {pos['symbol']}")
            
            await self.order_manager.create_order(
                symbol=pos['symbol'],
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=pos['quantity']
            )
            
    def get_status(self) -> Dict:
        """Retorna status atual do executor"""
        
        account = self.order_manager.get_account_summary()
        
        uptime = 0
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
            
        return {
            'is_running': self.is_running,
            'strategy_name': self.strategy.name,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'position_open': self.position_open,
            'last_signal': self.last_signal,
            'uptime_seconds': uptime,
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'candles_collected': len(self.candles_buffer),
            'account_summary': account
        }


# Teste
async def test_executor():
    """Teste do Strategy Executor"""
    
    # Importar estratégia de exemplo
    import sys
    sys.path.append('/app')
    from strategies.momentum import MomentumStrategy
    
    # Criar Order Manager
    order_manager = OrderManager(initial_balance=1000.0)
    
    # Criar Executor
    executor = StrategyExecutor(
        strategy_class=MomentumStrategy,
        strategy_parameters={'roc_period': 10, 'threshold': 0},
        order_manager=order_manager,
        symbol='BTCUSDT',
        timeframe='1m'
    )
    
    # Iniciar
    await executor.start()
    
    # Rodar por 2 minutos
    try:
        await asyncio.sleep(120)
    except KeyboardInterrupt:
        print("\n⏹️ Interrompido pelo usuário")
    finally:
        await executor.stop()
        
    # Mostrar resultados
    print("\n" + "="*60)
    print("📊 RESULTADOS FINAIS")
    print("="*60)
    status = executor.get_status()
    for key, value in status.items():
        if key != 'account_summary':
            print(f"{key}: {value}")
    print("\n💰 Resumo da Conta:")
    for key, value in status['account_summary'].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    print("🧪 Testando Strategy Executor...")
    asyncio.run(test_executor())
