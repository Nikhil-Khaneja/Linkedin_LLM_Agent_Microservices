require('dotenv').config();

const express = require('express');
const helmet = require('helmet');
const cors = require('cors');
const morgan = require('morgan');
const { v4: uuidv4 } = require('uuid');

const { connectMySQL } = require('./db/mysql');
const { connectRedis } = require('./db/redis');
const { connectKafka } = require('./kafka/producer');
const { errorHandler } = require('./middleware/errorHandler');
const { swaggerUi, spec } = require('./swagger');

const recruiterRoutes = require('./routes/recruiters');
const companyRoutes = require('./routes/companies');

const app = express();
const PORT = process.env.PORT || 3003;

app.use(helmet());
app.use(cors({ origin: '*' }));
app.use(express.json({ limit: '2mb' }));
app.use(morgan('combined'));

app.use((req, res, next) => {
  req.traceId = req.headers['x-trace-id'] || `trc_${uuidv4()}`;
  res.setHeader('X-Trace-Id', req.traceId);
  next();
});

app.use('/recruiters', recruiterRoutes);
app.use('/companies', companyRoutes);

app.get('/health', (req, res) => {
  return res.json({
    success: true,
    trace_id: req.traceId,
    data: {
      status: 'ok',
      service: 'recruiter-service',
      ts: new Date().toISOString()
    }
  });
});

app.use(
  '/api-docs',
  swaggerUi.serve,
  swaggerUi.setup(spec, {
    customCss: '.swagger-ui .topbar { display: none; }',
    customSiteTitle: 'Recruiter Service API Docs',
    swaggerOptions: {
      persistAuthorization: true
    }
  })
);

app.use(errorHandler);

async function bootstrap() {
  try {
    await connectMySQL();
    await connectRedis();
    await connectKafka('recruiter-service');

    app.listen(PORT, () => {
      console.log(`[recruiter-service] Listening on :${PORT}`);
    });
  } catch (err) {
    console.error('[recruiter-service] Bootstrap failed:', err);
    process.exit(1);
  }
}

bootstrap();