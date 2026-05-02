import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend
} from 'recharts';
import toast from 'react-hot-toast';

const COLORS = ['#0a66c2','#057642','#7c3aed','#e68a00','#cc1016','#06b6d4','#ec4899','#f59e0b'];

export default function AnalyticsPage() {
  const { user } = useAuth();
  const [topJobs, setTopJobs] = useState([]);
  const [lowJobs, setLowJobs] = useState([]);
  const [geoData, setGeoData] = useState([]);
  const [clickData, setClickData] = useState([]);
  const [savedData, setSavedData] = useState([]);
  const [profileViews, setProfileViews] = useState([]);
  const [appStatus, setAppStatus] = useState([]);
  const [funnelData, setFunnelData] = useState(null);
  const [funnelJob, setFunnelJob] = useState('');
  const [geoJob, setGeoJob] = useState('');
  const [memberId, setMemberId] = useState('');
  const [benchmarks, setBenchmarks] = useState([]);
  const [tab, setTab] = useState('recruiter');

  const authCfg = useMemo(() => ({ headers: { Authorization: 'Bearer ' + localStorage.getItem('access_token') } }), []);

  useEffect(() => {
    loadRecruiterDashboard();
    loadMemberDashboard();
    loadBenchmarks();
  }, []);

  const loadRecruiterDashboard = async () => {
    try {
      const [topData, lowData, viewData, savedDataResp] = await Promise.all([
        axios.post(`${BASE.analytics}/analytics/jobs/top`, { metric:'applications', window_days:30, limit:10 }, authCfg),
        axios.post(`${BASE.analytics}/analytics/jobs/top`, { metric:'applications', window_days:30, limit:50 }, authCfg),
        axios.post(`${BASE.analytics}/analytics/jobs/top`, { metric:'views', window_days:7, limit:8 }, authCfg),
        axios.post(`${BASE.analytics}/analytics/jobs/top`, { metric:'saves', window_days:7, limit:8 }, authCfg),
      ]);
      const jobs = topData.data?.data?.items || [];
      setTopJobs(jobs.map(j => ({ name: (j.title || j.job_id || 'Job').slice(0,20), count: j.count || j.metric_value || 0 })));
      const allJobs = lowData.data?.data?.items || [];
      const lowest = [...allJobs].sort((a,b) => ((a.count||a.metric_value||0)-(b.count||b.metric_value||0))).slice(0,5);
      setLowJobs(lowest.map(j => ({ name: (j.title || j.job_id || 'Job').slice(0,20), count: j.count || j.metric_value || 0 })));
      const viewJobs = viewData.data?.data?.items || [];
      setClickData(viewJobs.map(j => ({ name: (j.title || j.job_id || 'Job').slice(0,18), clicks: j.count || j.metric_value || 0 })));
      const savedJobs = savedDataResp.data?.data?.items || [];
      setSavedData(savedJobs.map(j => ({ name: (j.title || j.job_id || 'Job').slice(0,18), saved: j.count || j.metric_value || 0 })));
    } catch {
      setTopJobs([]); setLowJobs([]); setClickData([]); setSavedData([]);
    }
  };

  const loadMemberDashboard = async () => {
    try {
      const mid = user?.principalId || user?.userId;
      if (!mid) return;
      setMemberId(mid);
      const { data: dash } = await axios.post(`${BASE.analytics}/analytics/member/dashboard`, { member_id: mid }, authCfg);
      setProfileViews(dash.data?.profile_views || []);
      const breakdown = dash.data?.application_status_breakdown || {};
      setAppStatus(Object.entries(breakdown).map(([status, count]) => ({ status, count: Number(count || 0) })));
    } catch {
      setProfileViews([]);
      setAppStatus([]);
    }
  };

  const loadBenchmarks = async () => {
    try {
      const { data } = await axios.post(`${BASE.analytics}/benchmarks/list`, { limit: 20 }, authCfg);
      const items = (data?.data?.items || []).map((item) => ({
        name: item.variant || item.scenario || item.name || item.benchmark_id,
        latency: Number(item.latency_ms_avg || item.latency || 0),
        p95: Number(item.latency_ms_p95 || item.p95 || 0),
        throughput: Number(item.throughput || item.requests_per_second || 0),
        err: Number(item.error_rate_pct || item.err || 0),
        description: item.description || item.notes || '',
      }));
      setBenchmarks(items);
    } catch {
      setBenchmarks([]);
    }
  };

  const loadFunnel = async () => {
    if (!funnelJob.trim()) return toast.error('Enter a job ID');
    try {
      const { data } = await axios.post(`${BASE.analytics}/analytics/funnel`, { job_id: funnelJob, window_days:30 }, authCfg);
      const f = data.data?.funnel;
      setFunnelData([{ stage:'Views', count: f?.viewed || 0 }, { stage:'Saves', count: f?.saved || 0 }, { stage:'Started', count: f?.apply_started || 0 }, { stage:'Applications', count: f?.applications || f?.submitted || 0 }]);
    } catch {
      toast.error('Job not found or no data');
    }
  };

  const loadGeo = async () => {
    if (!geoJob.trim()) return toast.error('Enter a job ID');
    try {
      const { data } = await axios.post(`${BASE.analytics}/analytics/geo`, { job_id: geoJob, window_days:30 }, authCfg);
      const geo = data.data?.geo_distribution || data.data?.items || [];
      setGeoData(geo.slice(0,8).map(g => ({ name: g.key || [g.city, g.state].filter(Boolean).join(', ') || 'Unknown', count: g.count || g.application_count || 0 })));
    } catch {
      toast.error('No geo data found');
    }
  };

  return (
    <div style={{ maxWidth:1100, margin:'0 auto' }}>
      <h1 style={{ fontSize:24, fontWeight:700, marginBottom:4 }}>Analytics Dashboard</h1>
      <p style={{ color:'rgba(0,0,0,0.55)', marginBottom:20, fontSize:15 }}>
        Real-time insights powered by Kafka event pipeline
      </p>

      <div style={S.tabs}>
        {[['recruiter','📊 Recruiter Dashboard'],['member','👤 Member Dashboard'],['performance','⚡ Performance']].map(([key,label]) => (
          <button key={key} onClick={() => setTab(key)} style={{ ...S.tab, ...(tab===key ? S.tabActive : {}) }}>{label}</button>
        ))}
      </div>

      {tab === 'recruiter' && (
        <div style={S.grid2}>
          <div style={{ ...S.card, gridColumn:'1/-1' }}>
            <h2 style={S.ct}>Top 10 Job Postings by Applications</h2>
            <p style={S.cs}>Live rollup from application.submitted events.</p>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topJobs} margin={{ bottom:60, left:0, right:10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="name" tick={{ fontSize:11 }} angle={-25} textAnchor="end" interval={0} />
                <YAxis tick={{ fontSize:12 }} />
                <Tooltip formatter={v=>[v,'Applications']} />
                <Bar dataKey="count" radius={[4,4,0,0]}>{topJobs.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
            {topJobs.length === 0 && <p style={S.empty}>Waiting for live data… seed the stack and submit applications.</p>}
          </div>

          <div style={S.card}>
            <h2 style={S.ct}>Top 5 Jobs with Fewest Applications</h2>
            <p style={S.cs}>Low-traction roles from the same rollup.</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={lowJobs} layout="vertical" margin={{ left:10, right:30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis type="number" tick={{ fontSize:11 }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize:11 }} width={100} />
                <Tooltip formatter={v=>[v,'Applications']} />
                <Bar dataKey="count" fill="#cc1016" radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={S.card}>
            <h2 style={S.ct}>Clicks per Job Posting</h2>
            <p style={S.cs}>Derived from job.viewed events.</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={clickData} margin={{ bottom:50, left:0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="name" tick={{ fontSize:10 }} angle={-25} textAnchor="end" interval={0} />
                <YAxis tick={{ fontSize:11 }} />
                <Tooltip formatter={v=>[v,'Views']} />
                <Bar dataKey="clicks" fill="#0a66c2" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={S.card}>
            <h2 style={S.ct}>Saved Jobs</h2>
            <p style={S.cs}>Derived from job.saved events.</p>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={savedData} margin={{ left:0, right:10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="name" tick={{ fontSize:12 }} />
                <YAxis tick={{ fontSize:11 }} />
                <Tooltip formatter={v=>[v,'Saves']} />
                <Line type="monotone" dataKey="saved" stroke="#057642" strokeWidth={2.5} dot={{ fill:'#057642', r:4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={{ ...S.card, gridColumn:'1/-1' }}>
            <h2 style={S.ct}>City-wise Applications per Job</h2>
            <p style={S.cs}>Geographic distribution from application.submitted payloads.</p>
            <div style={{ display:'flex', gap:10, marginBottom:16 }}>
              <input value={geoJob} onChange={e => setGeoJob(e.target.value)} placeholder="Paste a job_id here…" style={S.searchInput} />
              <button onClick={loadGeo} style={S.searchBtn}>Load map</button>
            </div>
            {geoData.length > 0 ? (
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20 }}>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={geoData} layout="vertical" margin={{ left:10, right:20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                    <XAxis type="number" tick={{ fontSize:11 }} />
                    <YAxis dataKey="name" type="category" tick={{ fontSize:11 }} width={110} />
                    <Tooltip formatter={v=>[v,'Applications']} />
                    <Bar dataKey="count" fill="#7c3aed" radius={[0,4,4,0]} />
                  </BarChart>
                </ResponsiveContainer>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={geoData} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}>
                      {geoData.map((_, i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : <p style={S.empty}>Enter a job_id above and click Load map.</p>}
          </div>

          <div style={{ ...S.card, gridColumn:'1/-1' }}>
            <h2 style={S.ct}>Application Funnel</h2>
            <p style={S.cs}>View → Save → Apply start → Submit, all from real Kafka events.</p>
            <div style={{ display:'flex', gap:10, marginBottom:16 }}>
              <input value={funnelJob} onChange={e => setFunnelJob(e.target.value)} placeholder="Paste a job_id here…" style={S.searchInput} />
              <button onClick={loadFunnel} style={S.searchBtn}>Load funnel</button>
            </div>
            {funnelData ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={funnelData} layout="vertical" margin={{ left:20, right:40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                  <XAxis type="number" tick={{ fontSize:12 }} />
                  <YAxis dataKey="stage" type="category" tick={{ fontSize:14 }} width={100} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#0a66c2" radius={[0,6,6,0]} label={{ position:'right', fontSize:13, fill:'#333' }} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p style={S.empty}>Enter a job_id to see the conversion funnel.</p>}
          </div>
        </div>
      )}

      {tab === 'member' && (
        <div style={S.grid2}>
          <div style={{ ...S.card, gridColumn:'1/-1' }}>
            <h2 style={S.ct}>Profile Views — Last 30 Days</h2>
            <p style={S.cs}>Visible only to {memberId || 'the signed-in member'}.</p>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={profileViews} margin={{ left:0, right:20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="view_date" tick={{ fontSize:10 }} interval={4} />
                <YAxis tick={{ fontSize:11 }} />
                <Tooltip formatter={v=>[v,'Profile Views']} />
                <Line type="monotone" dataKey="view_count" stroke="#0a66c2" strokeWidth={2.5} dot={{ fill:'#0a66c2', r:3 }} activeDot={{ r:6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={S.card}>
            <h2 style={S.ct}>My Applications — Status Breakdown</h2>
            <p style={S.cs}>Live from application.status.updated events.</p>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={appStatus} dataKey="count" nameKey="status" cx="50%" cy="50%" outerRadius={90} label={({status,count})=>`${status}: ${count}`}>
                  {appStatus.map((_, i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div style={S.card}>
            <h2 style={S.ct}>Application Status Distribution</h2>
            <p style={S.cs}>Same status data rendered as bars for easier comparison.</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={appStatus} margin={{ bottom:20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="status" tick={{ fontSize:12 }} />
                <YAxis tick={{ fontSize:11 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[4,4,0,0]}>{appStatus.map((_, i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {tab === 'performance' && (
        <div>
          <div style={{ ...S.card, marginBottom:16, padding:'16px 20px' }}>
            <h2 style={S.ct}>Performance Benchmarks</h2>
            <p style={S.cs}>These charts render only stored benchmark runs from the analytics service. No hardcoded values.</p>
          </div>
          {benchmarks.length === 0 ? (
            <div style={S.card}>
              <p style={{ fontSize:15, color:'rgba(0,0,0,0.65)', marginBottom:8 }}>No benchmark runs recorded yet.</p>
              <p style={{ fontSize:14, color:'rgba(0,0,0,0.5)' }}>Run <code>scripts/run_performance_benchmarks.py</code> against your stack to populate these charts.</p>
            </div>
          ) : (
            <>
              <div style={S.grid2}>
                {[
                  { key:'latency', label:'Average Latency (ms)', color:'#cc1016' },
                  { key:'throughput', label:'Throughput (req/s)', color:'#057642' },
                  { key:'p95', label:'p95 Latency (ms)', color:'#7c3aed' },
                  { key:'err', label:'Error Rate (%)', color:'#e68a00' },
                ].map(({ key, label, color }) => (
                  <div key={key} style={S.card}>
                    <h3 style={{ fontSize:16, fontWeight:700, marginBottom:8 }}>{label}</h3>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={benchmarks} margin={{ bottom:20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                        <XAxis dataKey="name" tick={{ fontSize:11 }} />
                        <YAxis tick={{ fontSize:11 }} />
                        <Tooltip />
                        <Bar dataKey={key} fill={color} radius={[4,4,0,0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ))}
              </div>
              <div style={{ ...S.card, marginTop:16, padding:'0 0 8px' }}>
                <h3 style={{ fontSize:16, fontWeight:700, padding:'16px 20px 10px' }}>Benchmark Summary</h3>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:14 }}>
                  <thead>
                    <tr style={{ background:'#0a66c2', color:'#fff' }}>
                      {['Variant','Description','Avg Latency','p95 Latency','Throughput','Error Rate'].map(h => <th key={h} style={{ padding:'10px 16px', textAlign:'left', fontWeight:700 }}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {benchmarks.map((row, i) => (
                      <tr key={`${row.name}-${i}`} style={{ background: i%2===0 ? '#f3f6fb' : '#fff' }}>
                        <td style={{ padding:'10px 16px', fontWeight:700, color:'#0a66c2' }}>{row.name}</td>
                        <td style={{ padding:'10px 16px' }}>{row.description || 'Measured run'}</td>
                        <td style={{ padding:'10px 16px' }}>{row.latency}</td>
                        <td style={{ padding:'10px 16px' }}>{row.p95}</td>
                        <td style={{ padding:'10px 16px' }}>{row.throughput}</td>
                        <td style={{ padding:'10px 16px' }}>{row.err}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

const S = {
  tabs: { display:'flex', gap:0, marginBottom:20, borderBottom:'2px solid rgba(0,0,0,0.1)' },
  tab: { padding:'10px 24px', background:'transparent', border:'none', fontSize:15, fontWeight:600, cursor:'pointer', color:'rgba(0,0,0,0.55)', fontFamily:'inherit', borderBottom:'2px solid transparent', marginBottom:-2 },
  tabActive: { color:'#0a66c2', borderBottomColor:'#0a66c2' },
  grid2: { display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 },
  card: { background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.1)', padding:'18px 20px' },
  ct: { fontSize:16, fontWeight:700, marginBottom:2, color:'rgba(0,0,0,0.9)' },
  cs: { fontSize:12, color:'rgba(0,0,0,0.45)', marginBottom:14, fontStyle:'italic' },
  empty: { textAlign:'center', color:'rgba(0,0,0,0.4)', fontSize:14, padding:'32px 0' },
  searchInput: { flex:1, padding:'10px 14px', border:'1.5px solid rgba(0,0,0,0.25)', borderRadius:4, fontSize:14, fontFamily:'inherit', outline:'none' },
  searchBtn: { padding:'10px 22px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:4, fontSize:14, fontWeight:700, cursor:'pointer', fontFamily:'inherit', whiteSpace:'nowrap' },
};
