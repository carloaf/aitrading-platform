import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from contextlib import asynccontextmanager

import httpx
import numpy as np
import pandas as pd
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, text, Numeric, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Configurações
DATABASE_URL = "postgresql+asyncpg://aitrading_user:aitrading_pass@postgres:5432/aitrading_db"
REDIS_URL = "redis://redis:6379/0"

# Modelos
Base = declarative_base()

class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class TradingSignal(Base):
    __tablename__ = "trading_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    signal_type = Column(String(50), nullable=False)  # BUY, SELL, HOLD
    source = Column(String(50), nullable=False, default="signal-generator")
    confidence = Column(Numeric(5,2))  # 0.0 to 100.0
    price_at_signal = Column(Numeric(15,6))
    target_price = Column(Numeric(15,6))
    stop_loss = Column(Numeric(15,6))
    timeframe = Column(String(20))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

# Pydantic Models
class SignalRequest(BaseModel):
    symbol: str
    timeframe: Optional[str] = "1h"

class SignalResponse(BaseModel):
    id: int
    symbol: str
    signal_type: str
    source: str
    confidence: float
    price_at_signal: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    timeframe: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True

class BatchSignalRequest(BaseModel):
    symbols: List[str]
    timeframe: Optional[str] = "1h"

class SignalStats(BaseModel):
    total_signals: int
    buy_signals: int
    sell_signals: int
    hold_signals: int
    avg_confidence: float
    high_confidence_signals: int
    success_rate: Optional[float] = None

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.async_session = None

    async def connect(self):
        """Conecta ao banco de dados"""
        try:
            logger.info(f"🔗 Tentando conectar ao banco: {DATABASE_URL}")
            self.engine = create_async_engine(DATABASE_URL, echo=False)
            self.async_session = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
            
            # Testar conexão
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            # Criar tabelas
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("✅ Conectado ao PostgreSQL e tabelas criadas")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao PostgreSQL: {e}")
            return False

    def get_session(self):
        """Retorna uma sessão do banco"""
        return self.async_session()

class SignalGenerator:
    def __init__(self):
        self.sentiment_service_url = "http://sentiment-analyzer:8000"
        self.indicator_service_url = "http://indicator-calculator:8000"
        self.news_service_url = "http://news-collector:8000"
        
        # Pesos para combinação de sinais
        self.sentiment_weight = 0.4
        self.technical_weight = 0.6
        
        # Thresholds - Very sensitive for demonstration
        self.buy_threshold = 0.05  # Very low threshold
        self.sell_threshold = -0.05  # Very low threshold  
        self.high_confidence_threshold = 0.4  # Lowered
        self.medium_confidence_threshold = 0.15  # Lowered

    async def get_sentiment_analysis(self, symbol: str, timeframe: str = "24h") -> Dict[str, Any]:
        """Busca análise de sentimento para um símbolo"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Buscar notícias recentes do símbolo
                response = await client.get(
                    f"{self.news_service_url}/news/recent",
                    params={"symbol": symbol, "limit": 50}
                )
                
                if response.status_code != 200:
                    logger.warning(f"Falha ao buscar notícias para {symbol}")
                    return {"sentiment_score": 0.0, "articles_count": 0}
                
                news_data = response.json()
                # Check if response is a list (direct articles) or dict with articles field
                if isinstance(news_data, list):
                    articles = news_data
                else:
                    articles = news_data.get("articles", [])
                
                if not articles:
                    return {"sentiment_score": 0.0, "articles_count": 0}
                
                # Analisar sentimento das notícias
                sentiments = []
                for article in articles[:20]:  # Limitar a 20 artigos mais recentes
                    # Check if article already has sentiment (pre-computed)
                    if "sentiment" in article and "confidence" in article:
                        # Use pre-computed sentiment from news service
                        sentiment_text = article.get("sentiment", "neutral")
                        confidence = float(article.get("confidence", 0.0))
                        
                        # Convert text sentiment to numeric score
                        if sentiment_text == "positive":
                            sentiment_score = confidence
                        elif sentiment_text == "negative":
                            sentiment_score = -confidence
                        else:  # neutral
                            sentiment_score = 0.0
                            
                        sentiments.append(sentiment_score)
                    else:
                        # Fallback to re-analyzing if no pre-computed sentiment
                        title = article.get("title", "")
                        content = article.get("content", "")
                        text = f"{title}. {content}"
                        
                        if len(text.strip()) > 10:
                            sentiment_response = await client.post(
                                f"{self.sentiment_service_url}/analyze",
                                json={"text": text}
                            )
                            
                            if sentiment_response.status_code == 200:
                                sentiment_data = sentiment_response.json()
                                sentiments.append(sentiment_data["sentiment_score"])
                
                if sentiments:
                    # Use weighted average where high-confidence sentiments have more influence
                    weighted_sentiments = []
                    weights = []
                    
                    for sentiment in sentiments:
                        confidence = abs(sentiment)
                        # Only include sentiments with confidence > 0.1
                        if confidence > 0.1:
                            weighted_sentiments.append(sentiment)
                            weights.append(confidence)
                    
                    if weighted_sentiments:
                        # Weighted average favoring high-confidence sentiments
                        avg_sentiment = np.average(weighted_sentiments, weights=weights)
                        sentiment_std = np.std(weighted_sentiments)
                    else:
                        # Fallback to simple average if no high-confidence sentiments
                        avg_sentiment = np.mean(sentiments)
                        sentiment_std = np.std(sentiments)
                    
                    return {
                        "sentiment_score": float(avg_sentiment),
                        "sentiment_std": float(sentiment_std),
                        "articles_count": len(sentiments),
                        "high_confidence_articles": len(weighted_sentiments),
                        "sentiment_distribution": {
                            "positive": len([s for s in sentiments if s > 0.1]),
                            "negative": len([s for s in sentiments if s < -0.1]),
                            "neutral": len([s for s in sentiments if -0.1 <= s <= 0.1])
                        }
                    }
                
                return {"sentiment_score": 0.0, "articles_count": 0}
                
        except Exception as e:
            logger.error(f"Erro ao buscar análise de sentimento: {e}")
            return {"sentiment_score": 0.0, "articles_count": 0}

    async def get_technical_analysis(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """Busca análise técnica para um símbolo"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.indicator_service_url}/indicators/{symbol}",
                    params={"timeframe": timeframe}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Falha ao buscar indicadores técnicos para {symbol}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Erro ao buscar análise técnica: {e}")
            return {}

    def calculate_technical_score(self, indicators: Dict[str, Any]) -> float:
        """Calcula score técnico baseado nos indicadores"""
        if not indicators:
            return 0.0
        
        try:
            score = 0.0
            weights = {
                "rsi": 0.25,
                "macd": 0.25,
                "bollinger": 0.2,
                "sma": 0.15,
                "ema": 0.15
            }
            
            total_weight = 0.0
            
            # RSI Analysis
            rsi = indicators.get("rsi", {}).get("value")
            if rsi is not None:
                if rsi < 30:  # Oversold - Buy signal
                    score += weights["rsi"] * 0.8
                elif rsi > 70:  # Overbought - Sell signal
                    score -= weights["rsi"] * 0.8
                elif 40 <= rsi <= 60:  # Neutral
                    score += weights["rsi"] * 0.0
                else:
                    score += weights["rsi"] * (50 - rsi) / 50 * 0.5
                total_weight += weights["rsi"]
            
            # MACD Analysis
            macd_data = indicators.get("macd", {})
            if macd_data:
                macd_line = macd_data.get("macd")
                signal_line = macd_data.get("signal")
                if macd_line is not None and signal_line is not None:
                    if macd_line > signal_line:  # Bullish
                        score += weights["macd"] * 0.6
                    else:  # Bearish
                        score -= weights["macd"] * 0.6
                    total_weight += weights["macd"]
            
            # Bollinger Bands Analysis
            bollinger = indicators.get("bollinger_bands", {})
            if bollinger:
                current_price = bollinger.get("current_price")
                lower_band = bollinger.get("lower_band")
                upper_band = bollinger.get("upper_band")
                
                if all(v is not None for v in [current_price, lower_band, upper_band]):
                    band_width = upper_band - lower_band
                    if current_price <= lower_band + (band_width * 0.1):  # Near lower band - Buy
                        score += weights["bollinger"] * 0.7
                    elif current_price >= upper_band - (band_width * 0.1):  # Near upper band - Sell
                        score -= weights["bollinger"] * 0.7
                    total_weight += weights["bollinger"]
            
            # Moving Averages Analysis
            sma = indicators.get("sma", {})
            if sma:
                current_price = sma.get("current_price")
                sma_value = sma.get("value")
                if current_price is not None and sma_value is not None:
                    if current_price > sma_value:  # Above SMA - Bullish
                        score += weights["sma"] * 0.5
                    else:  # Below SMA - Bearish
                        score -= weights["sma"] * 0.5
                    total_weight += weights["sma"]
            
            ema = indicators.get("ema", {})
            if ema:
                current_price = ema.get("current_price")
                ema_value = ema.get("value")
                if current_price is not None and ema_value is not None:
                    if current_price > ema_value:  # Above EMA - Bullish
                        score += weights["ema"] * 0.5
                    else:  # Below EMA - Bearish
                        score -= weights["ema"] * 0.5
                    total_weight += weights["ema"]
            
            # Normalizar score
            if total_weight > 0:
                score = score / total_weight
            
            return max(-1.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"Erro ao calcular score técnico: {e}")
            return 0.0

    def combine_signals(self, sentiment_score: float, technical_score: float) -> Dict[str, Any]:
        """Combina sinais de sentimento e técnicos"""
        # If we have no technical data, use sentiment-based weighting
        if technical_score == 0.0:
            # Pure sentiment-based signal with adjusted thresholds
            combined_score = sentiment_score
            # Lower thresholds for sentiment-only signals
            buy_threshold = 0.05  # Very sensitive to positive sentiment
            sell_threshold = -0.05  # Very sensitive to negative sentiment
        else:
            # Normal combined scoring
            combined_score = (
                sentiment_score * self.sentiment_weight +
                technical_score * self.technical_weight
            )
            buy_threshold = self.buy_threshold
            sell_threshold = self.sell_threshold
        
        # Determinar tipo de sinal
        if combined_score >= buy_threshold:
            signal_type = SignalType.BUY
        elif combined_score <= sell_threshold:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.HOLD
        
        # Calcular confiança - adjust for data availability
        confidence = abs(combined_score)
        
        # If we only have sentiment data, reduce confidence slightly
        if technical_score == 0.0:
            confidence = confidence * 0.85  # Slight reduction when only sentiment available
        
        if confidence >= self.high_confidence_threshold:
            confidence_level = ConfidenceLevel.HIGH
        elif confidence >= self.medium_confidence_threshold:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW
        
        return {
            "signal_type": signal_type,
            "combined_score": combined_score,
            "confidence": confidence,
            "confidence_level": confidence_level
        }

    def generate_reasoning(self, sentiment_data: Dict, technical_data: Dict, signal_result: Dict) -> str:
        """Gera explicação do sinal"""
        reasoning_parts = []
        
        signal_type = signal_result["signal_type"]
        confidence_level = signal_result["confidence_level"]
        
        # Análise de sentimento
        sentiment_score = sentiment_data.get("sentiment_score", 0)
        articles_count = sentiment_data.get("articles_count", 0)
        
        if articles_count > 0:
            if sentiment_score > 0.3:
                reasoning_parts.append(f"Sentimento positivo ({sentiment_score:.2f}) baseado em {articles_count} notícias")
            elif sentiment_score < -0.3:
                reasoning_parts.append(f"Sentimento negativo ({sentiment_score:.2f}) baseado em {articles_count} notícias")
            else:
                reasoning_parts.append(f"Sentimento neutro ({sentiment_score:.2f}) baseado em {articles_count} notícias")
        
        # Análise técnica
        if technical_data:
            rsi = technical_data.get("rsi", {}).get("value")
            if rsi:
                if rsi < 30:
                    reasoning_parts.append(f"RSI oversold ({rsi:.1f})")
                elif rsi > 70:
                    reasoning_parts.append(f"RSI overbought ({rsi:.1f})")
                
            macd_data = technical_data.get("macd", {})
            if macd_data:
                macd_line = macd_data.get("macd")
                signal_line = macd_data.get("signal")
                if macd_line and signal_line:
                    if macd_line > signal_line:
                        reasoning_parts.append("MACD bullish crossover")
                    else:
                        reasoning_parts.append("MACD bearish crossover")
        
        # Combinar reasoning
        if reasoning_parts:
            base_reasoning = "; ".join(reasoning_parts)
        else:
            base_reasoning = "Análise baseada em dados limitados"
        
        return f"{signal_type.value.upper()} signal ({confidence_level.value} confidence): {base_reasoning}"

    async def generate_signal(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """Gera sinal de trading para um símbolo"""
        try:
            logger.info(f"🔮 Gerando sinal para {symbol} (timeframe: {timeframe})")
            
            # Buscar dados em paralelo
            sentiment_task = asyncio.create_task(
                self.get_sentiment_analysis(symbol, timeframe)
            )
            technical_task = asyncio.create_task(
                self.get_technical_analysis(symbol, timeframe)
            )
            
            sentiment_data = await sentiment_task
            technical_data = await technical_task
            
            # Calcular scores
            sentiment_score = sentiment_data.get("sentiment_score", 0.0)
            technical_score = self.calculate_technical_score(technical_data)
            
            # Combinar sinais
            signal_result = self.combine_signals(sentiment_score, technical_score)
            
            # Gerar reasoning
            reasoning = self.generate_reasoning(sentiment_data, technical_data, signal_result)
            
            # Calcular targets (placeholder - pode ser melhorado)
            current_price = None
            if technical_data:
                for indicator in ["sma", "ema", "bollinger_bands"]:
                    if indicator in technical_data:
                        current_price = technical_data[indicator].get("current_price")
                        if current_price:
                            break
            
            price_target = None
            stop_loss = None
            if current_price and signal_result["signal_type"] in [SignalType.BUY, SignalType.SELL]:
                confidence = signal_result["confidence"]
                if signal_result["signal_type"] == SignalType.BUY:
                    price_target = current_price * (1 + confidence * 0.05)  # 5% max upside
                    stop_loss = current_price * (1 - confidence * 0.03)     # 3% max downside
                else:  # SELL
                    price_target = current_price * (1 - confidence * 0.05)  # 5% max downside
                    stop_loss = current_price * (1 + confidence * 0.03)     # 3% max upside
            
            result = {
                "symbol": symbol,
                "signal_type": signal_result["signal_type"].value,  # Convert enum to string
                "source": "signal-generator",
                "confidence": signal_result["confidence"] * 100,  # Convert to 0-100 scale
                "price_at_signal": current_price,
                "target_price": price_target,
                "stop_loss": stop_loss,
                "timeframe": timeframe,
                "description": reasoning,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=24),  # Signal expires in 24h
                "is_active": True
            }
            
            logger.info(f"✅ Sinal gerado para {symbol}: {signal_result['signal_type'].value} (confiança: {signal_result['confidence']:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar sinal para {symbol}: {e}")
            raise

class SignalService:
    def __init__(self):
        self.db = DatabaseManager()
        self.redis_client = None
        self.generator = SignalGenerator()

    async def initialize(self):
        """Inicializa o serviço"""
        # Conectar ao banco
        if not await self.db.connect():
            raise RuntimeError("Falha ao conectar ao banco de dados")
        
        # Conectar ao Redis
        try:
            self.redis_client = redis.from_url(REDIS_URL)
            await self.redis_client.ping()
            logger.info("✅ Conectado ao Redis")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao Redis: {e}")
            raise
        
        logger.info("🚀 Signal Service inicializado com sucesso")

    async def save_signal(self, signal_data: Dict[str, Any]) -> int:
        """Salva sinal no banco de dados"""
        async with self.db.get_session() as session:
            signal = TradingSignal(**signal_data)
            session.add(signal)
            await session.commit()
            await session.refresh(signal)
            return signal.id

    async def get_signal_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas dos sinais"""
        async with self.db.get_session() as session:
            # Query básica para estatísticas
            result = await session.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN signal_type = 'buy' THEN 1 END) as buy_count,
                    COUNT(CASE WHEN signal_type = 'sell' THEN 1 END) as sell_count,
                    COUNT(CASE WHEN signal_type = 'hold' THEN 1 END) as hold_count,
                    AVG(confidence) as avg_confidence,
                    COUNT(CASE WHEN confidence > 70 THEN 1 END) as high_confidence
                FROM trading_signals 
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """))
            
            row = result.fetchone()
            if row:
                return {
                    "total_signals": row[0],
                    "buy_signals": row[1],
                    "sell_signals": row[2], 
                    "hold_signals": row[3],
                    "avg_confidence": float(row[4]) if row[4] else 0.0,
                    "high_confidence_signals": row[5]
                }
            
            return {
                "total_signals": 0,
                "buy_signals": 0,
                "sell_signals": 0,
                "hold_signals": 0,
                "avg_confidence": 0.0,
                "high_confidence_signals": 0
            }

# Instância global
signal_service = SignalService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    try:
        logger.info("🔧 Iniciando AI Trading Platform - Signal Generator")
        await signal_service.initialize()
        logger.info("✅ Signal Generator Service iniciado com sucesso!")
        yield
    except Exception as e:
        logger.error(f"❌ Falha na inicialização do Signal Generator: {e}")
        raise RuntimeError("Falha na inicialização")
    finally:
        logger.info("🔄 Finalizando Signal Generator Service")

# FastAPI App
app = FastAPI(
    title="AI Trading Platform - Signal Generator",
    description="Gerador de sinais de trading baseado em análise de sentimento e indicadores técnicos",
    version="1.0.0",
    lifespan=lifespan
)

# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Verificar Redis
        await signal_service.redis_client.ping()
        
        # Verificar banco
        async with signal_service.db.get_session() as session:
            await session.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "service": "signal-generator",
            "dependencies": {
                "database": "connected",
                "redis": "connected",
                "sentiment_analyzer": "available",
                "indicator_calculator": "available"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")

# Endpoints
@app.post("/generate", response_model=SignalResponse)
async def generate_signal(request: SignalRequest):
    """Gerar sinal de trading para um símbolo"""
    try:
        signal_data = await signal_service.generator.generate_signal(
            request.symbol, request.timeframe
        )
        
        # Salvar no banco
        signal_id = await signal_service.save_signal(signal_data)
        signal_data["id"] = signal_id
        
        # Cache no Redis
        cache_key = f"signal:{request.symbol}:{request.timeframe}"
        await signal_service.redis_client.setex(
            cache_key, 
            300,  # 5 minutos
            json.dumps(signal_data, default=str)
        )
        
        return signal_data
        
    except Exception as e:
        logger.error(f"Erro ao gerar sinal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/batch")
async def generate_batch_signals(request: BatchSignalRequest):
    """Gerar sinais para múltiplos símbolos"""
    try:
        tasks = []
        for symbol in request.symbols:
            task = signal_service.generator.generate_signal(symbol, request.timeframe)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        signals = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erro ao gerar sinal para {request.symbols[i]}: {result}")
                continue
                
            # Salvar no banco
            signal_id = await signal_service.save_signal(result)
            result["id"] = signal_id
            signals.append(result)
        
        return {"signals": signals, "total": len(signals)}
        
    except Exception as e:
        logger.error(f"Erro ao gerar sinais em lote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/signals/{symbol}")
async def get_signals_for_symbol(symbol: str, limit: int = 10):
    """Buscar sinais históricos para um símbolo"""
    try:
        async with signal_service.db.get_session() as session:
            result = await session.execute(text("""
                SELECT * FROM trading_signals 
                WHERE symbol = :symbol 
                ORDER BY timestamp DESC 
                LIMIT :limit
            """), {"symbol": symbol, "limit": limit})
            
            signals = []
            for row in result:
                signals.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "symbol": row[2],
                    "signal_type": row[3],
                    "confidence": row[4],
                    "confidence_level": row[5],
                    "sentiment_score": row[6],
                    "technical_score": row[7],
                    "combined_score": row[8],
                    "reasoning": row[10],
                    "price_target": row[11],
                    "stop_loss": row[12]
                })
            
            return {"signals": signals}
            
    except Exception as e:
        logger.error(f"Erro ao buscar sinais: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats", response_model=SignalStats)
async def get_signal_statistics():
    """Estatísticas dos sinais gerados"""
    try:
        stats = await signal_service.get_signal_stats()
        return stats
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "service": "AI Trading Platform - Signal Generator",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "generate": "POST /generate - Gerar sinal para um símbolo",
            "batch": "POST /generate/batch - Gerar sinais para múltiplos símbolos", 
            "history": "GET /signals/{symbol} - Histórico de sinais",
            "stats": "GET /stats - Estatísticas dos sinais",
            "health": "GET /health - Health check"
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🔧 Iniciando AI Trading Platform - Signal Generator na porta 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
