-- ==========================================
-- TABELA DE ALERTAS DE SÍMBOLOS
-- ==========================================
-- Registra eventos importantes sobre símbolos monitorados
-- (adições, falhas, recuperações, etc.)

CREATE TABLE IF NOT EXISTS symbol_alerts (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- 'added', 'failed', 'recovered', 'removed', 'no_data'
    message TEXT,
    severity VARCHAR(20) DEFAULT 'info', -- 'info', 'warning', 'error', 'success'
    metadata JSONB, -- Dados adicionais (ex: error_details, timeframes afetados)
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para consultas rápidas
CREATE INDEX IF NOT EXISTS idx_symbol_alerts_symbol ON symbol_alerts(symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_alerts_event_type ON symbol_alerts(event_type);
CREATE INDEX IF NOT EXISTS idx_symbol_alerts_created_at ON symbol_alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_symbol_alerts_severity ON symbol_alerts(severity);

-- Comentários
COMMENT ON TABLE symbol_alerts IS 'Registra eventos e alertas sobre símbolos monitorados';
COMMENT ON COLUMN symbol_alerts.event_type IS 'Tipo de evento: added, failed, recovered, removed, no_data';
COMMENT ON COLUMN symbol_alerts.severity IS 'Severidade: info, warning, error, success';
COMMENT ON COLUMN symbol_alerts.metadata IS 'Dados adicionais em formato JSON';

-- Exemplos de uso:
-- INSERT INTO symbol_alerts (symbol, event_type, message, severity, metadata)
-- VALUES ('BTCUSDT', 'failed', 'Falha ao buscar dados da Binance', 'error', '{"timeframe": "1h", "error": "timeout"}');

-- SELECT * FROM symbol_alerts WHERE symbol = 'BTCUSDT' ORDER BY created_at DESC LIMIT 10;
