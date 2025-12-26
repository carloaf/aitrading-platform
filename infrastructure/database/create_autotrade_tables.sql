-- Criação das tabelas para AutoTrade e Paper Trading

-- Tabela de sinais de auto-trade
CREATE TABLE IF NOT EXISTS autotrade_signals (
    signal_id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    direction INTEGER NOT NULL,  -- 1=LONG, -1=SHORT
    strength FLOAT NOT NULL,
    entry_price FLOAT NOT NULL,
    stop_loss FLOAT NOT NULL,
    take_profit FLOAT NOT NULL,
    rsi FLOAT,
    adx FLOAT,
    current_price FLOAT,
    market_regime TEXT,
    executed BOOLEAN DEFAULT FALSE,
    execution_reason TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    reason TEXT
);

-- Índices para melhorar performance
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_timestamp ON autotrade_signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_symbol ON autotrade_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_executed ON autotrade_signals(executed);
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_session ON autotrade_signals(session_id);

-- Tabela de trades executados (paper trading)
CREATE TABLE IF NOT EXISTS paper_trading_trades (
    trade_id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES autotrade_signals(signal_id),
    symbol TEXT NOT NULL,
    direction INTEGER NOT NULL,  -- 1=LONG, -1=SHORT
    entry_price FLOAT NOT NULL,
    exit_price FLOAT,
    stop_loss FLOAT NOT NULL,
    take_profit FLOAT NOT NULL,
    position_size FLOAT NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    pnl FLOAT,           -- P&L em $
    pnl_percent FLOAT,   -- P&L em %
    exit_reason TEXT,    -- TAKE_PROFIT, STOP_LOSS, TIMEOUT, MANUAL
    trade_type TEXT DEFAULT 'paper',  -- paper, live, backtest
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para melhorar performance
CREATE INDEX IF NOT EXISTS idx_paper_trading_trades_signal ON paper_trading_trades(signal_id);
CREATE INDEX IF NOT EXISTS idx_paper_trading_trades_symbol ON paper_trading_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trading_trades_entry_time ON paper_trading_trades(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trading_trades_pnl ON paper_trading_trades(pnl);

-- View para performance summary
CREATE OR REPLACE VIEW autotrade_performance_summary AS
SELECT 
    session_id,
    COUNT(*) as total_signals,
    COUNT(CASE WHEN executed = true THEN 1 END) as trades_executed,
    COUNT(CASE WHEN t.pnl > 0 THEN 1 END) as winning_trades,
    COUNT(CASE WHEN t.pnl <= 0 THEN 1 END) as losing_trades,
    ROUND(CAST(COUNT(CASE WHEN t.pnl > 0 THEN 1 END) AS NUMERIC) / NULLIF(COUNT(t.trade_id), 0) * 100, 2) as win_rate,
    ROUND(CAST(SUM(t.pnl) AS NUMERIC), 2) as total_pnl,
    ROUND(CAST(AVG(t.pnl_percent) AS NUMERIC), 2) as avg_pnl_percent,
    MIN(timestamp) as started_at,
    MAX(timestamp) as last_signal_at,
    CASE WHEN MAX(timestamp) > NOW() - INTERVAL '5 minutes' THEN true ELSE false END as is_active
FROM autotrade_signals s
LEFT JOIN paper_trading_trades t ON t.signal_id = s.signal_id
GROUP BY session_id;

-- View para performance por tipo de sinal
CREATE OR REPLACE VIEW autotrade_performance_by_signal_type AS
SELECT 
    signal_type,
    direction,
    COUNT(*) as total_signals,
    COUNT(CASE WHEN executed = true THEN 1 END) as trades_executed,
    COUNT(CASE WHEN t.pnl > 0 THEN 1 END) as winning_trades,
    COUNT(CASE WHEN t.pnl <= 0 THEN 1 END) as losing_trades,
    ROUND(CAST(COUNT(CASE WHEN t.pnl > 0 THEN 1 END) AS NUMERIC) / NULLIF(COUNT(t.trade_id), 0) * 100, 2) as win_rate,
    ROUND(CAST(SUM(t.pnl) AS NUMERIC), 2) as total_pnl,
    ROUND(CAST(AVG(t.pnl_percent) AS NUMERIC), 2) as avg_pnl_percent,
    COUNT(DISTINCT s.session_id) as sessions_count
FROM autotrade_signals s
LEFT JOIN paper_trading_trades t ON t.signal_id = s.signal_id
GROUP BY signal_type, direction;

COMMENT ON TABLE autotrade_signals IS 'Sinais detectados pelo scanner RSI Divergence com auto-trade';
COMMENT ON TABLE paper_trading_trades IS 'Trades executados em paper trading com PNL rastreado';
COMMENT ON VIEW autotrade_performance_summary IS 'Performance agregada por sessão de auto-trade';
COMMENT ON VIEW autotrade_performance_by_signal_type IS 'Performance agregada por tipo de sinal e direção';
