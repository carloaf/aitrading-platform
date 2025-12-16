const ccxt = require('ccxt');
const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'crypto_market',
  user: 'crypto_user',
  password: 'crypto_pass'
});

const exchange = new ccxt.binance({
  enableRateLimit: true,
  options: { defaultType: 'future' }
});

async function fetchAndStore2025Data() {
  console.log('🚀 BUSCANDO DADOS DE 2025\n');
  
  const startDate = '2025-01-10'; // Após os dados que já temos
  const endDate = '2025-12-11';   // Até hoje
  
  const since = new Date(startDate).getTime();
  const until = new Date(endDate).getTime();
  
  let allCandles = [];
  let currentTimestamp = since;
  
  console.log(`📊 Período: ${startDate} até ${endDate}\n`);
  
  while (currentTimestamp < until) {
    try {
      const candles = await exchange.fetchOHLCV(
        'BTC/USDT',
        '1h',
        currentTimestamp,
        1000
      );
      
      if (candles.length === 0) break;
      
      allCandles = allCandles.concat(candles);
      currentTimestamp = candles[candles.length - 1][0] + 1;
      
      console.log(`   ✓ ${candles.length} candles baixados (Total: ${allCandles.length})`);
      
      await new Promise(resolve => setTimeout(resolve, 250));
      
      if (candles.length < 1000) break;
      
    } catch (error) {
      console.error(`   ✗ Erro: ${error.message}`);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
  
  console.log(`\n💾 Salvando ${allCandles.length} candles no banco...\n`);
  
  let inserted = 0;
  for (const candle of allCandles) {
    const [timestamp, open, high, low, close, volume] = candle;
    
    try {
      await pool.query(
        `INSERT INTO market_data 
         (symbol, timestamp, open, high, low, close, price, volume, source) 
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
         ON CONFLICT DO NOTHING`,
        [
          'BTC/USDT',
          new Date(timestamp),
          open, high, low, close, close,
          Math.round(volume),
          'binance_2025'
        ]
      );
      inserted++;
    } catch (error) {
      console.error(`   ✗ Erro ao inserir: ${error.message}`);
    }
  }
  
  console.log(`\n✅ ${inserted} novos candles inseridos!\n`);
  
  // Verificar total
  const result = await pool.query(
    `SELECT 
       COUNT(*) as total,
       MIN(timestamp)::date as first_date,
       MAX(timestamp)::date as last_date
     FROM market_data 
     WHERE symbol = 'BTC/USDT'`
  );
  
  console.log('📊 TOTAL NO BANCO:');
  console.log(`   Candles: ${result.rows[0].total}`);
  console.log(`   De: ${result.rows[0].first_date}`);
  console.log(`   Até: ${result.rows[0].last_date}`);
  
  await pool.end();
}

fetchAndStore2025Data().catch(console.error).finally(() => process.exit(0));
