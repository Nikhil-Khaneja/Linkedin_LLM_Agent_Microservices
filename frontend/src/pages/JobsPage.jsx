import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import toast from 'react-hot-toast';

export default function JobsPage() {
  const [searchParams] = useSearchParams();
  const [jobs, setJobs] = useState([]);
  const [appliedJobIds, setAppliedJobIds] = useState(new Set());

  // Load applied jobs on mount
  React.useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    fetch('http://localhost:3005/applications/byMember', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify({})
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        const ids = new Set((data.data.applications || []).map(a => a.job_id));
        setAppliedJobIds(ids);
      }
    })
    .catch(() => {});
  }, []);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    keyword: searchParams.get('q') || '',
    location: '',
    work_mode: '',
    employment_type: ''
  });

  const search = useCallback(async (f = filters) => {
    setLoading(true);
    try {
      const { data } = await axios.post(`${BASE.job}/jobs/search`, { ...f, page_size: 25 });
      setJobs(data.data?.jobs || []);
    } catch { toast.error('Failed to load jobs'); }
    finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { search(); }, []);

  const set = k => e => setFilters(p => ({ ...p, [k]: e.target.value }));

  return (
    <div style={S.page}>
      {/* Search bar */}
      <div className="li-card" style={{ padding: '16px 20px', marginBottom: 8 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Find the right job for you</h1>
        <div style={S.searchRow}>
          <div style={S.searchField}>
            <span style={S.fieldIcon}>🔍</span>
            <input style={S.searchInput} value={filters.keyword} onChange={set('keyword')}
              placeholder="Title, skill, or company" onKeyDown={e => e.key==='Enter'&&search()} />
          </div>
          <div style={S.searchField}>
            <span style={S.fieldIcon}>📍</span>
            <input style={S.searchInput} value={filters.location} onChange={set('location')}
              placeholder="City, state, or remote" onKeyDown={e => e.key==='Enter'&&search()} />
          </div>
          <button onClick={search} className="li-btn-primary" style={{ padding: '12px 28px', fontSize: 16, borderRadius: 4 }}>
            Search
          </button>
        </div>

        {/* Filter pills */}
        <div style={S.filterRow}>
          <select style={S.filterSelect} value={filters.work_mode} onChange={set('work_mode')}>
            <option value="">Remote / On-site</option>
            {['remote','onsite','hybrid'].map(v=><option key={v} value={v}>{v}</option>)}
          </select>
          <select style={S.filterSelect} value={filters.employment_type} onChange={set('employment_type')}>
            <option value="">Job type</option>
            {['full_time','part_time','contract','internship'].map(v=><option key={v} value={v}>{v.replace('_',' ')}</option>)}
          </select>
          {(filters.keyword||filters.location||filters.work_mode||filters.employment_type) && (
            <button onClick={() => { setFilters({keyword:'',location:'',work_mode:'',employment_type:''}); }} style={S.clearBtn}>
              Clear all ✕
            </button>
          )}
        </div>
      </div>

      <div style={S.results}>
        {/* Results count */}
        {!loading && <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.6)', marginBottom: 8, paddingLeft: 4 }}>
          {jobs.length} job{jobs.length !== 1 ? 's' : ''} found
        </p>}

        {loading ? (
          <div className="li-card" style={{ padding: 48, textAlign: 'center', color: 'rgba(0,0,0,0.5)' }}>Loading jobs…</div>
        ) : jobs.length === 0 ? (
          <div className="li-card" style={{ padding: 48, textAlign: 'center' }}>
            <p style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No jobs found</p>
            <p style={{ color: 'rgba(0,0,0,0.6)' }}>Try different keywords or remove some filters</p>
          </div>
        ) : (
          jobs.map(job => <JobCard key={job.job_id} job={job} isApplied={appliedJobIds.has(job.job_id)} />)
        )}
      </div>
    </div>
  );
}

function JobCard({ job, isApplied }) {
  return (
    <Link to={`/jobs/${job.job_id}`} style={{ textDecoration: 'none', display: 'block', marginBottom: 2 }}>
      <div className="li-card" style={S.jobCard}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
          <div style={S.logo}>{(job.company_name||'C')[0]}</div>
          <div style={{ flex: 1 }}>
            <h3 style={S.jobTitle}>{job.title}</h3>
            <p style={S.company}>{job.company_name}</p>
            <p style={S.meta}>
              {job.city && `${job.city}, ${job.state}`}
              {job.city && job.work_mode && ' · '}
              {job.work_mode && <span style={S.workTag}>{job.work_mode}</span>}
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              {job.employment_type && <Tag>{job.employment_type.replace('_',' ')}</Tag>}
              {job.salary_min && <Tag>💰 ${Math.round(job.salary_min/1000)}k – ${Math.round((job.salary_max||job.salary_min*1.3)/1000)}k</Tag>}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
              <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)', margin: 0 }}>
                {job.applicants_count} applicant{job.applicants_count !== 1 ? 's' : ''} · {job.posted_at ? new Date(job.posted_at).toLocaleDateString('en-US',{month:'short',day:'numeric'}) : 'Today'}
              </p>
              {isApplied
                ? <span style={{ fontSize: 13, color: '#057642', fontWeight: 600, border: '1px solid #057642', borderRadius: 12, padding: '2px 10px' }}>✓ Applied</span>
                : <span style={{ fontSize: 13, color: '#0a66c2', fontWeight: 600, border: '1px solid #0a66c2', borderRadius: 12, padding: '2px 10px', background: '#fff' }}>Apply</span>
              }
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}

function Tag({ children }) {
  return <span style={{ background: '#f3f6fb', border: '1px solid #c8d8e8', color: '#0a66c2', padding: '2px 10px', borderRadius: 12, fontSize: 13 }}>{children}</span>;
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
  workTag: { background: 'transparent', fontWeight: 600 },
};
