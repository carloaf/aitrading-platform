"""
Live Trading Test Module - Binance Testnet Integration
======================================================

Este módulo implementa integração com Binance Testnet para testes de trading.
NÃO executa ordens reais - apenas simula e valida conectividade.

Features:
- Conexão com Binance Testnet API
- Validação de credenciais
- Simulação de ordens (dry-run)
- Logs de auditoria completos
- Kill switch de emergência
- Monitoramento de latência

Uso:
    client = BinanceTestnetClient(api_key, api_secret)
    await client.connect()
    result = await client.test_order(symbol="BTCUSDT", side="BUY", quantity=0.001)
"""

import asyncio
import hmac
import hashlib
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
import aiohttp
from collections import deque
import os

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


class TradingMode(str, Enum):
    TESTNET = "testnet"      # Binance Testnet (ordens reais em ambiente de teste)
    DRY_RUN = "dry_run"      # Simulação local sem conexão
    PAPER = "paper"          # Paper trading com dados reais


@dataclass
class TestOrderResult:
    """Resultado de uma ordem de teste"""
    success: bool
    order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    quantity: float = 0.0
    price: Optional[float] = None
    executed_qty: float = 0.0
    status: str = "PENDING"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    mode: str = "dry_run"
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class AuditLogEntry:
    """Entrada de log de auditoria"""
    timestamp: datetime
    action: str
    symbol: Optional[str]
    side: Optional[str]
    quantity: Optional[float]
    price: Optional[float]
    result: str
    latency_ms: float
    mode: str
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


class BinanceTestnetClient:
    """
    Cliente para Binance Testnet
    
    Endpoints:
    - Spot Testnet: https://testnet.binance.vision
    - Futures Testnet: https://testnet.binancefuture.com
    
    Nota: Requer credenciais de testnet (diferentes de produção)
    Obter em: https://testnet.binance.vision/
    """
    
    # URLs
    TESTNET_SPOT_URL = "https://testnet.binance.vision"
    TESTNET_FUTURES_URL = "https://testnet.binancefuture.com"
    PRODUCTION_URL = "https://api.binance.com"  # Apenas para dados públicos
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        mode: TradingMode = TradingMode.DRY_RUN,
        max_audit_entries: int = 1000
    ):
        self.api_key = api_key or os.getenv("BINANCE_TESTNET_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_TESTNET_API_SECRET", "")
        self.mode = mode
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Estado
        self.connected = False
        self.last_ping_ms: float = 0.0
        self.server_time_offset: int = 0
        
        # Auditoria
        self.audit_log: deque = deque(maxlen=max_audit_entries)
        
        # Kill switch
        self.kill_switch_active = False
        self.kill_switch_reason: Optional[str] = None
        
        # Estatísticas
        self.stats = {
            'total_test_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'total_latency_ms': 0.0,
            'connection_errors': 0,
            'last_error': None
        }
        
        # Limites de segurança
        self.max_order_value_usd = 1000.0  # Limite máximo por ordem
        self.max_daily_orders = 100        # Limite diário de ordens
        self.daily_orders_count = 0
        self.daily_reset_time = datetime.utcnow()
        
        logger.info(f"🔧 BinanceTestnetClient inicializado em modo: {mode.value}")
    
    async def connect(self) -> bool:
        """Estabelece conexão e valida credenciais"""
        try:
            self.session = aiohttp.ClientSession()
            
            # 1. Testar conectividade básica
            ping_result = await self._ping()
            if not ping_result:
                raise ConnectionError("Falha no ping inicial")
            
            # 2. Sincronizar tempo do servidor
            await self._sync_server_time()
            
            # 3. Validar credenciais (se fornecidas)
            if self.api_key and self.api_secret and self.mode == TradingMode.TESTNET:
                account_valid = await self._validate_credentials()
                if not account_valid:
                    logger.warning("⚠️ Credenciais inválidas - operando em modo DRY_RUN")
                    self.mode = TradingMode.DRY_RUN
            
            self.connected = True
            self._log_audit("CONNECT", result="SUCCESS", details={
                'mode': self.mode.value,
                'latency_ms': self.last_ping_ms
            })
            
            logger.info(f"✅ Conectado ao Binance ({self.mode.value}) - Latência: {self.last_ping_ms:.2f}ms")
            return True
            
        except Exception as e:
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"❌ Erro de conexão: {e}")
            self._log_audit("CONNECT", result="FAILED", details={'error': str(e)})
            return False
    
    async def disconnect(self):
        """Fecha conexão"""
        if self.session:
            await self.session.close()
            self.session = None
        self.connected = False
        self._log_audit("DISCONNECT", result="SUCCESS")
        logger.info("🔌 Desconectado do Binance")
    
    async def _ping(self) -> bool:
        """Testa latência da conexão"""
        url = f"{self.PRODUCTION_URL}/api/v3/ping"
        start = time.time()
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    self.last_ping_ms = (time.time() - start) * 1000
                    return True
        except Exception as e:
            logger.error(f"Ping falhou: {e}")
        return False
    
    async def _sync_server_time(self):
        """Sincroniza com tempo do servidor Binance"""
        url = f"{self.PRODUCTION_URL}/api/v3/time"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    server_time = data['serverTime']
                    local_time = int(time.time() * 1000)
                    self.server_time_offset = server_time - local_time
                    logger.debug(f"⏱️ Offset de tempo: {self.server_time_offset}ms")
        except Exception as e:
            logger.warning(f"Falha ao sincronizar tempo: {e}")
    
    async def _validate_credentials(self) -> bool:
        """Valida credenciais de API no testnet"""
        try:
            url = f"{self.TESTNET_SPOT_URL}/api/v3/account"
            timestamp = int(time.time() * 1000) + self.server_time_offset
            
            params = f"timestamp={timestamp}"
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                params.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            headers = {'X-MBX-APIKEY': self.api_key}
            full_url = f"{url}?{params}&signature={signature}"
            
            async with self.session.get(full_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Credenciais válidas - Conta: {len(data.get('balances', []))} ativos")
                    return True
                else:
                    error = await response.text()
                    logger.warning(f"⚠️ Validação falhou: {error}")
                    return False
                    
        except Exception as e:
            logger.error(f"Erro ao validar credenciais: {e}")
            return False
    
    def _generate_signature(self, params: str) -> str:
        """Gera assinatura HMAC-SHA256"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _log_audit(
        self,
        action: str,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        result: str = "UNKNOWN",
        latency_ms: float = 0.0,
        details: Dict = None
    ):
        """Registra entrada no log de auditoria"""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow(),
            action=action,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            result=result,
            latency_ms=latency_ms,
            mode=self.mode.value,
            details=details or {}
        )
        self.audit_log.append(entry)
    
    # ====================
    # KILL SWITCH
    # ====================
    
    def activate_kill_switch(self, reason: str = "Manual activation"):
        """Ativa kill switch de emergência - bloqueia todas as operações"""
        self.kill_switch_active = True
        self.kill_switch_reason = reason
        self._log_audit("KILL_SWITCH_ACTIVATED", result="ACTIVE", details={'reason': reason})
        logger.critical(f"🚨 KILL SWITCH ATIVADO: {reason}")
    
    def deactivate_kill_switch(self):
        """Desativa kill switch"""
        self.kill_switch_active = False
        self.kill_switch_reason = None
        self._log_audit("KILL_SWITCH_DEACTIVATED", result="INACTIVE")
        logger.info("✅ Kill switch desativado")
    
    def _check_kill_switch(self) -> bool:
        """Verifica se kill switch está ativo"""
        if self.kill_switch_active:
            logger.warning(f"⛔ Operação bloqueada - Kill switch ativo: {self.kill_switch_reason}")
            return True
        return False
    
    # ====================
    # MARKET DATA
    # ====================
    
    async def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Obtém preço atual do símbolo"""
        url = f"{self.PRODUCTION_URL}/api/v3/ticker/price"
        try:
            async with self.session.get(url, params={'symbol': symbol}) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['price'])
        except Exception as e:
            logger.error(f"Erro ao obter preço: {e}")
        return None
    
    async def get_exchange_info(self, symbol: str) -> Optional[Dict]:
        """Obtém informações do par de trading"""
        url = f"{self.PRODUCTION_URL}/api/v3/exchangeInfo"
        try:
            async with self.session.get(url, params={'symbol': symbol}) as response:
                if response.status == 200:
                    data = await response.json()
                    for s in data.get('symbols', []):
                        if s['symbol'] == symbol:
                            return s
        except Exception as e:
            logger.error(f"Erro ao obter exchange info: {e}")
        return None
    
    # ====================
    # ORDER TESTING
    # ====================
    
    async def test_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType = OrderType.MARKET,
        quantity: float = 0.0,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> TestOrderResult:
        """
        Testa uma ordem sem executar de verdade
        
        Args:
            symbol: Par de trading (ex: BTCUSDT)
            side: BUY ou SELL
            order_type: Tipo da ordem
            quantity: Quantidade do ativo base
            price: Preço (para ordens LIMIT)
            stop_price: Preço de stop (para ordens STOP)
        
        Returns:
            TestOrderResult com detalhes da simulação
        """
        start_time = time.time()
        
        # 1. Verificar kill switch
        if self._check_kill_switch():
            return TestOrderResult(
                success=False,
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                error_message=f"Kill switch ativo: {self.kill_switch_reason}",
                mode=self.mode.value
            )
        
        # 2. Verificar limites diários
        if not self._check_daily_limits():
            return TestOrderResult(
                success=False,
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                error_message="Limite diário de ordens atingido",
                mode=self.mode.value
            )
        
        # 3. Obter preço atual
        current_price = await self.get_ticker_price(symbol)
        if not current_price:
            return TestOrderResult(
                success=False,
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                error_message="Não foi possível obter preço atual",
                mode=self.mode.value
            )
        
        # 4. Validar ordem
        order_value = quantity * (price or current_price)
        if order_value > self.max_order_value_usd:
            return TestOrderResult(
                success=False,
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                price=price,
                error_message=f"Valor da ordem (${order_value:.2f}) excede limite de ${self.max_order_value_usd}",
                mode=self.mode.value
            )
        
        # 5. Executar teste conforme modo
        result = await self._execute_test_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            current_price=current_price
        )
        
        # 6. Calcular latência e atualizar estatísticas
        latency = (time.time() - start_time) * 1000
        result.latency_ms = latency
        
        self.stats['total_test_orders'] += 1
        self.stats['total_latency_ms'] += latency
        if result.success:
            self.stats['successful_orders'] += 1
        else:
            self.stats['failed_orders'] += 1
        
        self.daily_orders_count += 1
        
        # 7. Log de auditoria
        self._log_audit(
            action="TEST_ORDER",
            symbol=symbol,
            side=side.value,
            quantity=quantity,
            price=price or current_price,
            result="SUCCESS" if result.success else "FAILED",
            latency_ms=latency,
            details={
                'order_type': order_type.value,
                'order_value_usd': order_value,
                'current_price': current_price,
                'error': result.error_message
            }
        )
        
        return result
    
    async def _execute_test_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float],
        stop_price: Optional[float],
        current_price: float
    ) -> TestOrderResult:
        """Executa ordem de teste conforme modo"""
        
        if self.mode == TradingMode.DRY_RUN:
            # Simulação local - não envia nada
            return TestOrderResult(
                success=True,
                order_id=f"DRY-{int(time.time()*1000)}",
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                price=price or current_price,
                executed_qty=quantity,  # Assume execução total
                status="FILLED",
                mode="dry_run"
            )
        
        elif self.mode == TradingMode.TESTNET:
            # Envia para Binance Testnet (endpoint de teste)
            return await self._send_testnet_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price
            )
        
        elif self.mode == TradingMode.PAPER:
            # Paper trading com dados reais
            return TestOrderResult(
                success=True,
                order_id=f"PAPER-{int(time.time()*1000)}",
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                price=current_price,
                executed_qty=quantity,
                status="SIMULATED",
                mode="paper"
            )
        
        return TestOrderResult(
            success=False,
            error_message=f"Modo desconhecido: {self.mode}"
        )
    
    async def _send_testnet_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float],
        stop_price: Optional[float]
    ) -> TestOrderResult:
        """Envia ordem de teste para Binance Testnet"""
        try:
            url = f"{self.TESTNET_SPOT_URL}/api/v3/order/test"
            timestamp = int(time.time() * 1000) + self.server_time_offset
            
            # Montar parâmetros
            params = {
                'symbol': symbol,
                'side': side.value,
                'type': order_type.value,
                'quantity': quantity,
                'timestamp': timestamp
            }
            
            if price and order_type in [OrderType.LIMIT, OrderType.STOP_LOSS_LIMIT, OrderType.TAKE_PROFIT_LIMIT]:
                params['price'] = price
                params['timeInForce'] = 'GTC'
            
            if stop_price and order_type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_LIMIT, OrderType.TAKE_PROFIT, OrderType.TAKE_PROFIT_LIMIT]:
                params['stopPrice'] = stop_price
            
            # Gerar assinatura
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            signature = self._generate_signature(query_string)
            params['signature'] = signature
            
            # Enviar requisição
            headers = {'X-MBX-APIKEY': self.api_key}
            
            async with self.session.post(url, params=params, headers=headers) as response:
                if response.status == 200:
                    # Endpoint /order/test retorna {} em caso de sucesso
                    return TestOrderResult(
                        success=True,
                        order_id=f"TESTNET-{timestamp}",
                        symbol=symbol,
                        side=side.value,
                        order_type=order_type.value,
                        quantity=quantity,
                        price=price,
                        status="TEST_PASSED",
                        mode="testnet"
                    )
                else:
                    error = await response.json()
                    return TestOrderResult(
                        success=False,
                        symbol=symbol,
                        side=side.value,
                        order_type=order_type.value,
                        quantity=quantity,
                        price=price,
                        status="REJECTED",
                        error_message=f"Binance error: {error.get('msg', 'Unknown')}",
                        mode="testnet"
                    )
                    
        except Exception as e:
            return TestOrderResult(
                success=False,
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                error_message=str(e),
                mode="testnet"
            )
    
    def _check_daily_limits(self) -> bool:
        """Verifica limites diários"""
        # Reset diário
        now = datetime.utcnow()
        if now.date() > self.daily_reset_time.date():
            self.daily_orders_count = 0
            self.daily_reset_time = now
        
        return self.daily_orders_count < self.max_daily_orders
    
    # ====================
    # STATUS & STATS
    # ====================
    
    def get_status(self) -> Dict:
        """Retorna status completo do cliente"""
        avg_latency = (
            self.stats['total_latency_ms'] / self.stats['total_test_orders']
            if self.stats['total_test_orders'] > 0 else 0
        )
        
        return {
            'connected': self.connected,
            'mode': self.mode.value,
            'kill_switch': {
                'active': self.kill_switch_active,
                'reason': self.kill_switch_reason
            },
            'latency_ms': self.last_ping_ms,
            'avg_latency_ms': avg_latency,
            'server_time_offset_ms': self.server_time_offset,
            'statistics': {
                **self.stats,
                'success_rate': (
                    self.stats['successful_orders'] / self.stats['total_test_orders'] * 100
                    if self.stats['total_test_orders'] > 0 else 0
                )
            },
            'limits': {
                'max_order_value_usd': self.max_order_value_usd,
                'max_daily_orders': self.max_daily_orders,
                'daily_orders_used': self.daily_orders_count,
                'daily_orders_remaining': self.max_daily_orders - self.daily_orders_count
            },
            'credentials_configured': bool(self.api_key and self.api_secret)
        }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Retorna últimas entradas do log de auditoria"""
        entries = list(self.audit_log)[-limit:]
        return [e.to_dict() for e in entries]
    
    async def run_connectivity_test(self) -> Dict:
        """Executa teste completo de conectividade"""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'tests': {},
            'overall_status': 'UNKNOWN'
        }
        
        # 1. Ping test
        ping_ok = await self._ping()
        results['tests']['ping'] = {
            'status': 'PASS' if ping_ok else 'FAIL',
            'latency_ms': self.last_ping_ms
        }
        
        # 2. Server time sync
        try:
            await self._sync_server_time()
            results['tests']['time_sync'] = {
                'status': 'PASS',
                'offset_ms': self.server_time_offset
            }
        except Exception as e:
            results['tests']['time_sync'] = {
                'status': 'FAIL',
                'error': str(e)
            }
        
        # 3. Ticker price test
        price = await self.get_ticker_price('BTCUSDT')
        results['tests']['ticker'] = {
            'status': 'PASS' if price else 'FAIL',
            'btcusdt_price': price
        }
        
        # 4. Exchange info test
        info = await self.get_exchange_info('BTCUSDT')
        results['tests']['exchange_info'] = {
            'status': 'PASS' if info else 'FAIL',
            'symbol_status': info.get('status') if info else None
        }
        
        # 5. Credentials test (se configuradas)
        if self.api_key and self.api_secret:
            creds_ok = await self._validate_credentials()
            results['tests']['credentials'] = {
                'status': 'PASS' if creds_ok else 'FAIL'
            }
        else:
            results['tests']['credentials'] = {
                'status': 'SKIPPED',
                'reason': 'No credentials configured'
            }
        
        # Determinar status geral
        passed = sum(1 for t in results['tests'].values() if t['status'] == 'PASS')
        total = sum(1 for t in results['tests'].values() if t['status'] != 'SKIPPED')
        
        if passed == total:
            results['overall_status'] = 'HEALTHY'
        elif passed > 0:
            results['overall_status'] = 'DEGRADED'
        else:
            results['overall_status'] = 'UNHEALTHY'
        
        results['summary'] = f"{passed}/{total} tests passed"
        
        return results


# ====================
# SINGLETON INSTANCE
# ====================

_live_trading_client: Optional[BinanceTestnetClient] = None

def get_live_trading_client() -> BinanceTestnetClient:
    """Retorna instância singleton do cliente"""
    global _live_trading_client
    if _live_trading_client is None:
        _live_trading_client = BinanceTestnetClient(mode=TradingMode.DRY_RUN)
    return _live_trading_client

async def initialize_live_trading(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    mode: TradingMode = TradingMode.DRY_RUN
) -> BinanceTestnetClient:
    """Inicializa cliente de live trading"""
    global _live_trading_client
    _live_trading_client = BinanceTestnetClient(
        api_key=api_key,
        api_secret=api_secret,
        mode=mode
    )
    await _live_trading_client.connect()
    return _live_trading_client
