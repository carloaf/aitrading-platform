-- Inicialização do PostgreSQL Principal
-- Este script é executado quando o container Postgres é criado pela primeira vez

-- Garantir que o usuário aitrading_user existe e tem as permissões necessárias
-- Nota: O usuário principal já é criado pelas variáveis POSTGRES_USER/POSTGRES_PASSWORD
-- Mas vamos garantir as permissões no banco
GRANT ALL PRIVILEGES ON DATABASE aitrading_db TO aitrading_user;
ALTER USER aitrading_user CREATEDB;

-- Criar tabela de usuários
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela de perfis de usuário
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bio TEXT,
    profile_picture_url VARCHAR(255),
    preferences JSONB,
    risk_tolerance VARCHAR(20),
    investment_style VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela de portfólios
CREATE TABLE IF NOT EXISTS portfolios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

-- Criar tabela de posições em portfólios
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    average_price DECIMAL(15,6),
    current_price DECIMAL(15,6),
    cost_basis DECIMAL(15,2),
    market_value DECIMAL(15,2),
    unrealized_pl DECIMAL(15,2),
    realized_pl DECIMAL(15,2),
    allocation_percent DECIMAL(5,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, symbol)
);

-- Criar tabela de transações
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL, -- 'buy', 'sell'
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(15,6) NOT NULL,
    total_amount DECIMAL(15,2) NOT NULL,
    fees DECIMAL(10,2) DEFAULT 0,
    transaction_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela de watchlists
CREATE TABLE IF NOT EXISTS watchlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

-- Criar tabela de símbolos em watchlists
CREATE TABLE IF NOT EXISTS watchlist_items (
    id SERIAL PRIMARY KEY,
    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    UNIQUE(watchlist_id, symbol)
);

-- Criar tabela de alertas
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    alert_type VARCHAR(20) NOT NULL, -- 'price', 'technical', 'news', etc.
    condition VARCHAR(20) NOT NULL, -- 'above', 'below', 'crosses', etc.
    threshold DECIMAL(15,6) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_triggered BOOLEAN DEFAULT FALSE,
    last_triggered TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela de notificações
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL, -- 'alert', 'system', 'news', etc.
    related_entity VARCHAR(50), -- 'alert', 'portfolio', 'watchlist', etc.
    related_id INTEGER, -- ID da entidade relacionada
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela de sinais de trading
CREATE TABLE IF NOT EXISTS trading_signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    signal_type VARCHAR(50) NOT NULL, -- 'buy', 'sell', 'hold', 'strong_buy', etc.
    source VARCHAR(50) NOT NULL, -- 'ai', 'technical', 'fundamental', etc.
    confidence DECIMAL(5,2), -- de 0 a 100%
    price_at_signal DECIMAL(15,6),
    target_price DECIMAL(15,6),
    stop_loss DECIMAL(15,6),
    timeframe VARCHAR(20), -- '1d', '4h', '1w', etc.
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Criar tabela de configurações do sistema
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    data_type VARCHAR(20) NOT NULL, -- 'string', 'integer', 'boolean', 'json', etc.
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela para logs do sistema
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL, -- 'info', 'warning', 'error', 'debug'
    component VARCHAR(50) NOT NULL, -- 'api', 'collector', 'analyzer', etc.
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela para tokens de acesso
CREATE TABLE IF NOT EXISTS access_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_value VARCHAR(255) UNIQUE NOT NULL,
    token_type VARCHAR(20) NOT NULL DEFAULT 'bearer',
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela para fontes de dados
CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL, -- 'api', 'websocket', 'file', etc.
    endpoint_url VARCHAR(255),
    api_key_name VARCHAR(100),
    api_key_value VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 100, -- menor número = maior prioridade
    rate_limit_per_minute INTEGER,
    last_request_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela para instrumentos financeiros
CREATE TABLE IF NOT EXISTS financial_instruments (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    instrument_type VARCHAR(50) NOT NULL, -- 'stock', 'crypto', 'forex', 'etf', etc.
    exchange VARCHAR(50),
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    sector VARCHAR(100),
    industry VARCHAR(100),
    country VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    last_price DECIMAL(15,6),
    price_updated_at TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar tabela para estratégias de trading
CREATE TABLE IF NOT EXISTS trading_strategies (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    strategy_type VARCHAR(50) NOT NULL, -- 'momentum', 'trend_following', 'mean_reversion', etc.
    timeframe VARCHAR(20) NOT NULL, -- '1m', '5m', '1h', '1d', etc.
    parameters JSONB NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    performance_metrics JSONB,
    backtest_results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para melhorar a performance
CREATE INDEX idx_portfolio_positions_symbol ON portfolio_positions(symbol);
CREATE INDEX idx_portfolio_positions_portfolio_id ON portfolio_positions(portfolio_id);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_portfolio_id ON transactions(portfolio_id);
CREATE INDEX idx_transactions_symbol ON transactions(symbol);
CREATE INDEX idx_transactions_transaction_date ON transactions(transaction_date);
CREATE INDEX idx_watchlist_items_symbol ON watchlist_items(symbol);
CREATE INDEX idx_alerts_user_id ON alerts(user_id);
CREATE INDEX idx_alerts_symbol ON alerts(symbol);
CREATE INDEX idx_trading_signals_symbol ON trading_signals(symbol);
CREATE INDEX idx_trading_signals_created_at ON trading_signals(created_at);
CREATE INDEX idx_financial_instruments_symbol ON financial_instruments(symbol);
CREATE INDEX idx_financial_instruments_type ON financial_instruments(instrument_type);

-- Criar um usuário administrador de teste
INSERT INTO users (username, email, password_hash, first_name, last_name, role)
VALUES 
    ('admin', 'admin@example.com', '$2b$10$rPhaF2xwBp3zJ3G9VVjZKO9gxRDcJ5JZ8.4ULkTFQoM1bG5ZH2QXq', 'Admin', 'User', 'admin')
ON CONFLICT (username) DO NOTHING;

-- Inserir algumas configurações do sistema
INSERT INTO system_settings (setting_key, setting_value, data_type, description)
VALUES 
    ('data_collection_interval', '5', 'integer', 'Interval in minutes for collecting market data'),
    ('max_api_retries', '3', 'integer', 'Maximum number of retries for API calls'),
    ('enable_notifications', 'true', 'boolean', 'Enable or disable system notifications'),
    ('maintenance_mode', 'false', 'boolean', 'System maintenance mode')
ON CONFLICT (setting_key) DO NOTHING;

-- Inserir algumas fontes de dados
INSERT INTO data_sources (name, source_type, endpoint_url, api_key_name, is_active, priority)
VALUES 
    ('Alpha Vantage', 'api', 'https://www.alphavantage.co/query', 'apikey', true, 10),
    ('Polygon.io', 'api', 'https://api.polygon.io', 'apiKey', true, 20),
    ('BRAPI', 'api', 'https://brapi.dev/api', 'token', true, 30)
ON CONFLICT DO NOTHING;

-- Log de sucesso
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL initialization completed successfully';
    RAISE NOTICE 'Created all required tables and indices';
    RAISE NOTICE 'Added test admin user and system settings';
END $$;
