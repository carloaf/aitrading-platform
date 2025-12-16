#!/usr/bin/env python3
"""
AI Trading Platform - News Collector Service
===========================================

Serviço responsável por coletar notícias relacionadas ao mercado de criptomoedas
de múltiplas fontes e armazená-las para análise de sentimento.

Fontes de notícias implementadas:
- NewsAPI
- GNews API
- RSS Feeds de exchanges
- CoinDesk
- CoinTelegraph
- E mais...
"""

import asyncio
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from concurrent.futures import ThreadPoolExecutor

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import redis
import requests
import httpx
import feedparser
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from loguru import logger
from dotenv import load_dotenv
import schedule
import json
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import aiohttp

# Carregar variáveis de ambiente
load_dotenv()

# ==========================================
# CONFIGURAÇÕES
# ==========================================
class Config:
    # Servidor
    HTTP_PORT = int(os.getenv('HTTP_PORT', 8000))
    HOST = os.getenv('HOST', '0.0.0.0')
    
    # Banco de dados
    POSTGRES_URL = os.getenv('POSTGRES_URL', 'postgresql://aitrading_user:aitrading_pass@postgres:5432/aitrading_db')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
    
    # APIs externas
    NEWS_API_KEY = os.getenv('NEWS_API_KEY', '')
    GNEWS_API_KEY = os.getenv('GNEWS_API_KEY', '')
    
    # Configurações de coleta
    COLLECTION_INTERVAL = int(os.getenv('COLLECTION_INTERVAL', 300))  # 5 minutos
    MAX_ARTICLES_PER_SOURCE = int(os.getenv('MAX_ARTICLES_PER_SOURCE', 50))
    CACHE_TTL = int(os.getenv('CACHE_TTL', 3600))  # 1 hora
    
    # Palavras-chave crypto
    CRYPTO_KEYWORDS = [
        'bitcoin', 'btc', 'ethereum', 'eth', 'cryptocurrency', 'crypto',
        'blockchain', 'defi', 'nft', 'altcoin', 'binance', 'coinbase',
        'cardano', 'ada', 'solana', 'sol', 'polygon', 'matic', 'dogecoin',
        'doge', 'shiba', 'chainlink', 'link', 'polkadot', 'dot'
    ]

config = Config()

# ==========================================
# MODELOS DE BANCO DE DADOS
# ==========================================
Base = declarative_base()

class NewsArticle(Base):
    __tablename__ = 'news_articles'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    url = Column(String(1000), unique=True, nullable=False)
    source = Column(String(100), nullable=False)
    author = Column(String(200))
    published_at = Column(DateTime, nullable=False)
    collected_at = Column(DateTime, default=datetime.utcnow)
    language = Column(String(10), default='en')
    sentiment_score = Column(String(20))  # positive, negative, neutral
    sentiment_confidence = Column(String(10))
    keywords = Column(Text)  # JSON string
    is_crypto_related = Column(Boolean, default=True)
    processed = Column(Boolean, default=False)

# ==========================================
# GERENCIADOR DE BANCO DE DADOS
# ==========================================
class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.Session = None
        self.redis_client = None
        
    async def connect(self):
        """Conectar aos bancos de dados com retry"""
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Tentativa {attempt + 1}/{max_retries} de conexão aos bancos...")
                
                # PostgreSQL
                self.engine = create_engine(config.POSTGRES_URL, pool_pre_ping=True)
                
                # Criar tabelas
                Base.metadata.create_all(self.engine)
                self.Session = sessionmaker(bind=self.engine)
                
                # Testar conexão
                with self.engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    logger.info("✅ Conectado ao PostgreSQL")
                
                # Redis
                self.redis_client = redis.from_url(config.REDIS_URL, decode_responses=True)
                self.redis_client.ping()
                logger.info("✅ Conectado ao Redis")
                
                return  # Sucesso, sair do loop
                
            except Exception as e:
                logger.error(f"❌ Erro na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Aguardando {retry_delay}s antes da próxima tentativa...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("❌ Esgotadas todas as tentativas de conexão")
                    raise

# ==========================================
# COLETORES DE NOTÍCIAS
# ==========================================
class NewsCollector:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.session = aiohttp.ClientSession()
        
        # Inicializar analisador de sentimento
        try:
            self.sentiment_analyzer = SentimentIntensityAnalyzer()
        except Exception as e:
            logger.warning(f"Erro ao carregar analisador de sentimento: {e}")
            self.sentiment_analyzer = None
    
    async def collect_from_newsapi(self) -> List[Dict]:
        """Coletar notícias da NewsAPI"""
        if not config.NEWS_API_KEY:
            logger.warning("NEWS_API_KEY não configurada")
            return []
            
        articles = []
        keywords = ' OR '.join(config.CRYPTO_KEYWORDS[:5])  # Limitar para evitar URL muito longa
        
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': keywords,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': config.MAX_ARTICLES_PER_SOURCE,
                'apiKey': config.NEWS_API_KEY
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    for article in data.get('articles', []):
                        articles.append({
                            'title': article.get('title', ''),
                            'content': article.get('description', '') + ' ' + (article.get('content', '') or ''),
                            'url': article.get('url', ''),
                            'source': f"newsapi_{article.get('source', {}).get('name', 'unknown')}",
                            'author': article.get('author'),
                            'published_at': self._parse_datetime(article.get('publishedAt')),
                        })
                    logger.info(f"✅ NewsAPI: {len(articles)} artigos coletados")
                else:
                    logger.error(f"❌ NewsAPI erro: {response.status}")
                    
        except Exception as e:
            logger.error(f"❌ Erro ao coletar da NewsAPI: {e}")
            
        return articles
    
    async def collect_from_gnews(self) -> List[Dict]:
        """Coletar notícias da GNews API"""
        if not config.GNEWS_API_KEY:
            logger.warning("GNEWS_API_KEY não configurada")
            return []
            
        articles = []
        
        try:
            url = "https://gnews.io/api/v4/search"
            params = {
                'q': 'cryptocurrency OR bitcoin OR ethereum',
                'lang': 'en',
                'country': 'us',
                'max': config.MAX_ARTICLES_PER_SOURCE,
                'apikey': config.GNEWS_API_KEY
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    for article in data.get('articles', []):
                        articles.append({
                            'title': article.get('title', ''),
                            'content': article.get('description', ''),
                            'url': article.get('url', ''),
                            'source': f"gnews_{article.get('source', {}).get('name', 'unknown')}",
                            'author': None,
                            'published_at': self._parse_datetime(article.get('publishedAt')),
                        })
                    logger.info(f"✅ GNews: {len(articles)} artigos coletados")
                else:
                    logger.error(f"❌ GNews erro: {response.status}")
                    
        except Exception as e:
            logger.error(f"❌ Erro ao coletar da GNews: {e}")
            
        return articles
    
    async def collect_from_rss_feeds(self) -> List[Dict]:
        """Coletar notícias de feeds RSS"""
        rss_feeds = [
            'https://cointelegraph.com/rss',
            'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'https://decrypt.co/feed',
            'https://www.theblockcrypto.com/rss.xml'
        ]
        
        articles = []
        
        for feed_url in rss_feeds:
            try:
                async with self.session.get(feed_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        feed = feedparser.parse(content)
                        
                        source_name = feed.feed.get('title', 'rss_feed').lower().replace(' ', '_')
                        
                        for entry in feed.entries[:config.MAX_ARTICLES_PER_SOURCE // len(rss_feeds)]:
                            # Verificar se é relacionado a crypto
                            title_lower = entry.get('title', '').lower()
                            if any(keyword in title_lower for keyword in config.CRYPTO_KEYWORDS):
                                articles.append({
                                    'title': entry.get('title', ''),
                                    'content': entry.get('summary', ''),
                                    'url': entry.get('link', ''),
                                    'source': f"rss_{source_name}",
                                    'author': entry.get('author'),
                                    'published_at': self._parse_datetime(entry.get('published')),
                                })
                                
                        logger.info(f"✅ RSS {source_name}: {len([a for a in articles if source_name in a['source']])} artigos")
                        
            except Exception as e:
                logger.error(f"❌ Erro ao coletar RSS {feed_url}: {e}")
        
        return articles
    
    def _parse_datetime(self, date_string: str) -> datetime:
        """Converter string de data para datetime"""
        if not date_string:
            return datetime.utcnow()
            
        try:
            # Tentar diferentes formatos
            formats = [
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%a, %d %b %Y %H:%M:%S %Z',
                '%a, %d %b %Y %H:%M:%S GMT'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_string, fmt)
                except ValueError:
                    continue
                    
            # Se nenhum formato funcionou, usar regex para extrair componentes
            import re
            from dateutil.parser import parse
            return parse(date_string)
            
        except Exception as e:
            logger.warning(f"Erro ao parsear data '{date_string}': {e}")
            return datetime.utcnow()
    
    def analyze_sentiment(self, text: str) -> tuple:
        """Analisar sentimento do texto"""
        if not self.sentiment_analyzer or not text:
            return 'neutral', '0.0'
            
        try:
            scores = self.sentiment_analyzer.polarity_scores(text)
            compound = scores['compound']
            
            if compound >= 0.05:
                sentiment = 'positive'
            elif compound <= -0.05:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
                
            confidence = abs(compound)
            return sentiment, f"{confidence:.2f}"
            
        except Exception as e:
            logger.error(f"Erro na análise de sentimento: {e}")
            return 'neutral', '0.0'
    
    async def save_articles(self, articles: List[Dict]):
        """Salvar artigos no banco de dados"""
        session = self.db_manager.Session()
        saved_count = 0
        
        try:
            for article_data in articles:
                # Verificar se já existe
                existing = session.query(NewsArticle).filter_by(url=article_data['url']).first()
                if existing:
                    continue
                
                # Analisar sentimento
                full_text = f"{article_data['title']} {article_data['content']}"
                sentiment, confidence = self.analyze_sentiment(full_text)
                
                # Criar artigo
                article = NewsArticle(
                    title=article_data['title'][:500],
                    content=article_data['content'],
                    url=article_data['url'][:1000],
                    source=article_data['source'][:100],
                    author=article_data.get('author', '')[:200] if article_data.get('author') else None,
                    published_at=article_data['published_at'],
                    sentiment_score=sentiment,
                    sentiment_confidence=confidence,
                    keywords=json.dumps(config.CRYPTO_KEYWORDS),
                    is_crypto_related=True
                )
                
                session.add(article)
                saved_count += 1
            
            session.commit()
            logger.info(f"💾 {saved_count} novos artigos salvos no banco")
            
            # Cache no Redis
            cache_key = f"news:stats:{datetime.now().strftime('%Y-%m-%d-%H')}"
            self.db_manager.redis_client.setex(
                cache_key, 
                config.CACHE_TTL, 
                json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'articles_collected': saved_count,
                    'total_sources': len(set([a['source'] for a in articles]))
                })
            )
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Erro ao salvar artigos: {e}")
        finally:
            session.close()
    
    async def collect_all_news(self):
        """Coletar notícias de todas as fontes"""
        logger.info("📰 Iniciando coleta de notícias...")
        
        all_articles = []
        
        # Coletar de todas as fontes
        tasks = [
            self.collect_from_newsapi(),
            self.collect_from_gnews(),
            self.collect_from_rss_feeds()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Erro na coleta: {result}")
        
        # Salvar artigos
        if all_articles:
            await self.save_articles(all_articles)
            logger.info(f"✅ Coleta finalizada: {len(all_articles)} artigos processados")
        else:
            logger.warning("⚠️ Nenhum artigo coletado")
    
    async def close(self):
        """Fechar sessão HTTP"""
        await self.session.close()

# ==========================================
# SERVIÇO PRINCIPAL
# ==========================================
class NewsService:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.news_collector = None
        self.collection_thread = None
        self.running = False
    
    async def start(self):
        """Inicializar o serviço"""
        logger.info("🚀 Iniciando News Collector Service...")
        
        await self.db_manager.connect()
        self.news_collector = NewsCollector(self.db_manager)
        
        # Configurar agendamento
        self.start_scheduled_collection()
        
        # Fazer uma coleta inicial
        await self.news_collector.collect_all_news()
        
        self.running = True
        logger.info("✅ News Collector Service iniciado com sucesso!")
    
    def start_scheduled_collection(self):
        """Iniciar coleta agendada em thread separada"""
        def run_collections():
            schedule.every(config.COLLECTION_INTERVAL).seconds.do(
                lambda: asyncio.run(self.news_collector.collect_all_news())
            )
            
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Verificar a cada minuto
        
        self.collection_thread = threading.Thread(target=run_collections, daemon=True)
        self.collection_thread.start()
        logger.info(f"⏰ Coleta agendada a cada {config.COLLECTION_INTERVAL} segundos")
    
    async def get_recent_news(self, limit: int = 50, hours: int = 24) -> List[Dict]:
        """Obter notícias recentes"""
        session = self.db_manager.Session()
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            articles = session.query(NewsArticle).filter(
                NewsArticle.published_at >= since
            ).order_by(NewsArticle.published_at.desc()).limit(limit).all()
            
            return [
                {
                    'id': article.id,
                    'title': article.title,
                    'content': article.content[:500] + '...' if len(article.content) > 500 else article.content,
                    'url': article.url,
                    'source': article.source,
                    'author': article.author,
                    'published_at': article.published_at.isoformat(),
                    'sentiment': article.sentiment_score,
                    'confidence': article.sentiment_confidence
                }
                for article in articles
            ]
        finally:
            session.close()
    
    async def get_sentiment_stats(self, hours: int = 24) -> Dict:
        """Obter estatísticas de sentimento"""
        session = self.db_manager.Session()
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            total = session.query(NewsArticle).filter(
                NewsArticle.published_at >= since
            ).count()
            
            positive = session.query(NewsArticle).filter(
                NewsArticle.published_at >= since,
                NewsArticle.sentiment_score == 'positive'
            ).count()
            
            negative = session.query(NewsArticle).filter(
                NewsArticle.published_at >= since,
                NewsArticle.sentiment_score == 'negative'
            ).count()
            
            neutral = total - positive - negative
            
            return {
                'total_articles': total,
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'positive_percentage': round((positive / total * 100) if total > 0 else 0, 2),
                'negative_percentage': round((negative / total * 100) if total > 0 else 0, 2),
                'neutral_percentage': round((neutral / total * 100) if total > 0 else 0, 2)
            }
        finally:
            session.close()
    
    async def health_check(self) -> Dict:
        """Verificar saúde do serviço"""
        return {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database_connected': self.db_manager.engine is not None,
            'redis_connected': self.db_manager.redis_client is not None,
            'collection_running': self.running,
            'collection_interval': config.COLLECTION_INTERVAL
        }
    
    async def stop(self):
        """Parar o serviço"""
        self.running = False
        if self.news_collector:
            await self.news_collector.close()

# Instância global do serviço
service = NewsService()

# ==========================================
# API REST
# ==========================================
app = FastAPI(
    title="AI Trading Platform - News Collector",
    description="Serviço de coleta e análise de notícias do mercado de criptomoedas",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await service.start()

@app.on_event("shutdown")
async def shutdown_event():
    await service.stop()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await service.health_check()

@app.get("/news/recent")
async def get_recent_news(limit: int = 50, hours: int = 24):
    """Obter notícias recentes"""
    return await service.get_recent_news(limit, hours)

@app.get("/news/sentiment")
async def get_sentiment_stats(hours: int = 24):
    """Obter estatísticas de sentimento"""
    return await service.get_sentiment_stats(hours)

@app.post("/news/collect")
async def trigger_collection(background_tasks: BackgroundTasks):
    """Disparar coleta manual de notícias"""
    background_tasks.add_task(service.news_collector.collect_all_news)
    return {"message": "Coleta de notícias iniciada"}

@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "service": "AI Trading Platform - News Collector",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "recent_news": "/news/recent?limit=50&hours=24",
            "sentiment_stats": "/news/sentiment?hours=24",
            "trigger_collection": "/news/collect"
        }
    }

# ==========================================
# EXECUÇÃO PRINCIPAL
# ==========================================
def main():
    """Função principal"""
    logger.info("🔧 Iniciando AI Trading Platform - News Collector")
    
    # Configurar logs
    logger.add("logs/news_collector_{time}.log", rotation="1 day", retention="30 days")
    
    # Executar servidor
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.HTTP_PORT,
        log_level="info"
    )

if __name__ == "__main__":
    main()
