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
  const [loading, setLoading] = useState(false);
  const [activeTask, setActiveTask] = useState(null);
  const [log, setLog] = useState([]);
  const wsRef = useRef(null);

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

  const launch = async () => {
    if (!selJob) return toast.error('Select a job first');
    setLoading(true);
    try {
      const { data } = await axios.post(`${BASE.ai}/ai/tasks/create`, { job_id: selJob, task_type: taskType });
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
    const ws = new WebSocket(`${url}/ws/ai/tasks/${tid}`);
    wsRef.current = ws;
    setLog([]);
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      setLog(p => [...p, { ...msg, ts: new Date().toLocaleTimeString() }]);
      if (msg.type === 'task_state') setActiveTask(msg.data);
      setTasks(p => p.map(t => t.task_id===tid ? { ...t, current_step: msg.step||t.current_step, status: msg.type==='waiting_approval'?'waiting_approval':msg.type==='approved'?'approved':msg.type==='rejected'?'rejected':t.status } : t));
    };
    ws.onerror = () => {};
    pollTask(tid);
  };

  const pollTask = async (tid) => {
    try {
      const { data } = await axios.get(`${BASE.ai}/ai/tasks/${tid}`);
      setActiveTask(data.data);
      setTasks(p => p.map(t => t.task_id===tid ? {...t,...data.data} : t));
    } catch {}
  };

  const approve = async (tid) => {
    try { await axios.post(`${BASE.ai}/ai/tasks/${tid}/approve`, { approved:true }); toast.success('Approved!'); pollTask(tid); } catch {}
  };
  const reject = async (tid) => {
    try { await axios.post(`${BASE.ai}/ai/tasks/${tid}/reject`, { reason:'Not suitable' }); toast.success('Rejected'); pollTask(tid); } catch {}
  };

  const statusColor = { queued:'#888', running:'#0a66c2', waiting_approval:'#e68a00', approved:'#057642', rejected:'#cc1016', failed:'#cc1016' };

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div>
          <h1 style={{ fontSize:24, fontWeight:600 }}>AI Hiring Copilot</h1>
          <p style={{ fontSize:15, color:'rgba(0,0,0,0.6)', marginTop:2 }}>Supervisor agent with Resume Parser · Job Matcher · Outreach Generator</p>
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
              <option value="full_pipeline">Full pipeline</option>
              <option value="shortlist">Shortlist only</option>
              <option value="resume_parse">Resume parse</option>
            </select>
          </div>
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
                  <p style={{ fontSize:15, fontWeight:600 }}>{t.task_type.replace('_',' ')}</p>
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
            <h2 style={{ fontSize:20, fontWeight:600 }}>AI output</h2>
            {activeTask.status === 'waiting_approval' && (
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
          {activeTask.output.outreach_drafts?.length > 0 && (
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
  taskRow: { display:'flex', gap:12, padding:'12px 0', borderBottom:'1px solid rgba(0,0,0,0.06)', cursor:'pointer', alignItems:'center' },
  metric: { background:'#f3f6fb', borderRadius:8, padding:'12px 20px', textAlign:'center', minWidth:120, border:'1px solid rgba(0,0,0,0.08)' },
  candRow: { display:'flex', gap:14, alignItems:'center', padding:'12px 0', borderBottom:'1px solid rgba(0,0,0,0.06)' },
  candAvatar: { width:40, height:40, borderRadius:'50%', background:'#0a66c2', color:'#fff', fontSize:16, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
  skillPill: { background:'#e8f0fe', color:'#0a66c2', padding:'2px 10px', borderRadius:12, fontSize:12, fontWeight:500 },
};
