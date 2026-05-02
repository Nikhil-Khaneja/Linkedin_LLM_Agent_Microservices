import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';

const STATUS_CONFIG = {
  submitted:  { color:'#0a66c2', bg:'#e8f0fe', label:'Applied', pct:15 },
  reviewing:  { color:'#e68a00', bg:'#fef3d9', label:'In review', pct:35 },
  interview:  { color:'#7c3aed', bg:'#f3e8ff', label:'Interview', pct:65 },
  accepted:   { color:'#057642', bg:'#e8f5e9', label:'Accepted', pct:100 },
  offer:      { color:'#057642', bg:'#e8f5e9', label:'Offer! 🎉', pct:100 },
  rejected:   { color:'#cc1016', bg:'#fff0f0', label:'Not selected', pct:100 },
  withdrawn:  { color:'#666', bg:'#f5f5f5', label:'Withdrawn', pct:100 },
};

export default function ApplicationsPage() {
  const { user } = useAuth();
  const [apps, setApps] = useState([]);
  const [savedJobs, setSavedJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('applications');

  const loadApps = () => {
    const token = localStorage.getItem('access_token');
    if (!token) return Promise.resolve();
    setLoading(true);
    return Promise.all([
      axios.post(`${BASE.application}/applications/byMember`, {}, { headers: { Authorization: 'Bearer ' + token } })
        .then(r => setApps((r.data.data?.items || []).map(app => ({ ...app, status: app.status || 'submitted' }))))
        .catch(() => setApps([])),
      axios.post(`${BASE.job}/jobs/savedByMember`, {}, { headers: { Authorization: 'Bearer ' + token } })
        .then(r => setSavedJobs(r.data.data?.items || []))
        .catch(() => setSavedJobs([])),
    ]).finally(() => setLoading(false));
  };

  useEffect(() => { loadApps(); }, [user?.principalId]);
  useEffect(() => {
    const handler = () => loadApps();
    window.addEventListener('applications:changed', handler);
    window.addEventListener('saved-jobs:changed', handler);
    window.addEventListener('focus', handler);
    return () => {
      window.removeEventListener('applications:changed', handler);
      window.removeEventListener('saved-jobs:changed', handler);
      window.removeEventListener('focus', handler);
    };
  }, [user?.principalId]);

  const counts = useMemo(() => apps.reduce((acc, a) => {
    const key = a.status || 'submitted';
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {}), [apps]);

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>My Jobs</h1>
      <div style={S.tabs}>
        <button onClick={() => setTab('applications')} style={{ ...S.tab, ...(tab === 'applications' ? S.activeTab : {}) }}>Applications ({apps.length})</button>
        <button onClick={() => setTab('saved')} style={{ ...S.tab, ...(tab === 'saved' ? S.activeTab : {}) }}>Saved jobs ({savedJobs.length})</button>
      </div>
      {tab === 'applications' && Object.keys(counts).length > 0 && (
        <div style={S.summaryRow}>
          {Object.entries(counts).map(([status, count]) => {
            const cfg = STATUS_CONFIG[status] || { color:'#666', bg:'#f5f5f5', label:status };
            return <div key={status} style={{ ...S.summaryCard, background: cfg.bg, borderColor: cfg.color+'40' }}><span style={{ fontSize: 24, fontWeight: 700, color: cfg.color }}>{count}</span><span style={{ fontSize: 13, color: cfg.color, fontWeight: 600 }}>{cfg.label}</span></div>;
          })}
        </div>
      )}
      {loading ? (
        <div className="li-card" style={{ padding: 48, textAlign: 'center', color: 'rgba(0,0,0,0.5)' }}>Loading…</div>
      ) : tab === 'applications' ? (
        apps.length === 0 ? (
          <div className="li-card" style={{ padding: 60, textAlign: 'center' }}>
            <p style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>Start your job search</p>
            <p style={{ color: 'rgba(0,0,0,0.6)', marginBottom: 20, fontSize: 16 }}>Applications you submit will appear here.</p>
            <Link to="/jobs"><button className="li-btn-primary" style={{ borderRadius:4, padding:'10px 28px', fontSize:16 }}>Find jobs</button></Link>
          </div>
        ) : (
          apps.map(app => {
            const cfg = STATUS_CONFIG[app.status] || { color:'#666', bg:'#f5f5f5', label:app.status, pct:10 };
            const title = app.title || app.job_title || app.job_id;
            return (
              <div key={app.application_id} className="li-card" style={{ padding: 20, marginBottom: 8 }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:12 }}>
                  <div style={{ display:'flex', gap:14, alignItems:'flex-start' }}>
                    <div style={S.compLogo}>{(title||'J')[0]}</div>
                    <div>
                      <h3 style={{ fontSize:18, fontWeight:600, color:'rgba(0,0,0,0.9)', marginBottom:2 }}>{title}</h3>
                      <p style={{ fontSize:14, color:'rgba(0,0,0,0.6)', marginBottom:2 }}>{app.company_name || 'Company'}</p>
                      <p style={{ fontSize:14, color:'rgba(0,0,0,0.5)' }}>Applied {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : 'recently'}</p>
                    </div>
                  </div>
                  <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:8 }}>
                    <span style={{ background:cfg.bg, color:cfg.color, border:`1px solid ${cfg.color}40`, padding:'4px 14px', borderRadius:12, fontSize:13, fontWeight:600 }}>{cfg.label}</span>
                    <div style={{ width:160 }}><div style={{ background:'rgba(0,0,0,0.08)', borderRadius:4, height:4, overflow:'hidden' }}><div style={{ height:'100%', background:cfg.color, width:`${cfg.pct}%`, borderRadius:4 }} /></div></div>
                  </div>
                </div>
              </div>
            );
          })
        )
      ) : (
        savedJobs.length === 0 ? (
          <div className="li-card" style={{ padding: 60, textAlign: 'center' }}>
            <p style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>No saved jobs yet</p>
            <p style={{ color: 'rgba(0,0,0,0.6)', marginBottom: 20, fontSize: 16 }}>Save jobs you want to revisit later.</p>
            <Link to="/jobs"><button className="li-btn-primary" style={{ borderRadius:4, padding:'10px 28px', fontSize:16 }}>Browse jobs</button></Link>
          </div>
        ) : (
          savedJobs.map(job => (
            <Link key={job.job_id} to={`/jobs/${job.job_id}`} state={{ job }} style={{ textDecoration:'none', color:'inherit' }}>
              <div className="li-card" style={{ padding: 20, marginBottom: 8 }}>
                <div style={{ display:'flex', justifyContent:'space-between', gap:12 }}>
                  <div style={{ display:'flex', gap:14 }}>
                    <div style={S.compLogo}>{(job.title || 'J')[0]}</div>
                    <div>
                      <h3 style={{ fontSize:18, fontWeight:600, color:'#0a66c2', marginBottom:2 }}>{job.title || job.job_id}</h3>
                      <p style={{ fontSize:14, color:'rgba(0,0,0,0.6)', marginBottom:2 }}>{job.company_name || 'Company'}</p>
                      <p style={{ fontSize:14, color:'rgba(0,0,0,0.5)' }}>{job.location || 'Remote'} · Saved {job.saved_at ? new Date(job.saved_at).toLocaleDateString() : 'recently'}</p>
                    </div>
                  </div>
                  <span style={{ fontSize:13, color:'#0a66c2', fontWeight:600, border:'1px solid #0a66c2', borderRadius:12, padding:'4px 14px', height:'fit-content' }}>Saved</span>
                </div>
              </div>
            </Link>
          ))
        )
      )}
    </div>
  );
}
const S = {
  tabs: { display:'flex', gap:8, marginBottom:16 },
  tab: { padding:'10px 18px', border:'1px solid rgba(0,0,0,0.15)', borderRadius:999, background:'#fff', cursor:'pointer', fontFamily:'inherit', fontWeight:600 },
  activeTab: { background:'#eef5fc', color:'#0a66c2', borderColor:'#0a66c2' },
  summaryRow: { display:'flex', gap:10, flexWrap:'wrap', marginBottom:16 },
  summaryCard: { display:'flex', flexDirection:'column', gap:2, padding:'12px 20px', borderRadius:8, border:'1px solid', minWidth:100, alignItems:'center' },
  compLogo: { width:52, height:52, background:'#f3f2ef', border:'1px solid rgba(0,0,0,0.1)', borderRadius:4, display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, fontWeight:700, color:'#444', flexShrink:0 }
};
