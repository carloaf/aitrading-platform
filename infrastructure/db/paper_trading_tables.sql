-- ==========================================
-- TABELA DE TRADES DO PAPER TRADING
-- Armazenamento de todas as operações executadas
-- ==========================================

CREATE TABLE IF NOT EXISTS paper_trading_trades (
    id BIGSERIAL PRIMARY KEY,
    
    -- Identificação
    session_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    
    -- Dados da ordem
    trade_type VARCHAR(10) NOT NULL CHECK (trade_type IN ('BUY', 'SELL')),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price DECIMAL(20,8) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    
    -- Financeiro
    value DECIMAL(20,8) NOT NULL,           -- price * quantity
    fee DECIMAL(20,8) DEFAULT 0,
    balance_before DECIMAL(20,8),
    balance_after DECIMAL(20,8),
    
    -- Performance
    pnl DECIMAL(20,8),                      -- Profit/Loss em USD
    pnl_percent DECIMAL(10,4),              -- P&L em %
    cumulative_pnl DECIMAL(20,8),           -- P&L acumulado
    
    -- Contexto técnico
    signal_confidence DECIMAL(5,4),         -- 0.0 a 1.0
    indicators_snapshot JSONB,              -- Estado dos indicadores no momento
    
    -- Posição
    position_side VARCHAR(10),              -- LONG, SHORT, FLAT
    position_size DECIMAL(20,8),            -- Tamanho da posição após trade
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Converter para hypertable (TimescaleDB)
SELECT create_hypertable('paper_trading_trades', 'timestamp', if_not_exists => TRUE);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_trades_session 
ON paper_trading_trades (session_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trades_symbol 
ON paper_trading_trades (symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trades_strategy 
ON paper_trading_trades (strategy_name, timestamp DESC);

-- ==========================================
-- TABELA DE SESSÕES DE PAPER TRADING
-- Metadados das sessões ativas e históricas
-- ==========================================

CREATE TABLE IF NOT EXISTS paper_trading_sessions (
    id BIGSERIAL PRIMARY KEY,
    
    -- Identificação
    session_id VARCHAR(100) NOT NULL UNIQUE,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    
    -- Configuração
    initial_balance DECIMAL(20,8) NOT NULL,
    current_balance DECIMAL(20,8) NOT NULL,
    strategy_parameters JSONB,
    
    -- Timeframe
    timeframe VARCHAR(10),
    
    -- Status
    is_running BOOLEAN DEFAULT TRUE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    
    -- Performance
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(20,8) DEFAULT 0,
    total_pnl_percent DECIMAL(10,4) DEFAULT 0,
    max_drawdown DECIMAL(10,4),
    sharpe_ratio DECIMAL(10,4),
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_sessions_symbol 
ON paper_trading_sessions (symbol, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_status 
ON paper_trading_sessions (is_running, started_at DESC);

-- ==========================================
-- FUNÇÃO PARA ATUALIZAR ESTATÍSTICAS DA SESSÃO
-- ==========================================

CREATE OR REPLACE FUNCTION update_session_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Atualizar estatísticas da sessão após cada trade
    UPDATE paper_trading_sessions
    SET 
        total_trades = (
            SELECT COUNT(*) 
            FROM paper_trading_trades 
            WHERE session_id = NEW.session_id
        ),
        winning_trades = (
            SELECT COUNT(*) 
            FROM paper_trading_trades 
            WHERE session_id = NEW.session_id AND pnl > 0
        ),
        losing_trades = (
            SELECT COUNT(*) 
            FROM paper_trading_trades 
            WHERE session_id = NEW.session_id AND pnl < 0
        ),
        total_pnl = (
            SELECT COALESCE(SUM(pnl), 0) 
            FROM paper_trading_trades 
            WHERE session_id = NEW.session_id
        ),
        current_balance = NEW.balance_after,
        updated_at = NOW()
    WHERE session_id = NEW.session_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para atualizar stats automaticamente
DROP TRIGGER IF EXISTS trigger_update_session_stats ON paper_trading_trades;
CREATE TRIGGER trigger_update_session_stats
AFTER INSERT ON paper_trading_trades
FOR EACH ROW
EXECUTE FUNCTION update_session_stats();

-- ==========================================
-- VIEW: PERFORMANCE POR SESSÃO
-- ==========================================

CREATE OR REPLACE VIEW vw_session_performance AS
SELECT 
    s.session_id,
    s.symbol,
    s.strategy_name,
    s.initial_balance,
    s.current_balance,
    s.total_trades,
    s.winning_trades,
    s.losing_trades,
    CASE 
        WHEN s.total_trades > 0 
        THEN ROUND((s.winning_trades::DECIMAL / s.total_trades) * 100, 2) 
        ELSE 0 
    END as win_rate_percent,
    s.total_pnl,
    ROUND(((s.current_balance - s.initial_balance) / s.initial_balance) * 100, 2) as roi_percent,
    s.is_running,
    s.started_at,
    s.stopped_at,
    EXTRACT(EPOCH FROM (COALESCE(s.stopped_at, NOW()) - s.started_at))/3600 as runtime_hours
FROM paper_trading_sessions s;

-- ==========================================
-- VIEW: ÚLTIMOS TRADES
-- ==========================================

CREATE OR REPLACE VIEW vw_recent_trades AS
SELECT 
    t.id,
    t.session_id,
    s.strategy_name,
    t.symbol,
    t.trade_type,
    t.timestamp,
    t.price,
    t.quantity,
    t.value,
    t.pnl,
    t.pnl_percent,
    t.cumulative_pnl,
    t.balance_after,
    t.signal_confidence
FROM paper_trading_trades t
JOIN paper_trading_sessions s ON t.session_id = s.session_id
ORDER BY t.timestamp DESC
LIMIT 100;

-- ==========================================
-- COMENTÁRIOS
-- ==========================================

COMMENT ON TABLE paper_trading_trades IS 'Histórico completo de trades executados no paper trading';
COMMENT ON TABLE paper_trading_sessions IS 'Metadados e estatísticas das sessões de paper trading';
COMMENT ON COLUMN paper_trading_trades.indicators_snapshot IS 'JSON com valores de RSI, MACD, etc. no momento do trade';
COMMENT ON COLUMN paper_trading_trades.signal_confidence IS 'Confiança do sinal que gerou o trade (0.0 a 1.0)';

-- ==========================================
-- GRANTS (se necessário)
-- ==========================================

GRANT SELECT, INSERT, UPDATE ON paper_trading_trades TO crypto_user;
GRANT SELECT, INSERT, UPDATE ON paper_trading_sessions TO crypto_user;
GRANT SELECT ON vw_session_performance TO crypto_user;
GRANT SELECT ON vw_recent_trades TO crypto_user;
