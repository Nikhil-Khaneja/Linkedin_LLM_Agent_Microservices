import BASE from '../config/api';

/**
 * Rewrites signed member media URLs to the configured member API base (HTTPS + ALB host).
 * Fixes mixed content when URLs were signed with MEMBER_PUBLIC_URL=http://<ip>:8002 or cached in localStorage.
 */
export function normalizeMemberMediaUrl(raw, memberBase = BASE.member) {
  if (!raw || typeof raw !== 'string') return '';
  const t = raw.trim();
  if (!t) return '';
  const base = (memberBase || '').replace(/\/$/, '');
  if (!base) return t;
  try {
    const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
    const u = new URL(t, origin);
    if (!u.pathname.endsWith('/members/media')) return t;
    return `${base}/members/media${u.search}`;
  } catch {
    return t;
  }
}
