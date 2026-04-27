const mysql=require('mysql2/promise');
let pool;
async function connectMySQL(){
  pool=mysql.createPool({
    host:process.env.MYSQL_HOST||'localhost',
    port:parseInt(process.env.MYSQL_PORT||'3306'),
    user:process.env.MYSQL_USER||'linkedin_user',
    password:process.env.MYSQL_PASSWORD||'linkedin_pass',
    database:process.env.MYSQL_DATABASE||'linkedin_db',
    waitForConnections:true,
    connectionLimit:20,
    queueLimit:0,
    connectTimeout:10000,
  });
  // Retry logic
  let attempts=0;
  while(attempts<10){
    try{
      await pool.query('SELECT 1');
      console.log('[mysql] Connected');
      return;
    }catch(e){
      attempts++;
      console.log(`[mysql] Attempt ${attempts}/10 failed: ${e.message}`);
      await new Promise(r=>setTimeout(r,3000));
    }
  }
  throw new Error('MySQL connection failed after 10 attempts');
}
function getDB(){return pool;}
module.exports={connectMySQL,getDB};
