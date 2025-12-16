const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
const { createProxyMiddleware } = require('http-proxy-middleware');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const Redis = require('redis');
const { Client } = require('pg');
const winston = require('winston');
const Joi = require('joi');
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
  defaultMeta: { service: 'api-gateway' },
  transports: [
    new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/combined.log' }),
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

// ==========================================
// CONFIGURAÇÃO PRINCIPAL
// ==========================================
class APIGateway {
  constructor() {
    this.app = express();
    this.port = process.env.API_GATEWAY_PORT || 8080;
    this.isRunning = false;
    this.connections = {
      redis: null,
      postgres: null
    };
    
    this.initializeMiddleware();
    this.initializeRoutes();
    this.initializeConnections();
  }

  // ==========================================
  // MIDDLEWARE DE SEGURANÇA
  // ==========================================
  initializeMiddleware() {
    // Segurança básica
    this.app.use(helmet({
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          scriptSrc: ["'self'", "'unsafe-inline'"],
          styleSrc: ["'self'", "'unsafe-inline'"],
          imgSrc: ["'self'", "data:", "https:"],
        },
      },
    }));

    // Compressão
    this.app.use(compression());

    // CORS
    this.app.use(cors({
      origin: process.env.CORS_ORIGINS?.split(',') || ['http://localhost:3000'],
      credentials: true,
      optionsSuccessStatus: 200
    }));

    // Rate limiting global
    const globalLimiter = rateLimit({
      windowMs: 15 * 60 * 1000, // 15 minutos
      max: 1000, // máximo 1000 requests por IP
      message: {
        error: 'Muitas requisições, tente novamente em 15 minutos'
      },
      standardHeaders: true,
      legacyHeaders: false,
    });
    this.app.use(globalLimiter);

    // Rate limiting para autenticação
    const authLimiter = rateLimit({
      windowMs: 15 * 60 * 1000,
      max: 10, // máximo 10 tentativas de login por IP
      skipSuccessfulRequests: true,
    });
    this.app.use('/auth', authLimiter);

    // Parse JSON
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true }));

    // Logging de requests
    this.app.use((req, res, next) => {
      logger.info(`${req.method} ${req.path}`, {
        ip: req.ip,
        userAgent: req.get('User-Agent'),
        timestamp: new Date().toISOString()
      });
      next();
    });
  }

  // ==========================================
  // CONEXÕES COM BANCOS
  // ==========================================
  async initializeConnections() {
    try {
      await this.connectRedis();
      await this.connectPostgres();
      await this.createUserTables();
      
      this.isRunning = true;
      logger.info('API Gateway inicializado com sucesso');
      
    } catch (error) {
      logger.error('Erro na inicialização das conexões:', error);
      process.exit(1);
    }
  }

  async connectRedis() {
    const redisUrl = process.env.REDIS_URL || 'redis://redis:6379';
    this.connections.redis = Redis.createClient({ url: redisUrl });
    
    this.connections.redis.on('error', (err) => {
      logger.error('Redis connection error:', err);
    });

    await this.connections.redis.connect();
    logger.info('Redis conectado com sucesso');
  }

  async connectPostgres() {
    const connectionString = process.env.TIMESCALE_URL || 
      'postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_market';
    
    this.connections.postgres = new Client({ connectionString });
    await this.connections.postgres.connect();
    logger.info('PostgreSQL conectado com sucesso');
  }

  async createUserTables() {
    const createUsersTable = `
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'trader')),
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        last_login TIMESTAMPTZ,
        login_count INTEGER DEFAULT 0
      );

      CREATE TABLE IF NOT EXISTS user_sessions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        token_hash VARCHAR(255) NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        ip_address INET,
        user_agent TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
      CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
      CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token_hash);
      CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);
    `;

    await this.connections.postgres.query(createUsersTable);
    
    // Criar usuário admin padrão se não existir
    await this.createDefaultAdmin();
  }

  async createDefaultAdmin() {
    const adminExists = await this.connections.postgres.query(
      'SELECT id FROM users WHERE username = $1',
      ['admin']
    );

    if (adminExists.rows.length === 0) {
      const passwordHash = await bcrypt.hash('admin123', 12);
      await this.connections.postgres.query(
        'INSERT INTO users (username, email, password_hash, role) VALUES ($1, $2, $3, $4)',
        ['admin', 'admin@aitrading.dev', passwordHash, 'admin']
      );
      logger.info('Usuário admin padrão criado: admin/admin123');
    }
  }

  // ==========================================
  // MIDDLEWARE DE AUTENTICAÇÃO
  // ==========================================
  async authenticateToken(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) {
      return res.status(401).json({ error: 'Token de acesso requerido' });
    }

    try {
      // Verificar se token está na blacklist
      const isBlacklisted = await this.connections.redis.get(`blacklist:${token}`);
      if (isBlacklisted) {
        return res.status(401).json({ error: 'Token inválido' });
      }

      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      
      // Verificar se sessão ainda é válida
      const session = await this.connections.postgres.query(
        'SELECT * FROM user_sessions WHERE token_hash = $1 AND expires_at > NOW()',
        [await bcrypt.hash(token, 1)] // Hash simples para comparação
      );

      if (session.rows.length === 0) {
        return res.status(401).json({ error: 'Sessão expirada' });
      }

      req.user = decoded;
      next();
    } catch (error) {
      logger.error('Erro na autenticação:', error);
      res.status(403).json({ error: 'Token inválido' });
    }
  }

  // ==========================================
  // ROTAS DE AUTENTICAÇÃO
  // ==========================================
  initializeRoutes() {
    // Health check
    this.app.get('/health', (req, res) => {
      const status = {
        status: this.isRunning ? 'healthy' : 'unhealthy',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        connections: {
          redis: this.connections.redis?.isReady || false,
          postgres: this.connections.postgres?._connected || false
        },
        version: process.env.npm_package_version || '1.0.0'
      };
      
      res.status(this.isRunning ? 200 : 503).json(status);
    });

    // Métricas
    this.app.get('/metrics', this.authenticateToken.bind(this), (req, res) => {
      const metrics = {
        memory_usage: process.memoryUsage(),
        cpu_usage: process.cpuUsage(),
        uptime: process.uptime(),
        node_version: process.version
      };
      res.json(metrics);
    });

    // ==========================================
    // ROTAS DE AUTENTICAÇÃO
    // ==========================================
    
    // Login
    this.app.post('/auth/login', async (req, res) => {
      try {
        const schema = Joi.object({
          username: Joi.string().alphanum().min(3).max(30).required(),
          password: Joi.string().min(6).required()
        });

        const { error, value } = schema.validate(req.body);
        if (error) {
          return res.status(400).json({ error: error.details[0].message });
        }

        const { username, password } = value;

        // Buscar usuário
        const userResult = await this.connections.postgres.query(
          'SELECT * FROM users WHERE username = $1 AND is_active = true',
          [username]
        );

        if (userResult.rows.length === 0) {
          return res.status(401).json({ error: 'Credenciais inválidas' });
        }

        const user = userResult.rows[0];

        // Verificar senha
        const passwordValid = await bcrypt.compare(password, user.password_hash);
        if (!passwordValid) {
          return res.status(401).json({ error: 'Credenciais inválidas' });
        }

        // Gerar token JWT
        const token = jwt.sign(
          { 
            userId: user.id, 
            username: user.username, 
            role: user.role 
          },
          process.env.JWT_SECRET,
          { expiresIn: '24h' }
        );

        // Salvar sessão
        const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 horas
        await this.connections.postgres.query(
          'INSERT INTO user_sessions (user_id, token_hash, expires_at, ip_address, user_agent) VALUES ($1, $2, $3, $4, $5)',
          [user.id, await bcrypt.hash(token, 1), expiresAt, req.ip, req.get('User-Agent')]
        );

        // Atualizar último login
        await this.connections.postgres.query(
          'UPDATE users SET last_login = NOW(), login_count = login_count + 1 WHERE id = $1',
          [user.id]
        );

        logger.info(`Login realizado: ${username}`, { ip: req.ip });

        res.json({
          token,
          user: {
            id: user.id,
            username: user.username,
            email: user.email,
            role: user.role
          }
        });

      } catch (error) {
        logger.error('Erro no login:', error);
        res.status(500).json({ error: 'Erro interno do servidor' });
      }
    });

    // Logout
    this.app.post('/auth/logout', this.authenticateToken.bind(this), async (req, res) => {
      try {
        const token = req.headers['authorization'].split(' ')[1];
        
        // Adicionar token à blacklist
        await this.connections.redis.setEx(`blacklist:${token}`, 24 * 60 * 60, 'true');
        
        // Remover sessão do banco
        await this.connections.postgres.query(
          'DELETE FROM user_sessions WHERE token_hash = $1',
          [await bcrypt.hash(token, 1)]
        );

        logger.info(`Logout realizado: ${req.user.username}`);
        res.json({ message: 'Logout realizado com sucesso' });

      } catch (error) {
        logger.error('Erro no logout:', error);
        res.status(500).json({ error: 'Erro interno do servidor' });
      }
    });

    // ==========================================
    // PROXY PARA MICROSERVIÇOS
    // ==========================================
    
    // Market Data Service
    this.app.use('/api/market', 
      this.authenticateToken.bind(this),
      createProxyMiddleware({
        target: 'http://market-data-collector:3001',
        changeOrigin: true,
        pathRewrite: { '^/api/market': '' },
        onError: (err, req, res) => {
          logger.error('Proxy error para market service:', err);
          res.status(503).json({ error: 'Serviço temporariamente indisponível' });
        }
      })
    );

    // News Service
    this.app.use('/api/news',
      this.authenticateToken.bind(this),
      createProxyMiddleware({
        target: 'http://news-collector:8000',
        changeOrigin: true,
        pathRewrite: { '^/api/news': '' },
        onError: (err, req, res) => {
          logger.error('Proxy error para news service:', err);
          res.status(503).json({ error: 'Serviço temporariamente indisponível' });
        }
      })
    );

    // Indicators Service
    this.app.use('/api/indicators',
      this.authenticateToken.bind(this),
      createProxyMiddleware({
        target: 'http://indicator-calculator:8000',
        changeOrigin: true,
        pathRewrite: { '^/api/indicators': '' },
        onError: (err, req, res) => {
          logger.error('Proxy error para indicators service:', err);
          res.status(503).json({ error: 'Serviço temporariamente indisponível' });
        }
      })
    );

    // Sentiment Service
    this.app.use('/api/sentiment',
      this.authenticateToken.bind(this),
      createProxyMiddleware({
        target: 'http://sentiment-analyzer:8000',
        changeOrigin: true,
        pathRewrite: { '^/api/sentiment': '' },
        onError: (err, req, res) => {
          logger.error('Proxy error para sentiment service:', err);
          res.status(503).json({ error: 'Serviço temporariamente indisponível' });
        }
      })
    );

    // Signals Service - NOVO SERVIÇO
    this.app.use('/api/signals',
      this.authenticateToken.bind(this),
      createProxyMiddleware({
        target: 'http://signal-generator:8000',
        changeOrigin: true,
        pathRewrite: { '^/api/signals': '' },
        onError: (err, req, res) => {
          logger.error('Proxy error para signals service:', err);
          res.status(503).json({ error: 'Serviço temporariamente indisponível' });
        }
      })
    );

    // 404 handler
    this.app.use('*', (req, res) => {
      res.status(404).json({ error: 'Endpoint não encontrado' });
    });

    // Error handler
    this.app.use((err, req, res, next) => {
      logger.error('Erro não tratado:', err);
      res.status(500).json({ error: 'Erro interno do servidor' });
    });
  }

  // ==========================================
  // INICIALIZAR SERVIDOR
  // ==========================================
  start() {
    this.app.listen(this.port, '0.0.0.0', () => {
      logger.info(`API Gateway rodando na porta ${this.port}`);
    });

    // Graceful shutdown
    process.on('SIGTERM', () => this.shutdown());
    process.on('SIGINT', () => this.shutdown());
  }

  async shutdown() {
    logger.info('Iniciando shutdown graceful...');
    
    this.isRunning = false;
    
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
const gateway = new APIGateway();
gateway.start();
