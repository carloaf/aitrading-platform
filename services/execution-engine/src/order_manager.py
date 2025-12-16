"""
Order Manager - Gerenciamento de Ordens para Paper Trading
Simula execução de ordens sem conectar a exchange real
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class Order:
    """Representa uma ordem de trading"""
    order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    commission: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    
    def to_dict(self):
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'type': self.type.value,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'avg_price': self.avg_price,
            'commission': self.commission,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'filled_at': self.filled_at.isoformat() if self.filled_at else None
        }


@dataclass
class Position:
    """Representa uma posição aberta"""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    side: OrderSide
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    def update_price(self, new_price: float):
        """Atualiza preço atual e PnL"""
        self.current_price = new_price
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (new_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - new_price) * self.quantity
            
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'side': self.side.value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl
        }


class OrderManager:
    """
    Gerencia ordens para Paper Trading
    Simula execução, fill, slippage e comissões
    """
    
    def __init__(self, 
                 initial_balance: float = 10000.0,
                 commission_rate: float = 0.001,  # 0.1%
                 slippage_rate: float = 0.0005,  # 0.05%
                 session_id: str = None,
                 symbol: str = "BTCUSDT",
                 strategy_name: str = "unknown"):
        
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.session_id = session_id
        self.symbol = symbol
        self.strategy_name = strategy_name
        
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}
        self.order_history: List[Order] = []
        self.trades: List[Dict] = []
        
        self.current_prices: Dict[str, float] = {}
        
        # Conexão com banco (será inicializada async)
        self.db_conn = None
        self.db_enabled = True
        
        logger.info(f"💰 Order Manager iniciado - Saldo: ${initial_balance:.2f}")
    
    async def initialize_database(self):
        """Inicializa conexão com banco de dados e registra sessão"""
        import asyncpg
        import os
        
        try:
            conn_string = os.getenv('TIMESCALE_URL', 
                'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
            
            self.db_conn = await asyncpg.connect(conn_string)
            logger.info(f"📊 Conexão com banco estabelecida para sessão {self.session_id}")
            
            # Registrar ou atualizar sessão
            if self.session_id:
                await self._register_session()
                
        except Exception as e:
            logger.error(f"Erro ao conectar banco: {e}. Continuando sem persistência.")
            self.db_enabled = False
    
    async def _register_session(self):
        """Registra sessão no banco de dados"""
        if not self.db_conn or not self.session_id:
            return
        
        try:
            query = """
                INSERT INTO paper_trading_sessions 
                (session_id, symbol, strategy_name, initial_balance, current_balance, timeframe, started_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (session_id) 
                DO UPDATE SET 
                    current_balance = EXCLUDED.current_balance,
                    updated_at = NOW()
            """
            
            await self.db_conn.execute(
                query,
                self.session_id,
                self.symbol,
                self.strategy_name,
                self.initial_balance,
                self.balance,
                "1m"  # Default, pode ser passado como parâmetro
            )
            
            logger.info(f"✅ Sessão {self.session_id} registrada no banco")
            
        except Exception as e:
            logger.error(f"Erro ao registrar sessão: {e}")
    
    async def _save_trade_to_db(self, trade_data: Dict):
        """Salva trade no banco de dados"""
        if not self.db_conn or not self.db_enabled or not self.session_id:
            return
        
        try:
            # Calcular P&L
            pnl = 0
            pnl_percent = 0
            cumulative_pnl = sum([t.get('pnl', 0) for t in self.trades])
            
            if trade_data['side'] == 'SELL' and len(self.trades) >= 2:
                # Calcular P&L baseado no último BUY
                buy_trades = [t for t in self.trades if t['side'] == 'BUY']
                if buy_trades:
                    last_buy = buy_trades[-1]
                    pnl = (trade_data['price'] - last_buy['price']) * trade_data['quantity'] - trade_data['commission']
                    pnl_percent = (pnl / (last_buy['price'] * trade_data['quantity'])) * 100 if last_buy['price'] > 0 else 0
                    cumulative_pnl += pnl
            
            query = """
                INSERT INTO paper_trading_trades 
                (session_id, symbol, strategy_name, trade_type, timestamp, price, quantity,
                 value, fee, balance_before, balance_after, pnl, pnl_percent, cumulative_pnl,
                 position_side, position_size)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            """
            
            position_size = self.positions[self.symbol].quantity if self.symbol in self.positions else 0
            position_side = self.positions[self.symbol].side.value if self.symbol in self.positions else 'FLAT'
            
            await self.db_conn.execute(
                query,
                self.session_id,
                self.symbol,
                self.strategy_name,
                trade_data['side'],
                trade_data['timestamp'],
                trade_data['price'],
                trade_data['quantity'],
                trade_data['price'] * trade_data['quantity'],
                trade_data['commission'],
                trade_data.get('balance_before', self.balance),
                trade_data['balance_after'],
                pnl,
                pnl_percent,
                cumulative_pnl,
                position_side,
                position_size
            )
            
            logger.info(f"💾 Trade salvo no banco: {trade_data['side']} {trade_data['quantity']} @ ${trade_data['price']:.2f}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar trade: {e}")
    
    async def close_database(self):
        """Fecha conexão com banco"""
        if self.db_conn:
            try:
                await self.db_conn.close()
                logger.info("Conexão com banco fechada")
            except Exception as e:
                logger.error(f"Erro ao fechar conexão: {e}")
        
    def update_market_price(self, symbol: str, price: float):
        """Atualiza preço de mercado para um símbolo"""
        self.current_prices[symbol] = price
        
        # Atualizar posições abertas
        if symbol in self.positions:
            self.positions[symbol].update_price(price)
            
        # Verificar ordens pendentes que podem ser executadas
        asyncio.create_task(self._check_pending_orders(symbol, price))
        
    async def create_order(self, 
                          symbol: str,
                          side: OrderSide,
                          order_type: OrderType,
                          quantity: float,
                          price: Optional[float] = None,
                          stop_price: Optional[float] = None) -> Order:
        """
        Cria uma nova ordem
        
        Args:
            symbol: Par de trading
            side: BUY ou SELL
            order_type: Tipo de ordem
            quantity: Quantidade
            price: Preço (para limit orders)
            stop_price: Preço de stop (para stop orders)
        """
        
        # Gerar ID único
        order_id = str(uuid.uuid4())
        
        # Criar ordem
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price
        )
        
        # Validar ordem
        if not await self._validate_order(order):
            order.status = OrderStatus.REJECTED
            logger.warning(f"❌ Ordem rejeitada: {order_id}")
            return order
            
        # Adicionar às ordens ativas
        self.orders[order_id] = order
        
        # Se for market order, executar imediatamente
        if order_type == OrderType.MARKET:
            await self._execute_market_order(order)
            
        logger.info(f"📝 Nova ordem criada: {order_id} | {side.value} {quantity} {symbol} @ {price or 'MARKET'}")
        
        return order
        
    async def _validate_order(self, order: Order) -> bool:
        """Valida se ordem pode ser executada"""
        
        # Verificar se temos preço de mercado
        if order.symbol not in self.current_prices:
            logger.error(f"Preço de mercado não disponível para {order.symbol}")
            return False
            
        market_price = self.current_prices[order.symbol]
        
        # Para compra, verificar saldo disponível
        if order.side == OrderSide.BUY:
            estimated_cost = order.quantity * (order.price or market_price)
            estimated_commission = estimated_cost * self.commission_rate
            total_cost = estimated_cost + estimated_commission
            
            if total_cost > self.balance:
                logger.error(f"Saldo insuficiente: ${self.balance:.2f} < ${total_cost:.2f}")
                return False
                
        # Para venda, verificar se temos posição
        elif order.side == OrderSide.SELL:
            if order.symbol not in self.positions:
                logger.error(f"Posição não encontrada para {order.symbol}")
                return False
                
            if self.positions[order.symbol].quantity < order.quantity:
                logger.error(f"Quantidade insuficiente em posição")
                return False
                
        return True
        
    async def _execute_market_order(self, order: Order):
        """Executa ordem a mercado"""
        
        market_price = self.current_prices[order.symbol]
        
        # Simular slippage
        if order.side == OrderSide.BUY:
            execution_price = market_price * (1 + self.slippage_rate)
        else:
            execution_price = market_price * (1 - self.slippage_rate)
            
        # Calcular custos
        total_value = order.quantity * execution_price
        commission = total_value * self.commission_rate
        
        # Atualizar ordem
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_price = execution_price
        order.commission = commission
        order.filled_at = datetime.now()
        order.updated_at = datetime.now()
        
        # Atualizar posição e saldo
        if order.side == OrderSide.BUY:
            self.balance -= (total_value + commission)
            await self._open_position(order)
        else:
            self.balance += (total_value - commission)
            await self._close_position(order)
            
        # Mover para histórico
        self.order_history.append(order)
        del self.orders[order.order_id]
        
        # Registrar trade
        trade_data = {
            'timestamp': order.filled_at,
            'symbol': order.symbol,
            'side': order.side.value,
            'quantity': order.quantity,
            'price': execution_price,
            'commission': commission,
            'balance_before': self.balance + (total_value + commission) if order.side == OrderSide.BUY else self.balance - (total_value - commission),
            'balance_after': self.balance
        }
        
        self.trades.append(trade_data)
        
        # Salvar no banco de dados
        await self._save_trade_to_db(trade_data)
        
        logger.info(f"✅ Ordem executada: {order.order_id} | {order.side.value} {order.quantity} {order.symbol} @ ${execution_price:.2f}")
        
    async def _open_position(self, order: Order):
        """Abre ou adiciona a uma posição"""
        
        if order.symbol in self.positions:
            # Adicionar à posição existente
            pos = self.positions[order.symbol]
            new_quantity = pos.quantity + order.filled_quantity
            new_entry = ((pos.entry_price * pos.quantity) + (order.avg_price * order.filled_quantity)) / new_quantity
            pos.quantity = new_quantity
            pos.entry_price = new_entry
        else:
            # Criar nova posição
            self.positions[order.symbol] = Position(
                symbol=order.symbol,
                quantity=order.filled_quantity,
                entry_price=order.avg_price,
                current_price=order.avg_price,
                side=order.side
            )
            
        logger.info(f"📈 Posição aberta/aumentada: {order.symbol}")
        
    async def _close_position(self, order: Order):
        """Fecha ou reduz uma posição"""
        
        if order.symbol not in self.positions:
            logger.error(f"Tentativa de fechar posição inexistente: {order.symbol}")
            return
            
        pos = self.positions[order.symbol]
        
        # Calcular PnL realizado
        realized_pnl = (order.avg_price - pos.entry_price) * order.filled_quantity
        pos.realized_pnl += realized_pnl
        
        # Reduzir ou fechar posição
        pos.quantity -= order.filled_quantity
        
        if pos.quantity <= 0.0001:  # Praticamente zero
            logger.info(f"📉 Posição fechada: {order.symbol} | PnL: ${pos.realized_pnl:.2f}")
            del self.positions[order.symbol]
        else:
            logger.info(f"📉 Posição reduzida: {order.symbol} | Restante: {pos.quantity:.6f}")
            
    async def _check_pending_orders(self, symbol: str, current_price: float):
        """Verifica ordens pendentes que devem ser executadas"""
        
        for order_id, order in list(self.orders.items()):
            if order.symbol != symbol:
                continue
                
            should_execute = False
            
            # Stop Loss
            if order.type == OrderType.STOP_LOSS:
                if order.side == OrderSide.SELL and current_price <= order.stop_price:
                    should_execute = True
                elif order.side == OrderSide.BUY and current_price >= order.stop_price:
                    should_execute = True
                    
            # Limit Order
            elif order.type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and current_price <= order.price:
                    should_execute = True
                elif order.side == OrderSide.SELL and current_price >= order.price:
                    should_execute = True
                    
            if should_execute:
                await self._execute_market_order(order)
                
    async def cancel_order(self, order_id: str) -> bool:
        """Cancela uma ordem pendente"""
        
        if order_id not in self.orders:
            logger.error(f"Ordem não encontrada: {order_id}")
            return False
            
        order = self.orders[order_id]
        order.status = OrderStatus.CANCELED
        order.updated_at = datetime.now()
        
        self.order_history.append(order)
        del self.orders[order_id]
        
        logger.info(f"🚫 Ordem cancelada: {order_id}")
        return True
        
    def get_account_summary(self) -> Dict:
        """Retorna resumo da conta"""
        
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_realized_pnl = sum(pos.realized_pnl for pos in self.positions.values())
        
        equity = self.balance + sum(
            pos.quantity * pos.current_price 
            for pos in self.positions.values()
        )
        
        return {
            'balance': self.balance,
            'equity': equity,
            'initial_balance': self.initial_balance,
            'total_pnl': equity - self.initial_balance,
            'total_pnl_percent': ((equity - self.initial_balance) / self.initial_balance) * 100,
            'unrealized_pnl': total_unrealized_pnl,
            'realized_pnl': total_realized_pnl,
            'open_positions': len(self.positions),
            'active_orders': len(self.orders),
            'total_trades': len(self.trades)
        }
        
    def get_all_positions(self) -> List[Dict]:
        """Retorna todas as posições abertas"""
        return [pos.to_dict() for pos in self.positions.values()]
        
    def get_all_orders(self) -> List[Dict]:
        """Retorna todas as ordens ativas"""
        return [order.to_dict() for order in self.orders.values()]
        
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Retorna histórico de trades"""
        return self.trades[-limit:]


# Teste
async def test_order_manager():
    """Teste básico do Order Manager"""
    
    manager = OrderManager(initial_balance=10000.0)
    
    # Simular preço de mercado
    manager.update_market_price('BTCUSDT', 40000.0)
    
    # Criar ordem de compra
    buy_order = await manager.create_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    
    print(f"\n📊 Conta após compra:")
    print(manager.get_account_summary())
    print(f"\n📈 Posições: {manager.get_all_positions()}")
    
    # Simular mudança de preço
    await asyncio.sleep(1)
    manager.update_market_price('BTCUSDT', 41000.0)
    
    print(f"\n📊 Conta após valorização:")
    print(manager.get_account_summary())
    
    # Criar ordem de venda
    sell_order = await manager.create_order(
        symbol='BTCUSDT',
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    
    print(f"\n📊 Conta após venda:")
    print(manager.get_account_summary())
    print(f"\n💰 Histórico de trades: {manager.get_trade_history()}")


if __name__ == "__main__":
    print("🧪 Testando Order Manager...")
    asyncio.run(test_order_manager())
