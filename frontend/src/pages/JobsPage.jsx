import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

// Small pages keep first paint and scrolling light while you verify the app (use Next for more).
const PAGE_SIZE = 15;

export default function JobsPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [rawJobs, setRawJobs] = useState([]);
  const [appliedJobIds, setAppliedJobIds] = useState(new Set());
  const [savedJobIds, setSavedJobIds] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [hideApplied, setHideApplied] = useState(true);
  const [aiModal, setAiModal] = useState(null);
  const [filters, setFilters] = useState({ keyword: searchParams.get('q') || '', location: '', work_mode: '', employment_type: '', salary_min: '', salary_max: '' });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [debouncedKwLoc, setDebouncedKwLoc] = useState(() => ({
    kw: searchParams.get('q') || '',
    loc: '',
  }));

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedKwLoc({ kw: filters.keyword, loc: filters.location });
    }, 350);
    return () => clearTimeout(t);
  }, [filters.keyword, filters.location]);

  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const filterKey = `${debouncedKwLoc.kw}|${debouncedKwLoc.loc}|${filters.work_mode}|${filters.employment_type}|${filters.salary_min}|${filters.salary_max}`;
  const prevFilterKeyRef = useRef(filterKey);

  const token = localStorage.getItem('access_token');
  const currentId = user?.principalId || user?.userId;
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  const loadApplied = async () => {
    if (!token || !currentId) return;
    try {
      const { data } = await axios.post(`${BASE.application}/applications/byMember`, {}, authCfg);
      if (data.success) {
        setAppliedJobIds(new Set((data.data?.items || []).map((a) => a.job_id)));
      }
    } catch {
      setAppliedJobIds(new Set());
    }
  };

  const loadSaved = async () => {
    if (!token || !currentId || user?.userType !== 'member') return;
    try {
      const { data } = await axios.post(`${BASE.job}/jobs/savedByMember`, {}, authCfg);
      if (data.success) {
        setSavedJobIds(new Set((data.data?.items || []).map((a) => a.job_id)));
      }
    } catch {
      setSavedJobIds(new Set());
    }
  };

  const openAIScore = async (job) => {
    if (!token) return toast.error('Sign in to see your match score');
    setAiModal({ job_id: job.job_id, title: job.title, loading: true, result: null, error: null });
    try {
      const { data } = await axios.post(
        `${BASE.ai}/ai/coach/suggest`,
        { target_job_id: job.job_id },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setAiModal((prev) => prev?.job_id === job.job_id ? { ...prev, loading: false, result: data?.data || null } : prev);
      // Bust the Coach page session cache so fresh history loads on navigate
      sessionStorage.removeItem('coach_history_v1');
    } catch (err) {
      setAiModal((prev) => prev?.job_id === job.job_id ? { ...prev, loading: false, error: err?.response?.data?.error?.message || 'Failed to load score' } : prev);
    }
  };

  useEffect(() => { loadApplied(); loadSaved(); }, [currentId, token]);

  useEffect(() => {
    const handler = () => { loadApplied(); loadSaved(); };
    window.addEventListener('applications:changed', handler);
    window.addEventListener('saved-jobs:changed', handler);
    window.addEventListener('focus', handler);
    return () => {
      window.removeEventListener('applications:changed', handler);
      window.removeEventListener('saved-jobs:changed', handler);
      window.removeEventListener('focus', handler);
    };
  }, [currentId, token]);

  const fetchJobs = async (f, pageNum) => {
    if (!token) {
      toast.error('Please sign in first');
      return;
    }
    setLoading(true);
    try {
      const payload = { ...f, page: pageNum, page_size: PAGE_SIZE };
      if (!payload.keyword) delete payload.keyword;
      if (!payload.location) delete payload.location;
      if (!payload.work_mode) delete payload.work_mode;
      if (!payload.employment_type) delete payload.employment_type;
      if (!payload.salary_min) delete payload.salary_min;
      if (!payload.salary_max) delete payload.salary_max;
      const { data } = await axios.post(`${BASE.job}/jobs/search`, payload, {
        ...authCfg,
        timeout: 120000,
      });
      const items = Array.isArray(data?.data?.items) ? data.data.items : [];
      setRawJobs(items);
      const t = data?.meta?.total;
      setTotal(Number.isFinite(Number(t)) ? Number(t) : items.length);
    } catch (e) {
      toast.error(e?.response?.data?.error?.message || 'Failed to load jobs');
      setRawJobs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!token) return;
    const f = { ...filtersRef.current, keyword: debouncedKwLoc.kw, location: debouncedKwLoc.loc };
    const filterBumped = prevFilterKeyRef.current !== filterKey;
    prevFilterKeyRef.current = filterKey;
    const pageToFetch = filterBumped ? 1 : page;
    if (filterBumped && page !== 1) setPage(1);
    fetchJobs(f, pageToFetch);
  }, [token, currentId, page, filterKey]);

  const runSearch = () => {
    setDebouncedKwLoc({ kw: filtersRef.current.keyword, loc: filtersRef.current.location });
    setPage(1);
  };

  const jobs = useMemo(() => (
    hideApplied && user?.userType === 'member' ? rawJobs.filter((j) => !appliedJobIds.has(j.job_id)) : rawJobs
  ), [rawJobs, hideApplied, user?.userType, appliedJobIds]);

  const set = (k) => (e) => setFilters((p) => ({ ...p, [k]: e.target.value }));

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const rangeStart = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = total === 0 ? 0 : Math.min(page * PAGE_SIZE, total);

  return (
    <div style={S.page}>
      <div className="li-card" style={{ padding: '16px 20px', marginBottom: 8 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Find the right job for you</h1>
        <div style={S.searchRow}>
          <div style={S.searchField}><span style={S.fieldIcon}>🔍</span><input style={S.searchInput} value={filters.keyword} onChange={set('keyword')} placeholder="Title, skill, or company" onKeyDown={(e) => e.key === 'Enter' && runSearch()} /></div>
          <div style={S.searchField}><span style={S.fieldIcon}>📍</span><input style={S.searchInput} value={filters.location} onChange={set('location')} placeholder="City, state, or remote" onKeyDown={(e) => e.key === 'Enter' && runSearch()} /></div>
          <button type="button" onClick={() => runSearch()} className="li-btn-primary" style={{ padding: '12px 28px', fontSize: 16, borderRadius: 4 }}>Search</button>
        </div>
        <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.5)', margin: '0 0 12px' }}>
          Keyword and location refresh after you pause typing; <strong>Search</strong> or <strong>Enter</strong> applies immediately. For fast search on large data, run <strong>bash scripts/apply_mysql_schema.sh</strong> once so MySQL can add the jobs fulltext index.
        </p>
        {(filters.salary_min || filters.salary_max) && (
          <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.5)', marginTop: 10, marginBottom: 0, lineHeight: 1.45 }}>
            Only jobs with a posted salary range are included when Min or Max is set (matches server filter).
          </p>
        )}
        <div style={S.filterRow}>
          <select style={S.filterSelect} value={filters.work_mode} onChange={set('work_mode')}>
            <option value="">Remote / On-site</option>
            {['remote', 'onsite', 'hybrid'].map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          <select style={S.filterSelect} value={filters.employment_type} onChange={set('employment_type')}>
            <option value="">Job type</option>
            {['full_time', 'part_time', 'contract', 'internship'].map((v) => <option key={v} value={v}>{v.replace('_', ' ')}</option>)}
          </select>
          <input style={{ ...S.filterSelect, width: 120 }} type="number" min={0} placeholder="Min $" value={filters.salary_min} onChange={set('salary_min')} />
          <input style={{ ...S.filterSelect, width: 120 }} type="number" min={0} placeholder="Max $" value={filters.salary_max} onChange={set('salary_max')} />
          {(filters.keyword || filters.location || filters.work_mode || filters.employment_type || filters.salary_min || filters.salary_max) && (
            <button
              type="button"
              onClick={() => {
                const cleared = { keyword: '', location: '', work_mode: '', employment_type: '', salary_min: '', salary_max: '' };
                setFilters(cleared);
                setDebouncedKwLoc({ kw: '', loc: '' });
                setPage(1);
              }}
              style={S.clearBtn}
            >
              Clear all ✕
            </button>
          )}
        </div>
      </div>
      <div style={S.results}>
        {!loading && (
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8, paddingLeft: 4 }}>
            <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.6)', margin: 0 }}>
              {total > 0 ? `Showing ${rangeStart}–${rangeEnd} of ${total.toLocaleString()}` : 'No results'}
              {jobs.length !== rawJobs.length ? ` · ${jobs.length} visible` : ''}
              {hideApplied && rawJobs.length > jobs.length ? ` · ${rawJobs.length - jobs.length} applied hidden` : ''}
            </p>
            {user?.userType === 'member' && <label style={{ fontSize: 13, color: 'rgba(0,0,0,0.6)' }}><input type="checkbox" checked={hideApplied} onChange={(e) => setHideApplied(e.target.checked)} style={{ marginRight: 6 }} />Hide applied</label>}
          </div>
        )}
        {!loading && total > PAGE_SIZE && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, paddingLeft: 4 }}>
            <button type="button" className="li-btn-primary" style={{ padding: '8px 16px', fontSize: 14, borderRadius: 4, opacity: page <= 1 ? 0.45 : 1 }} disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</button>
            <span style={{ fontSize: 14, color: 'rgba(0,0,0,0.65)' }}>Page {page} of {totalPages}</span>
            <button type="button" className="li-btn-primary" style={{ padding: '8px 16px', fontSize: 14, borderRadius: 4, opacity: page >= totalPages ? 0.45 : 1 }} disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Next</button>
          </div>
        )}
        {loading ? (
          <div className="li-card" style={{ padding: 48, textAlign: 'center', color: 'rgba(0,0,0,0.5)' }}>Loading jobs…</div>
        ) : jobs.length === 0 ? (
          <div className="li-card" style={{ padding: 48, textAlign: 'center' }}>
            <p style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No jobs found</p>
            {hideApplied && user?.userType === 'member' && rawJobs.length > 0 ? (
              <p style={{ color: 'rgba(0,0,0,0.6)' }}>
                This page has {rawJobs.length} result{rawJobs.length === 1 ? '' : 's'}, but all are hidden because you applied. Turn off <strong>Hide applied</strong> above to see them.
              </p>
            ) : (
              <p style={{ color: 'rgba(0,0,0,0.6)' }}>Try different keywords or remove some filters</p>
            )}
          </div>
        ) : (
          jobs.map((job) => <JobCard key={job.job_id} job={{ ...job, is_saved: savedJobIds.has(job.job_id) || job.is_saved }} isApplied={appliedJobIds.has(job.job_id)} userType={user?.userType} onAIScore={openAIScore} />)
        )}
      </div>
      {aiModal && <AIScoreModal modal={aiModal} onClose={() => setAiModal(null)} />}
    </div>
  );
}

function AIScoreModal({ modal, onClose }) {
  const navigate = useNavigate();
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={onClose}>
      <div style={{ background: '#fff', borderRadius: 12, padding: '24px 28px', maxWidth: 440, width: '92%', boxShadow: '0 8px 40px rgba(0,0,0,0.22)' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18 }}>
          <div>
            <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 2 }}>AI Match Score</h3>
            <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.5)' }}>{modal.title}</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 22, color: '#999', lineHeight: 1, padding: 0 }}>✕</button>
        </div>

        {modal.loading ? (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div style={{ width: 32, height: 32, border: '3px solid #e5e7eb', borderTopColor: '#7c3aed', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
            <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.5)' }}>Analyzing your profile…</p>
          </div>
        ) : modal.result ? (
          <>
            <div style={{ display: 'flex', gap: 28, marginBottom: 20, paddingBottom: 20, borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
              <div style={{ textAlign: 'center' }}>
                <p style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Current match</p>
                <p style={{ fontSize: 46, fontWeight: 800, color: '#0a66c2', lineHeight: 1 }}>{modal.result.current_match_score}</p>
              </div>
              <div style={{ textAlign: 'center' }}>
                <p style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>If improved</p>
                <p style={{ fontSize: 46, fontWeight: 800, color: '#057642', lineHeight: 1 }}>{modal.result.match_score_if_improved}</p>
              </div>
              {modal.result.score_delta > 0 && (
                <div style={{ textAlign: 'center' }}>
                  <p style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Potential gain</p>
                  <p style={{ fontSize: 46, fontWeight: 800, color: '#057642', lineHeight: 1 }}>+{modal.result.score_delta}</p>
                </div>
              )}
            </div>

            {modal.result.skills_to_add?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'rgba(0,0,0,0.75)' }}>Skills to add</p>
                {modal.result.skills_to_add.map((s) => (
                  <span key={s} style={{ display: 'inline-block', padding: '3px 10px', borderRadius: 999, background: '#fff7ed', color: '#b45309', fontSize: 12, fontWeight: 600, marginRight: 6, marginBottom: 6, border: '1px solid #fed7aa' }}>{s}</span>
                ))}
              </div>
            )}

            {modal.result.resume_tips?.[0] && (
              <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.7)', background: '#f8f9fa', borderRadius: 6, padding: '10px 12px', marginBottom: 20, lineHeight: 1.5 }}>
                💡 {modal.result.resume_tips[0]}
              </p>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button onClick={onClose} style={{ padding: '8px 18px', border: '1.5px solid rgba(0,0,0,0.2)', borderRadius: 20, background: '#fff', cursor: 'pointer', fontSize: 14, fontFamily: 'inherit' }}>Close</button>
              <button onClick={() => { onClose(); navigate('/coach'); }} style={{ padding: '8px 18px', background: '#7c3aed', color: '#fff', border: 'none', borderRadius: 20, cursor: 'pointer', fontSize: 14, fontWeight: 600, fontFamily: 'inherit' }}>Full Analysis →</button>
            </div>
          </>
        ) : (
          <p style={{ color: '#cc1016', fontSize: 14, textAlign: 'center', padding: '24px 0' }}>{modal.error || 'Failed to load score. Make sure your profile is set up.'}</p>
        )}
      </div>
    </div>
  );
}

function JobCard({ job, isApplied, onAIScore, userType }) {
  return (
    <Link to={`/jobs/${job.job_id}`} state={{ job }} style={{ textDecoration: 'none', display: 'block', marginBottom: 8 }}>
      <div className="li-card" style={S.jobCard}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
          <div style={S.logo}>{(job.company_name || 'C')[0]}</div>
          <div style={{ flex: 1 }}>
            <h3 style={S.jobTitle}>{job.title}</h3>
            <p style={S.company}>{job.company_name}</p>
            <p style={S.meta}>
              {job.location || 'Remote'}
              {job.status ? ` · ${job.status}` : ''}
              {(job.salary_min != null || job.salary_max != null) ? (
                <span>{` · $${job.salary_min != null ? Number(job.salary_min).toLocaleString() : '?'}–$${job.salary_max != null ? Number(job.salary_max).toLocaleString() : '?'} ${job.salary_currency || 'USD'}`}</span>
              ) : (
                <span style={{ color: 'rgba(0,0,0,0.42)' }}> · Salary not listed</span>
              )}
            </p>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
              <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)', margin: 0 }}>{job.is_saved ? 'Saved job' : 'Open role'}</p>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {job.is_saved && <span style={{ fontSize: 13, color: '#0a66c2', fontWeight: 600, border: '1px solid #0a66c2', borderRadius: 12, padding: '2px 10px', background: '#eef5fc' }}>Saved</span>}
                {userType === 'member' && (
                  <button
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); onAIScore(job); }}
                    style={{ fontSize: 12, color: '#7c3aed', fontWeight: 600, border: '1px solid #7c3aed', borderRadius: 12, padding: '2px 10px', background: '#f5f3ff', cursor: 'pointer', fontFamily: 'inherit' }}
                  >
                    ✨ AI Score
                  </button>
                )}
                {isApplied ? <span style={{ fontSize: 13, color: '#057642', fontWeight: 600, border: '1px solid #057642', borderRadius: 12, padding: '2px 10px' }}>✓ Applied</span> : <span style={{ fontSize: 13, color: '#0a66c2', fontWeight: 600, border: '1px solid #0a66c2', borderRadius: 12, padding: '2px 10px', background: '#fff' }}>Apply</span>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}

const S = {
  page: { maxWidth: 720, margin: '0 auto' },
  searchRow: { display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 },
  searchField: { flex: 1, display: 'flex', alignItems: 'center', gap: 8, border: '1px solid rgba(0,0,0,0.3)', borderRadius: 4, padding: '10px 14px', background: '#fff' },
  fieldIcon: { fontSize: 16, flexShrink: 0 },
  searchInput: { flex: 1, border: 'none', outline: 'none', fontSize: 16, fontFamily: 'inherit', color: '#000', background: 'transparent' },
  filterRow: { display: 'flex', gap: 8, flexWrap: 'wrap' },
  filterSelect: { padding: '6px 12px', border: '1.5px solid rgba(0,0,0,0.4)', borderRadius: 20, fontSize: 14, fontFamily: 'inherit', background: '#fff', cursor: 'pointer', color: 'rgba(0,0,0,0.7)', outline: 'none' },
  clearBtn: { padding: '6px 14px', border: '1.5px solid rgba(0,0,0,0.3)', borderRadius: 20, background: '#fff', fontSize: 14, cursor: 'pointer', color: 'rgba(0,0,0,0.6)', fontFamily: 'inherit' },
  results: {},
  jobCard: { padding: '16px 20px', cursor: 'pointer', transition: 'box-shadow 0.15s', marginBottom: 2 },
  logo: { width: 56, height: 56, background: '#f3f2ef', border: '1px solid rgba(0,0,0,0.1)', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 700, color: '#444', flexShrink: 0 },
  jobTitle: { fontSize: 16, fontWeight: 600, color: '#0a66c2', marginBottom: 2, lineHeight: 1.3 },
  company: { fontSize: 14, color: 'rgba(0,0,0,0.9)', marginBottom: 2 },
  meta: { fontSize: 14, color: 'rgba(0,0,0,0.6)' },
};
