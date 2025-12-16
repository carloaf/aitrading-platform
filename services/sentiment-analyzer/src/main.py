#!/usr/bin/env python3
"""
AI Trading Platform - Sentiment Analyzer Service
Analisa sentimento de notícias financeiras usando múltiplos modelos de NLP
"""

import os
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import redis.asyncio as redis
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from loguru import logger
import nltk
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch

# Configurações
DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql://aitrading_user:aitrading_pass@postgres:5432/aitrading_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
HTTP_PORT = int(os.getenv("HTTP_PORT", "8000"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "300"))  # 5 minutos
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 hora
MODEL_NAME = os.getenv("SENTIMENT_MODEL", "cardiffnlp/twitter-roberta-base-sentiment-latest")
NEWS_COLLECTOR_URL = os.getenv("NEWS_COLLECTOR_URL", "http://news-collector:8000")

# Database Models
Base = declarative_base()

class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    news_article_id = Column(Integer, index=True)
    source_text = Column(Text)
    processed_text = Column(Text)
    
    # Scores de diferentes modelos
    vader_compound = Column(Float)
    vader_positive = Column(Float)
    vader_negative = Column(Float)
    vader_neutral = Column(Float)
    
    textblob_polarity = Column(Float)
    textblob_subjectivity = Column(Float)
    
    roberta_positive = Column(Float)
    roberta_negative = Column(Float)
    roberta_neutral = Column(Float)
    
    # Score final (ensemble)
    final_sentiment_score = Column(Float)
    final_sentiment_label = Column(String(20))  # positive, negative, neutral
    confidence = Column(Float)
    
    # Metadados
    language = Column(String(10))
    word_count = Column(Integer)
    processing_time_ms = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Pydantic Models
class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    include_details: bool = Field(default=False)

class SentimentResponse(BaseModel):
    sentiment_score: float = Field(..., ge=-1, le=1)
    sentiment_label: str
    confidence: float = Field(..., ge=0, le=1)
    processing_time_ms: float
    details: Optional[Dict[str, Any]] = None

class BatchSentimentRequest(BaseModel):
    texts: List[str] = Field(..., max_items=50)
    include_details: bool = Field(default=False)

class SentimentStats(BaseModel):
    total_analyzed: int
    avg_sentiment: float
    positive_ratio: float
    negative_ratio: float
    neutral_ratio: float
    last_updated: datetime


class SymbolSentimentResponse(BaseModel):
    symbol: str
    hours: int
    articles_count: int
    sentiment_score: float = Field(..., ge=-1, le=1)
    confidence: float = Field(..., ge=0, le=1)
    distribution: Dict[str, int]
    source: str

class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    async def connect(self):
        """Conectar ao banco e criar tabelas"""
        try:
            # Criar tabelas se não existirem
            Base.metadata.create_all(self.engine)
            logger.info("✅ Conectado ao PostgreSQL e tabelas criadas")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao PostgreSQL: {e}")
            return False
    
    def get_session(self):
        return self.SessionLocal()

class SentimentAnalyzer:
    def __init__(self):
        self.vader_analyzer = None
        self.roberta_pipeline = None
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
    async def initialize(self):
        """Inicializar modelos de análise de sentimento"""
        try:
            logger.info("🧠 Inicializando modelos de sentiment analysis...")
            
            # Download NLTK data se necessário
            try:
                nltk.data.find('vader_lexicon')
            except LookupError:
                logger.info("📥 Baixando NLTK VADER lexicon...")
                nltk.download('vader_lexicon', quiet=True)
            
            # Inicializar VADER
            self.vader_analyzer = SentimentIntensityAnalyzer()
            logger.info("✅ VADER analyzer inicializado")
            
            # Inicializar RoBERTa model
            logger.info(f"📥 Carregando modelo RoBERTa: {MODEL_NAME}")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
                self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
                self.roberta_pipeline = pipeline(
                    "sentiment-analysis",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    device=0 if self.device == "cuda" else -1
                )
                logger.info(f"✅ RoBERTa model carregado no device: {self.device}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao carregar RoBERTa: {e}, usando apenas VADER e TextBlob")
                self.roberta_pipeline = None
            
            logger.info("🎯 Todos os modelos de sentiment inicializados com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar sentiment analyzer: {e}")
            return False
    
    def preprocess_text(self, text: str) -> str:
        """Preprocessar texto para análise"""
        if not text:
            return ""
        
        # Limpar texto básico
        text = text.strip()
        
        # Remover URLs
        import re
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remover quebras de linha excessivas
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analisar sentimento usando múltiplos modelos"""
        start_time = time.time()
        
        # Preprocessar texto
        processed_text = self.preprocess_text(text)
        
        if not processed_text:
            return {
                "error": "Texto vazio após preprocessamento",
                "processing_time_ms": (time.time() - start_time) * 1000
            }
        
        results = {
            "original_text": text,
            "processed_text": processed_text,
            "word_count": len(processed_text.split()),
            "language": self.detect_language(processed_text)
        }
        
        # VADER Analysis
        try:
            vader_scores = self.vader_analyzer.polarity_scores(processed_text)
            results["vader"] = vader_scores
        except Exception as e:
            logger.error(f"Erro no VADER: {e}")
            results["vader"] = {"compound": 0, "pos": 0, "neu": 1, "neg": 0}
        
        # TextBlob Analysis
        try:
            blob = TextBlob(processed_text)
            results["textblob"] = {
                "polarity": blob.sentiment.polarity,
                "subjectivity": blob.sentiment.subjectivity
            }
        except Exception as e:
            logger.error(f"Erro no TextBlob: {e}")
            results["textblob"] = {"polarity": 0, "subjectivity": 0.5}
        
        # RoBERTa Analysis
        if self.roberta_pipeline:
            try:
                # Truncar texto se muito longo
                max_length = 512
                if len(processed_text) > max_length:
                    processed_text = processed_text[:max_length]
                
                roberta_result = self.roberta_pipeline(processed_text)[0]
                
                # Converter para formato padrão
                label = roberta_result['label'].lower()
                score = roberta_result['score']
                
                if 'negative' in label or 'neg' in label:
                    results["roberta"] = {"positive": 1-score, "negative": score, "neutral": 0}
                elif 'positive' in label or 'pos' in label:
                    results["roberta"] = {"positive": score, "negative": 1-score, "neutral": 0}
                else:
                    results["roberta"] = {"positive": 0, "negative": 0, "neutral": score}
                    
            except Exception as e:
                logger.error(f"Erro no RoBERTa: {e}")
                results["roberta"] = {"positive": 0, "negative": 0, "neutral": 1}
        else:
            results["roberta"] = {"positive": 0, "negative": 0, "neutral": 1}
        
        # Calcular sentiment final (ensemble)
        final_sentiment = self.calculate_ensemble_sentiment(results)
        results.update(final_sentiment)
        
        results["processing_time_ms"] = (time.time() - start_time) * 1000
        
        return results
    
    def detect_language(self, text: str) -> str:
        """Detectar idioma do texto"""
        try:
            from langdetect import detect
            return detect(text)
        except:
            return "en"  # default para inglês
    
    def calculate_ensemble_sentiment(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calcular sentiment final combinando múltiplos modelos"""
        
        # Pesos para cada modelo
        weights = {
            "vader": 0.3,
            "textblob": 0.2,
            "roberta": 0.5
        }
        
        # Normalizar scores para [-1, 1]
        vader_score = results["vader"]["compound"]
        textblob_score = results["textblob"]["polarity"]
        
        # RoBERTa: converter para score único
        roberta = results["roberta"]
        roberta_score = roberta["positive"] - roberta["negative"]
        
        # Calcular score ponderado
        final_score = (
            weights["vader"] * vader_score +
            weights["textblob"] * textblob_score +
            weights["roberta"] * roberta_score
        )
        
        # Determinar label e confidence
        if final_score > 0.1:
            label = "positive"
            confidence = min(abs(final_score), 1.0)
        elif final_score < -0.1:
            label = "negative"
            confidence = min(abs(final_score), 1.0)
        else:
            label = "neutral"
            confidence = 1.0 - abs(final_score)
        
        return {
            "final_sentiment_score": round(final_score, 4),
            "final_sentiment_label": label,
            "confidence": round(confidence, 4)
        }

class SentimentService:
    def __init__(self):
        self.db = DatabaseManager()
        self.analyzer = SentimentAnalyzer()
        self.redis_client = None
        
    async def initialize(self):
        """Inicializar todos os componentes"""
        # Conectar ao banco
        if not await self.db.connect():
            return False
        
        # Conectar ao Redis
        try:
            self.redis_client = redis.from_url(REDIS_URL)
            await self.redis_client.ping()
            logger.info("✅ Conectado ao Redis")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao Redis: {e}")
            return False
        
        # Inicializar analyzer
        if not await self.analyzer.initialize():
            return False
        
        logger.info("🚀 Sentiment Service inicializado com sucesso")
        return True
    
    async def analyze_text(self, text: str, save_to_db: bool = True) -> Dict[str, Any]:
        """Analisar sentimento de um texto"""
        result = self.analyzer.analyze_sentiment(text)
        
        if save_to_db and "error" not in result:
            await self.save_analysis(result)
        
        return result
    
    async def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analisar sentimento de múltiplos textos"""
        results = []
        
        for text in texts:
            result = await self.analyze_text(text, save_to_db=True)
            results.append(result)
        
        return results
    
    async def save_analysis(self, analysis: Dict[str, Any]):
        """Salvar análise no banco de dados"""
        try:
            session = self.db.get_session()
            
            sentiment_record = SentimentAnalysis(
                source_text=analysis["original_text"][:5000],  # truncar se muito longo
                processed_text=analysis["processed_text"][:5000],
                
                # VADER scores
                vader_compound=analysis["vader"]["compound"],
                vader_positive=analysis["vader"]["pos"],
                vader_negative=analysis["vader"]["neg"],
                vader_neutral=analysis["vader"]["neu"],
                
                # TextBlob scores
                textblob_polarity=analysis["textblob"]["polarity"],
                textblob_subjectivity=analysis["textblob"]["subjectivity"],
                
                # RoBERTa scores
                roberta_positive=analysis["roberta"]["positive"],
                roberta_negative=analysis["roberta"]["negative"],
                roberta_neutral=analysis["roberta"]["neutral"],
                
                # Final scores
                final_sentiment_score=analysis["final_sentiment_score"],
                final_sentiment_label=analysis["final_sentiment_label"],
                confidence=analysis["confidence"],
                
                # Metadata
                language=analysis["language"],
                word_count=analysis["word_count"],
                processing_time_ms=analysis["processing_time_ms"]
            )
            
            session.add(sentiment_record)
            session.commit()
            session.close()
            
        except Exception as e:
            logger.error(f"Erro ao salvar análise no banco: {e}")
    
    async def get_sentiment_stats(self) -> Dict[str, Any]:
        """Obter estatísticas de sentiment"""
        try:
            # Verificar cache primeiro
            cache_key = "sentiment_stats"
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
            
            # Calcular stats do banco
            session = self.db.get_session()
            
            # Stats das últimas 24 horas
            since = datetime.utcnow() - timedelta(hours=24)
            
            analyses = session.query(SentimentAnalysis).filter(
                SentimentAnalysis.created_at >= since
            ).all()
            
            if not analyses:
                return {
                    "total_analyzed": 0,
                    "avg_sentiment": 0.0,
                    "positive_ratio": 0.0,
                    "negative_ratio": 0.0,
                    "neutral_ratio": 0.0,
                    "last_updated": datetime.utcnow()
                }
            
            total = len(analyses)
            avg_sentiment = sum(a.final_sentiment_score for a in analyses) / total
            
            positive_count = sum(1 for a in analyses if a.final_sentiment_label == "positive")
            negative_count = sum(1 for a in analyses if a.final_sentiment_label == "negative")
            neutral_count = sum(1 for a in analyses if a.final_sentiment_label == "neutral")
            
            stats = {
                "total_analyzed": total,
                "avg_sentiment": round(avg_sentiment, 4),
                "positive_ratio": round(positive_count / total, 4),
                "negative_ratio": round(negative_count / total, 4),
                "neutral_ratio": round(neutral_count / total, 4),
                "last_updated": datetime.utcnow()
            }
            
            # Cache por 5 minutos
            await self.redis_client.setex(
                cache_key, 
                300, 
                json.dumps(stats, default=str)
            )
            
            session.close()
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter stats: {e}")
            return {
                "error": str(e),
                "total_analyzed": 0,
                "avg_sentiment": 0.0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "neutral_ratio": 0.0,
                "last_updated": datetime.utcnow()
            }
    
    async def process_news_articles(self):
        """Processar artigos de notícias pendentes"""
        try:
            # Buscar artigos não processados
            # Este método seria conectado ao news-collector
            logger.info("🔄 Processando artigos de notícias...")
            
            # Por enquanto, implementação básica
            # TODO: Integrar com news-collector service
            
        except Exception as e:
            logger.error(f"Erro ao processar artigos: {e}")

    async def get_symbol_sentiment(self, symbol: str, hours: int = 24, limit: int = 50, use_precomputed: bool = True) -> Dict[str, Any]:
        """Agrega sentimento para um símbolo baseado em notícias recentes do news-collector.

        Observação: por padrão usa o sentimento pré-computado do `news-collector` (label + confidence),
        evitando rodar o modelo RoBERTa em tempo real.
        """
        symbol_norm = (symbol or "").upper().strip()
        if not symbol_norm:
            return {
                "symbol": symbol_norm,
                "hours": hours,
                "articles_count": 0,
                "sentiment_score": 0.0,
                "confidence": 0.0,
                "distribution": {"positive": 0, "negative": 0, "neutral": 0},
                "source": "news-collector"
            }

        hours = max(1, min(int(hours), 168))
        limit = max(1, min(int(limit), 200))

        cache_key = f"sentiment:symbol:{symbol_norm}:h{hours}:l{limit}:pre{int(bool(use_precomputed))}"
        cached = await self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{NEWS_COLLECTOR_URL}/news/recent",
                params={"symbol": symbol_norm, "hours": hours, "limit": limit},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"news-collector error: {resp.status_code}")
            articles = resp.json() or []

        distribution = {"positive": 0, "negative": 0, "neutral": 0}
        scores: List[float] = []
        weights: List[float] = []

        if use_precomputed:
            for a in articles:
                label = (a.get("sentiment") or "neutral").lower()
                try:
                    conf = float(a.get("confidence") or 0.0)
                except Exception:
                    conf = 0.0

                if label == "positive":
                    score = max(0.0, min(conf, 1.0))
                    distribution["positive"] += 1
                elif label == "negative":
                    score = -max(0.0, min(conf, 1.0))
                    distribution["negative"] += 1
                else:
                    score = 0.0
                    distribution["neutral"] += 1

                scores.append(score)
                weights.append(max(0.05, abs(score)))

            if scores:
                sentiment_score = float(np.average(scores, weights=weights))
                confidence = float(min(np.mean([abs(s) for s in scores]), 1.0))
            else:
                sentiment_score = 0.0
                confidence = 0.0

            result = {
                "symbol": symbol_norm,
                "hours": hours,
                "articles_count": len(articles),
                "sentiment_score": round(float(np.clip(sentiment_score, -1, 1)), 4),
                "confidence": round(float(np.clip(confidence, 0, 1)), 4),
                "distribution": distribution,
                "source": "news-collector"
            }
        else:
            # Modo completo (modelos) pode ser implementado depois; por ora mantemos simples.
            result = {
                "symbol": symbol_norm,
                "hours": hours,
                "articles_count": len(articles),
                "sentiment_score": 0.0,
                "confidence": 0.0,
                "distribution": distribution,
                "source": "disabled"
            }

        await self.redis_client.setex(cache_key, 300, json.dumps(result, default=str))
        return result

# Serviço global
sentiment_service = SentimentService()

# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🔧 Iniciando AI Trading Platform - Sentiment Analyzer")
    
    success = await sentiment_service.initialize()
    if not success:
        logger.error("❌ Falha na inicialização do Sentiment Analyzer")
        raise RuntimeError("Falha na inicialização")
    
    # Iniciar processamento em background
    background_task = asyncio.create_task(background_processor())
    
    logger.info("✅ Sentiment Analyzer Service iniciado com sucesso!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Iniciando shutdown do Sentiment Analyzer...")
    background_task.cancel()
    try:
        await background_task
    except asyncio.CancelledError:
        pass
    
    if sentiment_service.redis_client:
        await sentiment_service.redis_client.close()
    
    logger.info("👋 Sentiment Analyzer Service finalizado")

# FastAPI App
app = FastAPI(
    title="AI Trading Platform - Sentiment Analyzer",
    description="Serviço de análise de sentimento para notícias financeiras",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background processor
async def background_processor():
    """Processador em background para análise contínua"""
    while True:
        try:
            await sentiment_service.process_news_articles()
            await asyncio.sleep(UPDATE_INTERVAL)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erro no background processor: {e}")
            await asyncio.sleep(60)

# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Verificar Redis
        await sentiment_service.redis_client.ping()
        
        # Verificar banco
        from sqlalchemy import text
        session = sentiment_service.db.get_session()
        session.execute(text("SELECT 1"))
        session.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "service": "sentiment-analyzer",
            "models_loaded": sentiment_service.analyzer.roberta_pipeline is not None,
            "device": sentiment_service.analyzer.device
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")

# Endpoints
@app.post("/analyze", response_model=SentimentResponse)
async def analyze_sentiment(request: SentimentRequest):
    """Analisar sentimento de um texto"""
    try:
        result = await sentiment_service.analyze_text(
            request.text, 
            save_to_db=True
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        response = SentimentResponse(
            sentiment_score=result["final_sentiment_score"],
            sentiment_label=result["final_sentiment_label"],
            confidence=result["confidence"],
            processing_time_ms=result["processing_time_ms"]
        )
        
        if request.include_details:
            response.details = {
                "vader": result["vader"],
                "textblob": result["textblob"],
                "roberta": result["roberta"],
                "language": result["language"],
                "word_count": result["word_count"]
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Erro na análise: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/batch")
async def analyze_batch_sentiment(request: BatchSentimentRequest):
    """Analisar sentimento de múltiplos textos"""
    try:
        results = await sentiment_service.analyze_batch(request.texts)
        
        responses = []
        for result in results:
            if "error" not in result:
                response = {
                    "sentiment_score": result["final_sentiment_score"],
                    "sentiment_label": result["final_sentiment_label"],
                    "confidence": result["confidence"],
                    "processing_time_ms": result["processing_time_ms"]
                }
                
                if request.include_details:
                    response["details"] = {
                        "vader": result["vader"],
                        "textblob": result["textblob"],
                        "roberta": result["roberta"],
                        "language": result["language"],
                        "word_count": result["word_count"]
                    }
                
                responses.append(response)
            else:
                responses.append({"error": result["error"]})
        
        return {"results": responses}
        
    except Exception as e:
        logger.error(f"Erro na análise em lote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats", response_model=SentimentStats)
async def get_sentiment_statistics():
    """Obter estatísticas de sentimento"""
    try:
        stats = await sentiment_service.get_sentiment_stats()
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return SentimentStats(**stats)
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models/status")
async def get_models_status():
    """Status dos modelos de ML"""
    return {
        "vader_loaded": sentiment_service.analyzer.vader_analyzer is not None,
        "roberta_loaded": sentiment_service.analyzer.roberta_pipeline is not None,
        "model_name": MODEL_NAME,
        "device": sentiment_service.analyzer.device,
        "torch_available": torch.cuda.is_available(),
        "batch_size": BATCH_SIZE
    }


@app.get("/sentiment/symbol", response_model=SymbolSentimentResponse)
async def get_symbol_sentiment(symbol: str, hours: int = 24, limit: int = 50, use_precomputed: bool = True):
    """Sentimento agregado por símbolo (baseado em notícias recentes)."""
    try:
        result = await sentiment_service.get_symbol_sentiment(
            symbol=symbol,
            hours=hours,
            limit=limit,
            use_precomputed=use_precomputed,
        )
        return SymbolSentimentResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter sentiment por símbolo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"🔧 Iniciando AI Trading Platform - Sentiment Analyzer na porta {HTTP_PORT}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=HTTP_PORT,
        reload=False,
        access_log=True
    )
