const {MongoClient}=require('mongodb');
let db;
async function connectMongoDB(){
  try{
    const uri=process.env.MONGODB_URI||'mongodb://localhost:27017/linkedin_nosql';
    const client=new MongoClient(uri,{serverSelectionTimeoutMS:5000});
    await client.connect();
    db=client.db();
    console.log('[messaging-service] MongoDB connected');
  }catch(e){
    console.warn('[messaging-service] MongoDB connection failed (non-fatal):',e.message);
  }
}
function getMongoDB(){return db;}
module.exports={connectMongoDB,getMongoDB};
