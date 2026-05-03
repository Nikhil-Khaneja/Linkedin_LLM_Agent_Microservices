/**
 * Parse API / MySQL datetimes for display. Naive "YYYY-MM-DD HH:mm:ss" (no offset)
 * is treated as UTC so it matches Docker MySQL TIMESTAMP behavior.
 */
export function parseApiDate(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const s = String(value).trim();
  const hasTz = /[zZ]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s);
  const naiveNoTz =
    /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(s) && !hasTz;
  const d = naiveNoTz ? new Date(s.replace(' ', 'T') + 'Z') : new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function jobPostedAt(job) {
  if (!job || typeof job !== 'object') return null;
  return job.posted_at ?? job.posted_datetime ?? job.created_at ?? null;
}

/**
 * Relative "posted" label. Clamps future timestamps (clock skew / parse quirks).
 */
export function formatPostedCalendar(job) {
  const p = parseApiDate(jobPostedAt(job));
  return p ? p.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : '—';
}

export function timeAgoPosted(value) {
  const t = value instanceof Date ? value : parseApiDate(value);
  if (!t) return '';
  let ms = Date.now() - t.getTime();
  if (ms < 0) ms = 0;
  const days = Math.floor(ms / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return '1 day ago';
  if (days < 7) return `${days} days ago`;
  if (days < 30) return `${Math.floor(days / 7)} week${days < 14 ? '' : 's'} ago`;
  return `${Math.floor(days / 30)} month${days < 60 ? '' : 's'} ago`;
}
