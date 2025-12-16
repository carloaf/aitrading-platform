-- ==========================================
-- INICIALIZAÇÃO DO BANCO TIMESCALEDB
-- Criação de tabelas otimizadas para séries temporais
-- ==========================================

-- Extensão TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ==========================================
-- TABELA PRINCIPAL DE DADOS DE MERCADO
-- ==========================================

CREATE TABLE IF NOT EXISTS market_data (
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
    interval_type VARCHAR(10) NOT NULL DEFAULT '1m', -- 1m, 5m, 15m, 1h, 4h, 1d
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Converter para hypertable (TimescaleDB)
SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time 
ON market_data (symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_interval 
ON market_data (symbol, interval_type, timestamp DESC);

-- ==========================================
-- TABELA DE INDICADORES TÉCNICOS
-- ==========================================

CREATE TABLE IF NOT EXISTS technical_indicators (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    interval_type VARCHAR(10) NOT NULL,
    
    -- Moving Averages
    sma_20 DECIMAL(20,8),
    sma_50 DECIMAL(20,8),
    sma_200 DECIMAL(20,8),
    ema_12 DECIMAL(20,8),
    ema_26 DECIMAL(20,8),
    
    -- Oscillators
    rsi_14 DECIMAL(10,4),
    macd_line DECIMAL(20,8),
    macd_signal DECIMAL(20,8),
    macd_histogram DECIMAL(20,8),
    
    -- Bollinger Bands
    bb_upper DECIMAL(20,8),
    bb_middle DECIMAL(20,8),
    bb_lower DECIMAL(20,8),
    
    -- Volume indicators
    volume_sma_20 DECIMAL(20,8),
    
    -- Price action
    support_level DECIMAL(20,8),
    resistance_level DECIMAL(20,8),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Converter para hypertable
SELECT create_hypertable('technical_indicators', 'timestamp', if_not_exists => TRUE);

-- Índices
CREATE INDEX IF NOT EXISTS idx_tech_indicators_symbol_time 
ON technical_indicators (symbol, timestamp DESC);

-- ==========================================
-- TABELA DE SINAIS DE TRADING
-- ==========================================

CREATE TABLE IF NOT EXISTS trading_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_type VARCHAR(10) NOT NULL CHECK (signal_type IN ('BUY', 'SELL', 'HOLD')),
    confidence DECIMAL(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    price DECIMAL(20,8) NOT NULL,
    
    -- Razões do sinal
    technical_score DECIMAL(5,4),
    sentiment_score DECIMAL(5,4),
    volume_score DECIMAL(5,4),
    
    -- Metadata
    strategy_name VARCHAR(50),
    conditions JSONB,
    
    -- Status
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'EXECUTED')),
    expires_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_trading_signals_symbol_time 
ON trading_signals (symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trading_signals_status 
ON trading_signals (status, timestamp DESC);

-- ==========================================
-- TABELA DE CONFIGURAÇÕES DE USUÁRIO
-- ==========================================

CREATE TABLE IF NOT EXISTS user_configurations (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- Configurações de alertas
    enable_notifications BOOLEAN DEFAULT TRUE,
    price_alert_threshold DECIMAL(5,4) DEFAULT 0.05, -- 5% change
    volume_alert_threshold DECIMAL(5,4) DEFAULT 2.0, -- 200% volume increase
    
    -- Configurações de trading
    risk_tolerance VARCHAR(10) DEFAULT 'MEDIUM' CHECK (risk_tolerance IN ('LOW', 'MEDIUM', 'HIGH')),
    max_position_size DECIMAL(10,4) DEFAULT 0.1, -- 10% of portfolio
    
    -- Preferências de indicadores
    preferred_indicators TEXT[] DEFAULT ARRAY['RSI', 'MACD', 'SMA'],
    custom_parameters JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, symbol)
);

-- ==========================================
-- TABELA DE LOGS DE SISTEMA
-- ==========================================

CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service_name VARCHAR(50) NOT NULL,
    log_level VARCHAR(10) NOT NULL CHECK (log_level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL')),
    message TEXT NOT NULL,
    metadata JSONB,
    error_details JSONB
);

-- Converter para hypertable
SELECT create_hypertable('system_logs', 'timestamp', if_not_exists => TRUE);

-- Índices
CREATE INDEX IF NOT EXISTS idx_system_logs_service_time 
ON system_logs (service_name, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_system_logs_level_time 
ON system_logs (log_level, timestamp DESC);

-- ==========================================
-- POLÍTICAS DE RETENÇÃO DE DADOS
-- ==========================================

-- Manter dados de mercado por 2 anos
SELECT add_retention_policy('market_data', INTERVAL '2 years', if_not_exists => TRUE);

-- Manter indicadores técnicos por 1 ano
SELECT add_retention_policy('technical_indicators', INTERVAL '1 year', if_not_exists => TRUE);

-- Manter logs do sistema por 3 meses
SELECT add_retention_policy('system_logs', INTERVAL '3 months', if_not_exists => TRUE);

-- ==========================================
-- CONTINUOUS AGGREGATES (MATERIALIZED VIEWS)
-- ==========================================

-- Agregação horária dos dados de mercado
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_hourly
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', timestamp) AS hour,
    symbol,
    exchange,
    FIRST(open_price, timestamp) AS open_price,
    MAX(high_price) AS high_price,
    MIN(low_price) AS low_price,
    LAST(close_price, timestamp) AS close_price,
    SUM(volume) AS volume,
    SUM(quote_volume) AS quote_volume,
    SUM(trades_count) AS trades_count
FROM market_data 
WHERE interval_type = '1m'
GROUP BY hour, symbol, exchange;

-- Política de refresh automático
SELECT add_continuous_aggregate_policy('market_data_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes',
    if_not_exists => TRUE);

-- ==========================================
-- FUNÇÕES AUXILIARES
-- ==========================================

-- Função para calcular variação percentual
CREATE OR REPLACE FUNCTION price_change_percent(current_price DECIMAL, previous_price DECIMAL)
RETURNS DECIMAL AS $$
BEGIN
    IF previous_price = 0 OR previous_price IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN ((current_price - previous_price) / previous_price) * 100;
END;
$$ LANGUAGE plpgsql;

-- Função para obter último preço de um símbolo
CREATE OR REPLACE FUNCTION get_latest_price(symbol_param VARCHAR)
RETURNS DECIMAL AS $$
DECLARE
    latest_price DECIMAL;
BEGIN
    SELECT close_price INTO latest_price
    FROM market_data 
    WHERE symbol = symbol_param 
    ORDER BY timestamp DESC 
    LIMIT 1;
    
    RETURN latest_price;
END;
$$ LANGUAGE plpgsql;

-- ==========================================
-- DADOS INICIAIS DE TESTE (OPCIONAL)
-- ==========================================

-- Inserir configuração padrão
INSERT INTO user_configurations (user_id, symbol) 
VALUES ('default', 'BTCUSDT'), ('default', 'ETHUSDT')
ON CONFLICT (user_id, symbol) DO NOTHING;

-- Mensagem de sucesso
DO $$
BEGIN
    RAISE NOTICE 'TimescaleDB inicializado com sucesso!';
    RAISE NOTICE 'Tabelas criadas: market_data, technical_indicators, trading_signals, user_configurations, system_logs';
    RAISE NOTICE 'Hypertables configuradas com políticas de retenção';
    RAISE NOTICE 'Continuous aggregates criadas para otimização de consultas';
END $$;
