import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

const STATUS_CONFIG = {
  submitted:  { color:'#0a66c2', bg:'#e8f0fe', label:'Applied',     pct:15 },
  reviewing:  { color:'#e68a00', bg:'#fef3d9', label:'In review',   pct:35 },
  interview:  { color:'#7c3aed', bg:'#f3e8ff', label:'Interview',   pct:65 },
  offer:      { color:'#057642', bg:'#e8f5e9', label:'Offer! 🎉',  pct:100 },
  rejected:   { color:'#cc1016', bg:'#fff0f0', label:'Not selected', pct:100 },
  withdrawn:  { color:'#666',    bg:'#f5f5f5', label:'Withdrawn',   pct:100 },
};

export default function ApplicationsPage() {
  const { user } = useAuth();
  const [apps, setApps] = useState([]);
  const [savedJobs, setSavedJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('applied');

  useEffect(() => {
    axios.post(`${BASE.application}/applications/byMember`, { member_id: user?.userId })
      .then(r => setApps(r.data.data?.applications || []))
      .catch(() => {})
      .finally(() => setLoading(false));

    // Load saved jobs
    axios.post(`${BASE.job}/jobs/saved`, {})
      .then(r => setSavedJobs(r.data.data?.jobs || []))
      .catch(() => {});
  }, []);

  const counts = apps.reduce((acc, a) => ({ ...acc, [a.status]: (acc[a.status]||0)+1 }), {});

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>My Jobs</h1>

      {/* Tabs */}
      <div style={{ display:'flex', gap:0, marginBottom:16, borderBottom:'2px solid #e0e0e0' }}>
        <button onClick={() => setActiveTab('applied')}
          style={{ padding:'10px 24px', border:'none', background:'none', cursor:'pointer', fontSize:15, fontWeight:600,
            color: activeTab==='applied' ? '#0a66c2' : 'rgba(0,0,0,0.6)',
            borderBottom: activeTab==='applied' ? '2px solid #0a66c2' : '2px solid transparent', marginBottom:-2 }}>
          Applied ({apps.length})
        </button>
        <button onClick={() => setActiveTab('saved')}
          style={{ padding:'10px 24px', border:'none', background:'none', cursor:'pointer', fontSize:15, fontWeight:600,
            color: activeTab==='saved' ? '#0a66c2' : 'rgba(0,0,0,0.6)',
            borderBottom: activeTab==='saved' ? '2px solid #0a66c2' : '2px solid transparent', marginBottom:-2 }}>
          Saved ({savedJobs.length})
        </button>
      </div>

      {/* Status summary */}
      {activeTab === "applied" && Object.keys(counts).length > 0 && (
        <div style={S.summaryRow}>
          {Object.entries(counts).map(([status, count]) => {
            const cfg = STATUS_CONFIG[status] || { color:'#666', bg:'#f5f5f5', label:status };
            return (
              <div key={status} style={{ ...S.summaryCard, background: cfg.bg, borderColor: cfg.color+'40' }}>
                <span style={{ fontSize: 24, fontWeight: 700, color: cfg.color }}>{count}</span>
                <span style={{ fontSize: 13, color: cfg.color, fontWeight: 600 }}>{cfg.label}</span>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'saved' ? (
        savedJobs.length === 0 ? (
          <div className="li-card" style={{ padding:60, textAlign:'center' }}>
            <p style={{ fontSize:20, fontWeight:600, marginBottom:8 }}>No saved jobs yet</p>
            <p style={{ color:'rgba(0,0,0,0.6)', marginBottom:20 }}>Save jobs to view them later.</p>
            <Link to="/jobs"><button className="li-btn-primary" style={{ borderRadius:4, padding:'10px 28px', fontSize:16 }}>Browse jobs</button></Link>
          </div>
        ) : (
          savedJobs.map(job => (
            <Link key={job.job_id} to={`/jobs/${job.job_id}`} style={{ textDecoration:'none' }}>
              <div className="li-card" style={{ padding:20, marginBottom:8, cursor:'pointer' }}>
                <div style={{ display:'flex', gap:14, alignItems:'flex-start' }}>
                  <div style={S.compLogo}>{(job.company_name||'C')[0]}</div>
                  <div style={{ flex:1 }}>
                    <h3 style={{ fontSize:18, fontWeight:600, color:'rgba(0,0,0,0.9)', marginBottom:2 }}>{job.title}</h3>
                    <p style={{ fontSize:15, color:'rgba(0,0,0,0.7)', marginBottom:4 }}>{job.company_name}</p>
                    <p style={{ fontSize:14, color:'rgba(0,0,0,0.5)' }}>{job.city}, {job.state} · {job.work_mode}</p>
                    {job.salary_min && <p style={{ fontSize:14, color:'rgba(0,0,0,0.6)', marginTop:4 }}>💰 ${Math.round(job.salary_min/1000)}k – ${Math.round((job.salary_max||job.salary_min*1.3)/1000)}k</p>}
                  </div>
                  <span style={{ background:'#e8f5e9', color:'#057642', border:'1px solid #05764240', padding:'4px 14px', borderRadius:12, fontSize:13, fontWeight:600, whiteSpace:'nowrap' }}>✓ Saved</span>
                </div>
              </div>
            </Link>
          ))
        )
      ) : loading ? (
        <div className="li-card" style={{ padding: 48, textAlign: 'center', color: 'rgba(0,0,0,0.5)' }}>Loading…</div>
      ) : apps.length === 0 ? (
        <div className="li-card" style={{ padding: 60, textAlign: 'center' }}>
          <p style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>Start your job search</p>
          <p style={{ color: 'rgba(0,0,0,0.6)', marginBottom: 20, fontSize: 16 }}>Applications you submit will appear here.</p>
          <Link to="/jobs"><button className="li-btn-primary" style={{ borderRadius:4, padding:'10px 28px', fontSize:16 }}>Find jobs</button></Link>
        </div>
      ) : (
        apps.map(app => {
          const cfg = STATUS_CONFIG[app.status] || { color:'#666', bg:'#f5f5f5', label:app.status, pct:10 };
          return (
            <div key={app.application_id} className="li-card" style={{ padding: 20, marginBottom: 8 }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:12 }}>
                <div style={{ display:'flex', gap:14, alignItems:'flex-start' }}>
                  <div style={S.compLogo}>{(app.company_name||app.title||'C')[0]}</div>
                  <div>
                    <h3 style={{ fontSize:18, fontWeight:600, color:'rgba(0,0,0,0.9)', marginBottom:2 }}>{app.title || 'Position'}</h3>
                    <p style={{ fontSize:15, color:'rgba(0,0,0,0.7)', marginBottom:4 }}>{app.company_name || ''}</p>
                    <p style={{ fontSize:14, color:'rgba(0,0,0,0.5)' }}>Applied {new Date(app.applied_at).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})}</p>
                  </div>
                </div>
                <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:8 }}>
                  <span style={{ background:cfg.bg, color:cfg.color, border:`1px solid ${cfg.color}40`, padding:'4px 14px', borderRadius:12, fontSize:13, fontWeight:600 }}>
                    {cfg.label}
                  </span>
                  {/* Progress bar */}
                  <div style={{ width:160 }}>
                    <div style={{ background:'rgba(0,0,0,0.08)', borderRadius:4, height:4, overflow:'hidden' }}>
                      <div style={{ height:'100%', background:cfg.color, width:`${cfg.pct}%`, borderRadius:4, transition:'width 0.6s' }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

const S = {
  summaryRow: { display:'flex', gap:10, flexWrap:'wrap', marginBottom:16 },
  summaryCard: { display:'flex', flexDirection:'column', gap:2, padding:'12px 20px', borderRadius:8, border:'1px solid', minWidth:100, alignItems:'center' },
  compLogo: { width:52, height:52, background:'#f3f2ef', border:'1px solid rgba(0,0,0,0.1)', borderRadius:4, display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, fontWeight:700, color:'#444', flexShrink:0 },
};
