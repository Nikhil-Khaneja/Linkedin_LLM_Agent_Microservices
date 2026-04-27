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
  if (days < 30) return `${Math.floor(days/7)} week${days<14?'':'s'} ago`;
  return `${Math.floor(days/30)} month${days<60?'':'s'} ago`;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [appliedJobIds, setAppliedJobIds] = useState(new Set());

  React.useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    fetch(`${BASE.application}/applications/byMember`, {
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
  const [profile, setProfile] = useState(null);
  const initial = ((user?.email || 'U')[0]).toUpperCase();

  useEffect(() => {
    axios.post(`${BASE.job}/jobs/search`, { page_size: 8 })
      .then(r => setJobs(r.data.data?.jobs || [])).catch(() => {});
    axios.post(`${BASE.member}/members/get`, { member_id: user?.userId })
      .then(r => setProfile(r.data.data)).catch(() => {});
  }, []);

  return (
    <div style={S.layout}>
      {/* Left sidebar */}
      <aside style={S.aside}>
        <div style={S.card}>
          <div style={S.banner} />
          <div style={{ padding:'0 16px 16px', textAlign:'center', marginTop:-34 }}>
            <div style={S.bigAvatar}>{initial}</div>
            <h3 style={{ fontSize:16, fontWeight:700, marginTop:8, marginBottom:2 }}>
              {profile ? `${profile.first_name} ${profile.last_name}` : user?.email?.split('@')[0]}
            </h3>
            <p style={{ fontSize:12, color:'rgba(0,0,0,0.55)', marginBottom:12 }}>
              {profile?.headline || 'Add a headline'}
            </p>
            <Link to="/profile" style={S.viewProfile}>View full profile</Link>
          </div>
          <div style={S.statsBox}>
            {[['Profile viewers','--'],['Post impressions','--']].map(([k,v]) => (
              <div key={k} style={{ display:'flex', justifyContent:'space-between', padding:'7px 16px', borderBottom:'1px solid rgba(0,0,0,0.06)', fontSize:13 }}>
                <span style={{ color:'rgba(0,0,0,0.6)' }}>{k}</span>
                <span style={{ fontWeight:700, color:'#0a66c2' }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ ...S.card, padding:'4px 0' }}>
          {(user?.userType === 'recruiter'
            ? [['📝','Post a job','/recruiter'],['🤖','AI Copilot','/ai'],['📊','Analytics','/analytics'],['💬','Messages','/messages']]
            : [['💼','Jobs for you','/jobs'],['📋','My applications','/applications'],['💬','Messages','/messages'],['👤','Edit profile','/profile']]
          ).map(([i,l,t]) => (
            <Link key={t} to={t} style={S.sideLink}>
              <span style={{ fontSize:18, width:24, textAlign:'center' }}>{i}</span>
              <span style={{ fontSize:14, fontWeight:500 }}>{l}</span>
            </Link>
          ))}
        </div>
      </aside>

      {/* Main feed */}
      <main>
        {/* Post bar */}
        <div style={{ ...S.card, padding:'12px 16px 8px', marginBottom:10 }}>
          <div style={{ display:'flex', gap:10, alignItems:'center', marginBottom:10 }}>
            <div style={S.smallAvatar}>{initial}</div>
            <button onClick={() => navigate(user?.userType==='recruiter'?'/recruiter':'/jobs')} style={S.postBtn}>
              {user?.userType==='recruiter' ? 'Post a new job opportunity…' : 'Search for your next role…'}
            </button>
          </div>
          <div style={{ display:'flex', borderTop:'1px solid rgba(0,0,0,0.08)', paddingTop:4 }}>
            {(user?.userType==='recruiter'
              ? [['📝','Post Job','/recruiter'],['🤖','AI Copilot','/ai'],['📊','Analytics','/analytics']]
              : [['💼','Find Jobs','/jobs'],['👤','Profile','/profile'],['📋','Applied','/applications']]
            ).map(([ic,lb,to]) => (
              <Link key={to} to={to} style={S.postAction}>
                <span style={{ fontSize:18 }}>{ic}</span>
                <span style={{ fontSize:13, fontWeight:600, color:'rgba(0,0,0,0.6)' }}>{lb}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Job posts */}
        {jobs.length === 0 ? (
          <div style={{ ...S.card, padding:'40px 20px', textAlign:'center' }}>
            <div style={{ fontSize:48, marginBottom:12 }}>💼</div>
            <h3 style={{ fontSize:18, fontWeight:700, marginBottom:8 }}>No jobs posted yet</h3>
            <p style={{ color:'rgba(0,0,0,0.55)', marginBottom:20, fontSize:15 }}>
              {user?.userType==='recruiter'
                ? 'Post your first job posting to start finding candidates.'
                : 'Check back soon — jobs will appear here once posted.'}
            </p>
            <Link to={user?.userType==='recruiter'?'/recruiter':'/jobs'}>
              <button style={S.ctaBtn}>{user?.userType==='recruiter'?'Post a job':'Browse jobs'}</button>
            </Link>
          </div>
        ) : (
          <>
            {jobs.map(job => <JobCard key={job.job_id} job={job} navigate={navigate} isApplied={appliedJobIds.has(job.job_id)} />)}
            <div style={{ ...S.card, padding:14, textAlign:'center' }}>
              <Link to="/jobs" style={{ color:'#0a66c2', fontWeight:700, fontSize:15 }}>See all jobs →</Link>
            </div>
          </>
        )}
      </main>

      {/* Right sidebar */}
      <aside style={S.aside}>
        <div style={S.card}>
          <h3 style={{ fontSize:15, fontWeight:700, padding:'14px 16px 10px', borderBottom:'1px solid rgba(0,0,0,0.08)' }}>
            LinkedIn DS News
          </h3>
          {[
            ['🚀','8 microservices running on Docker'],
            ['🤖','AI Copilot with Hiring Assistant agent'],
            ['📊','Real-time analytics via Kafka'],
            ['⚡','Redis caching — sub-10ms reads'],
            ['🔐','RS256 JWT auth across all services'],
          ].map(([ic,txt]) => (
            <div key={txt} style={{ display:'flex', gap:10, padding:'10px 16px', borderBottom:'1px solid rgba(0,0,0,0.05)', alignItems:'flex-start' }}>
              <span style={{ flexShrink:0 }}>{ic}</span>
              <p style={{ fontSize:13, color:'rgba(0,0,0,0.75)', lineHeight:1.5 }}>{txt}</p>
            </div>
          ))}
        </div>
        <div style={{ ...S.card, background:'linear-gradient(135deg,#0a66c2,#004182)', color:'#fff', padding:16, marginTop:8 }}>
          <p style={{ fontSize:13, fontWeight:700, marginBottom:8 }}>🏗️ Architecture</p>
          <div style={{ display:'flex', flexWrap:'wrap', gap:4 }}>
            {['Auth','Member','Recruiter','Job','Application','Messaging','Analytics','AI FastAPI'].map(s=>(
              <span key={s} style={{ background:'rgba(255,255,255,0.18)', padding:'2px 8px', borderRadius:20, fontSize:11, fontWeight:600 }}>{s}</span>
            ))}
          </div>
          <p style={{ fontSize:11, opacity:0.75, marginTop:8 }}>MySQL · MongoDB · Redis · Kafka</p>
        </div>
      </aside>
    </div>
  );
}

function JobCard({ job, navigate, isApplied }) {
  return (
    <div style={S.jobCard} onClick={() => navigate(`/jobs/${job.job_id}`)}>
      <div style={{ display:'flex', gap:14 }}>
        <div style={S.logo}>{(job.company_name||'C')[0]}</div>
        <div style={{ flex:1 }}>
          <h3 style={{ fontSize:16, fontWeight:700, color:'#0a66c2', marginBottom:2 }}>{job.title}</h3>
          <p style={{ fontSize:14, color:'rgba(0,0,0,0.85)', marginBottom:2 }}>{job.company_name}</p>
          <p style={{ fontSize:13, color:'rgba(0,0,0,0.55)', marginBottom:8 }}>
            {[job.city&&`📍 ${job.city}${job.state?', '+job.state:''}`, job.work_mode].filter(Boolean).join(' · ')}
          </p>
          <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:8 }}>
            {job.employment_type && <Chip>{job.employment_type.replace('_',' ')}</Chip>}
            {job.work_mode && <Chip>{job.work_mode}</Chip>}
            {job.salary_min && <Chip>💰 ${Math.round(job.salary_min/1000)}k{job.salary_max?`–$${Math.round(job.salary_max/1000)}k`:'+' }</Chip>}
          </div>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span style={{ fontSize:12, color:'rgba(0,0,0,0.4)' }}>{job.applicants_count} applicants · {timeAgo(job.posted_at)}</span>
            <button onClick={e=>{e.stopPropagation();if(!isApplied)navigate(`/jobs/${job.job_id}`);}} style={{...S.applyBtn, background: isApplied ? '#057642' : '#0a66c2', color: '#fff', border: isApplied ? '1.5px solid #057642' : '1.5px solid #0a66c2', cursor: isApplied ? 'default' : 'pointer'}}>{isApplied ? '✓ Applied' : 'Apply'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Chip({ children }) {
  return <span style={{ background:'#f3f2ef', border:'1px solid rgba(0,0,0,0.12)', color:'rgba(0,0,0,0.6)', padding:'2px 10px', borderRadius:20, fontSize:12 }}>{children}</span>;
}

const S = {
  layout: { display:'grid', gridTemplateColumns:'220px 1fr 280px', gap:20, alignItems:'start' },
  aside: { position:'sticky', top:72, display:'flex', flexDirection:'column', gap:10 },
  card: { background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.1)', overflow:'hidden' },
  banner: { height:56, background:'linear-gradient(135deg,#0a66c2,#7c3aed)' },
  bigAvatar: { width:64, height:64, borderRadius:'50%', background:'#0a66c2', color:'#fff', fontSize:24, fontWeight:800, display:'flex', alignItems:'center', justifyContent:'center', border:'3px solid #fff', margin:'0 auto' },
  viewProfile: { display:'inline-block', padding:'6px 16px', border:'1.5px solid rgba(0,0,0,0.5)', borderRadius:24, fontSize:14, fontWeight:700, color:'rgba(0,0,0,0.8)', textDecoration:'none' },
  statsBox: { borderTop:'1px solid rgba(0,0,0,0.08)' },
  sideLink: { display:'flex', gap:12, alignItems:'center', padding:'10px 16px', textDecoration:'none', color:'rgba(0,0,0,0.8)', borderBottom:'1px solid rgba(0,0,0,0.06)' },
  smallAvatar: { width:44, height:44, borderRadius:'50%', background:'#0a66c2', color:'#fff', fontSize:17, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
  postBtn: { flex:1, padding:'11px 16px', border:'1.5px solid rgba(0,0,0,0.35)', borderRadius:35, fontSize:15, color:'rgba(0,0,0,0.5)', background:'#fff', cursor:'pointer', textAlign:'left', fontFamily:'inherit' },
  postAction: { flex:1, display:'flex', flexDirection:'column', alignItems:'center', gap:3, padding:'8px 4px', textDecoration:'none' },
  ctaBtn: { padding:'11px 28px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:28, fontSize:16, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
  jobCard: { background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.1)', padding:'16px 20px', cursor:'pointer', marginBottom:10 },
  logo: { width:52, height:52, background:'#f3f2ef', border:'1px solid rgba(0,0,0,0.1)', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, fontWeight:800, color:'#555', flexShrink:0 },
  applyBtn: { padding:'6px 18px', border:'1.5px solid #0a66c2', borderRadius:24, background:'#fff', color:'#0a66c2', fontSize:14, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
};
