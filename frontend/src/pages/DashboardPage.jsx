import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';

const COLORS = ['#0a66c2', '#057642', '#7c3aed', '#e68a00', '#cc1016', '#06b6d4'];

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
  const [profileViews, setProfileViews] = useState([]);
  const [appStatus, setAppStatus] = useState([]);
  const [totalViews, setTotalViews] = useState(0);

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
    axios.post(`${BASE.analytics}/analytics/member/dashboard`, { member_id: currentId }, authCfg)
      .then((r) => {
        const d = r?.data?.data || {};
        const views = (d.profile_views || []).map(v => ({ view_date: v.view_date, view_count: Number(v.view_count || 0) }));
        setProfileViews(views);
        setTotalViews(Number(d.total_profile_views || 0));
        const breakdown = d.application_status_breakdown || {};
        setAppStatus(Object.entries(breakdown).map(([status, count]) => ({ status, count: Number(count || 0) })));
      })
      .catch(() => { setProfileViews([]); setAppStatus([]); });
  }, [currentId, token]);

  const displayName = profile ? `${profile.first_name || ''} ${profile.last_name || ''}`.trim() : `${user?.firstName || ''} ${user?.lastName || ''}`.trim();
  const initial = ((displayName || user?.email || 'U')[0]).toUpperCase();

  return (
    <div>
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

      {/* Member Analytics Dashboard */}
      <div style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16, color: 'rgba(0,0,0,0.85)' }}>Your Dashboard</h2>
        <div style={S.analyticsGrid}>
          {/* Profile Views */}
          <div style={{ ...S.aCard, gridColumn: '1 / -1' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700 }}>Profile Views — Last 30 Days</h3>
              {totalViews > 0 && <span style={{ fontSize: 22, fontWeight: 800, color: '#0a66c2' }}>{totalViews}</span>}
            </div>
            <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginBottom: 14, fontStyle: 'italic' }}>From profile.viewed Kafka events</p>
            {profileViews.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={profileViews} margin={{ left: 0, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                  <XAxis dataKey="view_date" tick={{ fontSize: 10 }} interval={Math.max(0, Math.floor(profileViews.length / 6) - 1)} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip formatter={v => [v, 'Views']} />
                  <Line type="monotone" dataKey="view_count" stroke="#0a66c2" strokeWidth={2.5} dot={{ fill: '#0a66c2', r: 3 }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ textAlign: 'center', color: 'rgba(0,0,0,0.4)', fontSize: 13, padding: '28px 0' }}>No profile views recorded yet — share your profile to start tracking views.</p>
            )}
          </div>

          {/* Application Status Pie */}
          <div style={S.aCard}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>My Applications</h3>
            <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginBottom: 14, fontStyle: 'italic' }}>Status breakdown from application events</p>
            {appStatus.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={appStatus} dataKey="count" nameKey="status" cx="50%" cy="50%" outerRadius={80} label={({ status, count }) => `${status}: ${count}`}>
                    {appStatus.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ textAlign: 'center', color: 'rgba(0,0,0,0.4)', fontSize: 13, padding: '28px 0' }}>No applications yet — apply to jobs to see your status here.</p>
            )}
          </div>

          {/* Application Status Bar */}
          <div style={S.aCard}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>Application Status by Count</h3>
            <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginBottom: 14, fontStyle: 'italic' }}>Same data as bars for easy comparison</p>
            {appStatus.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={appStatus} margin={{ bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                  <XAxis dataKey="status" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>{appStatus.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ textAlign: 'center', color: 'rgba(0,0,0,0.4)', fontSize: 13, padding: '28px 0' }}>Apply to jobs to see status analytics.</p>
            )}
          </div>
        </div>
      </div>
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
  aCard: { background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', padding: '18px 20px' },
  banner: { height: 56, background: 'linear-gradient(135deg,#0a66c2,#7c3aed)' },
  bigAvatar: { width: 64, height: 64, borderRadius: '50%', background: '#0a66c2', color: '#fff', fontSize: 24, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '3px solid #fff', margin: '0 auto' },
  viewProfile: { display: 'inline-block', padding: '6px 16px', border: '1.5px solid rgba(0,0,0,0.5)', borderRadius: 24, fontSize: 14, fontWeight: 700, color: 'rgba(0,0,0,0.8)', textDecoration: 'none' },
  ctaBtn: { padding: '11px 28px', background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 28, fontSize: 16, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' },
  jobCard: { background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', padding: '16px 20px', cursor: 'pointer', marginBottom: 10 },
  logo: { width: 52, height: 52, background: '#f3f2ef', border: '1px solid rgba(0,0,0,0.1)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 800, color: '#555', flexShrink: 0 },
  applyBtn: { padding: '6px 18px', borderRadius: 24, fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' },
  analyticsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
};
