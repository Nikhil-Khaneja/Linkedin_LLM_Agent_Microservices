import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts';

const COLORS = ['#0a66c2', '#057642', '#7c3aed', '#e68a00', '#cc1016', '#06b6d4', '#ec4899', '#f59e0b'];

export default function AnalyticsPage() {
  const { user } = useAuth();
  const authCfg = useMemo(() => ({ headers: { Authorization: 'Bearer ' + localStorage.getItem('access_token') } }), []);
  const isRecruiter = user?.userType === 'recruiter';

  return isRecruiter ? <RecruiterAnalytics authCfg={authCfg} user={user} /> : <MemberAnalytics authCfg={authCfg} user={user} />;
}

/* ─── Member Dashboard ────────────────────────────────────────────── */
function MemberAnalytics({ authCfg, user }) {
  const [profileViews, setProfileViews] = useState([]);
  const [appStatus, setAppStatus] = useState([]);
  const [totalViews, setTotalViews] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const mid = user?.principalId || user?.userId;
    if (!mid) return;
    setLoading(true);
    axios.post(`${BASE.analytics}/analytics/member/dashboard`, { member_id: mid }, authCfg)
      .then(({ data }) => {
        const d = data?.data || {};
        const views = (d.profile_views || []).map(v => ({ view_date: v.view_date, view_count: Number(v.view_count || 0) }));
        setProfileViews(views);
        setTotalViews(Number(d.total_profile_views || 0));
        const bd = d.application_status_breakdown || {};
        setAppStatus(Object.entries(bd).map(([status, count]) => ({ status, count: Number(count || 0) })));
      })
      .catch(() => { setProfileViews([]); setAppStatus([]); })
      .finally(() => setLoading(false));
  }, [user]);

  if (loading) return <LoadingCard text="Loading your dashboard…" />;

  return (
    <div>
      <PageHeader title="My Analytics" sub="Your profile activity and application insights" />
      <div style={S.grid2}>
        <div style={{ ...S.card, gridColumn: '1/-1' }}>
          <ChartHeader title="Profile Views — Last 30 Days" sub="From profile.viewed Kafka events" extra={totalViews > 0 && <span style={{ fontSize: 26, fontWeight: 800, color: '#0a66c2' }}>{totalViews} total</span>} />
          {profileViews.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={profileViews} margin={{ left: 0, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="view_date" tick={{ fontSize: 10 }} interval={Math.max(0, Math.floor(profileViews.length / 6) - 1)} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip formatter={v => [v, 'Views']} />
                <Line type="monotone" dataKey="view_count" stroke="#0a66c2" strokeWidth={2.5} dot={{ fill: '#0a66c2', r: 3 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty text="No profile views yet — share your profile to start tracking." />}
        </div>

        <div style={S.card}>
          <ChartHeader title="Applications by Status" sub="Live from application events" />
          {appStatus.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={appStatus} dataKey="count" nameKey="status" cx="50%" cy="50%" outerRadius={90} label={({ status, count }) => `${status}: ${count}`}>
                  {appStatus.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty text="No applications yet — apply to jobs to see your breakdown." />}
        </div>

        <div style={S.card}>
          <ChartHeader title="Application Status Distribution" sub="Same data as bars for comparison" />
          {appStatus.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={appStatus} margin={{ bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="status" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>{appStatus.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="Apply to jobs to see status analytics." />}
        </div>
      </div>
    </div>
  );
}

/* ─── Recruiter Dashboard ─────────────────────────────────────────── */
function RecruiterAnalytics({ authCfg, user }) {
  const [topJobs, setTopJobs] = useState([]);
  const [lowJobs, setLowJobs] = useState([]);
  const [clickData, setClickData] = useState([]);
  const [savedData, setSavedData] = useState([]);
  const [geoData, setGeoData] = useState([]);
  const [funnelData, setFunnelData] = useState(null);
  const [recruiterJobs, setRecruiterJobs] = useState([]);
  const [geoJob, setGeoJob] = useState('');
  const [funnelJob, setFunnelJob] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const [topData, lowData, viewData, savedDataResp, jobsResp] = await Promise.all([
          axios.post(`${BASE.analytics}/analytics/jobs/top`, { metric: 'applications', window_days: 30, limit: 10 }, authCfg),
          axios.post(`${BASE.analytics}/analytics/jobs/top`, { metric: 'applications', window_days: 30, limit: 50 }, authCfg),
          axios.post(`${BASE.analytics}/analytics/jobs/top`, { metric: 'views', window_days: 7, limit: 8 }, authCfg),
          axios.post(`${BASE.analytics}/analytics/jobs/top`, { metric: 'saves', window_days: 7, limit: 8 }, authCfg),
          axios.post(`${BASE.job}/jobs/byRecruiter`, { recruiter_id: user?.principalId || user?.userId }, authCfg).catch(() => ({ data: { data: { items: [] } } })),
        ]);
        setTopJobs((topData.data?.data?.items || []).map(j => ({ name: (j.title || j.job_id || 'Job').slice(0, 20), count: j.count || j.metric_value || 0 })));
        const all = (lowData.data?.data?.items || []).sort((a, b) => ((a.count || a.metric_value || 0) - (b.count || b.metric_value || 0))).slice(0, 5);
        setLowJobs(all.map(j => ({ name: (j.title || j.job_id || 'Job').slice(0, 20), count: j.count || j.metric_value || 0 })));
        setClickData((viewData.data?.data?.items || []).map(j => ({ name: (j.title || j.job_id || 'Job').slice(0, 18), clicks: j.count || j.metric_value || 0 })));
        setSavedData((savedDataResp.data?.data?.items || []).map(j => ({ name: (j.title || j.job_id || 'Job').slice(0, 18), saved: j.count || j.metric_value || 0 })));
        const rjobs = jobsResp.data?.data?.items || [];
        setRecruiterJobs(rjobs);
        if (rjobs.length > 0) { setGeoJob(rjobs[0].job_id); setFunnelJob(rjobs[0].job_id); }
      } catch {}
      finally { setLoading(false); }
    };
    init();
  }, [user]);

  useEffect(() => {
    if (!geoJob) return;
    axios.post(`${BASE.analytics}/analytics/geo`, { job_id: geoJob, window_days: 30 }, authCfg)
      .then(({ data }) => {
        const geo = data.data?.geo_distribution || data.data?.items || [];
        setGeoData(geo.slice(0, 8).map(g => ({ name: g.key || [g.city, g.state].filter(Boolean).join(', ') || 'Unknown', count: g.count || g.application_count || 0 })));
      })
      .catch(() => setGeoData([]));
  }, [geoJob]);

  useEffect(() => {
    if (!funnelJob) return;
    axios.post(`${BASE.analytics}/analytics/funnel`, { job_id: funnelJob, window_days: 30 }, authCfg)
      .then(({ data }) => {
        const f = data.data?.funnel || {};
        setFunnelData([
          { stage: 'Views', count: f.viewed || 0 },
          { stage: 'Saves', count: f.saved || 0 },
          { stage: 'Started', count: f.apply_started || 0 },
          { stage: 'Applications', count: f.applications || f.submitted || 0 },
        ]);
      })
      .catch(() => setFunnelData(null));
  }, [funnelJob]);

  if (loading) return <LoadingCard text="Loading recruiter analytics…" />;

  return (
    <div>
      <PageHeader title="Recruiter Analytics" sub="Real-time insights powered by Kafka event pipeline" />
      <div style={S.grid2}>
        <div style={{ ...S.card, gridColumn: '1/-1' }}>
          <ChartHeader title="Top 10 Job Postings by Applications" sub="Live rollup from application.submitted events" />
          {topJobs.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topJobs} margin={{ bottom: 60, left: 0, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" interval={0} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={v => [v, 'Applications']} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>{topJobs.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="No application data yet — seed the stack and submit applications." />}
        </div>

        <div style={S.card}>
          <ChartHeader title="Top 5 Jobs with Fewest Applications" sub="Low-traction roles — consider boosting visibility" />
          {lowJobs.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={lowJobs} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={110} />
                <Tooltip formatter={v => [v, 'Applications']} />
                <Bar dataKey="count" fill="#cc1016" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="Not enough data yet." />}
        </div>

        <div style={S.card}>
          <ChartHeader title="Clicks per Job Posting" sub="Derived from job.viewed Kafka events" />
          {clickData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={clickData} margin={{ bottom: 50, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" interval={0} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => [v, 'Views']} />
                <Bar dataKey="clicks" fill="#0a66c2" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="No view data yet." />}
        </div>

        <div style={S.card}>
          <ChartHeader title="Saved Jobs" sub="Derived from job.saved Kafka events" />
          {savedData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={savedData} margin={{ left: 0, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => [v, 'Saves']} />
                <Line type="monotone" dataKey="saved" stroke="#057642" strokeWidth={2.5} dot={{ fill: '#057642', r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty text="No save data yet." />}
        </div>

        <div style={{ ...S.card, gridColumn: '1/-1' }}>
          <ChartHeader title="City-wise Applications" sub="Geographic distribution from application.submitted payloads" />
          <JobDropdown jobs={recruiterJobs} value={geoJob} onChange={setGeoJob} label="Select job" />
          {geoData.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 12 }}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={geoData} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={110} />
                  <Tooltip formatter={v => [v, 'Applications']} />
                  <Bar dataKey="count" fill="#7c3aed" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={geoData} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {geoData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : <Empty text="No geo data for this job yet." />}
        </div>

        <div style={{ ...S.card, gridColumn: '1/-1' }}>
          <ChartHeader title="Application Funnel" sub="View → Save → Apply start → Submit from real Kafka events" />
          <JobDropdown jobs={recruiterJobs} value={funnelJob} onChange={setFunnelJob} label="Select job" />
          {funnelData ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={funnelData} layout="vertical" margin={{ left: 20, right: 40, top: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="stage" type="category" tick={{ fontSize: 14 }} width={100} />
                <Tooltip />
                <Bar dataKey="count" fill="#0a66c2" radius={[0, 6, 6, 0]} label={{ position: 'right', fontSize: 13, fill: '#333' }} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty text="No funnel data for this job yet." />}
        </div>
      </div>
    </div>
  );
}

/* ─── Shared helpers ──────────────────────────────────────────────── */
function PageHeader({ title, sub }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>{title}</h1>
      <p style={{ color: 'rgba(0,0,0,0.55)', fontSize: 15 }}>{sub}</p>
    </div>
  );
}

function ChartHeader({ title, sub, extra }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: extra ? 4 : 14 }}>
      <div>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 2, color: 'rgba(0,0,0,0.9)' }}>{title}</h2>
        {sub && <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', fontStyle: 'italic', marginBottom: extra ? 10 : 0 }}>{sub}</p>}
      </div>
      {extra}
    </div>
  );
}

function JobDropdown({ jobs, value, onChange, label }) {
  if (!jobs.length) return null;
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{ padding: '7px 12px', border: '1.5px solid rgba(0,0,0,0.2)', borderRadius: 6, fontSize: 14, fontFamily: 'inherit', background: '#fff', marginBottom: 4, maxWidth: 380 }}
    >
      <option value="">{label}</option>
      {jobs.map((j) => (
        <option key={j.job_id} value={j.job_id}>{j.title} — {j.job_id}</option>
      ))}
    </select>
  );
}

function Empty({ text }) {
  return <p style={{ textAlign: 'center', color: 'rgba(0,0,0,0.4)', fontSize: 14, padding: '32px 0' }}>{text}</p>;
}

function LoadingCard({ text }) {
  return (
    <div className="li-card" style={{ padding: 60, textAlign: 'center', color: 'rgba(0,0,0,0.5)' }}>
      <div style={{ width: 32, height: 32, border: '3px solid #e5e7eb', borderTopColor: '#0a66c2', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 14px' }} />
      {text}
    </div>
  );
}

const S = {
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  card: { background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', padding: '18px 20px' },
};
