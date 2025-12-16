const http = require('http');

// Health check para API Gateway
const options = {
  hostname: 'localhost',
  port: process.env.API_GATEWAY_PORT || 8080,
  path: '/health',
  timeout: 2000
};

const request = http.request(options, (res) => {
  if (res.statusCode === 200) {
    console.log('Health check passed');
    process.exit(0);
  } else {
    console.log(`Health check failed with status: ${res.statusCode}`);
    process.exit(1);
  }
});

request.on('error', (err) => {
  console.log(`Health check error: ${err.message}`);
  process.exit(1);
});

request.end();
