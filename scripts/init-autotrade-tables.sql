-- =====================================================
-- AUTOTRADE TABLES - AI Trading Platform
-- Version: 1.0
-- Date: 2025-12-19
-- Description: Tabelas para armazenar sinais e trades do AutoTrade
-- =====================================================

-- Tabela para armazenar TODOS os sinais processados pelo scanner
CREATE TABLE IF NOT EXISTS autotrade_signals (
    id SERIAL PRIMARY KEY,
    
    -- Identificação
    session_id VARCHAR(100) NOT NULL,
    signal_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Timing
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Símbolo e Mercado
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT '1h',
    
    -- Sinal
    signal_type VARCHAR(50) NOT NULL, -- 'bullish_divergence', 'bearish_divergence', etc
    direction VARCHAR(10) NOT NULL, -- 'BUY', 'SELL'
    strength DECIMAL(5,4) NOT NULL, -- 0.0 to 1.0
    
    -- Preços
    entry_price DECIMAL(20,8) NOT NULL,
    stop_loss DECIMAL(20,8),
    take_profit DECIMAL(20,8),
    current_price DECIMAL(20,8),
    
    -- Indicadores Técnicos
    rsi DECIMAL(7,4),
    adx DECIMAL(7,4),
    volume DECIMAL(20,4),
    volatility DECIMAL(10,6),
    
    -- Regime de Mercado
    market_regime VARCHAR(20), -- 'BULL', 'BEAR', 'SIDEWAYS'
    regime_confidence DECIMAL(5,4),
    
    -- Processamento
    processed BOOLEAN DEFAULT FALSE,
    executed BOOLEAN DEFAULT FALSE,
    reason VARCHAR(500),
    
    -- Trade Associado (se executado)
    paper_trading_trade_id INTEGER,
    
    -- Config usada
    min_strength_threshold DECIMAL(5,4),
    dry_run BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_symbol ON autotrade_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_timestamp ON autotrade_signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_session ON autotrade_signals(session_id);
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_executed ON autotrade_signals(executed);
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_direction ON autotrade_signals(direction);
CREATE INDEX IF NOT EXISTS idx_autotrade_signals_signal_type ON autotrade_signals(signal_type);

-- Tabela para armazenar sessões do AutoTrade
CREATE TABLE IF NOT EXISTS autotrade_sessions (
    id SERIAL PRIMARY KEY,
    
    -- Identificação
    session_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Configuração
    mode VARCHAR(20) NOT NULL DEFAULT 'DRY_RUN', -- 'DRY_RUN', 'LIVE'
    initial_capital DECIMAL(20,8) NOT NULL DEFAULT 10000.0,
    current_balance DECIMAL(20,8) NOT NULL DEFAULT 10000.0,
    
    -- Filtros
    min_strength DECIMAL(5,4) NOT NULL DEFAULT 0.5,
    symbols TEXT[], -- Array de símbolos monitorados
    timeframe VARCHAR(10) NOT NULL DEFAULT '1h',
    
    -- Estatísticas
    total_signals_processed INTEGER DEFAULT 0,
    total_trades_executed INTEGER DEFAULT 0,
    total_trades_won INTEGER DEFAULT 0,
    total_trades_lost INTEGER DEFAULT 0,
    
    -- Performance
    total_pnl DECIMAL(20,8) DEFAULT 0.0,
    total_pnl_percent DECIMAL(10,4) DEFAULT 0.0,
    win_rate DECIMAL(5,2) DEFAULT 0.0,
    sharpe_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_autotrade_sessions_active ON autotrade_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_autotrade_sessions_started ON autotrade_sessions(started_at DESC);

-- Estender tabela paper_trading_trades com informações do AutoTrade
ALTER TABLE paper_trading_trades 
ADD COLUMN IF NOT EXISTS autotrade_signal_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS signal_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS signal_strength DECIMAL(5,4),
ADD COLUMN IF NOT EXISTS entry_reason VARCHAR(500),
ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(500),
ADD COLUMN IF NOT EXISTS market_regime VARCHAR(20),
ADD COLUMN IF NOT EXISTS rsi_at_entry DECIMAL(7,4),
ADD COLUMN IF NOT EXISTS adx_at_entry DECIMAL(7,4);

-- Índice adicional
CREATE INDEX IF NOT EXISTS idx_paper_trades_autotrade_signal ON paper_trading_trades(autotrade_signal_id);

-- View para análise consolidada
CREATE OR REPLACE VIEW autotrade_performance_summary AS
SELECT 
    s.session_id,
    s.mode,
    s.started_at,
    s.stopped_at,
    s.is_active,
    
    -- Estatísticas gerais
    s.total_signals_processed,
    s.total_trades_executed,
    s.total_trades_won,
    s.total_trades_lost,
    s.win_rate,
    
    -- Performance financeira
    s.initial_capital,
    s.current_balance,
    s.total_pnl,
    s.total_pnl_percent,
    s.sharpe_ratio,
    s.max_drawdown,
    
    -- Tempo de operação
    CASE 
        WHEN s.stopped_at IS NOT NULL THEN 
            EXTRACT(EPOCH FROM (s.stopped_at - s.started_at))/3600 
        ELSE 
            EXTRACT(EPOCH FROM (NOW() - s.started_at))/3600 
    END as duration_hours,
    
    -- Taxa de execução
    CASE 
        WHEN s.total_signals_processed > 0 THEN 
            ROUND((s.total_trades_executed::DECIMAL / s.total_signals_processed * 100), 2)
        ELSE 0
    END as execution_rate_percent
    
FROM autotrade_sessions s
ORDER BY s.started_at DESC;

-- View para análise por símbolo
CREATE OR REPLACE VIEW autotrade_performance_by_symbol AS
SELECT 
    sig.symbol,
    sig.session_id,
    
    -- Contadores
    COUNT(*) as total_signals,
    SUM(CASE WHEN sig.executed THEN 1 ELSE 0 END) as trades_executed,
    
    -- Performance dos trades
    COUNT(t.id) as trades_with_data,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    
    -- P&L
    COALESCE(SUM(t.pnl), 0) as total_pnl,
    COALESCE(AVG(t.pnl_percent), 0) as avg_pnl_percent,
    COALESCE(MAX(t.pnl_percent), 0) as best_trade_percent,
    COALESCE(MIN(t.pnl_percent), 0) as worst_trade_percent,
    
    -- Win Rate
    CASE 
        WHEN COUNT(t.id) > 0 THEN 
            ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(t.id) * 100), 2)
        ELSE 0
    END as win_rate,
    
    -- Média de força dos sinais
    ROUND(AVG(sig.strength), 4) as avg_signal_strength,
    
    -- Timing
    MIN(sig.timestamp) as first_signal,
    MAX(sig.timestamp) as last_signal
    
FROM autotrade_signals sig
LEFT JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
GROUP BY sig.symbol, sig.session_id
ORDER BY total_pnl DESC;

-- View para análise por tipo de sinal
CREATE OR REPLACE VIEW autotrade_performance_by_signal_type AS
SELECT 
    sig.signal_type,
    sig.direction,
    sig.session_id,
    
    -- Contadores
    COUNT(*) as total_signals,
    SUM(CASE WHEN sig.executed THEN 1 ELSE 0 END) as trades_executed,
    
    -- Performance
    COUNT(t.id) as trades_with_data,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    
    -- P&L
    COALESCE(SUM(t.pnl), 0) as total_pnl,
    COALESCE(AVG(t.pnl_percent), 0) as avg_pnl_percent,
    
    -- Win Rate
    CASE 
        WHEN COUNT(t.id) > 0 THEN 
            ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(t.id) * 100), 2)
        ELSE 0
    END as win_rate,
    
    -- Força média
    ROUND(AVG(sig.strength), 4) as avg_signal_strength
    
FROM autotrade_signals sig
LEFT JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
GROUP BY sig.signal_type, sig.direction, sig.session_id
ORDER BY total_pnl DESC;

-- Função para atualizar estatísticas da sessão
CREATE OR REPLACE FUNCTION update_autotrade_session_stats(p_session_id VARCHAR)
RETURNS VOID AS $$
BEGIN
    UPDATE autotrade_sessions s
    SET 
        total_signals_processed = (
            SELECT COUNT(*) FROM autotrade_signals WHERE session_id = p_session_id
        ),
        total_trades_executed = (
            SELECT COUNT(*) FROM autotrade_signals WHERE session_id = p_session_id AND executed = TRUE
        ),
        total_trades_won = (
            SELECT COUNT(*) 
            FROM autotrade_signals sig
            JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
            WHERE sig.session_id = p_session_id AND t.pnl > 0
        ),
        total_trades_lost = (
            SELECT COUNT(*) 
            FROM autotrade_signals sig
            JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
            WHERE sig.session_id = p_session_id AND t.pnl < 0
        ),
        total_pnl = (
            SELECT COALESCE(SUM(t.pnl), 0)
            FROM autotrade_signals sig
            JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
            WHERE sig.session_id = p_session_id
        ),
        win_rate = (
            SELECT CASE 
                WHEN COUNT(t.id) > 0 THEN 
                    ROUND((SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(t.id) * 100), 2)
                ELSE 0
            END
            FROM autotrade_signals sig
            JOIN paper_trading_trades t ON sig.signal_id = t.autotrade_signal_id
            WHERE sig.session_id = p_session_id
        ),
        updated_at = NOW()
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_autotrade_signals_updated_at BEFORE UPDATE ON autotrade_signals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_autotrade_sessions_updated_at BEFORE UPDATE ON autotrade_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comentários nas tabelas
COMMENT ON TABLE autotrade_signals IS 'Armazena todos os sinais detectados pelo AutoTrade scanner';
COMMENT ON TABLE autotrade_sessions IS 'Armazena sessões do AutoTrade com estatísticas agregadas';
COMMENT ON VIEW autotrade_performance_summary IS 'View consolidada de performance das sessões';
COMMENT ON VIEW autotrade_performance_by_symbol IS 'Performance agregada por símbolo';
COMMENT ON VIEW autotrade_performance_by_signal_type IS 'Performance agregada por tipo de sinal';

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON autotrade_signals TO crypto_user;
GRANT SELECT, INSERT, UPDATE ON autotrade_sessions TO crypto_user;
GRANT SELECT ON autotrade_performance_summary TO crypto_user;
GRANT SELECT ON autotrade_performance_by_symbol TO crypto_user;
GRANT SELECT ON autotrade_performance_by_signal_type TO crypto_user;
GRANT USAGE, SELECT ON SEQUENCE autotrade_signals_id_seq TO crypto_user;
GRANT USAGE, SELECT ON SEQUENCE autotrade_sessions_id_seq TO crypto_user;

-- Log de criação
DO $$
BEGIN
    RAISE NOTICE '✅ AutoTrade tables created successfully!';
    RAISE NOTICE '   - autotrade_signals';
    RAISE NOTICE '   - autotrade_sessions';
    RAISE NOTICE '   - autotrade_performance_summary (VIEW)';
    RAISE NOTICE '   - autotrade_performance_by_symbol (VIEW)';
    RAISE NOTICE '   - autotrade_performance_by_signal_type (VIEW)';
END $$;
