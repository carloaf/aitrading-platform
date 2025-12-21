-- =====================================================
-- Script de inicialização: Tabela de símbolos monitorados
-- Permite gerenciamento dinâmico de símbolos pelo usuário
-- =====================================================

-- Criar tabela de símbolos monitorados
CREATE TABLE IF NOT EXISTS monitored_symbols (
    symbol VARCHAR(20) PRIMARY KEY,
    active BOOLEAN NOT NULL DEFAULT true,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT
);

-- Criar índice para consultas rápidas (apenas símbolos ativos)
CREATE INDEX IF NOT EXISTS idx_monitored_symbols_active 
ON monitored_symbols(active) WHERE active = true;

-- Criar índice para ordenação por data
CREATE INDEX IF NOT EXISTS idx_monitored_symbols_added 
ON monitored_symbols(added_at DESC);

-- Inserir os 80 símbolos padrão (todos ativos)
INSERT INTO monitored_symbols (symbol, active, notes) VALUES
    -- Top 10 - Major Assets
    ('BTCUSDT', true, 'Bitcoin - Major Asset'),
    ('ETHUSDT', true, 'Ethereum - Major Asset'),
    ('BNBUSDT', true, 'BNB - Major Asset'),
    ('SOLUSDT', true, 'Solana - Major Asset'),
    ('XRPUSDT', true, 'Ripple - Major Asset'),
    ('ADAUSDT', true, 'Cardano - Major Asset'),
    ('DOGEUSDT', true, 'Dogecoin - Major Asset'),
    ('AVAXUSDT', true, 'Avalanche - Major Asset'),
    ('DOTUSDT', true, 'Polkadot - Major Asset'),
    ('LINKUSDT', true, 'Chainlink - Major Asset'),
    
    -- Top 20 - Large Cap
    ('TRXUSDT', true, 'Tron - Large Cap'),
    ('TONUSDT', true, 'Toncoin - Large Cap'),
    ('BCHUSDT', true, 'Bitcoin Cash - Large Cap'),
    ('ETCUSDT', true, 'Ethereum Classic - Large Cap'),
    ('ICPUSDT', true, 'Internet Computer - Large Cap'),
    ('FILUSDT', true, 'Filecoin - Large Cap'),
    ('VETUSDT', true, 'VeChain - Large Cap'),
    ('HBARUSDT', true, 'Hedera - Large Cap'),
    ('MATICUSDT', true, 'Polygon - Large Cap'),
    ('SHIBUSDT', true, 'Shiba Inu - Large Cap'),
    
    -- Top 40 - Mid Cap + Layer 2
    ('LTCUSDT', true, 'Litecoin - Mid Cap'),
    ('ATOMUSDT', true, 'Cosmos - Mid Cap'),
    ('UNIUSDT', true, 'Uniswap - Mid Cap'),
    ('XLMUSDT', true, 'Stellar - Mid Cap'),
    ('NEARUSDT', true, 'NEAR Protocol - Mid Cap'),
    ('IMXUSDT', true, 'Immutable X - Layer 2'),
    ('STXUSDT', true, 'Stacks - Layer 2'),
    ('MANTAUSDT', true, 'Manta Network - Layer 2'),
    ('METISUSDT', true, 'Metis - Layer 2'),
    ('ZKUSDT', true, 'zkSync - Layer 2'),
    ('STRKUSDT', true, 'Starknet - Layer 2'),
    ('LOOMUSDT', true, 'Loom Network - Layer 2'),
    ('SKLUSDT', true, 'SKALE - Layer 2'),
    ('CELOUSDT', true, 'Celo - Layer 2'),
    ('ZETAUSDT', true, 'ZetaChain - Layer 2'),
    ('CYBERUSDT', true, 'CyberConnect - Mid Cap'),
    ('GLMUSDT', true, 'Golem - Mid Cap'),
    ('CELRUSDT', true, 'Celer Network - Mid Cap'),
    ('CTSIUSDT', true, 'Cartesi - Mid Cap'),
    
    -- DeFi Protocol Tokens
    ('AAVEUSDT', true, 'Aave - DeFi'),
    ('MKRUSDT', true, 'Maker - DeFi'),
    ('CRVUSDT', true, 'Curve - DeFi'),
    ('SNXUSDT', true, 'Synthetix - DeFi'),
    ('COMPUSDT', true, 'Compound - DeFi'),
    ('LDOUSDT', true, 'Lido DAO - DeFi'),
    ('SUSHIUSDT', true, 'SushiSwap - DeFi'),
    ('1INCHUSDT', true, '1inch - DeFi'),
    ('DYDXUSDT', true, 'dYdX - DeFi'),
    ('GMXUSDT', true, 'GMX - DeFi'),
    ('PENDLEUSDT', true, 'Pendle - DeFi'),
    ('JUPUSDT', true, 'Jupiter - DeFi'),
    ('RUNEUSDT', true, 'THORChain - DeFi'),
    ('YFIUSDT', true, 'Yearn Finance - DeFi'),
    ('BALUSDT', true, 'Balancer - DeFi'),
    
    -- AI / Oracle / Data
    ('FETUSDT', true, 'Fetch.ai - AI'),
    ('AGIXUSDT', true, 'SingularityNET - AI'),
    ('OCEANUSDT', true, 'Ocean Protocol - AI'),
    ('TAOUSDT', true, 'Bittensor - AI'),
    ('WLDUSDT', true, 'Worldcoin - AI'),
    ('ARKMUSDT', true, 'Arkham - AI'),
    ('GRTUSDT', true, 'The Graph - Oracle'),
    ('NMRUSDT', true, 'Numerai - AI'),
    ('IOTXUSDT', true, 'IoTeX - IoT'),
    ('RENDERUSDT', true, 'Render Token - GPU'),
    ('THETAUSDT', true, 'Theta Network - Video'),
    ('ARUSDT', true, 'Arweave - Storage'),
    
    -- Alt Layer-1 / Infrastructure
    ('KASUSDT', true, 'Kaspa - Layer 1'),
    ('ROSEUSDT', true, 'Oasis Network - Layer 1'),
    ('FTMUSDT', true, 'Fantom - Layer 1'),
    ('EGLDUSDT', true, 'MultiversX - Layer 1'),
    ('FLOWUSDT', true, 'Flow - Layer 1'),
    
    -- Hot / Trending
    ('APTUSDT', true, 'Aptos - Trending'),
    ('ARBUSDT', true, 'Arbitrum - Trending'),
    ('OPUSDT', true, 'Optimism - Trending'),
    ('INJUSDT', true, 'Injective - Trending'),
    ('SUIUSDT', true, 'Sui - Trending'),
    ('SEIUSDT', true, 'Sei - Trending'),
    ('TIAUSDT', true, 'Celestia - Trending'),
    ('ALGOUSDT', true, 'Algorand - Trending'),
    ('WIFUSDT', true, 'Dogwifhat - Meme'),
    ('BONKUSDT', true, 'Bonk - Meme'),
    ('PEPEUSDT', true, 'Pepe - Meme'),
    ('FLOKIUSDT', true, 'Floki - Meme')
ON CONFLICT (symbol) DO UPDATE SET
    active = EXCLUDED.active,
    updated_at = NOW(),
    notes = EXCLUDED.notes;

-- Exibir estatísticas
SELECT 
    COUNT(*) as total_symbols,
    COUNT(*) FILTER (WHERE active = true) as active_symbols,
    COUNT(*) FILTER (WHERE active = false) as inactive_symbols
FROM monitored_symbols;

-- Exibir todos os símbolos ativos
SELECT symbol, added_at, notes 
FROM monitored_symbols 
WHERE active = true 
ORDER BY symbol;
