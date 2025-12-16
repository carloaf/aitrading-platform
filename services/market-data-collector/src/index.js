const express = require('express');
const WebSocket = require('ws');
const Redis = require('redis');
const { Client } = require('pg');
const ccxt = require('ccxt');
const winston = require('winston');
const cron = require('node-cron');
require('dotenv').config();

// ==========================================
// CONFIGURAÇÃO DE LOGS
// ==========================================
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'market-data-collector' },
  transports: [
    new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/combined.log' }),
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

// ==========================================
// CONFIGURAÇÃO DE CONEXÕES
// ==========================================
class MarketDataCollector {
  constructor() {
    this.app = express();
    this.port = process.env.PORT || 3001;
    this.isRunning = false;
    this.connections = {
      redis: null,
      postgres: null,
      binance: null
    };
    this.websockets = new Map();
    this.symbols = process.env.CRYPTO_SYMBOLS?.split(',') || ['BTCUSDT', 'ETHUSDT'];
    this.intervals = process.env.MARKET_DATA_INTERVALS?.split(',') || ['1m', '5m', '1h'];
    
    this.setupExpress();
    this.initConnections();
  }

  // ==========================================
  // CONFIGURAÇÃO EXPRESS
  // ==========================================
  setupExpress() {
    this.app.use(express.json());
    
    // Health check endpoint
    this.app.get('/health', (req, res) => {
      const status = {
        status: this.isRunning ? 'healthy' : 'unhealthy',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        connections: {
          redis: this.connections.redis?.isReady || false,
          postgres: this.connections.postgres?._connected || false,
          binance: this.connections.binance?.has || false
        },
        symbols: this.symbols,
        websockets: this.websockets.size
      };
      
      res.status(this.isRunning ? 200 : 503).json(status);
    });

    // Métricas endpoint
    this.app.get('/metrics', (req, res) => {
      const metrics = {
        active_websockets: this.websockets.size,
        symbols_monitored: this.symbols.length,
        intervals_tracked: this.intervals.length,
        memory_usage: process.memoryUsage(),
        cpu_usage: process.cpuUsage()
      };
      
      res.json(metrics);
    });

    // Endpoint para backfill de dados históricos
    this.app.post('/backfill', async (req, res) => {
      try {
        const { symbol, interval, start_date, end_date } = req.body;
        
        if (!symbol || !interval || !start_date || !end_date) {
          return res.status(400).json({ 
            error: 'Parâmetros obrigatórios: symbol, interval, start_date, end_date' 
          });
        }

        logger.info(`Iniciando backfill: ${symbol} ${interval} de ${start_date} até ${end_date}`);
        
        const startTime = new Date(start_date).getTime();
        const endTime = new Date(end_date).getTime();
        let currentTime = startTime;
        let totalCandles = 0;
        
        // Binance permite no máximo 1000 candles por request
        const batchSize = 1000;
        
        while (currentTime < endTime) {
          try {
            logger.info(`Fetching OHLCV: ${symbol} ${interval} from ${new Date(currentTime).toISOString()}`);
            
            const ohlcv = await this.connections.binance.fetchOHLCV(
              symbol, 
              interval, 
              currentTime, 
              batchSize
            );
            
            logger.info(`Received ${ohlcv ? ohlcv.length : 0} candles from Binance`);
            
            if (!ohlcv || ohlcv.length === 0) break;
            
            for (const candle of ohlcv) {
              const [timestamp, open, high, low, close, volume] = candle;
              
              if (timestamp > endTime) break;
              
              // Salvar em market_data (usado pelo execution-engine)
              const query = `
                INSERT INTO market_data (symbol, timestamp, open, high, low, close, volume, price, source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (symbol, timestamp) DO NOTHING
              `;
              
              const values = [
                symbol,
                new Date(timestamp),
                open,
                high,
                low,
                close,
                Math.floor(volume), // Volume como inteiro (BIGINT)
                close, // price = close
                'backfill'
              ];
              
              await this.connections.postgres.query(query, values);
              totalCandles++;
            }
            
            // Mover para próximo batch
            currentTime = ohlcv[ohlcv.length - 1][0] + 1;
            
            logger.info(`Backfill progress: ${totalCandles} candles processadas`);
            
            // Rate limit da Binance: ~1200 requests/min
            await new Promise(resolve => setTimeout(resolve, 100));
            
          } catch (batchError) {
            logger.error('Erro no batch de backfill:', batchError);
            await new Promise(resolve => setTimeout(resolve, 1000));
          }
        }
        
        logger.info(`Backfill concluído: ${totalCandles} candles inseridas`);
        
        res.json({ 
          success: true, 
          symbol, 
          interval,
          start_date,
          end_date,
          candles_inserted: totalCandles 
        });
        
      } catch (error) {
        logger.error('Erro no backfill:', error);
        res.status(500).json({ error: error.message });
      }
    });
  }

  // ==========================================
  // INICIALIZAÇÃO DE CONEXÕES
  // ==========================================
  async initConnections() {
    try {
      await this.connectRedis();
      await this.connectPostgres();
      await this.connectBinance();
      await this.startDataCollection();
      
      this.isRunning = true;
      logger.info('Market Data Collector iniciado com sucesso', {
        symbols: this.symbols,
        intervals: this.intervals
      });
      
    } catch (error) {
      logger.error('Erro na inicialização:', error);
      process.exit(1);
    }
  }

  // ==========================================
  // CONEXÃO REDIS
  // ==========================================
  async connectRedis() {
    const redisUrl = process.env.REDIS_URL || 'redis://redis:6379';
    this.connections.redis = Redis.createClient({ url: redisUrl });
    
    this.connections.redis.on('error', (err) => {
      logger.error('Redis connection error:', err);
    });

    this.connections.redis.on('connect', () => {
      logger.info('Redis conectado com sucesso');
    });

    await this.connections.redis.connect();
  }

  // ==========================================
  // CONEXÃO POSTGRESQL/TIMESCALEDB
  // ==========================================
  async connectPostgres() {
    const connectionString = process.env.TIMESCALE_URL || 
      'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market';
    
    this.connections.postgres = new Client({ connectionString });
    
    await this.connections.postgres.connect();
    logger.info('TimescaleDB conectado com sucesso');

    // Criar tabelas se não existirem
    await this.createTables();
  }

  // ==========================================
  // CONEXÃO BINANCE
  // ==========================================
  async connectBinance() {
    this.connections.binance = new ccxt.binance({
      apiKey: process.env.BINANCE_API_KEY,
      secret: process.env.BINANCE_SECRET_KEY,
      sandbox: false, // DESABILITADO para usar dados reais da Binance
      enableRateLimit: true,
      options: {
        adjustForTimeDifference: true
      }
    });

    // Testar conexão
    try {
      await this.connections.binance.loadMarkets();
      logger.info('Binance API conectada com sucesso', {
        markets: Object.keys(this.connections.binance.markets).length
      });
    } catch (error) {
      logger.warn('Binance API não configurada, usando dados simulados', { error: error.message });
    }
  }

  // ==========================================
  // CRIAÇÃO DE TABELAS
  // ==========================================
  async createTables() {
    const createTableQuery = `
      CREATE TABLE IF NOT EXISTS market_data_realtime (
        id BIGSERIAL,
        symbol VARCHAR(20) NOT NULL,
        exchange VARCHAR(20) NOT NULL DEFAULT 'binance',
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        open_price DECIMAL(20,8) NOT NULL,
        high_price DECIMAL(20,8) NOT NULL,
        low_price DECIMAL(20,8) NOT NULL,
        close_price DECIMAL(20,8) NOT NULL,
        volume DECIMAL(20,8) NOT NULL,
        quote_volume DECIMAL(20,8),
        trades_count INTEGER,
        interval_type VARCHAR(10) NOT NULL DEFAULT '1m',
        created_at TIMESTAMPTZ DEFAULT NOW()
      );

      -- Criar hypertable se não existir
      SELECT create_hypertable('market_data_realtime', 'timestamp', if_not_exists => TRUE);

      -- Índices para performance
      CREATE INDEX IF NOT EXISTS idx_market_realtime_symbol_time 
      ON market_data_realtime (symbol, timestamp DESC);
    `;

    try {
      await this.connections.postgres.query(createTableQuery);
      logger.info('Tabelas criadas/verificadas com sucesso');
    } catch (error) {
      logger.error('Erro ao criar tabelas:', error);
    }
  }

  // ==========================================
  // INÍCIO DA COLETA DE DADOS
  // ==========================================
  async startDataCollection() {
    // Iniciar WebSockets para dados em tempo real
    for (const symbol of this.symbols) {
      await this.startWebSocketForSymbol(symbol);
    }

    // Agendar coleta de dados históricos
    this.scheduleHistoricalDataCollection();
    
    logger.info('Coleta de dados iniciada', {
      realtime_symbols: this.symbols.length,
      websockets_active: this.websockets.size
    });
  }

  // ==========================================
  // WEBSOCKET BINANCE
  // ==========================================
  async startWebSocketForSymbol(symbol) {
    const wsUrl = `wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@ticker`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.on('open', () => {
      logger.info(`WebSocket aberto para ${symbol}`);
      this.websockets.set(symbol, ws);
    });

    ws.on('message', async (data) => {
      try {
        const ticker = JSON.parse(data);
        await this.processTickerData(ticker);
      } catch (error) {
        logger.error(`Erro ao processar dados de ${symbol}:`, error);
      }
    });

    ws.on('error', (error) => {
      logger.error(`WebSocket erro para ${symbol}:`, error);
      // Reconectar após erro
      setTimeout(() => {
        this.startWebSocketForSymbol(symbol);
      }, 5000);
    });

    ws.on('close', () => {
      logger.warn(`WebSocket fechado para ${symbol}`);
      this.websockets.delete(symbol);
      // Reconectar após fechamento
      setTimeout(() => {
        this.startWebSocketForSymbol(symbol);
      }, 5000);
    });
  }

  // ==========================================
  // PROCESSAMENTO DE DADOS TICKER
  // ==========================================
  async processTickerData(ticker) {
    const marketData = {
      symbol: ticker.s,
      open_price: parseFloat(ticker.o),
      high_price: parseFloat(ticker.h),
      low_price: parseFloat(ticker.l),
      close_price: parseFloat(ticker.c),
      volume: parseFloat(ticker.v),
      quote_volume: parseFloat(ticker.q),
      trades_count: parseInt(ticker.n),
      timestamp: new Date(ticker.E),
      interval_type: '1m'
    };

    // Salvar no banco de dados
    await this.saveMarketData(marketData);
    
    // Publicar no Redis para outros serviços
    await this.publishToRedis(marketData);
    
    // Log de debug (apenas para algumas mensagens)
    if (Math.random() < 0.01) { // 1% das mensagens
      logger.debug('Dados processados:', {
        symbol: marketData.symbol,
        price: marketData.close_price,
        volume: marketData.volume
      });
    }
  }

  // ==========================================
  // SALVAR DADOS NO BANCO
  // ==========================================
  async saveMarketData(data) {
    const query = `
      INSERT INTO market_data_realtime 
      (symbol, open_price, high_price, low_price, close_price, volume, quote_volume, trades_count, timestamp, interval_type)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    `;

    const values = [
      data.symbol,
      data.open_price,
      data.high_price,
      data.low_price,
      data.close_price,
      data.volume,
      data.quote_volume,
      data.trades_count,
      data.timestamp,
      data.interval_type
    ];

    try {
      await this.connections.postgres.query(query, values);
    } catch (error) {
      logger.error('Erro ao salvar dados no banco:', error);
    }
  }

  // ==========================================
  // PUBLICAR NO REDIS
  // ==========================================
  async publishToRedis(data) {
    try {
      // Publicar dados em tempo real
      await this.connections.redis.publish('market:updates', JSON.stringify(data));
      
      // Cachear último preço
      await this.connections.redis.setEx(
        `market:${data.symbol}:latest`,
        60, // TTL de 60 segundos
        JSON.stringify({
          price: data.close_price,
          volume: data.volume,
          timestamp: data.timestamp
        })
      );
    } catch (error) {
      logger.error('Erro ao publicar no Redis:', error);
    }
  }

  // ==========================================
  // COLETA DE DADOS HISTÓRICOS
  // ==========================================
  scheduleHistoricalDataCollection() {
    // Coletar dados históricos a cada 5 minutos
    cron.schedule('*/5 * * * *', async () => {
      logger.info('Iniciando coleta de dados históricos');
      
      for (const symbol of this.symbols) {
        for (const interval of this.intervals) {
          if (interval !== '1m') { // 1m já é coletado via WebSocket
            await this.collectHistoricalData(symbol, interval);
          }
        }
      }
    });
  }

  async collectHistoricalData(symbol, interval) {
    try {
      const limit = 100; // Últimas 100 velas
      const ohlcv = await this.connections.binance.fetchOHLCV(symbol, interval, undefined, limit);
      
      for (const candle of ohlcv) {
        const [timestamp, open, high, low, close, volume] = candle;
        
        const marketData = {
          symbol,
          open_price: open,
          high_price: high,
          low_price: low,
          close_price: close,
          volume,
          quote_volume: null,
          trades_count: null,
          timestamp: new Date(timestamp),
          interval_type: interval
        };

        await this.saveMarketData(marketData);
      }
      
      logger.debug(`Dados históricos coletados: ${symbol} ${interval}`);
      
    } catch (error) {
      logger.error(`Erro ao coletar dados históricos ${symbol} ${interval}:`, error);
    }
  }

  // ==========================================
  // INICIALIZAR SERVIDOR
  // ==========================================
  start() {
    this.app.listen(this.port, '0.0.0.0', () => {
      logger.info(`Market Data Collector rodando na porta ${this.port}`);
    });

    // Graceful shutdown
    process.on('SIGTERM', () => this.shutdown());
    process.on('SIGINT', () => this.shutdown());
  }

  async shutdown() {
    logger.info('Iniciando shutdown graceful...');
    
    this.isRunning = false;
    
    // Fechar WebSockets
    for (const [symbol, ws] of this.websockets) {
      ws.close();
      logger.info(`WebSocket fechado para ${symbol}`);
    }
    
    // Fechar conexões
    if (this.connections.redis) {
      await this.connections.redis.quit();
    }
    
    if (this.connections.postgres) {
      await this.connections.postgres.end();
    }
    
    logger.info('Shutdown concluído');
    process.exit(0);
  }
}

// ==========================================
// INICIALIZAÇÃO
// ==========================================
const collector = new MarketDataCollector();
collector.start();
