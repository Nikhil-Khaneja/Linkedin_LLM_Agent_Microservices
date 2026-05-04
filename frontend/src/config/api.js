/**
 * API bases for microservices. When you open the UI as http://<this-host>:5173, calls must go to
 * the same host on ports 8001–8008 (Docker publishes them on 0.0.0.0). Using baked-in localhost
 * breaks for LAN IPs, Docker Machine hostnames, etc. and shows a generic Axios "Network Error".
 */
function loopbackHost(hostname) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}

function serviceBase(envUrl, port) {
  if (typeof window === 'undefined') {
    return envUrl || `http://127.0.0.1:${port}`;
  }
  const h = window.location.hostname;
  if (loopbackHost(h)) {
    return envUrl || `http://localhost:${port}`;
  }
  // Production: use full URL from build (e.g. https://auth.example.com) when CI set REACT_APP_*.
  const baked = (envUrl || '').trim();
  if (/^https?:\/\//i.test(baked)) {
    return baked.replace(/\/$/, '');
  }
  // ECS bridge / published host ports: services speak plain HTTP on 8001–8008. Using the page's
  // https:// here causes ERR_SSL_PROTOCOL_ERROR (nothing terminates TLS on each API port).
  // Put TLS in front (ALB/nginx on 443) and bake full https REACT_APP_* URLs if you need HTTPS APIs.
  return `http://${h}:${port}`;
}

const BASE = {
  auth: serviceBase(process.env.REACT_APP_AUTH_URL, 8001),
  member: serviceBase(process.env.REACT_APP_MEMBER_URL, 8002),
  recruiter: serviceBase(process.env.REACT_APP_RECRUITER_URL, 8003),
  job: serviceBase(process.env.REACT_APP_JOB_URL, 8004),
  application: serviceBase(process.env.REACT_APP_APP_URL, 8005),
  messaging: serviceBase(process.env.REACT_APP_MSG_URL, 8006),
  analytics: serviceBase(process.env.REACT_APP_ANALYTICS_URL, 8007),
  ai: serviceBase(process.env.REACT_APP_AI_URL, 8008),
};

export default BASE;
