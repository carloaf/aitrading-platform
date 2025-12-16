const http = require('http');

// Health check simples para Docker
const options = {
  hostname: '127.0.0.1', // Use IPv4 explicitly
  port: process.env.PORT || 3001,
  path: '/health',
  timeout: 2000,
  family: 4 // Force IPv4
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
