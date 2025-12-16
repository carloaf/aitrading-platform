#!/usr/bin/env node

const ccxt = require('ccxt');
const { Pool } = require('pg');

// Configuração do banco de dados
const pool = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'crypto_market',
  user: 'crypto_user',
  password: 'crypto_pass'
});

// Configuração da Binance
const exchange = new ccxt.binance({
  enableRateLimit: true,
  options: {
    defaultType: 'future', // Use USDT-M Futures para mais dados
  }
});

async function fetchAndStoreHistoricalData(symbol, timeframe, startDate, endDate) {
  console.log(`\n📊 Buscando dados históricos: ${symbol} (${timeframe})`);
  console.log(`   Período: ${startDate} até ${endDate}`);
  
  const since = new Date(startDate).getTime();
  const until = new Date(endDate).getTime();
  
  let allCandles = [];
  let currentTimestamp = since;
  
  while (currentTimestamp < until) {
    try {
      // Buscar 1000 candles por vez (limite da Binance)
      const candles = await exchange.fetchOHLCV(
        symbol,
        timeframe,
        currentTimestamp,
        1000
      );
      
      if (candles.length === 0) break;
      
      allCandles = allCandles.concat(candles);
      
      // Atualizar timestamp para próxima iteração
      currentTimestamp = candles[candles.length - 1][0] + 1;
      
      console.log(`   ✓ Baixados ${candles.length} candles (Total: ${allCandles.length})`);
      
      // Rate limiting
      await new Promise(resolve => setTimeout(resolve, 250));
      
      // Parar se chegou no fim
      if (candles.length < 1000) break;
      
    } catch (error) {
      console.error(`   ✗ Erro ao buscar dados:`, error.message);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
  
  console.log(`\n💾 Salvando ${allCandles.length} candles no banco de dados...`);
  
  // Inserir no banco
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
          symbol,
          new Date(timestamp),
          open,
          high,
          low,
          close,
          close, // price = close
          Math.round(volume), // Converter para inteiro
          'binance_historical'
        ]
      );
      inserted++;
    } catch (error) {
      console.error(`   ✗ Erro ao inserir candle:`, error.message);
    }
  }
  
  console.log(`✅ ${inserted} candles inseridos com sucesso!\n`);
  
  return allCandles;
}

async function main() {
  console.log('🚀 BUSCAR DADOS HISTÓRICOS DA BINANCE\n');
  console.log('=' .repeat(60));
  
  try {
    // Testar conexão com banco
    const client = await pool.connect();
    console.log('✅ Conectado ao TimescaleDB\n');
    client.release();
    
    // Buscar dados para os períodos do BLUE_PRINT
    const scenarios = [
      {
        name: 'Bull Run',
        start: '2021-01-01',
        end: '2021-04-30'
      },
      {
        name: 'Chop',
        start: '2021-05-01',
        end: '2021-07-31'
      },
      {
        name: 'Crash',
        start: '2021-11-01',
        end: '2022-01-31'
      },
      {
        name: 'Recovery',
        start: '2023-01-01',
        end: '2023-03-31'
      },
      {
        name: 'Recent Data',
        start: '2024-01-01',
        end: '2024-12-11'
      }
    ];
    
    for (const scenario of scenarios) {
      console.log(`\n${'='.repeat(60)}`);
      console.log(`📅 CENÁRIO: ${scenario.name}`);
      console.log(`${'='.repeat(60)}`);
      
      await fetchAndStoreHistoricalData(
        'BTC/USDT',
        '1h',
        scenario.start,
        scenario.end
      );
    }
    
    // Verificar total de dados
    const result = await pool.query(
      `SELECT 
         symbol,
         COUNT(*) as total_candles,
         MIN(timestamp) as first_date,
         MAX(timestamp) as last_date
       FROM market_data
       WHERE symbol = 'BTC/USDT'
       GROUP BY symbol`
    );
    
    console.log('\n' + '='.repeat(60));
    console.log('📊 RESUMO DOS DADOS HISTÓRICOS');
    console.log('='.repeat(60));
    console.log(result.rows[0]);
    console.log('='.repeat(60));
    
  } catch (error) {
    console.error('❌ Erro:', error);
  } finally {
    await pool.end();
    process.exit(0);
  }
}

main();
