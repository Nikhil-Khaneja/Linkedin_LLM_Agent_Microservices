const BASE = {
  // Owner 7 analytics is the only service running locally right now.
  // All other service URLs point to their future EC2 addresses via env vars.
  analytics:   process.env.REACT_APP_ANALYTICS_URL   || 'http://localhost:8000',
  auth:        process.env.REACT_APP_AUTH_URL        || 'http://localhost:3001',
  member:      process.env.REACT_APP_MEMBER_URL      || 'http://localhost:3002',
  recruiter:   process.env.REACT_APP_RECRUITER_URL   || 'http://localhost:3003',
  job:         process.env.REACT_APP_JOB_URL         || 'http://localhost:3004',
  application: process.env.REACT_APP_APP_URL         || 'http://localhost:3005',
  messaging:   process.env.REACT_APP_MSG_URL         || 'http://localhost:3006',
  ai:          process.env.REACT_APP_AI_URL          || 'http://localhost:3008',
};
export default BASE;
