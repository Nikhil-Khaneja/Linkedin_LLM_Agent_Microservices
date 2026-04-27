require('dotenv').config();
const express=require('express');
const helmet=require('helmet');
const cors=require('cors');
const morgan=require('morgan');
const {v4:uuidv4}=require('uuid');
const {connectMySQL}=require('./db/mysql');
const {connectMongoDB}=require('./db/mongodb');
const {connectRedis}=require('./db/redis');
const {connectKafka}=require('./kafka/producer');
const {errorHandler}=require('./middleware/errorHandler');
const routes=require('./routes/messaging');
const { swaggerUi, spec } = require('./swagger');

const app=express();
const PORT=process.env.PORT||3006;
app.use(helmet());app.use(cors({origin:'*'}));
app.use(express.json({limit:'2mb'}));app.use(morgan('combined'));
app.use((req,res,next)=>{req.traceId=req.headers['x-trace-id']||uuidv4();res.setHeader('X-Trace-Id',req.traceId);next();});
app.use('/',routes);
app.get('/health',(req,res)=>res.json({status:'ok',service:'messaging-service',ts:new Date().toISOString()}));

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
    await connectMongoDB();
    await connectRedis();
    await connectKafka('messaging-service');
    app.listen(PORT,()=>console.log('[messaging-service] Listening on :'+PORT));
  }catch(err){console.error('[messaging-service] Bootstrap failed:',err);process.exit(1);}
}
bootstrap();
