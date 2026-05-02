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
  const [companyForm, setCompanyForm] = useState({ company_name:'', company_industry:'', company_size:'medium' });
  const [savingCompany, setSavingCompany] = useState(false);
  const [sentConnections, setSentConnections] = useState({});

  const recruiterId = user?.principalId || user?.userId;
  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  useEffect(() => { if (recruiterId && token) loadRecruiter(); }, [recruiterId, token]);

  const loadRecruiter = async () => {
    try {
      const { data } = await axios.post(`${BASE.recruiter}/recruiters/get`, {}, authCfg);
      const recruiter = data?.data?.recruiter || null;
      setRecruiterInfo(recruiter);
      setCompanyForm({
        company_name: recruiter?.company_name || '',
        company_industry: recruiter?.company_industry || '',
        company_size: recruiter?.company_size || 'medium',
      });
      loadJobs(recruiter?.recruiter_id || recruiterId);
      loadSentConnections(recruiter?.recruiter_id || recruiterId);
    } catch (e) {
      const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
      setRecruiterInfo({
        recruiter_id: recruiterId,
        name: userData.firstName ? `${userData.firstName} ${userData.lastName || ''}`.trim() : (userData.email?.split('@')[0] || 'Recruiter'),
        email: userData.email || user?.email || '',
      });
      setJobs([]);
      loadSentConnections(recruiterId);
      if (e?.response?.status && e.response.status !== 404) {
        toast.error(e.response?.data?.error?.message || 'Failed to load recruiter profile');
      }
    }
  };

  const saveCompany = async () => {
    if (!companyForm.company_name.trim()) {
      toast.error('Company name is required');
      return;
    }
    setSavingCompany(true);
    try {
      await axios.post(`${BASE.recruiter}/companies/create`, { recruiter_id: recruiterId, ...companyForm }, authCfg);
      const { data } = await axios.post(`${BASE.recruiter}/recruiters/get`, {}, authCfg);
      setRecruiterInfo(data?.data?.recruiter || null);
      toast.success('Company details saved');
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to save company');
    } finally {
      setSavingCompany(false);
    }
  };

  const loadSentConnections = async (rid) => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/connections/sent`, { user_id: rid || recruiterId }, authCfg);
      const items = data?.data?.items || [];
      setSentConnections(items.reduce((acc, item) => ({ ...acc, [item.receiver_id]: item.request_id }), {}));
    } catch {
      setSentConnections({});
    }
  };

  const loadJobs = async (rid) => {
    try {
      const { data } = await axios.post(`${BASE.job}/jobs/byRecruiter`, { recruiter_id: rid || recruiterId, page_size: 100 }, authCfg);
      setJobs(data?.data?.items || []);
    } catch (err) {
      setJobs([]);
      if (err?.response?.data?.error?.message) toast.error(err.response.data.error.message);
    }
  };

  const postJob = async () => {
    if (!recruiterInfo?.company_name) {
      toast.error('Create your company profile before posting jobs');
      return;
    }
    if (!form.title || !form.description) {
      toast.error('Please fill in job title and description');
      return;
    }
    setPosting(true);
    try {
      const payload = {
        ...form,
        recruiter_id: recruiterId,
        skills_required: form.skills_required.split(',').map(s => s.trim()).filter(Boolean),
        salary_min: form.salary_min ? parseInt(form.salary_min, 10) : null,
        salary_max: form.salary_max ? parseInt(form.salary_max, 10) : null,
      };
      await axios.post(`${BASE.job}/jobs/create`, payload, authCfg);
      toast.success('✅ Job posted successfully!');
      setShowForm(false);
      setForm({ title:'', description:'', employment_type:'full_time', work_mode:'onsite', city:'', state:'', seniority_level:'mid', salary_min:'', salary_max:'', skills_required:'' });
      loadJobs(recruiterId);
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to post job');
    } finally { setPosting(false); }
  };

  const viewApplicants = async (job) => {
    if (expandedJob?.job_id === job.job_id) { setExpandedJob(null); setApplicants([]); return; }
    setExpandedJob(job);
    try {
      const { data } = await axios.post(`${BASE.application}/applications/byJob`, { job_id: job.job_id, page_size: 50 }, authCfg);
      setApplicants(data.data?.items || []);
    } catch { setApplicants([]); }
  };

  const updateStatus = async (appId, status) => {
    try {
      await axios.post(`${BASE.application}/applications/updateStatus`, { application_id: appId, new_status: status }, authCfg);
      setApplicants(p => p.map(a => a.application_id === appId ? { ...a, status } : a));
      if (expandedJob) { await viewApplicants(expandedJob); }
      loadJobs(recruiterId);
      toast.success('Status updated');
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to update status');
    }
  };

  const closeJob = async (jobId) => {
    try {
      await axios.post(`${BASE.job}/jobs/close`, { job_id: jobId }, authCfg);
      toast.success('Job closed');
      loadJobs(recruiterId);
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to close job');
    }
  };

  const connectApplicant = async (memberId, firstName) => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/connections/request`, { requester_id: recruiterId, receiver_id: memberId, message: `Hi ${firstName || 'there'}, I would love to connect regarding an opportunity at ${recruiterInfo?.company_name || 'our company'}.` }, authCfg);
      setSentConnections((prev) => ({ ...prev, [memberId]: data?.data?.request_id || true }));
      toast.success('Connection request sent');
    } catch (err) {
      const msg = err.response?.data?.error?.message || 'Failed to send connection request';
      if (/already/i.test(msg)) {
        loadSentConnections(recruiterId);
      }
      toast.error(msg);
    }
  };

  const withdrawConnection = async (memberId) => {
    const requestId = sentConnections[memberId];
    if (!requestId) return;
    try {
      await axios.post(`${BASE.messaging}/connections/withdraw`, { request_id: requestId }, authCfg);
      setSentConnections((prev) => {
        const next = { ...prev };
        delete next[memberId];
        return next;
      });
      toast.success('Connection request withdrawn');
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to withdraw connection request');
    }
  };

  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));
  const setCompany = k => e => setCompanyForm(p => ({ ...p, [k]: e.target.value }));

  return (
    <div style={{ maxWidth: 980, margin: '0 auto' }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
        <div>
          <h1 style={{ fontSize:24, fontWeight:700, marginBottom:2 }}>Recruiter workspace</h1>
          {recruiterInfo && (
            <p style={{ fontSize:14, color:'rgba(0,0,0,0.55)' }}>
              {(recruiterInfo.company_name || 'Set up your company')} · {jobs.length} posting{jobs.length!==1?'s':''}
            </p>
          )}
        </div>
        <button onClick={() => setShowForm(!showForm)} style={S.postBtn}>
          {showForm ? '✕ Cancel' : '+ Post a job'}
        </button>
      </div>

      <div style={{ ...S.card, padding:24, marginBottom:16 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
          <div>
            <h2 style={{ fontSize:20, fontWeight:700, marginBottom:4 }}>Company profile</h2>
            <p style={{ fontSize:14, color:'rgba(0,0,0,0.55)' }}>Recruiter sign-up now captures company details. You can edit them here anytime.</p>
          </div>
        </div>
        <div style={S.formGrid}>
          <FField label="Company name *" value={companyForm.company_name} onChange={setCompany('company_name')} placeholder="Northstar Labs" />
          <FField label="Industry" value={companyForm.company_industry} onChange={setCompany('company_industry')} placeholder="Software" />
          <FSel label="Company size" value={companyForm.company_size} onChange={setCompany('company_size')} options={['startup','small','medium','large','enterprise']} />
        </div>
        <div style={{ display:'flex', justifyContent:'flex-end', marginTop:16 }}>
          <button onClick={saveCompany} disabled={savingCompany} style={S.submitBtn}>{savingCompany ? 'Saving…' : 'Save company profile'}</button>
        </div>
      </div>

      {showForm && (
        <div style={{ ...S.card, padding:28, marginBottom:16 }}>
          <h2 style={{ fontSize:20, fontWeight:700, marginBottom:20 }}>Create a job posting</h2>
          <div style={S.formGrid}>
            <FField label="Job Title *" value={form.title} onChange={set('title')} placeholder="e.g. Senior Software Engineer" />
            <FField label="City" value={form.city} onChange={set('city')} placeholder="San Jose" />
            <FField label="State" value={form.state} onChange={set('state')} placeholder="CA" />
            <FSel label="Seniority Level" value={form.seniority_level} onChange={set('seniority_level')} options={['internship','entry','associate','mid','senior','director','executive']} />
            <FSel label="Work Mode" value={form.work_mode} onChange={set('work_mode')} options={['onsite','remote','hybrid']} />
            <FSel label="Employment Type" value={form.employment_type} onChange={set('employment_type')} options={['full_time','part_time','contract','internship']} />
            <FField label="Min Salary ($)" value={form.salary_min} onChange={set('salary_min')} placeholder="80000" />
            <FField label="Max Salary ($)" value={form.salary_max} onChange={set('salary_max')} placeholder="120000" />
            <div style={{ gridColumn:'1/-1' }}>
              <FField label="Required Skills (comma separated)" value={form.skills_required} onChange={set('skills_required')} placeholder="Python, React, SQL, Docker, AWS…" />
            </div>
            <div style={{ gridColumn:'1/-1' }}>
              <label style={S.lbl}>Job Description *</label>
              <textarea rows={6} style={{ ...S.inp, resize:'vertical' }} value={form.description} onChange={set('description')} placeholder="Describe the role, key responsibilities, requirements, and what makes this opportunity exciting…" />
            </div>
          </div>
          <div style={{ display:'flex', justifyContent:'flex-end', gap:12, marginTop:20, paddingTop:16, borderTop:'1px solid rgba(0,0,0,0.08)' }}>
            <button onClick={() => setShowForm(false)} style={S.cancelBtn}>Cancel</button>
            <button onClick={postJob} disabled={posting} style={S.submitBtn}>{posting ? 'Posting…' : 'Post job'}</button>
          </div>
        </div>
      )}

      {jobs.length === 0 ? (
        <div style={{ ...S.card, padding:60, textAlign:'center' }}>
          <div style={{ fontSize:48, marginBottom:12 }}>📋</div>
          <h3 style={{ fontSize:20, fontWeight:700, marginBottom:8 }}>No job postings yet</h3>
          <p style={{ color:'rgba(0,0,0,0.55)', fontSize:15, marginBottom:20 }}>Post your first job to start receiving applications from candidates.</p>
          <button onClick={() => setShowForm(true)} style={S.submitBtn}>Post a job</button>
        </div>
      ) : (
        jobs.map(job => (
          <div key={job.job_id} style={{ ...S.card, marginBottom:10, overflow:'hidden' }}>
            <div style={{ padding:'18px 20px', display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:16 }}>
              <div style={{ flex:1 }}>
                <h3 style={{ fontSize:18, fontWeight:700, marginBottom:4 }}>{job.title}</h3>
                <p style={{ fontSize:14, color:'rgba(0,0,0,0.6)', marginBottom:8 }}>{job.company_name} · {[job.city, job.state].filter(Boolean).join(', ')} · {job.work_mode}</p>
                <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap' }}>
                  <span style={{ ...S.statusBadge, ...(job.status==='open'?S.open:S.closed) }}>{job.status}</span>
                  <span style={{ fontSize:14, color:'rgba(0,0,0,0.6)' }}>👥 {job.applicants_count || 0} applicant{(job.applicants_count || 0)!==1?'s':''}</span>
                  <span style={{ fontSize:13, color:'rgba(0,0,0,0.4)' }}>{job.seniority_level} · {job.employment_type?.replace('_',' ')}</span>
                </div>
              </div>
              <div style={{ display:'flex', gap:8, flexShrink:0 }}>
                <button onClick={() => viewApplicants(job)} style={S.viewBtn}>{expandedJob?.job_id===job.job_id ? 'Hide applicants' : `View applicants (${job.applicants_count || 0})`}</button>
                {job.status==='open' && <button onClick={() => closeJob(job.job_id)} style={S.closeJobBtn}>Close</button>}
              </div>
            </div>
            {expandedJob?.job_id === job.job_id && (
              <div style={{ borderTop:'1px solid rgba(0,0,0,0.08)', padding:'16px 20px', background:'#fafafa' }}>
                <h4 style={{ fontSize:16, fontWeight:700, marginBottom:14 }}>Applicants — {applicants.length} total</h4>
                {applicants.length === 0 ? (
                  <p style={{ color:'rgba(0,0,0,0.55)' }}>No applicants yet.</p>
                ) : applicants.map(app => (
                  <div key={app.application_id} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'12px 0', borderBottom:'1px solid rgba(0,0,0,0.06)', gap: 12 }}>
                    <div>
                      <p style={{ fontWeight:700 }}>{[app.first_name, app.last_name].filter(Boolean).join(' ') || app.member_id}</p>
                      <p style={{ color:'rgba(0,0,0,0.55)', fontSize:13 }}>{app.headline || app.member_id}</p>
                      <p style={{ color:'rgba(0,0,0,0.45)', fontSize:12 }}>{app.status}</p>
                    </div>
                    <div style={{ display:'flex', gap:8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      {app.resume_url && <a href={app.resume_url} target="_blank" rel="noreferrer"><button style={S.smallBtn}>Resume</button></a>}
                      {sentConnections[app.member_id] ? (
                        <button onClick={() => withdrawConnection(app.member_id)} style={S.smallBtnDanger}>Withdraw request</button>
                      ) : (
                        <button onClick={() => connectApplicant(app.member_id, app.first_name)} style={S.smallBtn}>Connect</button>
                      )}
                      <button onClick={() => updateStatus(app.application_id, 'reviewing')} style={S.smallBtn}>Reviewing</button>
                      <button onClick={() => updateStatus(app.application_id, 'interview')} style={S.smallBtn}>Interview</button>
                      <button onClick={() => updateStatus(app.application_id, 'rejected')} style={S.smallBtn}>Reject</button>
                      <button onClick={() => updateStatus(app.application_id, 'offer')} style={S.smallBtnPrimary}>Offer</button>
                    </div>
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

function FField({ label, ...props }) { return <div><label style={S.lbl}>{label}</label><input style={S.inp} {...props} /></div>; }
function FSel({ label, options, ...props }) { return <div><label style={S.lbl}>{label}</label><select style={S.inp} {...props}>{options.map(o => <option key={o} value={o}>{o.replace('_',' ')}</option>)}</select></div>; }

const S = {
  card: { background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.1)' },
  postBtn: { padding:'10px 18px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:999, fontWeight:700, cursor:'pointer' },
  formGrid: { display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 },
  lbl: { display:'block', fontSize:13, fontWeight:600, marginBottom:6, color:'rgba(0,0,0,0.7)' },
  inp: { width:'100%', padding:'10px 12px', border:'1px solid rgba(0,0,0,0.2)', borderRadius:4, fontFamily:'inherit' },
  cancelBtn: { padding:'10px 18px', background:'#fff', border:'1px solid rgba(0,0,0,0.2)', borderRadius:6, cursor:'pointer' },
  submitBtn: { padding:'10px 18px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:6, cursor:'pointer', fontWeight:700 },
  viewBtn: { padding:'8px 12px', background:'#fff', color:'#0a66c2', border:'1px solid #0a66c2', borderRadius:20, cursor:'pointer', fontWeight:700 },
  closeJobBtn: { padding:'8px 12px', background:'#fff', color:'#b42318', border:'1px solid #b42318', borderRadius:20, cursor:'pointer', fontWeight:700 },
  statusBadge: { padding:'4px 10px', borderRadius:999, fontSize:12, fontWeight:700, textTransform:'uppercase' },
  open: { background:'#e7f7ee', color:'#057642' },
  closed: { background:'#fef3f2', color:'#b42318' },
  smallBtn: { padding:'7px 10px', background:'#fff', color:'#0a66c2', border:'1px solid #0a66c2', borderRadius:18, cursor:'pointer', fontWeight:700 },
  smallBtnMuted: { padding:'7px 10px', background:'#e8f3ff', color:'#0a66c2', border:'1px solid #bcd8f5', borderRadius:18, cursor:'default', fontWeight:700 },
  smallBtnDanger: { padding:'7px 10px', background:'#fff', color:'#b42318', border:'1px solid #b42318', borderRadius:18, cursor:'pointer', fontWeight:700 },
  smallBtnPrimary: { padding:'7px 10px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:18, cursor:'pointer', fontWeight:700 },
};
