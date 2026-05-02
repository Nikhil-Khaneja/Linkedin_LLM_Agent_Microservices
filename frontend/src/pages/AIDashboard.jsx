import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import BASE from '../config/api';

const STEPS = {
  queued: 'Queued',
  starting: 'Starting',
  fetching_job: 'Fetching job',
  fetching_candidates: 'Finding candidates',
  parsing_resumes: 'Parsing resumes',
  matching_candidates: 'Matching candidates',
  drafting_outreach: 'Drafting outreach',
  waiting_approval: 'Awaiting review',
  awaiting_approval: 'Awaiting review',
  approved: 'Approved',
  rejected: 'Rejected',
  failed: 'Failed',
};

const ACTIVE_TASK_KEY = 'ai_active_task_id';

const normalizeArray = (value) => {
  if (Array.isArray(value)) return value;
  if (value == null) return [];
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return [];
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        const parsed = JSON.parse(trimmed);
        return Array.isArray(parsed) ? parsed : [];
      } catch (_) {}
    }
    return trimmed.split(/[,|;\n]/).map((item) => item.trim()).filter(Boolean);
  }
  if (typeof value === 'object') return Object.values(value).filter(Boolean);
  return [value].filter(Boolean);
};

export default function AIDashboard() {
  const [jobs, setJobs] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [selJob, setSelJob] = useState('');
  const [taskType, setTaskType] = useState('full_pipeline');
  const [loading, setLoading] = useState(false);
  const [activeTask, setActiveTask] = useState(null);
  const [log, setLog] = useState([]);
  const [sendingOutreach, setSendingOutreach] = useState(false);
  const wsRef = useRef(null);
  const navigate = useNavigate();
  const activeTaskRef = useRef(null);
  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  useEffect(() => {
    if (!token) return;
    let mounted = true;
    const loadJobs = async () => {
      try {
        const recruiterRes = await axios.post(`${BASE.recruiter}/recruiters/get`, {}, authCfg);
        const rid = recruiterRes.data?.data?.recruiter?.recruiter_id;
        const jobsRes = rid
          ? await axios.post(`${BASE.job}/jobs/byRecruiter`, { recruiter_id: rid }, authCfg)
          : await axios.post(`${BASE.job}/jobs/search`, { page_size: 50 }, authCfg);
        if (mounted) {
          const items = jobsRes.data?.data?.items || [];
          setJobs(items);
          if (!selJob && items[0]) setSelJob(items[0].job_id);
        }
      } catch {
        try {
          const jobsRes = await axios.post(`${BASE.job}/jobs/search`, { page_size: 50 }, authCfg);
          if (mounted) {
            const items = jobsRes.data?.data?.items || [];
            setJobs(items);
            if (!selJob && items[0]) setSelJob(items[0].job_id);
          }
        } catch {
          if (mounted) setJobs([]);
        }
      }
    };
    loadJobs();
    return () => { mounted = false; };
  }, [token]);

  useEffect(() => {
    if (!token) return undefined;
    loadTasks();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [token]);

  useEffect(() => {
    if (!activeTask?.task_id || !['queued', 'running', 'waiting_approval', 'awaiting_approval'].includes(activeTask.status)) return undefined;
    const timer = setInterval(() => pollTask(activeTask.task_id, false), 3000);
    return () => clearInterval(timer);
  }, [activeTask?.task_id, activeTask?.status]);

  useEffect(() => {
    if (!activeTask?.task_id) return undefined;
    if (['queued', 'running', 'waiting_approval', 'awaiting_approval'].includes(activeTask.status)) {
      connectWS(activeTask.task_id, false);
    } else if (wsRef.current) {
      wsRef.current._manualClose = true;
      wsRef.current.close();
      wsRef.current = null;
    }
    return undefined;
  }, [activeTask?.task_id, activeTask?.status]);

  const parsedCandidates = normalizeArray(activeTask?.output?.parsed_candidates);
  const shortlist = normalizeArray(activeTask?.output?.shortlist).map((candidate) => ({
    ...candidate,
    skill_overlap: normalizeArray(candidate?.skill_overlap),
    missing_skills: normalizeArray(candidate?.missing_skills),
  }));
  const outreachDrafts = normalizeArray(activeTask?.output?.outreach_drafts);
  const sentMessages = normalizeArray(activeTask?.output?.sent_messages);
  const sendFailures = normalizeArray(activeTask?.output?.outreach_send_failures);

  const hydrateLogsFromTask = (task) => {
    const steps = Array.isArray(task?.steps) ? task.steps : [];
    return steps.map((step, idx) => ({
      type: 'task_state',
      current_step: step.step,
      ts: new Date().toLocaleTimeString(),
      payload: step.payload || {},
      idx,
    }));
  };

  const updateTaskState = (task) => {
    if (!task) return;
    activeTaskRef.current = task;
    setActiveTask(task);
    setTasks((prev) => {
      const next = prev.map((item) => (item.task_id === task.task_id ? { ...item, ...task } : item));
      return next.some((item) => item.task_id === task.task_id) ? next : [task, ...next];
    });
    setLog(hydrateLogsFromTask(task));
    localStorage.setItem(ACTIVE_TASK_KEY, task.task_id);
  };

  const loadTasks = async () => {
    try {
      const { data } = await axios.get(`${BASE.ai}/ai/tasks`, authCfg);
      const items = data?.data?.items || [];
      setTasks(items);
      const savedTaskId = localStorage.getItem(ACTIVE_TASK_KEY);
      const preferred = items.find((item) => item.task_id === savedTaskId)
        || items.find((item) => ['queued', 'running', 'waiting_approval', 'awaiting_approval'].includes(item.status))
        || items[0];
      if (preferred) updateTaskState(preferred);
    } catch {
      setTasks([]);
    }
  };

  const launch = async () => {
    if (!selJob) return toast.error('Select a job first');
    setLoading(true);
    try {
      const { data } = await axios.post(`${BASE.ai}/ai/tasks/create`, { job_id: selJob, task_type: taskType }, authCfg);
      const task = { task_id: data?.data?.task_id, status: 'queued', current_step: 'queued', input: { job_id: selJob, task_type: taskType }, steps: [] };
      toast.success('AI task launched');
      updateTaskState(task);
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Launch failed');
    } finally {
      setLoading(false);
    }
  };

  const connectWS = (taskId, resetLog = true) => {
    if (!taskId) return;
    if (wsRef.current && wsRef.current._taskId === taskId && wsRef.current.readyState <= 1) return;
    if (wsRef.current) {
      wsRef.current._manualClose = true;
      wsRef.current.close();
    }
    const wsBase = (BASE.ai || 'http://localhost:8008').replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsBase}/ws/ai/tasks/${taskId}`);
    ws._taskId = taskId;
    ws._manualClose = false;
    wsRef.current = ws;
    if (resetLog) setLog([]);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data || '{}');
      setLog((prev) => [...prev, { ...msg, ts: new Date().toLocaleTimeString() }]);
      if (msg.type === 'task_state' && msg.data) updateTaskState(msg.data);
    };
    ws.onerror = () => {};
    ws.onclose = () => {
      const current = activeTaskRef.current;
      if (!ws._manualClose && current?.task_id === taskId && ['queued', 'running', 'waiting_approval', 'awaiting_approval'].includes(current?.status)) {
        pollTask(taskId, false);
      }
      if (wsRef.current === ws) wsRef.current = null;
    };
    pollTask(taskId, false);
  };

  const pollTask = async (taskId, toastOnError = false) => {
    if (!taskId) return;
    try {
      const { data } = await axios.get(`${BASE.ai}/ai/tasks/${taskId}`, authCfg);
      const task = data?.data;
      if (task) updateTaskState(task);
    } catch (err) {
      if (toastOnError) toast.error(err.response?.data?.error?.message || 'Failed to load task');
    }
  };

  const approve = async (taskId, sendOutreach = true) => {
    try {
      setSendingOutreach(sendOutreach);
      const { data } = await axios.post(`${BASE.ai}/ai/tasks/${taskId}/approve`, { approved: true, send_outreach: sendOutreach }, authCfg);
      toast.success(sendOutreach ? `Approved and sent ${data?.data?.sent_count || 0} outreach messages` : 'Approved');
      pollTask(taskId, true);
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Approve failed');
    } finally {
      setSendingOutreach(false);
    }
  };

  const reject = async (taskId) => {
    try {
      await axios.post(`${BASE.ai}/ai/tasks/${taskId}/reject`, { reason: 'Not suitable' }, authCfg);
      toast.success('Task rejected');
      pollTask(taskId, true);
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Reject failed');
    }
  };

  const sendOutreach = async (taskId) => {
    try {
      setSendingOutreach(true);
      const { data } = await axios.post(`${BASE.ai}/ai/tasks/${taskId}/sendOutreach`, {}, authCfg);
      toast.success(`Sent ${data?.data?.sent_count || 0} outreach messages`);
      pollTask(taskId, true);
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Send outreach failed');
    } finally {
      setSendingOutreach(false);
    }
  };

  const openMessageComposer = (candidate, draftText = '') => {
    const candidateId = candidate?.candidate_id;
    if (!candidateId) {
      toast.error('Candidate ID missing');
      return;
    }
    const params = new URLSearchParams();
    params.set('user', candidateId);
    if (draftText) params.set('draft', draftText);
    navigate(`/messages?${params.toString()}`);
  };

  const draftByCandidateId = new Map(outreachDrafts.map((draft) => [draft?.candidate_id, draft]));

  const statusColor = useMemo(() => ({
    queued: '#888',
    running: '#0a66c2',
    waiting_approval: '#e68a00',
    awaiting_approval: '#e68a00',
    completed: '#057642',
    approved: '#057642',
    rejected: '#cc1016',
    failed: '#cc1016',
  }), []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 600 }}>AI Hiring Copilot</h1>
        <p style={{ fontSize: 15, color: 'rgba(0,0,0,0.6)', marginTop: 2 }}>Resume parsing, PDF extraction, candidate ranking, and outreach sending powered by heuristics or OpenRouter + Gemini Flash.</p>
      </div>

      <div className="li-card" style={{ padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Launch AI task</h2>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: 2, minWidth: 240 }}>
            <label style={S.lbl}>Select job posting</label>
            <select style={S.sel} value={selJob} onChange={(e) => setSelJob(e.target.value)}>
              <option value="">— Choose a job —</option>
              {jobs.map((job) => <option key={job.job_id} value={job.job_id}>{job.title}</option>)}
            </select>
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <label style={S.lbl}>Task type</label>
            <select style={S.sel} value={taskType} onChange={(e) => setTaskType(e.target.value)}>
              <option value="full_pipeline">Full pipeline</option>
              <option value="shortlist">Shortlist only</option>
              <option value="resume_parse">Resume parse + rank</option>
            </select>
          </div>
          <button onClick={launch} disabled={loading || !selJob} className="li-btn-primary" style={{ borderRadius: 4, padding: '11px 28px', fontSize: 16, opacity: loading || !selJob ? 0.6 : 1 }}>
            {loading ? 'Launching…' : 'Run AI'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) minmax(320px, 1fr)', gap: 16 }}>
        <div className="li-card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 14 }}>Task history</h3>
          {tasks.length === 0 ? (
            <p style={{ color: 'rgba(0,0,0,0.5)', fontSize: 14 }}>No tasks yet — launch one above.</p>
          ) : tasks.map((task) => (
            <div key={task.task_id} onClick={() => { updateTaskState(task); if (!['queued', 'running', 'waiting_approval', 'awaiting_approval'].includes(task.status)) pollTask(task.task_id, false); }} style={S.taskRow}>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 15, fontWeight: 600 }}>{(task.input?.task_type || task.task_type || 'task').replace(/_/g, ' ')}</p>
                <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.5)', fontFamily: 'monospace' }}>{task.task_id}</p>
                <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.6)', marginTop: 2 }}>{STEPS[task.current_step] || task.current_step}</p>
              </div>
              <span style={{ background: `${statusColor[task.status] || '#888'}18`, color: statusColor[task.status] || '#888', border: `1px solid ${(statusColor[task.status] || '#888')}40`, padding: '3px 12px', borderRadius: 12, fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>{task.status}</span>
            </div>
          ))}
        </div>

        <div className="li-card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 14 }}>Live progress</h3>
          {!activeTask ? (
            <p style={{ color: 'rgba(0,0,0,0.5)', fontSize: 14 }}>Choose a task from history to inspect progress.</p>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div>
                  <p style={{ fontSize: 15, fontWeight: 700 }}>{activeTask.input?.task_type?.replace(/_/g, ' ') || 'Task'}</p>
                  <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.5)' }}>{activeTask.task_id}</p>
                </div>
                <span style={{ color: statusColor[activeTask.status] || '#666', fontWeight: 700 }}>{STEPS[activeTask.current_step] || activeTask.current_step}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {log.length === 0 ? <p style={{ color: 'rgba(0,0,0,0.5)', fontSize: 14 }}>Waiting for updates…</p> : log.slice(-8).reverse().map((entry, idx) => (
                  <div key={`${entry.current_step}-${idx}`} style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 13 }}>
                    <span style={{ color: 'rgba(0,0,0,0.45)' }}>{entry.ts}</span>
                    <span style={{ color: '#0a66c2', fontWeight: 700 }}>[task_state]</span>
                    <span style={{ color: (entry.current_step === 'failed' ? '#cc1016' : '#057642') }}>{STEPS[entry.current_step] || entry.current_step}</span>
                  </div>
                ))}
              </div>
              {activeTask.status === 'failed' && (
                <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: '#fff3f2', color: '#b42318', fontSize: 14 }}>
                  {activeTask.output?.error || 'The task failed. Please retry after checking the resume or AI configuration.'}
                </div>
              )}
              {activeTask.output?.provider_warning && (
                <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: '#fff8e8', color: '#8a5b00', fontSize: 14 }}>
                  {activeTask.output.provider_warning}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {activeTask && (
        <div className="li-card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
            <div>
              <h2 style={{ fontSize: 20, fontWeight: 700 }}>Task output</h2>
              <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.55)' }}>Parsed resumes and ranked shortlist remain available even if you navigate away.</p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {['waiting_approval', 'awaiting_approval'].includes(activeTask.status) && (
                <>
                  <button onClick={() => approve(activeTask.task_id, false)} style={S.secondaryBtn}>Approve only</button>
                  <button onClick={() => approve(activeTask.task_id, true)} disabled={sendingOutreach} style={S.primaryBtn}>{sendingOutreach ? 'Sending…' : 'Approve + send outreach'}</button>
                  <button onClick={() => reject(activeTask.task_id)} style={S.dangerBtn}>Reject</button>
                </>
              )}
              {activeTask.status === 'completed' && outreachDrafts.length > 0 && sentMessages.length === 0 && (
                <button onClick={() => sendOutreach(activeTask.task_id)} disabled={sendingOutreach} style={S.primaryBtn}>{sendingOutreach ? 'Sending…' : 'Send outreach'}</button>
              )}
            </div>
          </div>

          {parsedCandidates.length > 0 && (
            <section>
              <h3 style={S.sectionTitle}>Parsed resumes</h3>
              <div style={S.grid}>
                {parsedCandidates.map((candidate) => (
                  <div key={candidate.candidate_id} style={S.outputCard}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                      <div>
                        <p style={{ fontWeight: 700 }}>{candidate.name}</p>
                        <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.55)' }}>{candidate.resume_parsed?.education || 'Education not detected'}</p>
                      </div>
                      <span style={S.scoreChip}>{candidate.match_score || 0}</span>
                    </div>
                    <p style={{ marginTop: 10, fontSize: 13, color: 'rgba(0,0,0,0.72)' }}>{candidate.rationale}</p>
                    <div style={S.tagWrap}>
                      {normalizeArray(candidate.resume_parsed?.skills).slice(0, 8).map((skill) => <span key={String(skill)} style={S.tag}>{skill}</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {shortlist.length > 0 && (
            <section>
              <h3 style={S.sectionTitle}>Ranked candidates</h3>
              <div style={S.grid}>
                {shortlist.map((candidate) => (
                  <div key={candidate.candidate_id} style={S.outputCard}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                      <div>
                        <p style={{ fontWeight: 700 }}>{candidate.name}</p>
                        <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.55)' }}>{candidate.headline || 'LinkedIn Member'}</p>
                        <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{candidate.location || 'Location unavailable'}</p>
                      </div>
                      <span style={S.scoreChip}>{candidate.match_score || 0}</span>
                    </div>
                    <p style={{ marginTop: 10, fontSize: 13, color: 'rgba(0,0,0,0.72)' }}>{candidate.rationale}</p>
                    <div style={S.tagWrap}>
                      {normalizeArray(candidate.skill_overlap).map((skill) => <span key={String(skill)} style={S.tag}>{skill}</span>)}
                    </div>
                    {normalizeArray(candidate.missing_skills).length > 0 && <p style={{ fontSize: 12, color: '#b42318', marginTop: 8 }}>Missing: {normalizeArray(candidate.missing_skills).join(', ')}</p>}
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                      <button onClick={() => openMessageComposer(candidate, draftByCandidateId.get(candidate?.candidate_id)?.draft || draftByCandidateId.get(candidate?.candidate_id)?.message || '')} style={S.secondaryBtn}>Send message</button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {outreachDrafts.length > 0 && (
            <section>
              <h3 style={S.sectionTitle}>Outreach drafts</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {outreachDrafts.map((draft) => (
                  <div key={draft.candidate_id} style={S.outputCard}>
                    <p style={{ fontWeight: 700, marginBottom: 8 }}>{draft.name || draft.candidate_id}</p>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 14, color: 'rgba(0,0,0,0.72)' }}>{draft.draft || draft.message}</pre>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                      <button onClick={() => openMessageComposer({ candidate_id: draft.candidate_id }, draft.draft || draft.message || '')} style={S.primaryBtn}>Send message</button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {(sentMessages.length > 0 || sendFailures.length > 0) && (
            <section>
              <h3 style={S.sectionTitle}>Outreach delivery</h3>
              {sentMessages.length > 0 && <p style={{ color: '#057642', fontWeight: 700, marginBottom: 6 }}>Sent to {sentMessages.length} candidate(s)</p>}
              {sendFailures.length > 0 && sendFailures.map((failure) => (
                <div key={`${failure.candidate_id}-${failure.error}`} style={{ fontSize: 13, color: '#b42318' }}>{failure.candidate_id || 'Candidate'}: {failure.error}</div>
              ))}
            </section>
          )}
        </div>
      )}
    </div>
  );
}

const S = {
  lbl: { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: 'rgba(0,0,0,0.7)' },
  sel: { width: '100%', padding: '11px 12px', border: '1px solid rgba(0,0,0,0.2)', borderRadius: 6, fontFamily: 'inherit' },
  taskRow: { display: 'flex', gap: 12, alignItems: 'center', padding: '12px 10px', borderRadius: 10, cursor: 'pointer', border: '1px solid rgba(0,0,0,0.06)', marginBottom: 10 },
  primaryBtn: { padding: '10px 16px', background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  secondaryBtn: { padding: '10px 16px', background: '#fff', color: '#0a66c2', border: '1px solid #0a66c2', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  dangerBtn: { padding: '10px 16px', background: '#fff', color: '#b42318', border: '1px solid #b42318', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  sectionTitle: { fontSize: 18, fontWeight: 700, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 },
  outputCard: { border: '1px solid rgba(0,0,0,0.08)', borderRadius: 10, padding: 14, background: '#fff' },
  scoreChip: { minWidth: 46, textAlign: 'center', padding: '6px 10px', borderRadius: 999, background: '#eef6ff', color: '#0a66c2', fontWeight: 700 },
  tagWrap: { display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  tag: { padding: '4px 10px', borderRadius: 999, background: '#f3f6fb', color: '#0a66c2', fontSize: 12, fontWeight: 600 },
};
