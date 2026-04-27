require('dotenv').config();
const express=require('express');
const helmet=require('helmet');
const cors=require('cors');
const morgan=require('morgan');
const {v4:uuidv4}=require('uuid');
const {connectMySQL}=require('./db/mysql');
const {connectRedis}=require('./db/redis');
const {connectKafka}=require('./kafka/producer');
const {connectElasticsearch}=require('./db/elasticsearch');
const {ensureMembersIndex,syncMembersToES}=require('./search/memberSearch');
const {errorHandler}=require('./middleware/errorHandler');
const memberRoutes=require('./routes/members');
const { swaggerUi, spec } = require('./swagger');

const app=express();
const PORT=process.env.PORT||3002;
app.use(helmet());
app.use(cors({origin:'*'}));
app.use(express.json({limit:'2mb'}));
app.use(morgan('combined'));
app.use((req,res,next)=>{
  req.traceId=req.headers['x-trace-id']||uuidv4();
  res.setHeader('X-Trace-Id',req.traceId);
  next();
});
app.use('/members',memberRoutes);
app.get('/health',(req,res)=>res.json({
  status:'ok',service:'member-service',
  elasticsearch:require('./db/elasticsearch').isReady()?'connected':'fallback-mysql',
  ts:new Date().toISOString()
}));

// ── Swagger API Docs ─────────────────────────────────────────
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(spec || specs, {
  customCss: '.swagger-ui .topbar { display: none }',
  customSiteTitle: 'LinkedIn API Docs',
  swaggerOptions: { persistAuthorization: true }
}));

app.use(errorHandler);
async function bootstrap(){
  try{
    await connectMySQL();
    await connectRedis();
    await connectKafka('member-service');
    connectElasticsearch().then(async()=>{
      await ensureMembersIndex();
      setTimeout(syncMembersToES,8000);
    }).catch(e=>console.warn('[member-service] ES setup failed:',e.message));
    app.listen(PORT,()=>console.log('[member-service] Listening on :'+PORT));
  }catch(err){console.error('[member-service] Bootstrap failed:',err);process.exit(1);}
}
bootstrap();
