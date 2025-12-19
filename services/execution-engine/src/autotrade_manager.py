"""
AutoTrade Manager - Gerenciamento de sinais e trades do AutoTrade
Integração completa com banco de dados TimescaleDB
"""

import asyncpg
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AutoTradeSignalData:
    """Estrutura de dados para um sinal do AutoTrade"""
    symbol: str
    direction: str  # 'BUY' ou 'SELL'
    signal_type: str
    strength: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: Optional[float] = None
    timeframe: str = '1h'
    
    # Indicadores técnicos
    rsi: Optional[float] = None
    adx: Optional[float] = None
    volume: Optional[float] = None
    volatility: Optional[float] = None
    
    # Regime de mercado
    market_regime: Optional[str] = None
    regime_confidence: Optional[float] = None
    
    # Motivo da decisão
    reason: Optional[str] = None


class AutoTradeManager:
    """
    Gerencia a persistência e análise de sinais/trades do AutoTrade
    """
    
    def __init__(self, db_host: str = "timescaledb", db_port: int = 5432,
                 db_name: str = "crypto_market", db_user: str = "crypto_user",
                 db_password: str = "crypto_pass"):
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.db_conn: Optional[asyncpg.Connection] = None
        
    async def connect(self):
        """Conecta ao banco de dados"""
        try:
            self.db_conn = await asyncpg.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            logger.info(f"✅ AutoTradeManager conectado ao banco {self.db_name}")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao banco: {e}")
            raise
    
    async def disconnect(self):
        """Desconecta do banco de dados"""
        if self.db_conn:
            await self.db_conn.close()
            logger.info("🔌 AutoTradeManager desconectado do banco")
    
    async def create_session(self, session_id: str, mode: str = 'DRY_RUN',
                           initial_capital: float = 10000.0,
                           min_strength: float = 0.5,
                           symbols: List[str] = None,
                           timeframe: str = '1h') -> bool:
        """
        Cria uma nova sessão de AutoTrade
        
        Returns:
            True se criada com sucesso, False se já existe
        """
        try:
            query = """
                INSERT INTO autotrade_sessions 
                (session_id, mode, initial_capital, current_balance, min_strength, symbols, timeframe)
                VALUES ($1, $2, $3, $3, $4, $5, $6)
                ON CONFLICT (session_id) DO NOTHING
                RETURNING id
            """
            
            result = await self.db_conn.fetchval(
                query,
                session_id,
                mode,
                initial_capital,
                min_strength,
                symbols or [],
                timeframe
            )
            
            if result:
                logger.info(f"✅ Sessão AutoTrade criada: {session_id} ({mode})")
                return True
            else:
                logger.warning(f"⚠️ Sessão já existe: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar sessão: {e}")
            return False
    
    async def save_signal(self, session_id: str, signal_data: AutoTradeSignalData,
                         processed: bool = False, executed: bool = False) -> Optional[str]:
        """
        Salva um sinal no banco de dados
        
        Returns:
            signal_id se salvo com sucesso, None caso contrário
        """
        try:
            signal_id = f"sig_{uuid.uuid4().hex[:12]}"
            
            query = """
                INSERT INTO autotrade_signals (
                    signal_id, session_id, symbol, timeframe, signal_type, direction,
                    strength, entry_price, stop_loss, take_profit, current_price,
                    rsi, adx, volume, volatility,
                    market_regime, regime_confidence,
                    processed, executed, reason,
                    min_strength_threshold, dry_run
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                    $16, $17, $18, $19, $20, $21, $22
                )
                RETURNING id
            """
            
            # Determinar dry_run do modo da sessão
            session_mode = await self.db_conn.fetchval(
                "SELECT mode FROM autotrade_sessions WHERE session_id = $1", 
                session_id
            )
            dry_run = session_mode == 'DRY_RUN'
            
            # Pegar min_strength da sessão
            min_strength = await self.db_conn.fetchval(
                "SELECT min_strength FROM autotrade_sessions WHERE session_id = $1",
                session_id
            )
            
            result = await self.db_conn.fetchval(
                query,
                signal_id, session_id, signal_data.symbol, signal_data.timeframe,
                signal_data.signal_type, signal_data.direction, signal_data.strength,
                signal_data.entry_price, signal_data.stop_loss, signal_data.take_profit,
                signal_data.current_price, signal_data.rsi, signal_data.adx,
                signal_data.volume, signal_data.volatility, signal_data.market_regime,
                signal_data.regime_confidence, processed, executed, signal_data.reason,
                min_strength, dry_run
            )
            
            if result:
                logger.info(f"💾 Sinal salvo: {signal_id} - {signal_data.symbol} {signal_data.direction}")
                
                # Atualizar contadores da sessão
                await self.db_conn.execute(
                    """
                    UPDATE autotrade_sessions 
                    SET total_signals_processed = total_signals_processed + 1,
                        updated_at = NOW()
                    WHERE session_id = $1
                    """,
                    session_id
                )
                
                return signal_id
            else:
                logger.error("❌ Erro ao salvar sinal: nenhum ID retornado")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao salvar sinal: {e}")
            return None
    
    async def update_signal_execution(self, signal_id: str, executed: bool,
                                     reason: str, trade_id: Optional[int] = None):
        """Atualiza o status de execução de um sinal"""
        try:
            query = """
                UPDATE autotrade_signals
                SET executed = $1, reason = $2, paper_trading_trade_id = $3, updated_at = NOW()
                WHERE signal_id = $4
            """
            
            await self.db_conn.execute(query, executed, reason, trade_id, signal_id)
            
            # Se foi executado, incrementar contador de trades
            if executed:
                session_id = await self.db_conn.fetchval(
                    "SELECT session_id FROM autotrade_signals WHERE signal_id = $1",
                    signal_id
                )
                await self.db_conn.execute(
                    """
                    UPDATE autotrade_sessions
                    SET total_trades_executed = total_trades_executed + 1,
                        updated_at = NOW()
                    WHERE session_id = $1
                    """,
                    session_id
                )
            
            logger.info(f"✅ Sinal atualizado: {signal_id} - Executado: {executed}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar sinal: {e}")
    
    async def stop_session(self, session_id: str):
        """Marca uma sessão como finalizada e atualiza estatísticas"""
        try:
            # Atualizar estatísticas finais usando a função SQL
            await self.db_conn.execute(
                "SELECT update_autotrade_session_stats($1)",
                session_id
            )
            
            # Marcar como inativa
            await self.db_conn.execute(
                """
                UPDATE autotrade_sessions
                SET is_active = FALSE, stopped_at = NOW(), updated_at = NOW()
                WHERE session_id = $1
                """,
                session_id
            )
            
            logger.info(f"⏹️ Sessão finalizada: {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar sessão: {e}")
    
    async def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retorna estatísticas da sessão"""
        try:
            query = """
                SELECT * FROM autotrade_performance_summary
                WHERE session_id = $1
            """
            
            row = await self.db_conn.fetchrow(query, session_id)
            
            if row:
                return dict(row)
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar stats: {e}")
            return None
    
    async def get_performance_by_symbol(self, session_id: str) -> List[Dict[str, Any]]:
        """Retorna performance agregada por símbolo"""
        try:
            query = """
                SELECT * FROM autotrade_performance_by_symbol
                WHERE session_id = $1
                ORDER BY total_pnl DESC
            """
            
            rows = await self.db_conn.fetch(query, session_id)
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar performance por símbolo: {e}")
            return []
    
    async def get_performance_by_signal_type(self, session_id: str) -> List[Dict[str, Any]]:
        """Retorna performance agregada por tipo de sinal"""
        try:
            query = """
                SELECT * FROM autotrade_performance_by_signal_type
                WHERE session_id = $1
                ORDER BY total_pnl DESC
            """
            
            rows = await self.db_conn.fetch(query, session_id)
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar performance por tipo: {e}")
            return []
    
    async def get_recent_signals(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna sinais recentes da sessão"""
        try:
            query = """
                SELECT 
                    signal_id, timestamp, symbol, direction, signal_type,
                    strength, entry_price, stop_loss, take_profit,
                    executed, reason, market_regime
                FROM autotrade_signals
                WHERE session_id = $1
                ORDER BY timestamp DESC
                LIMIT $2
            """
            
            rows = await self.db_conn.fetch(query, session_id, limit)
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar sinais recentes: {e}")
            return []
    
    async def link_signal_to_trade(self, signal_id: str, trade_id: int):
        """Vincula um sinal a um trade do paper_trading_trades"""
        try:
            # Atualizar tabela de sinais
            await self.db_conn.execute(
                """
                UPDATE autotrade_signals
                SET paper_trading_trade_id = $1, updated_at = NOW()
                WHERE signal_id = $2
                """,
                trade_id, signal_id
            )
            
            # Atualizar tabela de trades com info do sinal
            signal_data = await self.db_conn.fetchrow(
                """
                SELECT signal_type, strength, market_regime, rsi, adx
                FROM autotrade_signals
                WHERE signal_id = $1
                """,
                signal_id
            )
            
            if signal_data:
                await self.db_conn.execute(
                    """
                    UPDATE paper_trading_trades
                    SET autotrade_signal_id = $1, 
                        signal_type = $2,
                        signal_strength = $3,
                        market_regime = $4,
                        rsi_at_entry = $5,
                        adx_at_entry = $6
                    WHERE id = $7
                    """,
                    signal_id, signal_data['signal_type'], signal_data['strength'],
                    signal_data['market_regime'], signal_data['rsi'], signal_data['adx'],
                    trade_id
                )
            
            logger.info(f"🔗 Sinal {signal_id} vinculado ao trade {trade_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao vincular sinal ao trade: {e}")
