// AUTOMATED BY AI — single source for all backend URLs.
// In production, set REACT_APP_API_BASE_URL to the API Gateway / ALB URL.
// In local Docker Compose the nginx proxy rewrites /api/v1/* so BASE can stay "".
const BASE = {
  auth:        process.env.REACT_APP_AUTH_URL        || 'http://localhost:8001',
  member:      process.env.REACT_APP_MEMBER_URL      || 'http://localhost:8002',
  recruiter:   process.env.REACT_APP_RECRUITER_URL   || 'http://localhost:8003',
  job:         process.env.REACT_APP_JOB_URL         || 'http://localhost:8004',
  application: process.env.REACT_APP_APP_URL         || 'http://localhost:8005',
  messaging:   process.env.REACT_APP_MESSAGING_URL   || 'http://localhost:8006',
  analytics:   process.env.REACT_APP_ANALYTICS_URL   || 'http://localhost:8007',
  ai:          process.env.REACT_APP_AI_URL          || 'http://localhost:8008',
};
export default BASE;
