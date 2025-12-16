require('dotenv').config();  // carrega o .env
console.log('BRAPI_TOKEN from env:', process.env.BRAPI_TOKEN);

const axios = require('axios');
const { Client } = require('pg');

const client = new Client({
  host: 'db',
  user: 'n8n',
  password: 'n8npass',
  database: 'n8n',
});

async function fetchData() {
  try {
    await client.connect();
    console.log('Connected to Postgres');

    // const symbols = ['WDOFUT', 'WINFUT'];
    const symbols = ['PETR4'];
    // const url = `https://brapi.dev/api/quote/${symbols.join(',')}?token=${process.env.BRAPI_TOKEN}`;
    const url = `https://brapi.dev/api/quote/${symbols}?token=${process.env.BRAPI_TOKEN}`;

    console.log(`Fetching data from: ${url}`);  // debug opcional

    const response = await axios.get(url);
    const data = response.data.results;

    for (const item of data) {
      console.log(`Inserting data for ${item.symbol}: ${item.regularMarketPrice}`);

      await client.query(
        'INSERT INTO market_data(symbol, price, timestamp) VALUES($1, $2, NOW())',
        [item.symbol, item.regularMarketPrice]
      );
    }

    await client.end();
  } catch (error) {
    console.error('Error:', error.response ? error.response.data : error.message);
  }
}

fetchData();
