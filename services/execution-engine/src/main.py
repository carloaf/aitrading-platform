"""
FastAPI Main - REST API para Execution Engine
Endpoints para controlar paper trading e monitorar performance
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import asyncio
import os
import numpy as np

from order_manager import OrderManager, OrderSide, OrderType
from strategy_executor import StrategyExecutor
from auto_strategy_selector import AutoStrategySelector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


# Models
class StartPaperTradingRequest(BaseModel):
    session_id: str
    strategy_name: str
    strategy_parameters: Dict
    symbol: str = "BTCUSDT"
    timeframe: str = "1m"
    initial_balance: float = 10000.0
    commission_rate: float = 0.001
    slippage_rate: float = 0.0005


class ManualOrderRequest(BaseModel):
    session_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str  # "MARKET", "LIMIT", etc
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None


# Endpoints
@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "execution-engine",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(executors)
    }


# ==========================================
# MARKET REGIME DETECTOR
# ==========================================

class MarketRegimeRequest(BaseModel):
    """Requisição para detectar regime de mercado"""
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    lookback_days: int = 90  # Período para análise


@app.post("/api/market-regime/detect")
async def detect_market_regime(request: MarketRegimeRequest):
    """
    Detecta automaticamente o regime de mercado (Bull/Bear/Sideways/Volatile)
    
    Analisa múltiplos indicadores técnicos e retorna:
    - Regime detectado
    - Confiança da classificação
    - Força da tendência
    - Volatilidade
    - Estratégias recomendadas
    """
    import asyncpg
    from market_regime_detector import MarketRegimeDetector
    from datetime import timedelta
    
    try:
        logger.info(f"🔍 Detectando regime de mercado: {request.symbol} ({request.interval})")
        
        # 1. Buscar dados históricos do TimescaleDB
        conn_string = os.getenv('TIMESCALE_URL', 
            'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market')
        
        conn = await asyncpg.connect(conn_string)
        
        # Calcular data inicial
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
        
        if len(rows) < 200:
            raise HTTPException(
                status_code=400, 
                detail=f"Dados insuficientes: {len(rows)} candles. Mínimo: 200"
            )
        
        # 2. Converter para DataFrame
        import pandas as pd
        df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        logger.info(f"📊 {len(df)} candles carregados ({df['timestamp'].min()} a {df['timestamp'].max()})")
        
        # 3. Executar detecção de regime
        detector = MarketRegimeDetector()
        analysis = detector.analyze(df)
        
        result = analysis.to_dict()
        
        # Adicionar informações adicionais
        result['metadata'] = {
            'symbol': request.symbol,
            'interval': request.interval,
            'lookback_days': request.lookback_days,
            'candles_analyzed': len(df),
            'analysis_date': datetime.utcnow().isoformat(),
            'price_current': float(df['close'].iloc[-1]),
            'price_7d_ago': float(df['close'].iloc[-7]) if len(df) >= 7 else None,
            'price_30d_ago': float(df['close'].iloc[-30]) if len(df) >= 30 else None
        }
        
        logger.info(f"✅ Regime detectado: {result['regime']} ({result['confidence']:.1f}% confiança)")
        
        return result
        
    except asyncpg.PostgresError as e:
        logger.error(f"Erro no banco de dados: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")
    except Exception as e:
        logger.error(f"Erro na detecção de regime: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    """Request para backtest da estratégia RSI Divergence"""
    symbol: str = "BTCUSDT"
    start_date: str = "2023-01-01"
    end_date: str = "2024-01-01"
    initial_capital: float = 100000.0
    timeframe: str = "1h"  # Suporte multi-timeframe: 15m, 1h, 4h, 1d
    # Parâmetros da estratégia
    rsi_period: int = 14
    lookback_periods: int = 20
    min_adx_trend: int = 20
    stop_loss_atr_mult: float = 2.0
    take_profit_atr_mult: float = 4.0
    min_signal_strength: float = 0.5


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
        
        # Criar estratégia com parâmetros
        strategy_params = {
            'rsi_period': request.rsi_period,
            'lookback_periods': request.lookback_periods,
            'min_adx_trend': request.min_adx_trend,
            'stop_loss_atr_mult': request.stop_loss_atr_mult,
            'take_profit_atr_mult': request.take_profit_atr_mult,
            'min_signal_strength': request.min_signal_strength
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


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8001))
    
    logger.info(f"🚀 Iniciando Execution Engine na porta {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
