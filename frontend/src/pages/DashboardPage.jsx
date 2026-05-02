import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';

function timeAgo(d) {
  if (!d) return '';
  const days = Math.floor((Date.now() - new Date(d)) / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return '1 day ago';
  if (days < 7) return `${days} days ago`;
  if (days < 30) return `${Math.floor(days / 7)} week${days < 14 ? '' : 's'} ago`;
  return `${Math.floor(days / 30)} month${days < 60 ? '' : 's'} ago`;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [appliedJobIds, setAppliedJobIds] = useState(new Set());
  const [profile, setProfile] = useState(null);

  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
  const currentId = user?.principalId || user?.userId;

  const loadApplied = async () => {
    if (!token || !currentId) return;
    try {
      const { data } = await axios.post(`${BASE.application}/applications/byMember`, { member_id: currentId }, authCfg);
      const ids = new Set((data?.data?.items || []).map((a) => a.job_id));
      setAppliedJobIds(ids);
    } catch {
      setAppliedJobIds(new Set());
    }
  };

  useEffect(() => {
    if (!token) return;
    axios.post(`${BASE.job}/jobs/search`, { page_size: 8 }, authCfg).then((r) => setJobs(r?.data?.data?.items || [])).catch(() => setJobs([]));
  }, [token]);

  useEffect(() => {
    if (!currentId || !token) return;
    loadApplied();
    axios.post(`${BASE.member}/members/get`, { member_id: currentId }, authCfg).then((r) => setProfile(r?.data?.data?.profile || null)).catch(() => setProfile(null));
  }, [currentId, token]);

  const displayName = profile ? `${profile.first_name || ''} ${profile.last_name || ''}`.trim() : `${user?.firstName || ''} ${user?.lastName || ''}`.trim();
  const initial = ((displayName || user?.email || 'U')[0]).toUpperCase();

  return (
    <div style={S.layout}>
      <aside style={S.aside}>
        <div style={S.card}>
          <div style={S.banner} />
          <div style={{ padding: '0 16px 16px', textAlign: 'center', marginTop: -34 }}>
            <div style={S.bigAvatar}>{initial}</div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginTop: 8, marginBottom: 2 }}>{displayName || user?.email?.split('@')[0] || 'Your profile'}</h3>
            <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.55)', marginBottom: 12 }}>{profile?.headline || 'Add a headline'}</p>
            <Link to="/profile" style={S.viewProfile}>View full profile</Link>
          </div>
        </div>
      </aside>

      <main>
        {jobs.length === 0 ? (
          <div style={{ ...S.card, padding: '40px 20px', textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>💼</div>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>No jobs posted yet</h3>
            <Link to="/jobs"><button style={S.ctaBtn}>Browse jobs</button></Link>
          </div>
        ) : (
          jobs.map((job) => <JobCard key={job.job_id} job={job} navigate={navigate} isApplied={appliedJobIds.has(job.job_id)} />)
        )}
      </main>

      <aside style={S.aside} />
    </div>
  );
}

function JobCard({ job, navigate, isApplied }) {
  return (
    <div style={S.jobCard} onClick={() => navigate(`/jobs/${job.job_id}`, { state: { job } })}>
      <div style={{ display: 'flex', gap: 14 }}>
        <div style={S.logo}>{(job.company_name || 'C')[0]}</div>
        <div style={{ flex: 1 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0a66c2', marginBottom: 2 }}>{job.title}</h3>
          <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.85)', marginBottom: 2 }}>{job.company_name}</p>
          <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.55)', marginBottom: 8 }}>{[job.city && `📍 ${job.city}${job.state ? ', ' + job.state : ''}`, job.work_mode].filter(Boolean).join(' · ')}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'rgba(0,0,0,0.4)' }}>{job.applicants_count || 0} applicants · {timeAgo(job.posted_at || job.posted_datetime)}</span>
            <button onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${job.job_id}`, { state: { job } }); }} style={{ ...S.applyBtn, background: isApplied ? '#057642' : '#0a66c2', color: '#fff', border: isApplied ? '1.5px solid #057642' : '1.5px solid #0a66c2' }}>{isApplied ? '✓ Applied' : 'Apply'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

const S = {
  layout: { display: 'grid', gridTemplateColumns: '220px 1fr 280px', gap: 20, alignItems: 'start' },
  aside: { position: 'sticky', top: 72 },
  card: { background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', overflow: 'hidden' },
  banner: { height: 56, background: 'linear-gradient(135deg,#0a66c2,#7c3aed)' },
  bigAvatar: { width: 64, height: 64, borderRadius: '50%', background: '#0a66c2', color: '#fff', fontSize: 24, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '3px solid #fff', margin: '0 auto' },
  viewProfile: { display: 'inline-block', padding: '6px 16px', border: '1.5px solid rgba(0,0,0,0.5)', borderRadius: 24, fontSize: 14, fontWeight: 700, color: 'rgba(0,0,0,0.8)', textDecoration: 'none' },
  ctaBtn: { padding: '11px 28px', background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 28, fontSize: 16, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' },
  jobCard: { background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', padding: '16px 20px', cursor: 'pointer', marginBottom: 10 },
  logo: { width: 52, height: 52, background: '#f3f2ef', border: '1px solid rgba(0,0,0,0.1)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 800, color: '#555', flexShrink: 0 },
  applyBtn: { padding: '6px 18px', borderRadius: 24, fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' },
};
