import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

export default function JobDetailPage() {
  const { jobId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [job, setJob]           = useState(null);
  const [applying, setApplying] = useState(false);
  const [hasApplied, setHasApplied] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

  // Check if already saved
  React.useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    const jobId = window.location.pathname.split('/').pop();
    fetch(`${BASE.job}/jobs/saved`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify({})
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        const already = (data.data.jobs || []).some(j => j.job_id === jobId);
        if (already) setIsSaved(true);
      }
    })
    .catch(() => {});
  }, []);

  const handleSave = async () => {
    const token = localStorage.getItem('access_token');
    const jobId = window.location.pathname.split('/').pop();
    const endpoint = isSaved ? 'unsave' : 'save';
    try {
      const r = await fetch(`${BASE.job}/jobs/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({ job_id: jobId })
      });
      const data = await r.json();
      if (data.success) {
        setIsSaved(!isSaved);
      }
    } catch(e) {}
  };
  const [applied, setApplied]   = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [coverLetter, setCoverLetter] = useState('');
  const [resumeText, setResumeText]   = useState('');
  const [resumeFile, setResumeFile]   = useState(null);
  const [activeTab, setActiveTab]     = useState('upload'); // 'upload' | 'paste'

  useEffect(() => {
    axios.post(`${BASE.job}/jobs/get`, { job_id: jobId })
      .then(r => setJob(r.data.data))
      .catch(() => toast.error('Job not found'));
  }, [jobId]);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error('File must be under 5MB'); return; }
    setResumeFile(file);
    // Also read as text if it's a text/plain file
    if (file.type === 'text/plain') {
      const reader = new FileReader();
      reader.onload = (ev) => setResumeText(ev.target.result);
      reader.readAsText(file);
    }
    toast.success(`Resume selected: ${file.name}`);
  };

  // Check if already applied when job loads
  React.useEffect(() => {
    const checkApplied = async () => {
      try {
        const res = await fetch(BASE.application + '/applications/byMember', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + localStorage.getItem('access_token') },
          body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.success) {
          const jobId = window.location.pathname.split('/').pop();
          const already = (data.data.applications || []).some(a => a.job_id === jobId);
          if (already) setHasApplied(true);
        }
      } catch(e) {}
    };
    checkApplied();
  }, []);

  const apply = async () => {
    setApplying(true);
    try {
      await axios.post(`${BASE.application}/applications/submit`, {
        job_id: jobId,
        cover_letter: coverLetter,
        resume_text: resumeText || (resumeFile ? `Resume file: ${resumeFile.name}` : ''),
        resume_url: resumeFile ? `uploaded:${resumeFile.name}` : '',
      });
      setApplied(true);
      setShowModal(false);
      toast.success('✅ Application submitted successfully!');
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Application failed');
    setHasApplied(true); } finally { setApplying(false); }
  };

  if (!job) return (
    <div style={{ textAlign:'center', padding:60, color:'rgba(0,0,0,0.45)', fontSize:16 }}>
      Loading job details…
    </div>
  );

  return (
    <div style={S.layout}>
      {/* Main */}
      <div>
        <div style={S.card}>
          <button onClick={() => navigate(-1)} style={S.back}>← Back to jobs</button>
          <div style={{ display:'flex', gap:16, alignItems:'flex-start', marginTop:14 }}>
            <div style={S.logo}>{(job.company_name||'C')[0]}</div>
            <div style={{ flex:1 }}>
              <h1 style={{ fontSize:22, fontWeight:700, marginBottom:4 }}>{job.title}</h1>
              <p style={{ fontSize:15, color:'rgba(0,0,0,0.85)', marginBottom:4 }}>{job.company_name}</p>
              <p style={{ fontSize:14, color:'rgba(0,0,0,0.55)', marginBottom:12 }}>
                {[job.city&&`${job.city}${job.state?', '+job.state:''}`, job.work_mode, `${job.applicants_count} applicants`].filter(Boolean).join(' · ')}
              </p>
              <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:14 }}>
                {job.skills?.map(sk => <Pill key={sk.skill_name}>✓ {sk.skill_name}</Pill>)}
              </div>
              <StatusBadge status={job.status} />
            </div>
          </div>

          {/* Apply + Save buttons */}
          <div style={{ padding:'16px 0 4px', borderTop:'1px solid rgba(0,0,0,0.08)', marginTop:14, display:'flex', gap:10 }}>
            {user?.userType === 'member' && job.status === 'open' && (
              applied ? (
                <div style={S.appliedBadge}>✅ Application sent</div>
              ) : (
                <button onClick={() => !hasApplied && setShowModal(true)} style={{...S.applyBtn, background: hasApplied ? '#057642' : '#0a66c2', cursor: hasApplied ? 'default' : 'pointer'}}>{hasApplied ? '✓ Applied' : 'Apply'}</button>
              )
            )}
            <button onClick={handleSave} style={{...S.saveBtn, color: isSaved ? '#057642' : 'rgba(0,0,0,0.7)', borderColor: isSaved ? '#057642' : 'rgba(0,0,0,0.4)', fontWeight: 700}}>
              {isSaved ? '✓ Saved' : '+ Save'}
            </button>
          </div>
        </div>

        {/* Description */}
        <div style={{ ...S.card, marginTop:10, padding:24 }}>
          <h2 style={S.secTitle}>About the job</h2>
          <p style={{ fontSize:15, lineHeight:1.8, color:'rgba(0,0,0,0.85)', whiteSpace:'pre-wrap' }}>
            {job.description}
          </p>
        </div>

        {job.skills?.length > 0 && (
          <div style={{ ...S.card, marginTop:10, padding:24 }}>
            <h2 style={S.secTitle}>Skills</h2>
            <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
              {job.skills.map(sk => (
                <span key={sk.skill_name} style={S.skillTag}>✓ {sk.skill_name}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Sidebar */}
      <aside style={{ position:'sticky', top:72 }}>
        <div style={S.card}>
          <h3 style={{ fontSize:18, fontWeight:700, marginBottom:16 }}>Job details</h3>
          <Detail icon="💼" label="Job type"       value={job.employment_type?.replace('_',' ')} />
          <Detail icon="🏢" label="Work mode"      value={job.work_mode} />
          <Detail icon="📊" label="Seniority level" value={job.seniority_level} />
          {job.salary_min && <Detail icon="💰" label="Base salary" value={`$${Math.round(job.salary_min/1000)}k – $${Math.round((job.salary_max||job.salary_min*1.3)/1000)}k`} />}
          <Detail icon="📅" label="Posted" value={new Date(job.posted_at).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})} />

          {user?.userType === 'member' && job.status === 'open' && !applied && (
            <button onClick={() => setShowModal(true)} style={{ ...S.applyBtn, width:'100%', marginTop:16, borderRadius:4 }}>
              Apply now
            </button>
          )}
        </div>

        {job.company_name && (
          <div style={{ ...S.card, padding:20, marginTop:10 }}>
            <h3 style={{ fontSize:17, fontWeight:700, marginBottom:10 }}>{job.company_name}</h3>
            {job.company_industry && <p style={{ fontSize:14, color:'rgba(0,0,0,0.6)', marginBottom:4 }}>🏭 {job.company_industry}</p>}
          </div>
        )}
      </aside>

      {/* ── Apply Modal ── */}
      {showModal && (
        <div style={S.overlay} onClick={() => setShowModal(false)}>
          <div style={S.modal} onClick={e => e.stopPropagation()}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
              <div>
                <h2 style={{ fontSize:20, fontWeight:700, marginBottom:2 }}>Apply to {job.company_name}</h2>
                <p style={{ fontSize:14, color:'rgba(0,0,0,0.55)' }}>{job.title}</p>
              </div>
              <button onClick={() => setShowModal(false)} style={S.closeBtn}>✕</button>
            </div>

            {/* Resume section */}
            <div style={{ marginBottom:20 }}>
              <p style={{ fontSize:15, fontWeight:700, marginBottom:10 }}>Resume</p>
              <div style={{ display:'flex', gap:0, marginBottom:14, borderBottom:'2px solid rgba(0,0,0,0.08)' }}>
                {[['upload','📎 Upload file'],['paste','📝 Paste text']].map(([key,label]) => (
                  <button key={key} onClick={() => setActiveTab(key)}
                    style={{ padding:'8px 16px', background:'none', border:'none', cursor:'pointer',
                      fontSize:14, fontWeight:600, fontFamily:'inherit',
                      color: activeTab===key ? '#0a66c2' : 'rgba(0,0,0,0.55)',
                      borderBottom: activeTab===key ? '2px solid #0a66c2' : '2px solid transparent',
                      marginBottom:-2 }}>
                    {label}
                  </button>
                ))}
              </div>

              {activeTab === 'upload' ? (
                <div>
                  <label style={S.fileLabel}>
                    <input type="file" accept=".pdf,.doc,.docx,.txt" onChange={handleFileChange}
                      style={{ display:'none' }} />
                    {resumeFile ? (
                      <div style={{ display:'flex', alignItems:'center', gap:10, padding:'12px 16px', background:'#f0f7ff', border:'2px solid #0a66c2', borderRadius:6 }}>
                        <span style={{ fontSize:24 }}>📄</span>
                        <div>
                          <p style={{ fontWeight:700, fontSize:14, color:'#0a66c2' }}>{resumeFile.name}</p>
                          <p style={{ fontSize:12, color:'rgba(0,0,0,0.45)' }}>{(resumeFile.size/1024).toFixed(0)} KB — Click to change</p>
                        </div>
                      </div>
                    ) : (
                      <div style={{ border:'2px dashed rgba(0,0,0,0.2)', borderRadius:6, padding:'28px 20px', textAlign:'center', cursor:'pointer', background:'#fafafa' }}>
                        <div style={{ fontSize:36, marginBottom:8 }}>📎</div>
                        <p style={{ fontSize:15, fontWeight:600, color:'#0a66c2', marginBottom:4 }}>Upload your resume</p>
                        <p style={{ fontSize:13, color:'rgba(0,0,0,0.45)' }}>PDF, DOC, DOCX, TXT — max 5MB</p>
                      </div>
                    )}
                  </label>
                </div>
              ) : (
                <textarea rows={5} value={resumeText} onChange={e => setResumeText(e.target.value)}
                  placeholder="Paste your resume text here…&#10;&#10;Include: skills, experience, education"
                  style={{ width:'100%', padding:'12px', border:'1.5px solid rgba(0,0,0,0.2)', borderRadius:6, fontSize:14, fontFamily:'inherit', resize:'vertical', outline:'none', boxSizing:'border-box' }} />
              )}
            </div>

            {/* Cover letter */}
            <div style={{ marginBottom:20 }}>
              <p style={{ fontSize:15, fontWeight:700, marginBottom:8 }}>Cover letter <span style={{ fontWeight:400, color:'rgba(0,0,0,0.45)', fontSize:13 }}>(optional)</span></p>
              <textarea rows={4} value={coverLetter} onChange={e => setCoverLetter(e.target.value)}
                placeholder="Tell the hiring manager why you're interested in this role and what makes you a great fit…"
                style={{ width:'100%', padding:'12px', border:'1.5px solid rgba(0,0,0,0.2)', borderRadius:6, fontSize:14, fontFamily:'inherit', resize:'vertical', outline:'none', boxSizing:'border-box' }} />
            </div>

            <div style={{ display:'flex', justifyContent:'flex-end', gap:10 }}>
              <button onClick={() => setShowModal(false)} style={S.cancelBtn}>Cancel</button>
              <button onClick={apply} disabled={applying} style={{ ...S.applyBtn, borderRadius:4, padding:'11px 28px', fontSize:15, opacity:applying?0.7:1 }}>
                {applying ? 'Submitting…' : 'Submit application'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ icon, label, value }) {
  if (!value) return null;
  return (
    <div style={{ display:'flex', gap:10, padding:'8px 0', borderBottom:'1px solid rgba(0,0,0,0.06)', alignItems:'flex-start' }}>
      <span style={{ fontSize:18, flexShrink:0 }}>{icon}</span>
      <div>
        <p style={{ fontSize:13, color:'rgba(0,0,0,0.5)' }}>{label}</p>
        <p style={{ fontSize:15, fontWeight:600, color:'rgba(0,0,0,0.9)', textTransform:'capitalize' }}>{value}</p>
      </div>
    </div>
  );
}
function Pill({ children }) {
  return <span style={{ background:'#f3f6fb', border:'1px solid #c8d8e8', color:'#0a66c2', padding:'3px 12px', borderRadius:12, fontSize:13 }}>{children}</span>;
}
function StatusBadge({ status }) {
  const color = status==='open' ? '#057642' : '#cc1016';
  return <span style={{ background:color+'18', color, border:`1px solid ${color}40`, padding:'3px 12px', borderRadius:12, fontSize:12, fontWeight:700, textTransform:'uppercase' }}>{status}</span>;
}

const S = {
  layout:     { display:'grid', gridTemplateColumns:'1fr 300px', gap:16, alignItems:'start' },
  card:       { background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.1)', padding:'20px 24px', overflow:'hidden' },
  back:       { background:'none', border:'none', color:'#0a66c2', cursor:'pointer', fontSize:14, padding:0, fontFamily:'inherit', fontWeight:600 },
  logo:       { width:72, height:72, background:'#f3f2ef', border:'1px solid rgba(0,0,0,0.1)', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center', fontSize:28, fontWeight:800, color:'#444', flexShrink:0 },
  applyBtn:   { padding:'10px 24px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:24, fontSize:16, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
  saveBtn:    { padding:'9px 20px', border:'1.5px solid rgba(0,0,0,0.4)', borderRadius:24, background:'#fff', fontSize:15, fontWeight:600, cursor:'pointer', fontFamily:'inherit', color:'rgba(0,0,0,0.7)' },
  appliedBadge: { display:'inline-flex', alignItems:'center', gap:6, padding:'10px 20px', background:'#e8f5e9', color:'#057642', borderRadius:6, fontSize:15, fontWeight:700 },
  secTitle:   { fontSize:18, fontWeight:700, marginBottom:14, paddingBottom:10, borderBottom:'1px solid rgba(0,0,0,0.08)' },
  skillTag:   { background:'#f0f7ff', border:'1px solid #0a66c2', color:'#0a66c2', padding:'5px 14px', borderRadius:20, fontSize:13, fontWeight:600 },
  overlay:    { position:'fixed', inset:0, background:'rgba(0,0,0,0.55)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000, padding:16 },
  modal:      { background:'#fff', borderRadius:10, padding:'28px 28px 24px', width:'100%', maxWidth:560, boxShadow:'0 8px 40px rgba(0,0,0,0.3)', maxHeight:'90vh', overflowY:'auto' },
  closeBtn:   { background:'none', border:'none', fontSize:22, cursor:'pointer', color:'rgba(0,0,0,0.5)', padding:4 },
  cancelBtn:  { padding:'10px 20px', border:'1.5px solid rgba(0,0,0,0.35)', borderRadius:4, background:'#fff', fontSize:15, fontWeight:600, cursor:'pointer', fontFamily:'inherit' },
  fileLabel:  { display:'block', cursor:'pointer' },
};
