const Redis=require('ioredis');
let client;
async function connectRedis(){
  client=new Redis(process.env.REDIS_URL||'redis://localhost:6379',{
    retryStrategy:(times)=>Math.min(times*200,2000),
    maxRetriesPerRequest:3,
    lazyConnect:true,
  });
  client.on('error',(e)=>console.error('[redis] Error:',e.message));
  try{
    await client.connect();
    await client.ping();
    console.log('[redis] Connected');
  }catch(e){
    console.warn('[redis] Connection failed (non-fatal):',e.message);
  }
}
function getRedis(){return client;}
module.exports={connectRedis,getRedis};
