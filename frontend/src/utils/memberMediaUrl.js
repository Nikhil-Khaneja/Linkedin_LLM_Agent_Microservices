import BASE from '../config/api';

function _isLoopbackHost(hostname) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}

/**
 * Rewrites signed member media URLs so the browser loads them through the site origin (ALB :443),
 * not legacy http://host:8002… links that time out in production.
 *
 * - HTTPS SPA: always same origin + /members/media + query (fixes :8002, EC2 IP in signed URLs).
 * - HTTP SPA on real domain + href http://same:8002/: strip port and use https://host (ALB TLS).
 * - Localhost dev: keep BASE.member (http://localhost:8002).
 */
export function normalizeMemberMediaUrl(raw, memberBase = BASE.member) {
  if (!raw || typeof raw !== 'string') return '';
  const t = raw.trim();
  if (!t) return '';
  const base = (memberBase || '').replace(/\/$/, '');
  try {
    const win = typeof window !== 'undefined' ? window : null;
    const pageOrigin = win ? win.location.origin : 'http://localhost';
    const u = new URL(t, pageOrigin);
    const pathOk = u.pathname === '/members/media' || u.pathname.endsWith('/members/media');
    if (!pathOk) return t;

    if (!win) {
      if (!base) return t;
      return `${base}/members/media${u.search}`;
    }

    const sameHost = u.hostname === win.location.hostname;
    const loopback = _isLoopbackHost(u.hostname);

    // HTTPS page: never follow http://…:8002 — same origin hits ALB path routing.
    if (win.location.protocol === 'https:') {
      return `${win.location.origin}/members/media${u.search}`;
    }

    // HTTP page (rare prod misconfig): href still points at :8002 on same host → use HTTPS canonical origin.
    if (!loopback && sameHost && u.port === '8002') {
      return `https://${u.hostname}/members/media${u.search}`;
    }

    if (!base) return t;
    return `${base}/members/media${u.search}`;
  } catch {
    return t;
  }
}
