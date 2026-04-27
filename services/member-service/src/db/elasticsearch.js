const { Client } = require('@elastic/elasticsearch');

let client = null;
let esReady = false;

async function connectElasticsearch() {
  const url = process.env.ELASTICSEARCH_URL || 'http://localhost:9200';
  client = new Client({ node: url });
  
  // Wait for ES with retries
  let attempts = 0;
  while (attempts < 15) {
    try {
      await client.cluster.health({ wait_for_status: 'yellow', timeout: '10s' });
      console.log('[elasticsearch-member] Connected ✅');
      esReady = true;
      return;
    } catch (e) {
      attempts++;
      console.log(`[elasticsearch-member] Attempt ${attempts}/15 — waiting...`);
      await new Promise(r => setTimeout(r, 5000));
    }
  }
  console.warn('[elasticsearch-member] Could not connect — falling back to MySQL search');
}

function getES() { return client; }
function isReady() { return esReady; }

module.exports = { connectElasticsearch, getES, isReady };
