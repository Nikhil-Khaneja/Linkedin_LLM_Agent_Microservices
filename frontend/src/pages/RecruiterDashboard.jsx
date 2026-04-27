import React, { useEffect, useState } from 'react';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

export default function RecruiterDashboard() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title:'', description:'', employment_type:'full_time',
    work_mode:'onsite', city:'', state:'', seniority_level:'mid',
    salary_min:'', salary_max:'', skills_required:''
  });
  const [posting, setPosting] = useState(false);
  const [expandedJob, setExpandedJob] = useState(null);
  const [applicants, setApplicants] = useState([]);
  const [recruiterInfo, setRecruiterInfo] = useState(null);

  useEffect(() => { loadRecruiter(); }, []);

  const loadRecruiter = async () => {
    try {
      // Auto-create recruiter profile if needed
      const { data } = await axios.post(`${BASE.recruiter}/recruiters/get`, { recruiter_id: user?.userId });
      setRecruiterInfo(data.data);
      loadJobs(data.data.recruiter_id);
    } catch {
      // Create recruiter profile automatically
      try {
        const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
        await axios.post(`${BASE.recruiter}/recruiters/create`, {
          first_name: userData.email?.split('@')[0] || 'Recruiter',
          last_name: '',
          email: userData.email || user?.email || '',
        });
        loadRecruiter();
      } catch (e) {
        loadJobs(user?.userId);
      }
    }
  };

  const loadJobs = async (rid) => {
    try {
      const { data } = await axios.post(`${BASE.job}/jobs/byRecruiter`, { recruiter_id: rid || user?.userId });
      setJobs(data.data?.jobs || []);
    } catch {}
  };

  const postJob = async () => {
    if (!form.title || !form.description) {
      toast.error('Please fill in job title and description');
      return;
    }
    setPosting(true);
    try {
      const payload = {
        ...form,
        skills_required: form.skills_required.split(',').map(s => s.trim()).filter(Boolean),
        salary_min: form.salary_min ? parseInt(form.salary_min) : null,
        salary_max: form.salary_max ? parseInt(form.salary_max) : null,
        // Company ID will be auto-resolved from recruiter profile on the server
        company_id: recruiterInfo?.company_id || 'cmp_default',
      };
      await axios.post(`${BASE.job}/jobs/create`, payload);
      toast.success('✅ Job posted successfully!');
      setShowForm(false);
      setForm({ title:'', description:'', employment_type:'full_time', work_mode:'onsite', city:'', state:'', seniority_level:'mid', salary_min:'', salary_max:'', skills_required:'' });
      loadJobs(recruiterInfo?.recruiter_id || user?.userId);
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to post job');
    } finally { setPosting(false); }
  };

  const viewApplicants = async (job) => {
    if (expandedJob?.job_id === job.job_id) { setExpandedJob(null); setApplicants([]); return; }
    setExpandedJob(job);
    try {
      const { data } = await axios.post(`${BASE.application}/applications/byJob`, { job_id: job.job_id, page_size: 50 });
      setApplicants(data.data?.applications || []);
    } catch {}
  };

  const updateStatus = async (appId, status) => {
    try {
      await axios.post(`${BASE.application}/applications/updateStatus`, { application_id: appId, status });
      setApplicants(p => p.map(a => a.application_id === appId ? { ...a, status } : a));
      toast.success('Status updated');
    } catch {}
  };

  const closeJob = async (jobId) => {
    try {
      await axios.post(`${BASE.job}/jobs/close`, { job_id: jobId });
      toast.success('Job closed');
      loadJobs(recruiterInfo?.recruiter_id || user?.userId);
    } catch {}
  };

  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
        <div>
          <h1 style={{ fontSize:24, fontWeight:700, marginBottom:2 }}>Job Postings</h1>
          {recruiterInfo && (
            <p style={{ fontSize:14, color:'rgba(0,0,0,0.55)' }}>
              {recruiterInfo.company_name || 'Your Company'} · {jobs.length} active posting{jobs.length!==1?'s':''}
            </p>
          )}
        </div>
        <button onClick={() => setShowForm(!showForm)} style={S.postBtn}>
          {showForm ? '✕ Cancel' : '+ Post a job'}
        </button>
      </div>

      {/* Post job form */}
      {showForm && (
        <div style={{ ...S.card, padding:28, marginBottom:16 }}>
          <h2 style={{ fontSize:20, fontWeight:700, marginBottom:20 }}>Create a job posting</h2>
          <div style={S.formGrid}>
            <FField label="Job Title *" value={form.title} onChange={set('title')} placeholder="e.g. Senior Software Engineer" />
            <FField label="City" value={form.city} onChange={set('city')} placeholder="San Jose" />
            <FField label="State" value={form.state} onChange={set('state')} placeholder="CA" />
            <FSel label="Seniority Level" value={form.seniority_level} onChange={set('seniority_level')}
              options={['internship','entry','associate','mid','senior','director','executive']} />
            <FSel label="Work Mode" value={form.work_mode} onChange={set('work_mode')}
              options={['onsite','remote','hybrid']} />
            <FSel label="Employment Type" value={form.employment_type} onChange={set('employment_type')}
              options={['full_time','part_time','contract','internship']} />
            <FField label="Min Salary ($)" value={form.salary_min} onChange={set('salary_min')} placeholder="80000" />
            <FField label="Max Salary ($)" value={form.salary_max} onChange={set('salary_max')} placeholder="120000" />
            <div style={{ gridColumn:'1/-1' }}>
              <FField label="Required Skills (comma separated)" value={form.skills_required} onChange={set('skills_required')}
                placeholder="Python, React, SQL, Docker, AWS…" />
            </div>
            <div style={{ gridColumn:'1/-1' }}>
              <label style={S.lbl}>Job Description *</label>
              <textarea rows={6} style={{ ...S.inp, resize:'vertical' }} value={form.description}
                onChange={set('description')}
                placeholder="Describe the role, key responsibilities, requirements, and what makes this opportunity exciting…" />
            </div>
          </div>
          <div style={{ display:'flex', justifyContent:'flex-end', gap:12, marginTop:20, paddingTop:16, borderTop:'1px solid rgba(0,0,0,0.08)' }}>
            <button onClick={() => setShowForm(false)} style={S.cancelBtn}>Cancel</button>
            <button onClick={postJob} disabled={posting} style={S.submitBtn}>
              {posting ? 'Posting…' : 'Post job'}
            </button>
          </div>
        </div>
      )}

      {/* Job list */}
      {jobs.length === 0 ? (
        <div style={{ ...S.card, padding:60, textAlign:'center' }}>
          <div style={{ fontSize:48, marginBottom:12 }}>📋</div>
          <h3 style={{ fontSize:20, fontWeight:700, marginBottom:8 }}>No job postings yet</h3>
          <p style={{ color:'rgba(0,0,0,0.55)', fontSize:15, marginBottom:20 }}>
            Post your first job to start receiving applications from candidates.
          </p>
          <button onClick={() => setShowForm(true)} style={S.submitBtn}>Post a job</button>
        </div>
      ) : (
        jobs.map(job => (
          <div key={job.job_id} style={{ ...S.card, marginBottom:10, overflow:'hidden' }}>
            <div style={{ padding:'18px 20px', display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:16 }}>
              <div style={{ flex:1 }}>
                <h3 style={{ fontSize:18, fontWeight:700, marginBottom:4 }}>{job.title}</h3>
                <p style={{ fontSize:14, color:'rgba(0,0,0,0.6)', marginBottom:8 }}>
                  {job.company_name} · {[job.city, job.state].filter(Boolean).join(', ')} · {job.work_mode}
                </p>
                <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap' }}>
                  <span style={{ ...S.statusBadge, ...(job.status==='open'?S.open:S.closed) }}>
                    {job.status}
                  </span>
                  <span style={{ fontSize:14, color:'rgba(0,0,0,0.6)' }}>
                    👥 {job.applicants_count} applicant{job.applicants_count!==1?'s':''}
                  </span>
                  <span style={{ fontSize:13, color:'rgba(0,0,0,0.4)' }}>
                    {job.seniority_level} · {job.employment_type?.replace('_',' ')}
                  </span>
                </div>
              </div>
              <div style={{ display:'flex', gap:8, flexShrink:0 }}>
                <button onClick={() => viewApplicants(job)} style={S.viewBtn}>
                  {expandedJob?.job_id===job.job_id ? 'Hide applicants' : `View applicants (${job.applicants_count})`}
                </button>
                {job.status==='open' && (
                  <button onClick={() => closeJob(job.job_id)} style={S.closeJobBtn}>Close</button>
                )}
              </div>
            </div>

            {/* Applicants panel */}
            {expandedJob?.job_id === job.job_id && (
              <div style={{ borderTop:'1px solid rgba(0,0,0,0.08)', padding:'16px 20px', background:'#fafafa' }}>
                <h4 style={{ fontSize:16, fontWeight:700, marginBottom:14 }}>
                  Applicants — {applicants.length} total
                </h4>
                {applicants.length === 0 ? (
                  <p style={{ color:'rgba(0,0,0,0.45)', fontSize:14 }}>No applicants yet.</p>
                ) : applicants.map(app => (
                  <div key={app.application_id} style={S.appRow}>
                    <div style={S.appAvatar}>{(app.first_name||'?')[0]}</div>
                    <div style={{ flex:1 }}>
                      <p style={{ fontSize:15, fontWeight:700 }}>{app.first_name} {app.last_name}</p>
                      {app.headline && <p style={{ fontSize:13, color:'rgba(0,0,0,0.55)' }}>{app.headline}</p>}
                      <p style={{ fontSize:12, color:'rgba(0,0,0,0.4)' }}>
                        Applied {new Date(app.applied_at).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})}
                      </p>
                    </div>
                    <select value={app.status}
                      onChange={e => updateStatus(app.application_id, e.target.value)}
                      style={S.statusSel}>
                      {['submitted','reviewing','interview','offer','rejected'].map(s => (
                        <option key={s} value={s}>{s.charAt(0).toUpperCase()+s.slice(1)}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}

function FField({ label, value, onChange, placeholder='' }) {
  return (
    <div>
      <label style={{ display:'block', fontSize:14, fontWeight:600, color:'rgba(0,0,0,0.7)', marginBottom:5 }}>{label}</label>
      <input value={value} onChange={onChange} placeholder={placeholder}
        style={{ width:'100%', padding:'11px 14px', border:'1.5px solid rgba(0,0,0,0.25)', borderRadius:4, fontSize:15, fontFamily:'inherit', outline:'none', boxSizing:'border-box' }} />
    </div>
  );
}
function FSel({ label, value, onChange, options }) {
  return (
    <div>
      <label style={{ display:'block', fontSize:14, fontWeight:600, color:'rgba(0,0,0,0.7)', marginBottom:5 }}>{label}</label>
      <select value={value} onChange={onChange}
        style={{ width:'100%', padding:'11px 14px', border:'1.5px solid rgba(0,0,0,0.25)', borderRadius:4, fontSize:15, fontFamily:'inherit', outline:'none' }}>
        {options.map(o => <option key={o} value={o}>{o.replace('_',' ')}</option>)}
      </select>
    </div>
  );
}

const S = {
  card: { background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.1)' },
  postBtn: { padding:'10px 22px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:24, fontSize:15, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
  formGrid: { display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 },
  lbl: { display:'block', fontSize:14, fontWeight:600, color:'rgba(0,0,0,0.7)', marginBottom:5 },
  inp: { width:'100%', padding:'11px 14px', border:'1.5px solid rgba(0,0,0,0.25)', borderRadius:4, fontSize:15, fontFamily:'inherit', outline:'none', boxSizing:'border-box' },
  cancelBtn: { padding:'10px 20px', border:'1.5px solid rgba(0,0,0,0.35)', borderRadius:4, background:'#fff', fontSize:15, fontWeight:600, cursor:'pointer', fontFamily:'inherit' },
  submitBtn: { padding:'10px 28px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:4, fontSize:16, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
  statusBadge: { padding:'3px 12px', borderRadius:12, fontSize:12, fontWeight:700, textTransform:'uppercase' },
  open: { background:'#e8f5e9', color:'#057642' },
  closed: { background:'#fff0f0', color:'#cc1016' },
  viewBtn: { padding:'7px 16px', border:'1.5px solid #0a66c2', color:'#0a66c2', borderRadius:20, background:'#fff', fontSize:13, fontWeight:600, cursor:'pointer', fontFamily:'inherit', whiteSpace:'nowrap' },
  closeJobBtn: { padding:'7px 14px', border:'1.5px solid #cc1016', color:'#cc1016', borderRadius:20, background:'#fff', fontSize:13, fontWeight:600, cursor:'pointer', fontFamily:'inherit' },
  appRow: { display:'flex', gap:12, alignItems:'center', padding:'10px 0', borderBottom:'1px solid rgba(0,0,0,0.06)' },
  appAvatar: { width:42, height:42, borderRadius:'50%', background:'#0a66c2', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize:16, fontWeight:700, flexShrink:0 },
  statusSel: { padding:'7px 12px', border:'1.5px solid rgba(0,0,0,0.25)', borderRadius:4, fontSize:13, fontFamily:'inherit', cursor:'pointer', outline:'none' },
};
