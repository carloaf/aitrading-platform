from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
import ta
from dataclasses import dataclass
import asyncio
import redis.asyncio as redis
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar data providers
try:
    from .data_providers import get_market_data
    logger.info("✅ Data providers carregados")
except Exception as e:
    logger.warning(f"⚠️ Erro ao carregar data providers: {e}")
    # Fallback para implementação simples
    def get_market_data(symbol, start_date, end_date, interval='1d'):
        import yfinance as yf
        return yf.download(symbol, start=start_date, end=end_date, progress=False)

# Importar estratégias profissionais
try:
    from .strategies.strategy_manager import StrategyManager
    from .strategies.base_strategy import BaseStrategy
    strategy_manager = StrategyManager()
    logger.info(f"✅ StrategyManager carregado com {len(strategy_manager.list_strategies())} estratégias")
except Exception as e:
    logger.warning(f"⚠️ Erro ao carregar StrategyManager: {e}")
    strategy_manager = None

# Criar instância FastAPI
app = FastAPI(
    title="Backtesting Engine",
    description="Motor de backtesting para estratégias de trading",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:3000", 
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Configuração Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Modelos Pydantic
class TradingStrategy(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    entry_conditions: List[str]
    exit_conditions: List[str]

class BacktestRequest(BaseModel):
    symbol: str
    strategy: TradingStrategy
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
    commission: float = 0.001  # 0.1%

class Trade(BaseModel):
    entry_date: str
    exit_date: Optional[str] = None
    entry_price: float
    exit_price: Optional[float] = None
    quantity: int
    side: str  # 'buy' or 'sell'
    pnl: Optional[float] = None
    commission_paid: float = 0.0

class BacktestResult(BaseModel):
    strategy_name: str
    symbol: str
    period: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    trades: List[Trade]
    equity_curve: List[Dict[str, Any]]

@dataclass
class BacktestEngine:
    """Motor de backtesting para estratégias de trading"""
    
    def __init__(self):
        self.current_position = 0
        self.current_price = 0
        self.equity = 0
        self.initial_capital = 0
        self.commission = 0.001
        self.trades = []
        self.equity_curve = []
        
    def get_market_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Buscar dados do mercado com fallback para dados simulados"""
        try:
            # Tentar buscar dados reais primeiro
            logger.info(f"Tentando buscar dados reais para {symbol}")
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date, timeout=10)
            
            if data.empty or len(data) == 0:
                logger.warning(f"Nenhum dado real encontrado para {symbol}, gerando dados simulados")
                return self.generate_mock_data(symbol, start_date, end_date)
            
            logger.info(f"Dados reais obtidos para {symbol}: {len(data)} registros")
            # Calcular indicadores técnicos para dados reais
            data = self.add_technical_indicators(data)
            return data
            
        except Exception as e:
            logger.warning(f"Erro ao buscar dados reais para {symbol}: {e}")
            logger.info(f"Gerando dados simulados para {symbol}")
            return self.generate_mock_data(symbol, start_date, end_date)
    
    def add_technical_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Adicionar indicadores técnicos aos dados"""
        try:
            # Médias móveis
            data['SMA_10'] = ta.trend.sma_indicator(data['Close'], window=10)
            data['SMA_20'] = ta.trend.sma_indicator(data['Close'], window=20)
            
            # RSI
            data['RSI'] = ta.momentum.rsi(data['Close'], window=14)
            
            # MACD
            macd = ta.trend.MACD(data['Close'])
            data['MACD'] = macd.macd()
            data['MACD_signal'] = macd.macd_signal()
            
            # Preencher valores NaN
            data = data.bfill().ffill()
            
            return data
        except Exception as e:
            logger.warning(f"Erro ao calcular indicadores técnicos: {e}")
            # Se falhar, retornar dados sem indicadores
            return data
    
    def generate_mock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Gerar dados simulados para demonstração"""
        import random
        import numpy as np
        
        # Converter datas
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # Gerar range de datas
        dates = pd.date_range(start=start, end=end, freq='D')
        dates = [d for d in dates if d.weekday() < 5]  # Apenas dias úteis
        
        # Preço inicial baseado no símbolo
        base_prices = {
            'AAPL': 150, 'MSFT': 300, 'GOOGL': 2500, 'TSLA': 200,
            'AMZN': 3200, 'NVDA': 400, 'META': 250, '^GSPC': 4500,
            '^DJI': 35000, 'BTC-USD': 45000, 'ETH-USD': 3000
        }
        
        initial_price = base_prices.get(symbol, 100)
        
        # Simular dados usando random walk
        prices = [initial_price]
        for i in range(1, len(dates)):
            # Movimento aleatório com tendência ligeiramente positiva
            change = random.gauss(0.001, 0.02)  # 0.1% drift, 2% volatilidade
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, 1))  # Preço mínimo de $1
        
        # Criar DataFrame
        data = pd.DataFrame(index=dates)
        data['Open'] = prices
        data['High'] = [p * (1 + abs(random.gauss(0, 0.01))) for p in prices]
        data['Low'] = [p * (1 - abs(random.gauss(0, 0.01))) for p in prices]
        data['Close'] = [p * (1 + random.gauss(0, 0.005)) for p in prices]
        data['Adj Close'] = data['Close']
        data['Volume'] = [random.randint(1000000, 10000000) for _ in prices]
        
        # Ajustar High/Low para serem consistentes
        for i in range(len(data)):
            high = max(data.iloc[i]['Open'], data.iloc[i]['Close'])
            low = min(data.iloc[i]['Open'], data.iloc[i]['Close'])
            data.iloc[i, data.columns.get_loc('High')] = max(data.iloc[i]['High'], high)
            data.iloc[i, data.columns.get_loc('Low')] = min(data.iloc[i]['Low'], low)
        
        # Adicionar indicadores técnicos
        data = self.add_technical_indicators(data)
        
        logger.info(f"Dados simulados gerados para {symbol}: {len(data)} registros")
        return data
    
    def evaluate_conditions(self, conditions: List[str], row: pd.Series) -> bool:
        """Avaliar condições de entrada/saída"""
        try:
            for condition in conditions:
                # Substituir variáveis na condição
                condition_eval = condition
                for col in row.index:
                    if col in condition_eval:
                        condition_eval = condition_eval.replace(col, str(row[col]))
                
                # Avaliar condição
                if not eval(condition_eval):
                    return False
            return True
        except Exception as e:
            logger.warning(f"Erro ao avaliar condição: {e}")
            return False
    
    def execute_trade(self, side: str, price: float, date: str, quantity: int = None):
        """Executar negociação"""
        if quantity is None:
            # Calcular quantidade baseada no capital disponível
            if side == 'buy':
                quantity = int(self.equity * 0.95 / price)  # 95% do capital
            else:
                quantity = abs(self.current_position)
        
        commission_cost = quantity * price * self.commission
        
        if side == 'buy' and self.current_position <= 0:
            self.current_position = quantity
            self.equity -= (quantity * price + commission_cost)
            
            trade = Trade(
                entry_date=date,
                entry_price=price,
                quantity=quantity,
                side=side,
                commission_paid=commission_cost
            )
            self.trades.append(trade)
            
        elif side == 'sell' and self.current_position > 0:
            # Fechar posição
            pnl = (price - self.trades[-1].entry_price) * quantity - commission_cost
            self.equity += (quantity * price - commission_cost)
            
            # Atualizar último trade
            if self.trades:
                self.trades[-1].exit_date = date
                self.trades[-1].exit_price = price
                self.trades[-1].pnl = pnl
                
            self.current_position = 0
    
    async def run_backtest(self, request: BacktestRequest) -> BacktestResult:
        """Executar backtesting"""
        logger.info(f"Iniciando backtest para {request.symbol}")
        
        try:
            # Inicializar variáveis
            self.initial_capital = request.initial_capital
            self.equity = request.initial_capital
            self.commission = request.commission
            self.current_position = 0
            self.trades = []
            self.equity_curve = []
            
            # Buscar dados históricos
            data = self.get_market_data(
                request.symbol, 
                request.start_date, 
                request.end_date
            )
            
            if data is None or data.empty:
                logger.error(f"Nenhum dado encontrado para {request.symbol}")
                raise Exception(f"Nenhum dado encontrado para {request.symbol}")
            
            logger.info(f"Executando backtest com {len(data)} registros de dados")
            
            # Executar backtest
            for date, row in data.iterrows():
                self.current_price = row['Close']
                
                # Verificar condições de entrada
                if (self.current_position <= 0 and 
                    self.evaluate_conditions(request.strategy.entry_conditions, row)):
                    self.execute_trade('buy', self.current_price, str(date))
                
                # Verificar condições de saída
                elif (self.current_position > 0 and 
                      self.evaluate_conditions(request.strategy.exit_conditions, row)):
                    self.execute_trade('sell', self.current_price, str(date))
                
                # Calcular equity atual
                current_equity = self.equity
                if self.current_position > 0:
                    current_equity += self.current_position * self.current_price
                
                self.equity_curve.append({
                    'date': str(date),
                    'equity': current_equity,
                    'price': self.current_price
                })
            
            # Fechar posição aberta se houver
            if self.current_position > 0:
                self.execute_trade('sell', self.current_price, str(data.index[-1]))
            
            # Calcular métricas
            result = self.calculate_metrics(request)
            logger.info(f"Backtest concluído com {result.total_trades} operações")
            return result
            
        except Exception as e:
            logger.error(f"Erro detalhado no backtest: {str(e)}")
            raise Exception(f"Erro no backtest: {str(e)}")
    
    def calculate_metrics(self, request: BacktestRequest) -> BacktestResult:
        """Calcular métricas de performance"""
        completed_trades = [t for t in self.trades if t.pnl is not None]
        
        if not completed_trades:
            return BacktestResult(
                strategy_name=request.strategy.name,
                symbol=request.symbol,
                period=f"{request.start_date} to {request.end_date}",
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_return=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                profit_factor=0.0,
                trades=self.trades,
                equity_curve=self.equity_curve
            )
        
        # Métricas básicas
        winning_trades = sum(1 for t in completed_trades if t.pnl > 0)
        losing_trades = sum(1 for t in completed_trades if t.pnl <= 0)
        win_rate = winning_trades / len(completed_trades) if completed_trades else 0
        
        # Retorno total
        final_equity = self.equity_curve[-1]['equity'] if self.equity_curve else self.initial_capital
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        # Maximum Drawdown
        peak = self.initial_capital
        max_drawdown = 0
        for point in self.equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            drawdown = (peak - point['equity']) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        # Sharpe Ratio (simplificado)
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_equity = self.equity_curve[i-1]['equity']
            curr_equity = self.equity_curve[i]['equity']
            daily_return = (curr_equity - prev_equity) / prev_equity
            returns.append(daily_return)
        
        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
            # Verificar se é um valor válido para JSON
            if not np.isfinite(sharpe_ratio):
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        # Profit Factor
        gross_profit = sum(t.pnl for t in completed_trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in completed_trades if t.pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.99  # Usar valor alto ao invés de infinito
        
        return BacktestResult(
            strategy_name=request.strategy.name,
            symbol=request.symbol,
            period=f"{request.start_date} to {request.end_date}",
            total_trades=len(completed_trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            trades=self.trades,
            equity_curve=self.equity_curve
        )

# Instância global do motor
engine = BacktestEngine()

@app.get("/")
async def root():
    """Documentação da API"""
    return {
        "service": "AI Trading Platform - Backtesting Engine",
        "version": "1.0.0",
        "description": "Motor de backtesting para estratégias de trading de criptomoedas",
        "endpoints": {
            "health": {
                "method": "GET",
                "path": "/health",
                "description": "Verificar status do serviço"
            },
            "strategies": {
                "method": "GET",
                "path": "/strategies/professional",
                "description": "Listar todas as estratégias profissionais disponíveis"
            },
            "strategy_details": {
                "method": "GET",
                "path": "/strategies/{strategy_name}",
                "description": "Obter detalhes de uma estratégia específica",
                "example": "/strategies/trend_following"
            },
            "backtest": {
                "method": "POST",
                "path": "/strategies/{strategy_name}/backtest",
                "description": "Executar backtest de uma estratégia",
                "parameters": {
                    "symbol": "BTCUSDT, ETHUSDT, etc.",
                    "start_date": "YYYY-MM-DD",
                    "end_date": "YYYY-MM-DD",
                    "initial_capital": "valor inicial (padrão: 10000)"
                },
                "example": "/strategies/trend_following/backtest?symbol=BTCUSDT&start_date=2023-01-01&end_date=2024-01-01&initial_capital=10000"
            },
            "examples": {
                "method": "GET",
                "path": "/strategies/examples",
                "description": "Exemplos de estratégias para referência"
            },
            "symbols": {
                "method": "GET",
                "path": "/symbols/popular",
                "description": "Lista de símbolos populares para trading"
            }
        },
        "available_strategies": [
            "trend_following",
            "mean_reversion",
            "volatility_breakout",
            "macd_rsi_combo",
            "bollinger_bands",
            "momentum",
            "volume_profile",
            "multi_timeframe",
            "dynamic_position_sizing"
        ],
        "documentation": "/docs",
        "interactive_docs": "/redoc"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "backtesting-engine",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.post("/backtest", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest):
    """Executar backtesting de estratégia"""
    try:
        logger.info(f"Recebida requisição de backtest: {request.symbol}")
        result = await engine.run_backtest(request)
        return result
    except Exception as e:
        logger.error(f"Erro no backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/strategies/examples")
async def get_example_strategies():
    """Retornar estratégias de exemplo"""
    strategies = [
        {
            "name": "SMA Crossover",
            "description": "Estratégia baseada em cruzamento de médias móveis",
            "parameters": {"sma_fast": 10, "sma_slow": 20},
            "entry_conditions": ["SMA_10 > SMA_20"],
            "exit_conditions": ["SMA_10 < SMA_20"]
        },
        {
            "name": "RSI Oversold/Overbought",
            "description": "Estratégia baseada no RSI",
            "parameters": {"rsi_oversold": 30, "rsi_overbought": 70},
            "entry_conditions": ["RSI < 30"],
            "exit_conditions": ["RSI > 70"]
        },
        {
            "name": "MACD Signal",
            "description": "Estratégia baseada no MACD",
            "parameters": {},
            "entry_conditions": ["MACD > 0"],
            "exit_conditions": ["MACD < 0"]
        }
    ]
    return {"strategies": strategies}

@app.get("/symbols/popular")
async def get_popular_symbols():
    """Retornar símbolos populares para backtesting"""
    symbols = [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "GOOGL", "name": "Alphabet Inc."},
        {"symbol": "MSFT", "name": "Microsoft Corporation"},
        {"symbol": "TSLA", "name": "Tesla Inc."},
        {"symbol": "BTC-USD", "name": "Bitcoin USD"},
        {"symbol": "ETH-USD", "name": "Ethereum USD"},
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
        {"symbol": "QQQ", "name": "Invesco QQQ Trust"}
    ]
    return {"symbols": symbols}

@app.get("/strategies/professional")
async def get_professional_strategies():
    """
    Retorna todas as estratégias profissionais disponíveis para trading de criptomoedas
    """
    if not strategy_manager:
        raise HTTPException(status_code=500, detail="Strategy Manager não disponível")
    
    try:
        strategies = strategy_manager.list_strategies()
        return {
            "total": len(strategies),
            "strategies": strategies,
            "categories": {
                "trend": ["TrendFollowing"],
                "mean_reversion": ["MeanReversion", "BollingerBands"],
                "volatility": ["VolatilityBreakout"],
                "combo": ["MacdRsiCombo", "MultiTimeframe"],
                "momentum": ["Momentum", "VolumeProfile"],
                "risk_management": ["DynamicPositionSizing"]
            }
        }
    except Exception as e:
        logger.error(f"Erro ao listar estratégias: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/strategies/{strategy_name}")
async def get_strategy_details(strategy_name: str):
    """
    Retorna detalhes completos de uma estratégia específica
    """
    if not strategy_manager:
        raise HTTPException(status_code=500, detail="Strategy Manager não disponível")
    
    try:
        strategy = strategy_manager.get_strategy(strategy_name)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Estratégia '{strategy_name}' não encontrada")
        
        return {
            "name": strategy.name,
            "description": strategy.description,
            "default_parameters": strategy.parameters,
            "risk_per_trade": strategy.risk_per_trade,
            "timeframe": strategy.timeframe
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter estratégia {strategy_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/strategies/{strategy_name}/backtest")
async def backtest_professional_strategy(
    strategy_name: str,
    symbol: str = "BTC-USD",
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 10000.0,
    parameters: Dict[str, Any] = None
):
    """
    Executa backtest de uma estratégia profissional específica
    """
    if not strategy_manager:
        raise HTTPException(status_code=500, detail="Strategy Manager não disponível")
    
    try:
        # Obter estratégia
        strategy = strategy_manager.get_strategy(strategy_name, parameters or {})
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Estratégia '{strategy_name}' não encontrada")
        
        # Datas padrão
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        # Obter dados de mercado usando novo data provider
        logger.info(f"Coletando dados: {symbol} de {start_date} até {end_date}")
        data = get_market_data(symbol, start_date, end_date, interval='1d')
        
        if data.empty or len(data) == 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Sem dados para {symbol}. Tente: BTCUSDT, ETHUSDT, BNBUSDT"
            )
        
        # Preparar dados - padronizar nomes de colunas
        # As estratégias esperam colunas em maiúsculas: Open, High, Low, Close, Volume
        column_mapping = {}
        for col in data.columns:
            col_str = col if isinstance(col, str) else str(col).lower()
            col_lower = col_str.lower()
            
            if 'open' in col_lower:
                column_mapping[col] = 'Open'
            elif 'high' in col_lower:
                column_mapping[col] = 'High'
            elif 'low' in col_lower:
                column_mapping[col] = 'Low'
            elif 'close' in col_lower:
                column_mapping[col] = 'Close'
            elif 'volume' in col_lower:
                column_mapping[col] = 'Volume'
        
        data.rename(columns=column_mapping, inplace=True)
        
        # Garantir que temos as colunas necessárias
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            raise HTTPException(
                status_code=400,
                detail=f"Colunas faltando nos dados: {missing_cols}"
            )
        
        logger.info(f"Dados preparados: {len(data)} candles com colunas {list(data.columns)}")
        
        # Calcular indicadores
        data = strategy.calculate_indicators(data)
        
        # Gerar sinais
        data = strategy.generate_signals(data)
        
        # Simular trades
        capital = initial_capital
        position = 0
        trades = []
        equity_curve = [{"date": start_date, "equity": capital}]
        
        for i in range(1, len(data)):
            current_row = data.iloc[i]
            
            # Entrada
            if current_row.get('signal') == 1 and position == 0:
                position = capital / current_row['Close']
                entry_date = data.index[i].strftime('%Y-%m-%d')
                entry_price = current_row['Close']
                logger.info(f"COMPRA: {position:.4f} @ ${entry_price:.2f}")
                
            # Saída
            elif current_row.get('signal') == -1 and position > 0:
                exit_price = current_row['Close']
                exit_date = data.index[i].strftime('%Y-%m-%d')
                pnl = (exit_price - entry_price) * position
                capital += pnl
                
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "quantity": float(position),
                    "pnl": float(pnl),
                    "pnl_pct": float((exit_price - entry_price) / entry_price * 100)
                })
                
                logger.info(f"VENDA: {position:.4f} @ ${exit_price:.2f} | PnL: ${pnl:.2f}")
                position = 0
            
            # Atualizar equity curve
            current_equity = capital + (position * current_row['Close'] if position > 0 else 0)
            equity_curve.append({
                "date": data.index[i].strftime('%Y-%m-%d'),
                "equity": float(current_equity)
            })
        
        # Calcular métricas
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        total_return = ((capital - initial_capital) / initial_capital) * 100
        
        return {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "period": f"{start_date} até {end_date}",
            "initial_capital": initial_capital,
            "final_capital": float(capital),
            "total_return": float(total_return),
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": len(winning_trades) / len(trades) * 100 if trades else 0,
            "trades": trades[-10:],  # Últimos 10 trades
            "equity_curve": equity_curve[-100:]  # Últimos 100 pontos
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no backtest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/strategies/{strategy_name}/optimize")
async def optimize_strategy(
    strategy_name: str,
    symbol: str = "BTCUSDT",
    start_date: str = "2023-01-01",
    end_date: str = None,
    n_splits: int = 5,
    train_ratio: float = 0.7
):
    """
    Otimiza parâmetros de uma estratégia usando Grid Search com Walk-Forward Analysis
    
    Args:
        strategy_name: Nome da estratégia
        symbol: Símbolo a testar
        start_date: Data inicial
        end_date: Data final
        n_splits: Número de splits para walk-forward
        train_ratio: Proporção de dados para treino
    """
    try:
        # Importar optimizer
        from .optimizer import ParameterOptimizer, create_optimizer_report
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Iniciando otimização de {strategy_name}")
        
        # Obter classe da estratégia
        try:
            strategy_class = strategy_manager.get_strategy_class(strategy_name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        # Definir ranges de parâmetros (exemplo - pode ser customizado)
        param_ranges = {
            'volume_profile': {
                'obv_period': [10, 15, 20, 25, 30]
            },
            'momentum': {
                'roc_period': [5, 10, 15, 20],
                'threshold': [-1.0, 0.0, 1.0, 2.0]
            },
            'macd_rsi_combo': {
                'macd_fast': [8, 12, 16],
                'macd_slow': [21, 26, 31],
                'rsi_lower': [30, 35, 40]
            },
            'volatility_breakout': {
                'atr_period': [10, 14, 18],
                'breakout_multiplier': [1.0, 1.5, 2.0]
            },
            'multi_timeframe': {
                'trend_ema': [40, 50, 60],
                'entry_ema_fast': [15, 20, 25]
            }
        }.get(strategy_name, {})
        
        if not param_ranges:
            # Criar instância temporária para obter parâmetros padrão
            temp_strategy = strategy_class()
            default_params = temp_strategy.parameters
            # Criar ranges simples variando +/- 20%
            param_ranges = {}
            for key, value in default_params.items():
                if isinstance(value, (int, float)) and value > 0:
                    param_ranges[key] = [int(value * 0.8), value, int(value * 1.2)]
        
        logger.info(f"Ranges de parâmetros: {param_ranges}")
        
        # Criar data provider wrapper com padronização de colunas
        def data_provider_wrapper(sym, start, end):
            data = get_market_data(sym, start, end, interval='1d')
            
            # Padronizar nomes de colunas para maiúsculas (Open, High, Low, Close, Volume)
            column_mapping = {}
            for col in data.columns:
                col_str = col if isinstance(col, str) else str(col).lower()
                col_lower = col_str.lower()
                
                if 'open' in col_lower:
                    column_mapping[col] = 'Open'
                elif 'high' in col_lower:
                    column_mapping[col] = 'High'
                elif 'low' in col_lower:
                    column_mapping[col] = 'Low'
                elif 'close' in col_lower:
                    column_mapping[col] = 'Close'
                elif 'volume' in col_lower:
                    column_mapping[col] = 'Volume'
            
            data = data.rename(columns=column_mapping)
            data.index.name = 'Date'
            
            return data
        
        # Criar otimizador
        optimizer = ParameterOptimizer(
            strategy_class=strategy_class,
            data_provider=data_provider_wrapper,
            n_splits=n_splits,
            train_ratio=train_ratio
        )
        
        # Executar otimização
        results = optimizer.optimize_grid_search(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            param_ranges=param_ranges
        )
        
        if not results:
            raise HTTPException(status_code=500, detail="Otimização não retornou resultados")
        
        # Salvar resultados
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"/app/optimization_{strategy_name}_{symbol}_{timestamp}.json"
        optimizer.save_results(results, filename)
        
        # Retornar top 5 resultados
        top_results = [r.to_dict() for r in results[:5]]
        
        return {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "period": f"{start_date} até {end_date}",
            "total_combinations_tested": len(results),
            "optimization_method": "Grid Search + Walk-Forward Analysis",
            "walk_forward_splits": n_splits,
            "best_parameters": results[0].parameters,
            "best_performance": {
                "out_sample_return": results[0].out_sample_return,
                "out_sample_sharpe": results[0].out_sample_sharpe,
                "out_sample_win_rate": results[0].out_sample_win_rate,
                "robustness_score": results[0].robustness_score,
                "max_drawdown": results[0].max_drawdown
            },
            "top_5_results": top_results,
            "results_file": filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na otimização: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WALK-FORWARD ANALYSIS ENDPOINTS
# =============================================================================

class WFARequest(BaseModel):
    """Request para Walk-Forward Analysis"""
    strategy_name: str
    symbol: str = "BTCUSDT"
    start_date: str = None
    end_date: str = None
    n_windows: int = 5
    train_ratio: float = 0.7
    mode: str = "rolling"  # rolling, anchored, expanding
    optimize_metric: str = "sharpe_ratio"
    param_ranges: Optional[Dict[str, List[Any]]] = None


@app.post("/walk-forward-analysis")
async def run_walk_forward_analysis(request: WFARequest):
    """
    Executa Walk-Forward Analysis para validação estatística de estratégia.
    
    Walk-Forward Analysis:
    1. Divide dados em múltiplas janelas temporais
    2. Para cada janela: otimiza em dados "in-sample", testa em "out-of-sample"
    3. Agrega resultados para avaliar robustez e evitar overfitting
    
    Args:
        strategy_name: Nome da estratégia
        symbol: Par de trading (ex: BTCUSDT)
        n_windows: Número de janelas WF (default: 5)
        train_ratio: Proporção treino (default: 0.7)
        mode: rolling, anchored, ou expanding
    """
    try:
        from .walk_forward_analysis import (
            WalkForwardAnalyzer, WFAMode, 
            generate_wfa_report, wfa_result_to_dict
        )
        
        logger.info(f"Iniciando Walk-Forward Analysis para {request.strategy_name}")
        
        # Configurar datas
        if request.end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        else:
            end_date = request.end_date
            
        if request.start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        else:
            start_date = request.start_date
        
        # Obter dados
        logger.info(f"Obtendo dados: {request.symbol} de {start_date} até {end_date}")
        data = get_market_data(request.symbol, start_date, end_date, interval='1h')
        
        if data is None or len(data) < 100:
            raise HTTPException(status_code=400, detail="Dados insuficientes para análise")
        
        # Padronizar colunas
        column_mapping = {}
        for col in data.columns:
            col_str = col if isinstance(col, str) else str(col).lower()
            col_lower = col_str.lower()
            if 'open' in col_lower:
                column_mapping[col] = 'Open'
            elif 'high' in col_lower:
                column_mapping[col] = 'High'
            elif 'low' in col_lower:
                column_mapping[col] = 'Low'
            elif 'close' in col_lower:
                column_mapping[col] = 'Close'
            elif 'volume' in col_lower:
                column_mapping[col] = 'Volume'
        data = data.rename(columns=column_mapping)
        
        logger.info(f"Dados obtidos: {len(data)} candles")
        
        # Obter estratégia
        try:
            strategy_class = strategy_manager.get_strategy_class(request.strategy_name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=f"Estratégia não encontrada: {request.strategy_name}")
        
        # Configurar param_ranges
        param_ranges = request.param_ranges
        if not param_ranges:
            # Defaults por estratégia
            param_ranges = {
                'momentum': {
                    'roc_period': [5, 10, 15, 20],
                    'threshold': [-1.0, 0.0, 1.0]
                },
                'trend_following': {
                    'fast_ema': [15, 21, 30],
                    'slow_ema': [40, 55, 70]
                },
                'mean_reversion': {
                    'bb_period': [15, 20, 25],
                    'bb_std': [1.5, 2.0, 2.5]
                },
                'macd_rsi_combo': {
                    'macd_fast': [8, 12, 16],
                    'rsi_period': [10, 14, 18]
                },
                'bollinger_bands': {
                    'period': [15, 20, 25],
                    'std_dev': [1.5, 2.0, 2.5]
                },
                'volatility_breakout': {
                    'atr_period': [10, 14, 18],
                    'breakout_multiplier': [1.0, 1.5, 2.0]
                }
            }.get(request.strategy_name, {'period': [10, 15, 20]})
        
        # Criar função de backtest wrapper
        def backtest_func(df: pd.DataFrame, params: Dict[str, Any]) -> Dict:
            """Executa backtest com parâmetros dados"""
            try:
                # Criar cópia do dataframe para não modificar o original
                df_copy = df.copy()
                logger.info(f"[WFA Backtest] Dados: {len(df_copy)} candles, Params: {params}")
                
                # Criar estratégia com parâmetros
                strategy = strategy_class(parameters=params) if params else strategy_class()
                logger.info(f"[WFA Backtest] Estratégia: {strategy.name}, Params finais: {strategy.parameters}")
                
                # Calcular indicadores primeiro (se o método existir)
                if hasattr(strategy, 'calculate_indicators'):
                    df_copy = strategy.calculate_indicators(df_copy)
                    logger.info(f"[WFA Backtest] Indicadores calculados: {[c for c in df_copy.columns if c not in ['Open','High','Low','Close','Volume']]}")
                
                # Gerar sinais
                signals = strategy.generate_signals(df_copy)
                
                if signals is None or len(signals) == 0:
                    logger.warning("[WFA Backtest] Nenhum sinal gerado")
                    return None
                
                signal_counts = signals['signal'].value_counts().to_dict()
                logger.info(f"[WFA Backtest] Sinais: {signal_counts}")
                
                # Calcular retornos
                returns = []
                trades = []
                position = 0
                entry_price = 0
                entry_date = None
                
                close_col = 'Close' if 'Close' in df_copy.columns else 'close'
                
                for i, (idx, row) in enumerate(signals.iterrows()):
                    signal = row.get('signal', 0)
                    price = df_copy.loc[idx, close_col] if idx in df_copy.index else df_copy[close_col].iloc[i]
                    
                    if position == 0 and signal == 1:  # Compra
                        position = 1
                        entry_price = price
                        entry_date = idx
                    elif position == 1 and signal == -1:  # Venda
                        pnl = (price - entry_price) / entry_price
                        returns.append(pnl)
                        trades.append({
                            'entry_date': str(entry_date),
                            'exit_date': str(idx),
                            'entry_price': entry_price,
                            'exit_price': price,
                            'pnl': pnl * 100,
                            'side': 'long'
                        })
                        position = 0
                    elif position == 0:
                        returns.append(0)
                
                if len(returns) < 5:
                    return None
                
                # Calcular métricas
                returns_arr = np.array(returns)
                total_return = (np.prod(1 + returns_arr) - 1) * 100
                
                if np.std(returns_arr) > 0:
                    sharpe = (np.mean(returns_arr) / np.std(returns_arr)) * np.sqrt(252 * 24)
                else:
                    sharpe = 0
                
                wins = [r for r in returns if r > 0]
                win_rate = len(wins) / len(returns) * 100 if returns else 0
                
                # Calcular drawdown
                cumulative = np.cumprod(1 + returns_arr)
                running_max = np.maximum.accumulate(cumulative)
                drawdown = (cumulative - running_max) / running_max
                max_drawdown = abs(np.min(drawdown)) * 100 if len(drawdown) > 0 else 0
                
                return {
                    'metrics': {
                        'total_return': total_return,
                        'sharpe_ratio': sharpe,
                        'sortino_ratio': sharpe * 1.2,  # Aproximação
                        'max_drawdown': max_drawdown,
                        'win_rate': win_rate,
                        'total_trades': len(trades)
                    },
                    'returns': list(returns),
                    'trades': trades
                }
            except Exception as e:
                logger.warning(f"Erro no backtest: {e}")
                return None
        
        # Modo WFA
        mode_map = {
            'rolling': WFAMode.ROLLING,
            'anchored': WFAMode.ANCHORED,
            'expanding': WFAMode.EXPANDING
        }
        wfa_mode = mode_map.get(request.mode, WFAMode.ROLLING)
        
        # Criar analisador
        analyzer = WalkForwardAnalyzer(
            strategy_func=backtest_func,
            param_grid=param_ranges,
            optimize_metric=request.optimize_metric,
            min_trades_required=20
        )
        
        # Executar análise
        result = analyzer.run_analysis(
            data=data,
            n_windows=request.n_windows,
            train_ratio=request.train_ratio,
            mode=wfa_mode,
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe='1h'
        )
        
        # Gerar relatório
        report = generate_wfa_report(result)
        logger.info(report)
        
        # Salvar resultado
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"/app/wfa_{request.strategy_name}_{request.symbol}_{timestamp}.json"
        
        result_dict = wfa_result_to_dict(result)
        with open(filename, 'w') as f:
            json.dump(result_dict, f, indent=2, default=str)
        
        # Função auxiliar para converter tipos numpy para Python nativo
        def to_python_type(val):
            if isinstance(val, (np.bool_, np.bool8)):
                return bool(val)
            elif isinstance(val, np.integer):
                return int(val)
            elif isinstance(val, np.floating):
                return float(val)
            elif isinstance(val, np.ndarray):
                return val.tolist()
            return val
        
        return {
            "status": "success",
            "strategy_name": request.strategy_name,
            "symbol": request.symbol,
            "period": f"{start_date} até {end_date}",
            "data_points": len(data),
            "analysis_mode": request.mode,
            "n_windows": request.n_windows,
            "validation_result": {
                "passed": to_python_type(result.passed_validation),
                "score": float(result.validation_score),
                "consistency_score": float(result.consistency_score),
                "degradation_ratio": float(result.degradation_ratio)
            },
            "oos_metrics": {
                "total_return": round(float(result.oos_metrics.total_return), 2),
                "sharpe_ratio": round(float(result.oos_metrics.sharpe_ratio), 2),
                "sortino_ratio": round(float(result.oos_metrics.sortino_ratio), 2),
                "calmar_ratio": round(float(result.oos_metrics.calmar_ratio), 2),
                "max_drawdown": round(float(result.oos_metrics.max_drawdown), 2),
                "total_trades": int(result.oos_metrics.total_trades),
                "win_rate": round(float(result.oos_metrics.win_rate), 2),
                "profit_factor": round(float(result.oos_metrics.profit_factor), 2),
                "is_statistically_significant": to_python_type(result.oos_metrics.is_statistically_significant),
                "p_value": round(float(result.oos_metrics.p_value), 4)
            },
            "is_vs_oos_comparison": {
                "is_sharpe": round(float(result.is_metrics.sharpe_ratio), 2),
                "oos_sharpe": round(float(result.oos_metrics.sharpe_ratio), 2),
                "is_return": round(float(result.is_metrics.total_return), 2),
                "oos_return": round(float(result.oos_metrics.total_return), 2)
            },
            "parameter_stability": {
                k: round(float(v), 1) for k, v in result.parameter_stability.items()
            },
            "windows_summary": [
                {
                    "window": w.window_id + 1,
                    "train_period": f"{w.train_start} to {w.train_end}",
                    "test_period": f"{w.test_start} to {w.test_end}",
                    "optimal_params": w.optimal_params,
                    "is_sharpe": round(w.train_metrics.get('sharpe_ratio', 0), 2),
                    "oos_sharpe": round(float(w.test_metrics.get('sharpe_ratio', 0)), 2),
                    "oos_return": round(float(w.test_metrics.get('total_return', 0)), 2)
                }
                for w in result.windows
            ],
            "recommendations": result.recommendations,
            "results_file": filename,
            "report": report
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no Walk-Forward Analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/walk-forward-analysis/modes")
async def get_wfa_modes():
    """Retorna modos disponíveis de Walk-Forward Analysis"""
    return {
        "modes": [
            {
                "name": "rolling",
                "description": "Janela deslizante de tamanho fixo que se move no tempo",
                "use_case": "Melhor para dados estacionários e validação consistente"
            },
            {
                "name": "anchored",
                "description": "Treino sempre começa do início, teste desliza",
                "use_case": "Melhor para capturar tendências de longo prazo"
            },
            {
                "name": "expanding",
                "description": "Treino expande continuamente, teste desliza",
                "use_case": "Simula comportamento real de uso crescente de dados"
            }
        ],
        "metrics_available": [
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "total_return",
            "win_rate",
            "profit_factor"
        ]
    }


@app.post("/walk-forward-analysis/batch")
async def run_batch_wfa(
    strategies: List[str],
    symbol: str = "BTCUSDT",
    start_date: str = None,
    end_date: str = None,
    n_windows: int = 5
):
    """
    Executa Walk-Forward Analysis em lote para múltiplas estratégias.
    Útil para comparar robustez entre estratégias.
    """
    results = []
    
    for strategy_name in strategies:
        try:
            request = WFARequest(
                strategy_name=strategy_name,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                n_windows=n_windows
            )
            result = await run_walk_forward_analysis(request)
            results.append({
                "strategy": strategy_name,
                "status": "success",
                "passed": result["validation_result"]["passed"],
                "score": result["validation_result"]["score"],
                "sharpe_oos": result["oos_metrics"]["sharpe_ratio"],
                "consistency": result["validation_result"]["consistency_score"]
            })
        except Exception as e:
            results.append({
                "strategy": strategy_name,
                "status": "error",
                "error": str(e)
            })
    
    # Ranking por score
    successful = [r for r in results if r["status"] == "success"]
    successful.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "total_strategies": len(strategies),
        "successful_analyses": len(successful),
        "passed_validation": sum(1 for r in successful if r["passed"]),
        "ranking": successful,
        "failed": [r for r in results if r["status"] == "error"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
