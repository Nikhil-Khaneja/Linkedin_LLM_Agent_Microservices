import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

function matchesClientFilters(job, filters) {
  const keyword = (filters.keyword || '').trim().toLowerCase();
  const location = (filters.location || '').trim().toLowerCase();

  const haystack = [
    job.title,
    job.company_name,
    job.location,
    job.city,
    job.state,
    job.description_text,
  ].filter(Boolean).join(' ').toLowerCase();

  const keywordOk = !keyword || haystack.includes(keyword);
  const locationOk = !location || haystack.includes(location);
  const workModeOk = !filters.work_mode || (job.work_mode || '').toLowerCase() === filters.work_mode.toLowerCase();
  const typeOk = !filters.employment_type || (job.employment_type || '').toLowerCase() === filters.employment_type.toLowerCase();

  return keywordOk && locationOk && workModeOk && typeOk;
}

export default function JobsPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [rawJobs, setRawJobs] = useState([]);
  const [appliedJobIds, setAppliedJobIds] = useState(new Set());
  const [savedJobIds, setSavedJobIds] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [hideApplied, setHideApplied] = useState(true);
  const [filters, setFilters] = useState({ keyword: searchParams.get('q') || '', location: '', work_mode: '', employment_type: '' });

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

  const search = async (f = filters) => {
    if (!token) {
      toast.error('Please sign in first');
      return;
    }
    setLoading(true);
    try {
      const payload = { ...f, page_size: 50 };
      if (!payload.keyword) delete payload.keyword;
      if (!payload.location) delete payload.location;
      if (!payload.work_mode) delete payload.work_mode;
      if (!payload.employment_type) delete payload.employment_type;
      const { data } = await axios.post(`${BASE.job}/jobs/search`, payload, authCfg);
      let items = Array.isArray(data?.data?.items) ? data.data.items : [];

      if (items.length === 0 && (payload.keyword || payload.location || payload.work_mode || payload.employment_type)) {
        const fallback = await axios.post(`${BASE.job}/jobs/search`, { page_size: 100 }, authCfg);
        const allItems = Array.isArray(fallback?.data?.data?.items) ? fallback.data.data.items : [];
        items = allItems.filter((job) => matchesClientFilters(job, f));
      }

      setRawJobs(items);
    } catch (e) {
      toast.error(e?.response?.data?.error?.message || 'Failed to load jobs');
      setRawJobs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token) search(filters); }, [token, currentId]);
  useEffect(() => { if (token) search(filters); }, [filters.work_mode, filters.employment_type]);

  const jobs = useMemo(() => (
    hideApplied && user?.userType === 'member' ? rawJobs.filter((j) => !appliedJobIds.has(j.job_id)) : rawJobs
  ), [rawJobs, hideApplied, user?.userType, appliedJobIds]);

  const set = (k) => (e) => setFilters((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div style={S.page}>
      <div className="li-card" style={{ padding: '16px 20px', marginBottom: 8 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Find the right job for you</h1>
        <div style={S.searchRow}>
          <div style={S.searchField}><span style={S.fieldIcon}>🔍</span><input style={S.searchInput} value={filters.keyword} onChange={set('keyword')} placeholder="Title, skill, or company" onKeyDown={(e) => e.key === 'Enter' && search()} /></div>
          <div style={S.searchField}><span style={S.fieldIcon}>📍</span><input style={S.searchInput} value={filters.location} onChange={set('location')} placeholder="City, state, or remote" onKeyDown={(e) => e.key === 'Enter' && search()} /></div>
          <button onClick={() => search()} className="li-btn-primary" style={{ padding: '12px 28px', fontSize: 16, borderRadius: 4 }}>Search</button>
        </div>
        <div style={S.filterRow}>
          <select style={S.filterSelect} value={filters.work_mode} onChange={set('work_mode')}>
            <option value="">Remote / On-site</option>
            {['remote', 'onsite', 'hybrid'].map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          <select style={S.filterSelect} value={filters.employment_type} onChange={set('employment_type')}>
            <option value="">Job type</option>
            {['full_time', 'part_time', 'contract', 'internship'].map((v) => <option key={v} value={v}>{v.replace('_', ' ')}</option>)}
          </select>
          {(filters.keyword || filters.location || filters.work_mode || filters.employment_type) && (
            <button onClick={() => { const cleared = { keyword: '', location: '', work_mode: '', employment_type: '' }; setFilters(cleared); search(cleared); }} style={S.clearBtn}>Clear all ✕</button>
          )}
        </div>
      </div>
      <div style={S.results}>
        {!loading && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, paddingLeft: 4 }}>
            <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.6)' }}>{jobs.length} job{jobs.length !== 1 ? 's' : ''} found{hideApplied && rawJobs.length > jobs.length ? ` · ${rawJobs.length - jobs.length} applied hidden` : ''}</p>
            {user?.userType === 'member' && <label style={{ fontSize: 13, color: 'rgba(0,0,0,0.6)' }}><input type="checkbox" checked={hideApplied} onChange={(e) => setHideApplied(e.target.checked)} style={{ marginRight: 6 }} />Hide applied</label>}
          </div>
        )}
        {loading ? (
          <div className="li-card" style={{ padding: 48, textAlign: 'center', color: 'rgba(0,0,0,0.5)' }}>Loading jobs…</div>
        ) : jobs.length === 0 ? (
          <div className="li-card" style={{ padding: 48, textAlign: 'center' }}><p style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No jobs found</p><p style={{ color: 'rgba(0,0,0,0.6)' }}>Try different keywords or remove some filters</p></div>
        ) : (
          jobs.map((job) => <JobCard key={job.job_id} job={{ ...job, is_saved: savedJobIds.has(job.job_id) || job.is_saved }} isApplied={appliedJobIds.has(job.job_id)} />)
        )}
      </div>
    </div>
  );
}

function JobCard({ job, isApplied }) {
  return (
    <Link to={`/jobs/${job.job_id}`} state={{ job }} style={{ textDecoration: 'none', display: 'block', marginBottom: 8 }}>
      <div className="li-card" style={S.jobCard}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
          <div style={S.logo}>{(job.company_name || 'C')[0]}</div>
          <div style={{ flex: 1 }}>
            <h3 style={S.jobTitle}>{job.title}</h3>
            <p style={S.company}>{job.company_name}</p>
            <p style={S.meta}>{job.location || 'Remote'}{job.status ? ` · ${job.status}` : ''}</p>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
              <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)', margin: 0 }}>{job.is_saved ? 'Saved job' : 'Open role'}</p>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {job.is_saved && <span style={{ fontSize: 13, color: '#0a66c2', fontWeight: 600, border: '1px solid #0a66c2', borderRadius: 12, padding: '2px 10px', background: '#eef5fc' }}>Saved</span>}
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
