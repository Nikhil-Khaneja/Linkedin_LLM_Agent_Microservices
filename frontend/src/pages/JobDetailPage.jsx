import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

function newApplyKey(userId, jobId) {
  const rand = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${userId || 'anon'}:${jobId}:${rand}`;
}

export default function JobDetailPage() {
  const { jobId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [job, setJob] = useState(location.state?.job || null);
  const [loading, setLoading] = useState(!location.state?.job);
  const [loadError, setLoadError] = useState('');
  const [applying, setApplying] = useState(false);
  const [hasApplied, setHasApplied] = useState(false);
  const [isSaved, setIsSaved] = useState(Boolean(location.state?.job?.is_saved));
  const [saving, setSaving] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [coverLetter, setCoverLetter] = useState('');
  const [resumeText, setResumeText] = useState('');
  const [resumeFile, setResumeFile] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');
  const submitLockRef = useRef(false);
  const applyKeyRef = useRef(newApplyKey(user?.principalId || user?.userId, jobId));

  useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem('access_token');
    setLoading(true);
    setLoadError('');
    axios.post(`${BASE.job}/jobs/get`, { job_id: jobId }, token ? { headers: { Authorization: 'Bearer ' + token } } : undefined)
      .then(r => {
        if (cancelled) return;
        const loaded = r.data?.data?.job || null;
        setJob(loaded);
        setIsSaved(Boolean(loaded?.is_saved));
        if (!loaded) setLoadError('Job not found');
      })
      .catch((err) => {
        if (cancelled) return;
        const status = err?.response?.status;
        const msg = err?.response?.data?.error?.message;
        setLoadError(status === 401 ? 'Please sign in again to view this job.' : (msg || 'Job not found'));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId]);

  useEffect(() => {
    applyKeyRef.current = newApplyKey(user?.principalId || user?.userId, jobId);
  }, [jobId, user?.principalId, user?.userId]);

  useEffect(() => {
    const checkApplied = async () => {
      if (!user?.principalId) return;
      try {
        const res = await fetch(BASE.application + '/applications/byMember', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + localStorage.getItem('access_token')
          },
          body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.success) {
          setHasApplied((data.data?.items || []).some(a => a.job_id === jobId));
        }
      } catch {}
    };
    checkApplied();
  }, [jobId, user?.principalId]);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error('File must be under 5MB');
      return;
    }
    setResumeFile(file);
    if (file.type === 'text/plain') {
      const reader = new FileReader();
      reader.onload = (ev) => setResumeText(ev.target.result || '');
      reader.readAsText(file);
    }
    toast.success(`Resume selected: ${file.name}`);
  };

  const waitForUpload = async (uploadId) => {
    for (let i = 0; i < 30; i += 1) {
      const { data } = await axios.get(`${BASE.member}/members/upload-status/${uploadId}`, {
        headers: { Authorization: 'Bearer ' + localStorage.getItem('access_token') },
      });
      const item = data?.data || {};
      if (item.status === 'completed') return item;
      if (item.status === 'failed') throw new Error(item.error || 'Resume upload failed');
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error('Resume upload is still processing. Please retry in a moment.');
  };

  const markApplyStarted = async () => {
    try {
      await axios.post(`${BASE.application}/applications/start`, { job_id: jobId, session_id: applyKeyRef.current }, {
        headers: { Authorization: 'Bearer ' + localStorage.getItem('access_token') }
      });
    } catch {}
  };

  const toggleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const endpoint = isSaved ? '/jobs/unsave' : '/jobs/save';
      await axios.post(`${BASE.job}${endpoint}`, { job_id: jobId }, { headers: { Authorization: 'Bearer ' + localStorage.getItem('access_token') } });
      setIsSaved(!isSaved);
      setJob((prev) => prev ? { ...prev, is_saved: !isSaved } : prev);
      toast.success(isSaved ? 'Job removed from saved list.' : 'Job saved.');
      window.dispatchEvent(new CustomEvent('saved-jobs:changed', { detail: { jobId, isSaved: !isSaved } }));
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Unable to update saved job');
    } finally {
      setSaving(false);
    }
  };

  const apply = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    if (submitLockRef.current || applying) return;
    if (!resumeFile && !resumeText.trim()) {
      toast.error('Upload a resume or paste resume text before submitting.');
      return;
    }

    submitLockRef.current = true;
    setApplying(true);
    try {
      let resumeRef = resumeFile ? `uploaded:${resumeFile.name}` : (resumeText ? 'resume-text.txt' : '');
      let finalResumeText = resumeText || '';
      if (resumeFile && user?.principalId) {
        const fd = new FormData();
        fd.append('member_id', user.principalId);
        fd.append('media_type', 'resume');
        fd.append('file', resumeFile);
        const uploadRes = await axios.post(`${BASE.member}/members/upload-media`, fd, {
          headers: {
            Authorization: 'Bearer ' + localStorage.getItem('access_token'),
            'Content-Type': 'multipart/form-data',
          },
        });
        const uploadId = uploadRes.data?.data?.upload_id;
        const uploadItem = uploadId ? await waitForUpload(uploadId) : null;
        resumeRef = uploadItem?.file_url || uploadRes.data?.data?.file_url || resumeRef;
        if (!finalResumeText?.trim() && uploadItem?.extracted_text) {
          finalResumeText = uploadItem.extracted_text;
          setResumeText(uploadItem.extracted_text);
        }
      }
      await axios.post(`${BASE.application}/applications/submit`, {
        job_id: jobId,
        cover_letter: coverLetter,
        resume_ref: resumeRef,
        resume_text: finalResumeText || undefined,
        idempotency_key: applyKeyRef.current,
      });
      setHasApplied(true);
      setShowModal(false);
      window.dispatchEvent(new CustomEvent('applications:changed', { detail: { jobId } }));
      toast.success('Application submitted successfully!');
      applyKeyRef.current = newApplyKey(user?.principalId || user?.userId, jobId);
    } catch (err) {
      const code = err?.response?.data?.error?.code;
      const msg = err?.response?.data?.error?.message || 'Application failed';
      if (code === 'duplicate_application' || /already applied/i.test(msg)) {
        setHasApplied(true);
        setShowModal(false);
        window.dispatchEvent(new CustomEvent('applications:changed', { detail: { jobId } }));
        toast.success('Application already submitted for this job.');
      } else {
        toast.error(msg);
      }
    } finally {
      setApplying(false);
      submitLockRef.current = false;
    }
  };

  if (loading) return <div style={{ textAlign:'center', padding:60, color:'rgba(0,0,0,0.45)', fontSize:16 }}>Loading job details…</div>;
  if (!job) return <div style={{ textAlign:'center', padding:60, color:'rgba(0,0,0,0.6)', fontSize:16 }}><div style={{ marginBottom: 12 }}>{loadError || 'Job not found'}</div><button onClick={() => navigate('/jobs')} style={{ background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 20, padding: '10px 18px', cursor: 'pointer', fontWeight: 600 }}>Back to jobs</button></div>;

  return (
    <div style={S.layout}>
      <div>
        <div style={S.card}>
          <button onClick={() => navigate(-1)} style={S.back}>← Back to jobs</button>
          <div style={{ display:'flex', gap:16, alignItems:'flex-start', marginTop:14 }}>
            <div style={S.logo}>{(job.company_name||'C')[0]}</div>
            <div style={{ flex:1 }}>
              <h1 style={{ fontSize:22, fontWeight:700, marginBottom:4 }}>{job.title}</h1>
              <p style={{ fontSize:15, color:'rgba(0,0,0,0.85)', marginBottom:4 }}>{job.company_name}</p>
              <p style={{ fontSize:14, color:'rgba(0,0,0,0.55)', marginBottom:12 }}>{[job.location, job.work_mode, job.status].filter(Boolean).join(' · ')}</p>
              <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:14 }}>{(job.skills || []).map(sk => <Pill key={sk.skill_name || sk}>✓ {sk.skill_name || sk}</Pill>)}</div>
              <StatusBadge status={job.status} />
            </div>
          </div>
          <div style={{ padding:'16px 0 4px', borderTop:'1px solid rgba(0,0,0,0.08)', marginTop:14, display:'flex', gap:10 }}>
            {user?.userType === 'member' && (
              <>
                {job.status === 'open' && (
                  <button onClick={() => { if (!hasApplied) { markApplyStarted(); setShowModal(true); } }} style={{...S.applyBtn, background: hasApplied ? '#057642' : '#0a66c2', cursor: hasApplied ? 'default' : 'pointer'}}>{hasApplied ? '✓ Applied' : 'Apply'}</button>
                )}
                {job.status === 'open' && (
                  <button onClick={() => navigate(`/coach?job=${jobId}`)} style={{ ...S.applyBtn, background: '#fff', color: '#0a66c2', border: '1.5px solid #0a66c2', marginLeft: 8 }} title="Get AI tips to improve your match for this job">Optimize</button>
                )}
                <button onClick={toggleSave} disabled={saving} style={{...S.cancelBtn, borderRadius:24, color:isSaved ? '#0a66c2' : 'rgba(0,0,0,0.7)', borderColor:isSaved ? '#0a66c2' : 'rgba(0,0,0,0.35)'}}>{saving ? 'Saving…' : (isSaved ? 'Saved' : 'Save')}</button>
              </>
            )}
          </div>
        </div>

        <div style={{ ...S.card, marginTop:10, padding:24 }}>
          <h2 style={S.secTitle}>About the job</h2>
          <p style={{ fontSize:15, lineHeight:1.8, color:'rgba(0,0,0,0.85)', whiteSpace:'pre-wrap' }}>{job.description || job.description_text}</p>
        </div>
      </div>

      <aside style={{ position:'sticky', top:72 }}>
        <div style={S.card}>
          <h3 style={{ fontSize:18, fontWeight:700, marginBottom:16 }}>Job details</h3>
          <Detail icon="💼" label="Job type" value={job.employment_type?.replace('_',' ')} />
          <Detail icon="🏢" label="Work mode" value={job.work_mode} />
          <Detail icon="📊" label="Seniority level" value={job.seniority_level} />
          <Detail icon="📅" label="Posted" value={new Date(job.posted_at || job.created_at || Date.now()).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})} />
          {user?.userType === 'member' && job.status === 'open' && !hasApplied && <button onClick={() => { markApplyStarted(); setShowModal(true); }} style={{ ...S.applyBtn, width:'100%', marginTop:16, borderRadius:4 }}>Apply now</button>}
          {user?.userType === 'member' && job.status === 'open' && <button onClick={() => navigate(`/coach?job=${jobId}`)} style={{ ...S.applyBtn, background: '#fff', color: '#0a66c2', border: '1.5px solid #0a66c2', width:'100%', marginTop:8, borderRadius:4 }}>Optimize my profile for this job</button>}
        </div>
      </aside>

      {showModal && (
        <div style={S.overlay} onClick={() => setShowModal(false)}>
          <div style={S.modal} onClick={e => e.stopPropagation()}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
              <div><h2 style={{ fontSize:20, fontWeight:700, marginBottom:2 }}>Apply to {job.company_name}</h2><p style={{ fontSize:14, color:'rgba(0,0,0,0.55)' }}>{job.title}</p></div>
              <button onClick={() => setShowModal(false)} style={S.closeBtn}>✕</button>
            </div>
            <form onSubmit={apply}>
              <div style={{ marginBottom:20 }}>
                <p style={{ fontSize:15, fontWeight:700, marginBottom:10 }}>Resume</p>
                <div style={{ display:'flex', gap:0, marginBottom:14, borderBottom:'2px solid rgba(0,0,0,0.08)' }}>
                  {[['upload','📎 Upload file'],['paste','📝 Paste text']].map(([key,label]) => <button type="button" key={key} onClick={() => setActiveTab(key)} style={{ padding:'8px 16px', background:'none', border:'none', cursor:'pointer', fontSize:14, fontWeight:600, fontFamily:'inherit', color: activeTab===key ? '#0a66c2' : 'rgba(0,0,0,0.55)', borderBottom: activeTab===key ? '2px solid #0a66c2' : '2px solid transparent', marginBottom:-2 }}>{label}</button>)}
                </div>
                {activeTab === 'upload' ? (
                  <div><label style={S.fileLabel}><input type="file" accept=".pdf,.doc,.docx,.txt" onChange={handleFileChange} style={{ display:'none' }} />{resumeFile ? <div style={{ display:'flex', alignItems:'center', gap:10, padding:'12px 16px', background:'#f0f7ff', border:'2px solid #0a66c2', borderRadius:6 }}><span style={{ fontSize:24 }}>📄</span><div><p style={{ fontWeight:700, fontSize:14, color:'#0a66c2' }}>{resumeFile.name}</p><p style={{ fontSize:12, color:'rgba(0,0,0,0.45)' }}>{(resumeFile.size/1024).toFixed(0)} KB — Click to change</p></div></div> : <div style={{ border:'2px dashed rgba(0,0,0,0.2)', borderRadius:6, padding:'28px 20px', textAlign:'center', cursor:'pointer', background:'#fafafa' }}><div style={{ fontSize:36, marginBottom:8 }}>📎</div><p style={{ fontSize:15, fontWeight:600, color:'#0a66c2', marginBottom:4 }}>Upload your resume</p><p style={{ fontSize:13, color:'rgba(0,0,0,0.45)' }}>PDF, DOC, DOCX, TXT — max 5MB</p></div>}</label></div>
                ) : (
                  <textarea rows={5} value={resumeText} onChange={e => setResumeText(e.target.value)} placeholder="Paste your resume text here…" style={{ width:'100%', padding:'12px', border:'1.5px solid rgba(0,0,0,0.2)', borderRadius:6, fontSize:14, fontFamily:'inherit', resize:'vertical', outline:'none', boxSizing:'border-box' }} />
                )}
              </div>
              <div style={{ marginBottom:20 }}><p style={{ fontSize:15, fontWeight:700, marginBottom:8 }}>Cover letter <span style={{ fontWeight:400, color:'rgba(0,0,0,0.45)', fontSize:13 }}>(optional)</span></p><textarea rows={4} value={coverLetter} onChange={e => setCoverLetter(e.target.value)} placeholder="Tell the hiring manager why you're interested in this role…" style={{ width:'100%', padding:'12px', border:'1.5px solid rgba(0,0,0,0.2)', borderRadius:6, fontSize:14, fontFamily:'inherit', resize:'vertical', outline:'none', boxSizing:'border-box' }} /></div>
              <div style={{ display:'flex', justifyContent:'flex-end', gap:10 }}><button type="button" onClick={() => setShowModal(false)} style={S.cancelBtn}>Cancel</button><button type="submit" disabled={applying} style={{ ...S.applyBtn, borderRadius:4, padding:'11px 28px', fontSize:15, opacity:applying?0.7:1 }}>{applying ? 'Submitting…' : 'Submit application'}</button></div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ icon, label, value }) { if (!value) return null; return <div style={{ display:'flex', gap:10, padding:'8px 0', borderBottom:'1px solid rgba(0,0,0,0.06)', alignItems:'flex-start' }}><span style={{ fontSize:18, flexShrink:0 }}>{icon}</span><div><p style={{ fontSize:13, color:'rgba(0,0,0,0.5)' }}>{label}</p><p style={{ fontSize:15, fontWeight:600, color:'rgba(0,0,0,0.9)', textTransform:'capitalize' }}>{value}</p></div></div>; }
function Pill({ children }) { return <span style={{ background:'#f3f6fb', border:'1px solid #c8d8e8', color:'#0a66c2', padding:'3px 12px', borderRadius:12, fontSize:13 }}>{children}</span>; }
function StatusBadge({ status }) { const color = status==='open' ? '#057642' : '#cc1016'; return <span style={{ background:color+'18', color, border:`1px solid ${color}40`, padding:'3px 12px', borderRadius:12, fontSize:12, fontWeight:700, textTransform:'uppercase' }}>{status}</span>; }
const S = { layout:{ display:'grid', gridTemplateColumns:'1fr 300px', gap:16, alignItems:'start' }, card:{ background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.1)', padding:'20px 24px', overflow:'hidden' }, back:{ background:'none', border:'none', color:'#0a66c2', cursor:'pointer', fontSize:14, padding:0, fontFamily:'inherit', fontWeight:600 }, logo:{ width:72, height:72, background:'#f3f2ef', border:'1px solid rgba(0,0,0,0.1)', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center', fontSize:28, fontWeight:800, color:'#444', flexShrink:0 }, applyBtn:{ padding:'10px 24px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:24, fontSize:16, fontWeight:700, cursor:'pointer', fontFamily:'inherit' }, secTitle:{ fontSize:18, fontWeight:700, marginBottom:14, paddingBottom:10, borderBottom:'1px solid rgba(0,0,0,0.08)' }, overlay:{ position:'fixed', inset:0, background:'rgba(0,0,0,0.55)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000, padding:16 }, modal:{ background:'#fff', borderRadius:10, padding:'28px 28px 24px', width:'100%', maxWidth:560, boxShadow:'0 8px 40px rgba(0,0,0,0.3)', maxHeight:'90vh', overflowY:'auto' }, closeBtn:{ background:'none', border:'none', fontSize:22, cursor:'pointer', color:'rgba(0,0,0,0.5)', padding:4 }, cancelBtn:{ padding:'10px 20px', border:'1.5px solid rgba(0,0,0,0.35)', borderRadius:4, background:'#fff', fontSize:15, fontWeight:600, cursor:'pointer', fontFamily:'inherit' }, fileLabel:{ display:'block', cursor:'pointer' } };
