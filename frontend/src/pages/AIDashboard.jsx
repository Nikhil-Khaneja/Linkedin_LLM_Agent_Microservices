import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import BASE from '../config/api';
import toast from 'react-hot-toast';

const STEPS = { queued:'Queued',starting:'Starting',fetching_job:'Fetching job',fetching_candidates:'Finding candidates',parsing_resumes:'Parsing resumes',matching_candidates:'Matching candidates',drafting_outreach:'Drafting outreach',waiting_approval:'Awaiting review',approved:'Approved',rejected:'Rejected',failed:'Error' };

export default function AIDashboard() {
  const [jobs, setJobs] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [selJob, setSelJob] = useState('');
  const [taskType, setTaskType] = useState('full_pipeline');
  const [resumeParseLimit, setResumeParseLimit] = useState(25);
  const [jobApplicantCount, setJobApplicantCount] = useState(null);
  const [jobApplicantCountLoading, setJobApplicantCountLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTask, setActiveTask] = useState(null);
  const [log, setLog] = useState([]);
  const wsRef = useRef(null);
  const aiAuthConfig = () => ({
    headers: { Authorization: 'Bearer ' + (localStorage.getItem('access_token') || '') }
  });

  useEffect(() => {
    // Load recruiter's jobs
    const token = localStorage.getItem('access_token');
    const headers = { Authorization: 'Bearer ' + token };
    axios.post(`${BASE.recruiter}/recruiters/get`, {}, { headers })
      .then(r => {
        const rid = r.data.data?.recruiter_id;
        if (rid) {
          return axios.post(`${BASE.job}/jobs/byRecruiter`, { recruiter_id: rid }, { headers });
        }
        // fallback - load all jobs
        return axios.post(`${BASE.job}/jobs/search`, { page_size: 50 }, { headers });
      })
      .then(r => setJobs(r.data.data?.jobs || []))
      .catch(() => {
        // final fallback
        const token2 = localStorage.getItem('access_token');
        axios.post(`${BASE.job}/jobs/search`, { page_size: 50 }, { headers: { Authorization: 'Bearer ' + token2 } })
          .then(r => setJobs(r.data.data?.jobs || [])).catch(() => {});
      });
  }, []);

  useEffect(() => {
    const loadApplicantCount = async () => {
      if (!selJob || taskType === 'resume_parse') {
        setJobApplicantCount(null);
        return;
      }
      setJobApplicantCountLoading(true);
      try {
        const token = localStorage.getItem('access_token');
        const { data } = await axios.post(
          `${BASE.application}/applications/byJob`,
          { job_id: selJob, page_size: 500 },
          { headers: { Authorization: 'Bearer ' + token } }
        );
        setJobApplicantCount((data?.data?.applications || []).length);
      } catch {
        setJobApplicantCount(null);
      } finally {
        setJobApplicantCountLoading(false);
      }
    };
    loadApplicantCount();
  }, [selJob, taskType]);

  const diagnosticsForTask = (task) => {
    if (!task?.output) return [];
    const diag = [];
    if (task.task_type === 'resume_parse') {
      const total = task.output.total_candidates ?? task.output.metrics?.total_candidates ?? 0;
      const parsed = task.output.parsed_with_text_count ?? task.output.metrics?.parsed_with_text_count ?? 0;
      if (total === 0) diag.push('NO_APPLICANTS_FOR_SELECTED_JOB');
      if (total > 0 && parsed === 0) diag.push('NO_RESUME_TEXT_FOUND_IN_APPLICATIONS');
      if (parsed > 0) diag.push('PARSE_SUCCESS');
      return diag;
    }
    const total = task.output.total_candidates;
    const shortlist = task.output.metrics?.shortlist_size;
    if (typeof total === 'number' && total === 0) diag.push('NO_APPLICANTS_FOR_SELECTED_JOB');
    if (typeof total === 'number' && total > 0 && typeof shortlist === 'number' && shortlist === 0) diag.push('NO_MATCHING_CANDIDATES_AFTER_SCORING');
    if (typeof shortlist === 'number' && shortlist > 0) diag.push('SHORTLIST_SUCCESS');
    return diag;
  };

  const launch = async () => {
    if (!selJob) return toast.error('Select a job first');
    setLoading(true);
    try {
      const payload = { job_id: selJob, task_type: taskType };
      if (taskType === 'resume_parse') {
        payload.parameters = { limit: resumeParseLimit };
      }
      const { data } = await axios.post(`${BASE.ai}/ai/tasks/create`, payload, aiAuthConfig());
      const tid = data.data.task_id;
      toast.success('AI task launched!');
      const newTask = { task_id:tid, status:'queued', current_step:'queued', job_id:selJob, task_type:taskType };
      setTasks(p => [newTask, ...p]);
      connectWS(tid);
    } catch (err) { toast.error(err.response?.data?.detail || 'Launch failed'); }
    finally { setLoading(false); }
  };

  const connectWS = (tid) => {
    if (wsRef.current) wsRef.current.close();
    const url = (BASE.ai||'http://localhost:8000').replace('http','ws');
    const token = localStorage.getItem('access_token') || '';
    const ws = new WebSocket(`${url}/ws/ai/tasks/${tid}?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;
    setLog([]);
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      setLog(p => [...p, { ...msg, ts: new Date().toLocaleTimeString() }]);
      if (msg.type === 'task_state') {
        setActiveTask(msg.data);
      } else {
        setActiveTask(prev => {
          if (!prev || prev.task_id !== tid) return prev;
          return {
            ...prev,
            current_step: msg.step || prev.current_step,
            status:
              msg.type === 'waiting_approval' ? 'waiting_approval'
              : msg.type === 'approved' ? 'approved'
              : msg.type === 'rejected' ? 'rejected'
              : msg.type === 'error' ? 'failed'
              : prev.status,
            output: msg.output || prev.output,
          };
        });
      }
      setTasks(p => p.map(t => t.task_id===tid ? {
        ...t,
        current_step: msg.step||t.current_step,
        status: msg.type==='waiting_approval'?'waiting_approval':msg.type==='approved'?'approved':msg.type==='rejected'?'rejected':msg.type==='error'?'failed':t.status,
      } : t));
      if (msg.type === 'waiting_approval' || msg.type === 'approved' || msg.type === 'rejected' || msg.type === 'error') {
        pollTask(tid);
      }
    };
    ws.onerror = () => {};
    pollTask(tid);
  };

  const pollTask = async (tid) => {
    try {
      const { data } = await axios.get(`${BASE.ai}/ai/tasks/${tid}`, aiAuthConfig());
      setActiveTask(data.data);
      setTasks(p => p.map(t => t.task_id===tid ? {...t,...data.data} : t));
    } catch {}
  };

  const approve = async (tid) => {
    try { await axios.post(`${BASE.ai}/ai/tasks/${tid}/approve`, { approved:true }, aiAuthConfig()); toast.success('Approved!'); pollTask(tid); } catch {}
  };
  const reject = async (tid) => {
    try { await axios.post(`${BASE.ai}/ai/tasks/${tid}/reject`, { reason:'Not suitable' }, aiAuthConfig()); toast.success('Rejected'); pollTask(tid); } catch {}
  };

  const statusColor = { queued:'#888', running:'#0a66c2', waiting_approval:'#e68a00', approved:'#057642', rejected:'#cc1016', failed:'#cc1016' };
  const isPipelineTask = (task) => ['full_pipeline', 'shortlist_and_outreach'].includes(task?.requested_task_type || task?.task_type);
  const isShortlistTask = (task) => (task?.task_type === 'shortlist');
  const taskLabel = (value) => {
    if (value === 'resume_parse') return 'Resume Parser Skill';
    if (value === 'shortlist') return 'Shortlist';
    if (value === 'full_pipeline' || value === 'shortlist_and_outreach') return 'Hiring Assistant Agent';
    return (value || '').replace(/_/g, ' ');
  };

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div>
          <h1 style={{ fontSize:24, fontWeight:600 }}>AI Hiring Copilot</h1>
          <p style={{ fontSize:15, color:'rgba(0,0,0,0.6)', marginTop:2 }}>Supervisor agent with Resume Parser · Job Matcher · Outreach Generator</p>
        </div>
        <div style={{ marginTop:12, fontSize:13, color:'rgba(0,0,0,0.65)' }}>
          {taskType === 'resume_parse' ? (
            <span>Diagnostic: parsing top <strong>{resumeParseLimit}</strong> applicants for selected job</span>
          ) : (
            <span>
              Diagnostic: applicants for selected job ={' '}
              <strong>{jobApplicantCountLoading ? 'checking...' : (jobApplicantCount ?? 'unknown')}</strong>
            </span>
          )}
        </div>
      </div>

      {/* Launch panel */}
      <div className="li-card" style={{ padding:24 }}>
        <h2 style={{ fontSize:18, fontWeight:600, marginBottom:16 }}>Launch AI task</h2>
        <div style={{ display:'flex', gap:12, flexWrap:'wrap', alignItems:'flex-end' }}>
          <div style={{ flex:2, minWidth:220 }}>
            <label style={S.lbl}>Select job posting</label>
            <select style={S.sel} value={selJob} onChange={e=>setSelJob(e.target.value)}>
              <option value="">— Choose a job —</option>
              {jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.title}</option>)}
            </select>
          </div>
          <div style={{ flex:1, minWidth:180 }}>
            <label style={S.lbl}>Task type</label>
            <select style={S.sel} value={taskType} onChange={e=>setTaskType(e.target.value)}>
              <option value="full_pipeline">Hiring Assistant Agent</option>
              <option value="shortlist">Shortlist</option>
              <option value="resume_parse">Resume Parser Skill</option>
            </select>
          </div>
          {taskType === 'resume_parse' && (
            <div style={{ minWidth:140 }}>
              <label style={S.lbl}>Top applicants</label>
              <select style={S.sel} value={resumeParseLimit} onChange={e => setResumeParseLimit(Number(e.target.value))}>
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          )}
          <button onClick={launch} disabled={loading||!selJob} className="li-btn-primary"
            style={{ borderRadius:4, padding:'11px 28px', fontSize:16, opacity: loading||!selJob?0.6:1 }}>
            {loading ? 'Launching…' : '🚀 Run AI'}
          </button>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
        {/* Task history */}
        <div className="li-card" style={{ padding:20 }}>
          <h3 style={{ fontSize:18, fontWeight:600, marginBottom:14 }}>Task history</h3>
          {tasks.length === 0
            ? <p style={{ color:'rgba(0,0,0,0.5)', fontSize:14 }}>No tasks yet — launch one above.</p>
            : tasks.map(t => (
              <div key={t.task_id} onClick={() => { setActiveTask(t); connectWS(t.task_id); }}
                style={S.taskRow}>
                <div style={{ flex:1 }}>
                  <p style={{ fontSize:15, fontWeight:600 }}>{taskLabel(t.requested_task_type || t.task_type)}</p>
                  <p style={{ fontSize:12, color:'rgba(0,0,0,0.5)', fontFamily:'monospace' }}>{t.task_id.slice(-12)}</p>
                  <p style={{ fontSize:13, color:'rgba(0,0,0,0.6)', marginTop:2 }}>{STEPS[t.current_step]||t.current_step}</p>
                </div>
                <span style={{ background:(statusColor[t.status]||'#888')+'18', color:statusColor[t.status]||'#888', border:`1px solid ${statusColor[t.status]||'#888'}40`, padding:'3px 12px', borderRadius:12, fontSize:12, fontWeight:600, whiteSpace:'nowrap' }}>
                  {t.status}
                </span>
              </div>
            ))
          }
        </div>

        {/* Live log */}
        <div className="li-card" style={{ padding:20 }}>
          <h3 style={{ fontSize:18, fontWeight:600, marginBottom:14 }}>Live progress</h3>
          <div style={{ maxHeight:240, overflowY:'auto', display:'flex', flexDirection:'column', gap:3 }}>
            {log.length === 0
              ? <p style={{ color:'rgba(0,0,0,0.4)', fontSize:13 }}>Waiting for events…</p>
              : log.map((l,i) => (
                <div key={i} style={{ display:'flex', gap:8, fontSize:12, padding:'3px 0', borderBottom:'1px solid rgba(0,0,0,0.04)' }}>
                  <span style={{ color:'rgba(0,0,0,0.4)', flexShrink:0 }}>{l.ts}</span>
                  <span style={{ color:'#0a66c2', fontWeight:600, flexShrink:0 }}>[{l.type}]</span>
                  {l.step && <span style={{ color:'#057642' }}>{STEPS[l.step]||l.step}</span>}
                  {l.message && <span style={{ color:'#cc1016' }}>{l.message}</span>}
                </div>
              ))
            }
          </div>
        </div>
      </div>

      {/* AI output */}
      {activeTask?.output && (
        <div className="li-card" style={{ padding:24 }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
            <div style={{ display:'flex', alignItems:'center', gap:10 }}>
              <h2 style={{ fontSize:20, fontWeight:600, margin:0 }}>AI output</h2>
              {activeTask?.task_type && (
                <span style={{ fontSize:12, fontWeight:700, letterSpacing:0.4, textTransform:'uppercase', color:'#0a66c2', border:'1px solid rgba(10,102,194,0.35)', background:'#eef5ff', borderRadius:999, padding:'4px 10px' }}>
                  {taskLabel(activeTask.requested_task_type || activeTask.task_type)}
                </span>
              )}
            </div>
            {activeTask.status === 'waiting_approval' && activeTask.task_type !== 'resume_parse' && (
              <div style={{ display:'flex', gap:10 }}>
                <button onClick={() => approve(activeTask.task_id)} className="li-btn-primary" style={{ borderRadius:4, padding:'8px 24px', fontSize:15, background:'#057642' }}>
                  ✅ Approve
                </button>
                <button onClick={() => reject(activeTask.task_id)} style={{ padding:'8px 24px', border:'1.5px solid #cc1016', color:'#cc1016', borderRadius:4, background:'#fff', fontSize:15, fontWeight:600, cursor:'pointer', fontFamily:'inherit' }}>
                  ❌ Reject
                </button>
              </div>
            )}
            {activeTask.status === 'approved' && <span style={{ color:'#057642', fontWeight:700, fontSize:16 }}>✅ Approved</span>}
          </div>
          {(isPipelineTask(activeTask) || isShortlistTask(activeTask)) && (
            <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:14 }}>
              <span style={S.capPill}>Candidate ranking</span>
              {isPipelineTask(activeTask)
                ? <span style={S.capPill}>Outreach drafts</span>
                : <span style={{ ...S.capPill, opacity: 0.55 }}>Outreach drafts (hidden for shortlist)</span>}
              <span style={S.capPill}>Human approval step</span>
            </div>
          )}

          {/* Metrics */}
          {activeTask.output.metrics && (
            <div style={{ display:'flex', gap:12, marginBottom:20, flexWrap:'wrap' }}>
              {Object.entries(activeTask.output.metrics).map(([k,v]) => (
                <div key={k} style={S.metric}>
                  <p style={{ fontSize:22, fontWeight:700, color:'#0a66c2' }}>{typeof v==='number'?v.toLocaleString():v}</p>
                  <p style={{ fontSize:12, color:'rgba(0,0,0,0.6)' }}>{k.replace(/_/g,' ')}</p>
                </div>
              ))}
            </div>
          )}

          {/* Resume parse output */}
          {activeTask.task_type === 'resume_parse' && (
            <div style={{ marginBottom:20 }}>
              {(activeTask.output.parsed_with_text_count ?? 0) === 0 ? (
                <div style={{ padding:'12px 14px', border:'1px solid rgba(230,138,0,0.35)', background:'#fff8ef', borderRadius:8 }}>
                  <p style={{ margin:0, fontSize:14, color:'#8a5a00', lineHeight:1.5 }}>
                    No parseable resume text was found in applications for this job. This can happen when resumes are not uploaded yet.
                  </p>
                </div>
              ) : (
                <div style={{ display:'grid', gridTemplateColumns:'repeat(3, minmax(160px, 1fr))', gap:12 }}>
                  <div style={S.metric}>
                    <p style={{ fontSize:22, fontWeight:700, color:'#0a66c2' }}>{activeTask.output.parsed_with_text_count ?? 0}</p>
                    <p style={{ fontSize:12, color:'rgba(0,0,0,0.6)' }}>parsed with text</p>
                  </div>
                  <div style={S.metric}>
                    <p style={{ fontSize:22, fontWeight:700, color:'#0a66c2' }}>{activeTask.output.total_candidates ?? 0}</p>
                    <p style={{ fontSize:12, color:'rgba(0,0,0,0.6)' }}>total applicants scanned</p>
                  </div>
                  <div style={S.metric}>
                    <p style={{ fontSize:22, fontWeight:700, color:'#0a66c2' }}>{activeTask.output.average_years_experience ?? 0}</p>
                    <p style={{ fontSize:12, color:'rgba(0,0,0,0.6)' }}>avg years experience</p>
                  </div>
                </div>
              )}
              {(activeTask.output.top_skills || []).length > 0 && (
                <div style={{ marginTop:12, display:'flex', gap:6, flexWrap:'wrap' }}>
                  {activeTask.output.top_skills.map(sk => <span key={sk} style={S.skillPill}>{sk}</span>)}
                </div>
              )}
            </div>
          )}

          {/* No data hint */}
          {activeTask.output.total_candidates === 0 && (
            <div style={{ marginBottom:20, padding:'12px 14px', border:'1px solid rgba(230,138,0,0.35)', background:'#fff8ef', borderRadius:8 }}>
              <p style={{ margin:0, fontSize:14, color:'#8a5a00', lineHeight:1.5 }}>
                No applicants found for this job yet, so the AI shortlist is empty. Try another job that has applications,
                or ask a member account to submit applications first.
              </p>
            </div>
          )}

          {/* Diagnostics */}
          <div style={{ marginBottom:20, padding:'10px 12px', border:'1px solid rgba(0,0,0,0.1)', borderRadius:8, background:'#fafafa' }}>
            <p style={{ margin:'0 0 6px 0', fontSize:13, fontWeight:600, color:'rgba(0,0,0,0.75)' }}>Diagnostics</p>
            <p style={{ margin:0, fontSize:13, color:'rgba(0,0,0,0.65)' }}>
              {(diagnosticsForTask(activeTask).length ? diagnosticsForTask(activeTask) : ['PENDING_RESULT']).join(' | ')}
            </p>
          </div>

          {/* Shortlist */}
          {activeTask.output.shortlist?.length > 0 && (
            <div style={{ marginBottom:20 }}>
              <h3 style={{ fontSize:17, fontWeight:600, marginBottom:12 }}>Shortlisted candidates</h3>
              {activeTask.output.shortlist.slice(0,5).map((c,i) => (
                <div key={i} style={S.candRow}>
                  <div style={S.candAvatar}>{i+1}</div>
                  <div style={{ flex:1 }}>
                    <p style={{ fontSize:15, fontWeight:600 }}>{c.first_name} {c.last_name}</p>
                    <div style={{ display:'flex', gap:4, flexWrap:'wrap', marginTop:3 }}>
                      {(c.skill_overlap||[]).slice(0,4).map(sk => <span key={sk} style={S.skillPill}>{sk}</span>)}
                    </div>
                  </div>
                  <div style={{ textAlign:'right' }}>
                    <p style={{ fontSize:20, fontWeight:700, color: c.match_score>70?'#057642':c.match_score>40?'#e68a00':'#cc1016' }}>{c.match_score}</p>
                    <p style={{ fontSize:11, color:'rgba(0,0,0,0.5)' }}>/ 100</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Outreach drafts */}
          {isPipelineTask(activeTask) && activeTask.output.outreach_drafts?.length > 0 && (
            <div>
              <h3 style={{ fontSize:17, fontWeight:600, marginBottom:12 }}>Outreach drafts <span style={{ fontSize:13, color:'rgba(0,0,0,0.5)', fontWeight:400 }}>(human review required before sending)</span></h3>
              {activeTask.output.outreach_drafts.map((d,i) => (
                <div key={i} style={{ background:'#f8f9fa', border:'1px solid rgba(0,0,0,0.1)', borderRadius:8, padding:16, marginBottom:10 }}>
                  <p style={{ fontSize:12, color:'rgba(0,0,0,0.5)', marginBottom:8 }}>For: {d.candidate_id}</p>
                  <pre style={{ fontSize:14, whiteSpace:'pre-wrap', fontFamily:'inherit', lineHeight:1.7, color:'rgba(0,0,0,0.85)' }}>{d.draft}</pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const S = {
  lbl: { display:'block', fontSize:14, fontWeight:600, color:'rgba(0,0,0,0.7)', marginBottom:6 },
  sel: { width:'100%', padding:'11px 14px', border:'1px solid rgba(0,0,0,0.3)', borderRadius:4, fontSize:15, fontFamily:'inherit', outline:'none' },
  txtarea: { width:'100%', padding:'11px 14px', border:'1px solid rgba(0,0,0,0.3)', borderRadius:4, fontSize:14, fontFamily:'inherit', outline:'none', resize:'vertical' },
  taskRow: { display:'flex', gap:12, padding:'12px 0', borderBottom:'1px solid rgba(0,0,0,0.06)', cursor:'pointer', alignItems:'center' },
  metric: { background:'#f3f6fb', borderRadius:8, padding:'12px 20px', textAlign:'center', minWidth:120, border:'1px solid rgba(0,0,0,0.08)' },
  candRow: { display:'flex', gap:14, alignItems:'center', padding:'12px 0', borderBottom:'1px solid rgba(0,0,0,0.06)' },
  candAvatar: { width:40, height:40, borderRadius:'50%', background:'#0a66c2', color:'#fff', fontSize:16, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
  skillPill: { background:'#e8f0fe', color:'#0a66c2', padding:'2px 10px', borderRadius:12, fontSize:12, fontWeight:500 },
  capPill: { background:'#f5f7fa', color:'rgba(0,0,0,0.72)', padding:'4px 10px', borderRadius:12, fontSize:12, fontWeight:600, border:'1px solid rgba(0,0,0,0.12)' },
};
