const express = require('express');
const axios = require('axios');
const path = require('path');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;
const API_GATEWAY_URL = process.env.API_GATEWAY_URL || 'http://api-gateway:8080';

// ==========================================
// MIDDLEWARE
// ==========================================
const EXECUTION_ENGINE_URL = process.env.EXECUTION_ENGINE_URL || 'http://localhost:3008';

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net", "https://unpkg.com"],
      scriptSrcAttr: ["'unsafe-inline'"],
      styleSrc: ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
      imgSrc: ["'self'", "data:", "https:"],
      mediaSrc: ["'self'", "https://assets.mixkit.co"],
      connectSrc: [
        "'self'",
        API_GATEWAY_URL,
        EXECUTION_ENGINE_URL,
        "http://localhost:3008",
        "http://execution-engine:8001",
        "http://localhost:3007",
        "ws://localhost:3002",
        "wss://stream.binance.com:9443",
        "https://api.binance.com",
        "https://api.telegram.org",
        "https://discord.com",
        "https://discordapp.com",
        "https://cdn.jsdelivr.net"
      ],
      fontSrc: ["'self'", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net"],
    },
  },
}));

app.use(compression());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Rate limiting
const limiter = rateLimit({
  windowMs: 1 * 60 * 1000, // 1 minuto
  max: 500 // máximo 500 requests por IP por minuto (suficiente para SPA)
});
app.use(limiter);

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ==========================================
// HELPER FUNCTIONS
// ==========================================
const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString('pt-BR');
};

const getConfidenceColor = (confidence) => {
  if (confidence >= 70) return 'success';
  if (confidence >= 40) return 'warning';
  return 'danger';
};

const getSignalTypeColor = (type) => {
  switch (type.toLowerCase()) {
    case 'buy': return 'success';
    case 'sell': return 'danger';
    case 'hold': return 'secondary';
    default: return 'secondary';
  }
};

// ==========================================
// ROUTES
// ==========================================

// Home page
app.get('/', async (req, res) => {
  try {
    // Buscar estatísticas gerais
    const stats = await Promise.allSettled([
      axios.get(`${API_GATEWAY_URL}/health`),
      axios.get(`http://signal-generator:8000/stats`),
      axios.get(`http://news-collector:8000/stats`),
    ]);

    const platformHealth = stats[0].status === 'fulfilled' ? stats[0].value.data : null;
    const signalStats = stats[1].status === 'fulfilled' ? stats[1].value.data : null;
    const newsStats = stats[2].status === 'fulfilled' ? stats[2].value.data : null;

    res.render('index', {
      title: 'AI Trading Platform',
      platformHealth,
      signalStats,
      newsStats,
      formatDate,
      getConfidenceColor
    });

  } catch (error) {
    console.error('Erro ao carregar dashboard:', error.message);
    res.render('index', {
      title: 'AI Trading Platform',
      platformHealth: null,
      signalStats: null,
      newsStats: null,
      formatDate,
      getConfidenceColor,
      error: 'Erro ao carregar dados da plataforma'
    });
  }
});

// Dashboard page
app.get('/dashboard', (req, res) => {
  res.render('dashboard', {
    title: 'Dashboard - AI Trading Platform'
  });
});

// Signals page
app.get('/signals', async (req, res) => {
  try {
    const symbol = req.query.symbol || 'BTCUSDT';
    
    // Buscar estatísticas e sinais recentes
    const [statsResponse, signalsResponse] = await Promise.allSettled([
      axios.get(`http://signal-generator:8000/stats`),
      axios.post(`http://signal-generator:8000/generate`, { 
        symbol: symbol,
        timeframe: '1h'
      })
    ]);

    const stats = statsResponse.status === 'fulfilled' ? statsResponse.value.data : null;
    const latestSignal = signalsResponse.status === 'fulfilled' ? signalsResponse.value.data : null;

    res.render('signals', {
      title: 'Trading Signals',
      stats,
      latestSignal,
      symbol,
      formatDate,
      getConfidenceColor,
      getSignalTypeColor
    });

  } catch (error) {
    console.error('Erro ao carregar sinais:', error.message);
    res.render('signals', {
      title: 'Trading Signals',
      stats: null,
      latestSignal: null,
      symbol: 'BTCUSDT',
      formatDate,
      getConfidenceColor,
      getSignalTypeColor,
      error: 'Erro ao carregar sinais'
    });
  }
});

// Rota para notícias
app.get('/news', async (req, res) => {
  try {
    const symbol = req.query.symbol || 'bitcoin';
    
    // Buscar notícias
    const newsResponse = await axios.get(`http://localhost:3004/news?symbol=${symbol}`);
    const articles = newsResponse.data.articles || [];
    
    res.render('news', {
      title: 'Notícias',
      symbol,
      articles
    });
  } catch (error) {
    console.error('Erro ao buscar notícias:', error.message);
    res.render('news', {
      title: 'Notícias',
      symbol: 'bitcoin',
      articles: [],
      error: 'Erro ao carregar notícias'
    });
  }
});

// Rota para backtesting
app.get('/backtesting', (req, res) => {
  res.render('backtesting', {
    title: 'Backtesting'
  });
});

// ==========================================
// CONSOLIDATED DASHBOARD (PASSO 31)
// ==========================================
app.get('/consolidated', (req, res) => {
  const executionEngineUrl = process.env.EXECUTION_ENGINE_PUBLIC_URL || 'http://localhost:3008';
  res.render('consolidated-dashboard', {
    title: 'Dashboard Consolidado',
    executionEngineUrl
  });
});

// ==========================================
// RSI DIVERGENCE SCANNER DASHBOARD (PASSO 32)
// ==========================================

// Proxy para execution-engine scanner API (evita CORS - lê do banco TimescaleDB)
// Handles both GET and POST requests
app.get('/api/scanner/*', async (req, res) => {
  try {
    const apiPath = req.url;
    const url = `${EXECUTION_ENGINE_URL}${apiPath}`;
    
    console.log(`[Proxy] ${req.method} ${apiPath} → ${url}`);
    
    const response = await axios.get(url, {
      params: req.query,
      timeout: 60000  // 60s timeout - scan pode demorar
    });
    
    res.json(response.data);
  } catch (error) {
    console.error('[Proxy] Error:', error.message);
    if (error.code === 'ECONNABORTED') {
      console.error('[Proxy] Timeout! Considere dividir em grupos menores.');
    }
    res.status(error.response?.status || 500).json({
      success: false,
      error: error.message,
      code: error.code
    });
  }
});

app.post('/api/scanner/*', async (req, res) => {
  try {
    const apiPath = req.url;
    const url = `${EXECUTION_ENGINE_URL}${apiPath}`;
    
    console.log(`[Proxy] ${req.method} ${apiPath} → ${url}`);
    
    const response = await axios.post(url, req.body, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 60000  // 60s timeout - scan pode demorar
    });
    
    res.json(response.data);
  } catch (error) {
    console.error('[Proxy] Error:', error.message);
    if (error.code === 'ECONNABORTED') {
      console.error('[Proxy] Timeout! Considere dividir em grupos menores.');
    }
    res.status(error.response?.status || 500).json({
      success: false,
      error: error.message,
      code: error.code
    });
  }
});

// Proxy para AutoTrade Health (rápido - 10s timeout)
app.get('/api/autotrade/health', async (req, res) => {
  try {
    const url = `${EXECUTION_ENGINE_URL}/api/autotrade/health`;
    console.log(`[Proxy] GET /api/autotrade/health → ${url}`);
    
    const response = await axios.get(url, {
      timeout: 10000  // 10s timeout para health check
    });
    
    res.json(response.data);
  } catch (error) {
    console.error('[Proxy] Health check error:', error.message);
    res.status(error.response?.status || 500).json({
      healthy: false,
      error: error.message,
      code: error.code
    });
  }
});

// Proxy para AutoTrade API (POST requests)
app.post('/api/autotrade/*', async (req, res) => {
  try {
    const apiPath = req.url;
    const url = `${EXECUTION_ENGINE_URL}${apiPath}`;
    
    console.log(`[Proxy] ${req.method} ${apiPath} → ${url}`);
    
    const response = await axios.post(url, req.body, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 60000  // 60s para autotrade (aumentado)
    });
    
    res.json(response.data);
  } catch (error) {
    console.error('[Proxy] Error:', error.message);
    if (error.code === 'ECONNABORTED') {
      console.error('[Proxy] Timeout ao acessar AutoTrade (60s)!');
    }
    res.status(error.response?.status || 500).json({
      success: false,
      error: error.message,
      code: error.code
    });
  }
});

// Proxy para AutoTrade API (GET requests)
app.get('/api/autotrade/*', async (req, res) => {
  try {
    const apiPath = req.url;
    const url = `${EXECUTION_ENGINE_URL}${apiPath}`;
    
    console.log(`[Proxy] ${req.method} ${apiPath} → ${url}`);
    
    const response = await axios.get(url, {
      params: req.query,
      timeout: 60000  // 60s para autotrade (aumentado)
    });
    
    res.json(response.data);
  } catch (error) {
    console.error('[Proxy] Error:', error.message);
    if (error.code === 'ECONNABORTED') {
      console.error('[Proxy] Timeout ao acessar AutoTrade (60s)!');
    }
    res.status(error.response?.status || 500).json({
      success: false,
      error: error.message,
      code: error.code
    });
  }
});

app.get('/scanner', (req, res) => {
  // Disable cache to ensure latest JS code is always loaded
  res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');
  
  res.render('scanner-dashboard', {
    title: 'RSI Divergence Scanner'
  });
});

// ==========================================
// BACKTEST VISUAL DASHBOARD (PASSO 33)
// ==========================================
app.get('/backtest-visual', (req, res) => {
  const executionEngineUrl = process.env.EXECUTION_ENGINE_PUBLIC_URL || 'http://localhost:3008';
  res.render('backtest-visual', {
    title: 'Backtest Visual Dashboard',
    executionEngineUrl
  });
});

// Rota para Paper Trading Dashboard
app.get('/paper-trading', (req, res) => {
  // Use localhost URL for browser access (not Docker internal URL)
  const executionEngineUrl = process.env.EXECUTION_ENGINE_PUBLIC_URL || 'http://localhost:3008';
  res.render('paper-trading', {
    title: 'Paper Trading',
    executionEngineUrl
  });
});

// Rota para Trading Dashboard Avançado (TradingView Charts)
app.get('/trading-dashboard', (req, res) => {
  const executionEngineUrl = process.env.EXECUTION_ENGINE_PUBLIC_URL || 'http://localhost:3008';
  res.render('trading-dashboard', {
    title: 'Trading Dashboard',
    executionEngineUrl
  });
});

// Rota para estratégias profissionais
app.get('/strategies', (req, res) => {
  res.render('strategies', {
    title: 'Estratégias Profissionais'
  });
});

// Rota para análise técnica
app.get('/technical-analysis', (req, res) => {
  res.render('technical-analysis', {
    title: 'Análise Técnica'
  });
});

// Rota alternativa para análise técnica usando Chart.js
app.get('/technical-analysis-chartjs', (req, res) => {
  res.render('technical-analysis-chartjs', {
    title: 'Análise Técnica (Chart.js)'
  });
});

// Rota de teste para gráficos
app.get('/test-chart', (req, res) => {
  res.render('test-chart', {
    title: 'Teste de Gráfico'
  });
});

// API Routes for Dashboard
app.get('/api/market-data/historical', async (req, res) => {
  try {
    const { symbol, interval, limit } = req.query;
    
    // Try to get data from market data collector
    const response = await axios.get(`http://market-data-collector:8000/historical`, {
      params: { symbol, interval, limit },
      timeout: 5000
    });
    
    if (response.data && response.data.success) {
      res.json(response.data);
    } else {
      throw new Error('No data from market service');
    }
    
  } catch (error) {
    console.error('Error fetching historical data:', error.message);
    
    // Return mock data as fallback
    const mockData = generateMockHistoricalData(req.query.symbol, parseInt(req.query.limit) || 100);
    res.json({
      success: true,
      data: mockData,
      source: 'mock'
    });
  }
});

app.get('/api/market-data/ticker', async (req, res) => {
  try {
    const { symbol } = req.query;
    
    const response = await axios.get(`http://market-data-collector:8000/ticker/${symbol}`, {
      timeout: 5000
    });
    
    res.json(response.data);
    
  } catch (error) {
    console.error('Error fetching ticker data:', error.message);
    
    // Return mock ticker data
    res.json({
      success: true,
      data: {
        symbol: req.query.symbol,
        price: (45000 + Math.random() * 10000).toFixed(2),
        change: ((Math.random() - 0.5) * 1000).toFixed(2),
        changePercent: ((Math.random() - 0.5) * 5).toFixed(2),
        volume: (Math.random() * 1000000).toFixed(0)
      },
      source: 'mock'
    });
  }
});

app.get('/api/market-data/stats', async (req, res) => {
  try {
    // Try to get market stats from external API or service
    res.json({
      success: true,
      data: {
        marketCap: "$2.1T",
        volume24h: "$87.2B",
        btcDominance: "45.2%",
        fearGreed: 32
      }
    });
    
  } catch (error) {
    console.error('Error fetching market stats:', error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// Helper function to generate mock historical data
function generateMockHistoricalData(symbol, limit) {
  const data = [];
  const basePrice = symbol && symbol.includes('BTC') ? 45000 : symbol && symbol.includes('ETH') ? 3000 : 1.5;
  const now = Math.floor(Date.now() / 1000);
  
  for (let i = limit; i > 0; i--) {
    const timestamp = now - (i * 3600); // 1 hour intervals
    const open = basePrice * (1 + (Math.random() - 0.5) * 0.02);
    const close = open * (1 + (Math.random() - 0.5) * 0.02);
    const high = Math.max(open, close) * (1 + Math.random() * 0.01);
    const low = Math.min(open, close) * (1 - Math.random() * 0.01);
    const volume = Math.random() * 1000000;
    
    data.push({
      timestamp,
      open: open.toFixed(8),
      high: high.toFixed(8),
      low: low.toFixed(8),
      close: close.toFixed(8),
      volume: volume.toFixed(8)
    });
  }
  
  return data;
}

// API endpoint para gerar sinal
app.post('/api/generate-signal', async (req, res) => {
  try {
    const { symbol, timeframe } = req.body;
    
    const response = await axios.post(`http://signal-generator:8000/generate`, {
      symbol: symbol || 'BTCUSDT',
      timeframe: timeframe || '1h'
    });

    res.json(response.data);

  } catch (error) {
    console.error('Erro ao gerar sinal:', error.message);
    res.status(500).json({ 
      error: 'Erro ao gerar sinal',
      details: error.response?.data || error.message
    });
  }
});

// GET /history - Histórico de trades
app.get('/history', async (req, res) => {
  try {
    res.render('history', {
      title: 'Histórico de Trading'
    });
  } catch (error) {
    console.error('Erro ao carregar histórico:', error.message);
    res.render('error', {
      title: 'Erro',
      message: 'Erro ao carregar página de histórico',
      error: error
    });
  }
});

// GET /monte-carlo - Dashboard Monte Carlo Simulation
app.get('/monte-carlo', async (req, res) => {
  try {
    res.render('monte-carlo', {
      title: 'Monte Carlo Simulation - Análise de Estratégias'
    });
  } catch (error) {
    console.error('Erro ao carregar Monte Carlo:', error.message);
    res.render('error', {
      title: 'Erro',
      message: 'Erro ao carregar dashboard Monte Carlo',
      error: error
    });
  }
});

// Health check
app.get('/health', async (req, res) => {
  try {
    const healthResponse = await axios.get(`${API_GATEWAY_URL}/health`);
    res.json({
      status: 'healthy',
      frontend: 'running',
      gateway: healthResponse.data
    });
  } catch (error) {
    res.status(503).json({
      status: 'unhealthy',
      frontend: 'running',
      gateway: 'unreachable'
    });
  }
});

// ==========================================
// ERROR HANDLERS
// ==========================================
app.use((req, res) => {
  res.status(404).render('error', {
    title: 'Página não encontrada',
    message: 'A página que você procura não existe.',
    error: { status: 404 }
  });
});

app.use((err, req, res, next) => {
  console.error('Erro não tratado:', err);
  res.status(500).render('error', {
    title: 'Erro interno',
    message: 'Ocorreu um erro interno no servidor.',
    error: err
  });
});

// ==========================================
// START SERVER
// ==========================================
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Frontend server running on port ${PORT}`);
  console.log(`📊 Dashboard: http://localhost:${PORT}`);
});

module.exports = app;
