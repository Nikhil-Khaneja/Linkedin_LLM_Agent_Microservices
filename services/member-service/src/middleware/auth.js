const jwt=require('jsonwebtoken');
const axios=require('axios');
const {AppError}=require('./errorHandler');
let pubKey,pubKeyFetched=false;
async function fetchPublicKey(){
  if(pubKeyFetched)return;
  try{
    const {data}=await axios.get(process.env.AUTH_SERVICE_JWKS_URL||'http://auth-service:3001/.well-known/jwks.json');
    const k=data.keys[0];
    const {createPublicKey}=require('crypto');
    const keyObj=createPublicKey({key:{...k,kty:'RSA'},format:'jwk'});
    pubKey=keyObj.export({type:'pkcs1',format:'pem'});
    pubKeyFetched=true;
  }catch(e){console.warn('[auth-mw] Could not fetch JWKS:',e.message);}
}
function requireAuth(req,res,next){
  const header=req.headers['authorization'];
  if(!header?.startsWith('Bearer '))return next(new AppError(401,'auth_required','Missing bearer token.',false));
  const token=header.slice(7);
  (async()=>{
    await fetchPublicKey();
    try{
      const decoded=jwt.verify(token,pubKey,{algorithms:['RS256']});
      req.user={userId:decoded.sub,userType:decoded.type};
      next();
    }catch{next(new AppError(401,'auth_required','Invalid or expired token.',false));}
  })().catch(next);
}
module.exports={requireAuth};
