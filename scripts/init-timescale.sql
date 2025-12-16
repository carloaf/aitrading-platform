-- Inicialização do TimescaleDB
-- Este script é executado quando o container TimescaleDB é criado pela primeira vez

-- Primeiro, criar o banco de dados crypto_market se não existir
SELECT 'CREATE DATABASE crypto_market'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'crypto_market')\gexec

-- Conectar ao banco crypto_market
\c crypto_market

-- Criar a extensão TimescaleDB se não existir
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Criar tabela para dados de preços em tempo real
CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price DECIMAL(15,8) NOT NULL,
    volume BIGINT DEFAULT 0,
    high DECIMAL(15,8),
    low DECIMAL(15,8),
    open DECIMAL(15,8),
    close DECIMAL(15,8),
    source VARCHAR(50) DEFAULT 'unknown',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Converter a tabela em hypertable (característica principal do TimescaleDB)
SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);

-- Criar índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp ON market_data (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data (timestamp DESC);

-- Criar tabela para indicadores técnicos
CREATE TABLE IF NOT EXISTS technical_indicators (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    indicator_type VARCHAR(50) NOT NULL,
    indicator_value DECIMAL(15,8) NOT NULL,
    period INTEGER,
    parameters JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Converter em hypertable
SELECT create_hypertable('technical_indicators', 'timestamp', if_not_exists => TRUE);

-- Criar índices
CREATE INDEX IF NOT EXISTS idx_technical_indicators_symbol_type_timestamp 
ON technical_indicators (symbol, indicator_type, timestamp DESC);

-- Criar tabela para dados agregados (OHLCV por período)
CREATE TABLE IF NOT EXISTS ohlcv_data (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- '1m', '5m', '15m', '1h', '1d', etc
    open DECIMAL(15,8) NOT NULL,
    high DECIMAL(15,8) NOT NULL,
    low DECIMAL(15,8) NOT NULL,
    close DECIMAL(15,8) NOT NULL,
    volume BIGINT DEFAULT 0,
    vwap DECIMAL(15,8), -- Volume Weighted Average Price
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timestamp, timeframe)
);

-- Converter em hypertable
SELECT create_hypertable('ohlcv_data', 'timestamp', if_not_exists => TRUE);

-- Criar índices
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_timeframe_timestamp 
ON ohlcv_data (symbol, timeframe, timestamp DESC);

-- Criar política de retenção (manter dados por 1 ano)
SELECT add_retention_policy('market_data', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('technical_indicators', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('ohlcv_data', INTERVAL '2 years', if_not_exists => TRUE);

-- Criar continuous aggregates para dados OHLCV (com configurações corrigidas)
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1h
WITH (timescaledb.continuous) AS
SELECT 
    symbol,
    time_bucket('1 hour', timestamp) AS bucket,
    FIRST(price, timestamp) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    LAST(price, timestamp) AS close,
    SUM(volume) AS volume,
    AVG(price) AS vwap
FROM market_data
GROUP BY symbol, bucket;

-- Política de refresh corrigida para a view materializada (janela maior)
SELECT add_continuous_aggregate_policy('ohlcv_1h',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '30 minutes',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE);

-- Criar view materializada para dados diários
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1d
WITH (timescaledb.continuous) AS
SELECT 
    symbol,
    time_bucket('1 day', timestamp) AS bucket,
    FIRST(price, timestamp) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    LAST(price, timestamp) AS close,
    SUM(volume) AS volume,
    AVG(price) AS vwap
FROM market_data
GROUP BY symbol, bucket;

-- Política de refresh corrigida para dados diários (janela maior)
SELECT add_continuous_aggregate_policy('ohlcv_1d',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '12 hours',
    schedule_interval => INTERVAL '12 hours',
    if_not_exists => TRUE);

-- Criar função para inserir dados de mercado com validação
CREATE OR REPLACE FUNCTION insert_market_data(
    p_symbol VARCHAR(20),
    p_timestamp TIMESTAMPTZ,
    p_price DECIMAL(15,8),
    p_volume BIGINT DEFAULT 0,
    p_high DECIMAL(15,8) DEFAULT NULL,
    p_low DECIMAL(15,8) DEFAULT NULL,
    p_open DECIMAL(15,8) DEFAULT NULL,
    p_close DECIMAL(15,8) DEFAULT NULL,
    p_source VARCHAR(50) DEFAULT 'api'
) RETURNS BIGINT AS $$
DECLARE
    result_id BIGINT;
BEGIN
    -- Validar se o preço é positivo
    IF p_price <= 0 THEN
        RAISE EXCEPTION 'Price must be positive: %', p_price;
    END IF;
    
    -- Validar se o timestamp não é futuro
    IF p_timestamp > NOW() + INTERVAL '1 hour' THEN
        RAISE EXCEPTION 'Timestamp cannot be more than 1 hour in the future: %', p_timestamp;
    END IF;
    
    INSERT INTO market_data (
        symbol, timestamp, price, volume, high, low, open, close, source
    ) VALUES (
        UPPER(p_symbol), p_timestamp, p_price, p_volume, p_high, p_low, p_open, p_close, p_source
    ) RETURNING id INTO result_id;
    
    RETURN result_id;
END;
$$ LANGUAGE plpgsql;

-- Criar função para obter últimos preços
CREATE OR REPLACE FUNCTION get_latest_prices(p_symbols TEXT[] DEFAULT NULL)
RETURNS TABLE (
    symbol VARCHAR(20),
    price DECIMAL(15,8),
    ts TIMESTAMPTZ,
    volume BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (md.symbol)
        md.symbol,
        md.price,
        md.timestamp,
        md.volume
    FROM market_data md
    WHERE (p_symbols IS NULL OR md.symbol = ANY(p_symbols))
    ORDER BY md.symbol, md.timestamp DESC;
END;
$$ LANGUAGE plpgsql;

-- Criar usuário crypto_user se não existir
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'crypto_user') THEN
        CREATE USER crypto_user WITH PASSWORD 'crypto_pass';
    END IF;
END
$$;

-- Conceder permissões ao usuário
GRANT CONNECT ON DATABASE crypto_market TO crypto_user;
GRANT USAGE ON SCHEMA public TO crypto_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO crypto_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO crypto_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO crypto_user;

-- Logs de sucesso
DO $$
BEGIN
    RAISE NOTICE 'TimescaleDB initialization completed successfully';
    RAISE NOTICE 'Created database: crypto_market';
    RAISE NOTICE 'Created user: crypto_user';
    RAISE NOTICE 'Created hypertables: market_data, technical_indicators, ohlcv_data';
    RAISE NOTICE 'Created materialized views: ohlcv_1h, ohlcv_1d';
    RAISE NOTICE 'Created functions: insert_market_data, get_latest_prices';
END $$;