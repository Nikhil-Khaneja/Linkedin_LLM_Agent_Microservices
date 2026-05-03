import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useSearchParams } from 'react-router-dom';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';

const S = {
  lbl: { display: 'block', fontSize: 13, fontWeight: 600, color: 'rgba(0,0,0,0.75)', marginBottom: 4 },
  sel: { width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid rgba(0,0,0,0.15)', fontSize: 14, background: '#fff' },
  chip: { display: 'inline-block', padding: '4px 10px', borderRadius: 999, background: '#0a66c218', color: '#0a66c2', fontSize: 12, fontWeight: 600, marginRight: 6, marginBottom: 6 },
  chipMissing: { display: 'inline-block', padding: '4px 10px', borderRadius: 999, background: '#e68a0018', color: '#b45309', fontSize: 12, fontWeight: 600, marginRight: 6, marginBottom: 6 },
  tipLi: { marginBottom: 8, lineHeight: 1.5, fontSize: 14, color: 'rgba(0,0,0,0.8)' },
  score: { fontSize: 40, fontWeight: 700, lineHeight: 1 },
};

export default function CareerCoachPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const prefilledJobId = searchParams.get('job') || '';
  const [jobs, setJobs] = useState([]);
  const [selJob, setSelJob] = useState(prefilledJobId);
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const autoRanRef = useRef(false);

  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  useEffect(() => {
    if (!token) return;
    let mounted = true;
    const load = async () => {
      try {
        const res = await axios.post(`${BASE.job}/jobs/search`, { page_size: 50 }, authCfg);
        if (mounted) {
          const items = res.data?.data?.items || [];
          setJobs(items);
          // Respect prefilled job from URL if it's in the list, else fall back to first.
          if (!selJob && !prefilledJobId && items[0]) setSelJob(items[0].job_id);
        }
      } catch {
        if (mounted) setJobs([]);
      }
    };
    load();
    return () => { mounted = false; };
  }, [token]);

  const runCoach = useCallback(async (jobId) => {
    const target = jobId || selJob;
    if (!target) return toast.error('Select a job first');
    setLoading(true);
    setSuggestion(null);
    try {
      const { data } = await axios.post(
        `${BASE.ai}/ai/coach/suggest`,
        { target_job_id: target },
        authCfg,
      );
      setSuggestion(data?.data || null);
      if (!data?.data) toast.error('No suggestions returned');
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Coach failed');
    } finally {
      setLoading(false);
    }
  }, [selJob, authCfg]);

  // Auto-run once when we arrive with ?job=<id> and the token is present.
  useEffect(() => {
    if (autoRanRef.current) return;
    if (!token || !prefilledJobId) return;
    autoRanRef.current = true;
    runCoach(prefilledJobId);
  }, [token, prefilledJobId, runCoach]);

  const selectedJob = jobs.find((job) => job.job_id === selJob);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 600 }}>Career Coach</h1>
        <p style={{ fontSize: 15, color: 'rgba(0,0,0,0.6)', marginTop: 2 }}>
          Pick a job and we'll suggest a headline, the skills to add, and concrete resume tips — plus show the match score you'd reach.
        </p>
      </div>

      <div className="li-card" style={{ padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Optimize for a job</h2>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: 2, minWidth: 280 }}>
            <label style={S.lbl}>Select a target job</label>
            <select style={S.sel} value={selJob} onChange={(e) => setSelJob(e.target.value)}>
              <option value="">— Choose a job —</option>
              {jobs.map((job) => (
                <option key={job.job_id} value={job.job_id}>
                  {job.title} {job.company_name ? `· ${job.company_name}` : ''}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => runCoach()}
            disabled={loading || !selJob}
            className="li-btn-primary"
            style={{ borderRadius: 4, padding: '11px 28px', fontSize: 16, opacity: loading || !selJob ? 0.6 : 1 }}
          >
            {loading ? 'Coaching…' : 'Optimize for this job'}
          </button>
        </div>
        {selectedJob && (
          <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.55)', marginTop: 10 }}>
            Target: <strong>{selectedJob.title}</strong>
            {selectedJob.seniority_level ? ` · ${selectedJob.seniority_level}` : ''}
            {selectedJob.location ? ` · ${selectedJob.location}` : ''}
          </p>
        )}
      </div>

      {suggestion && (
        <>
          <div className="li-card" style={{ padding: 24, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
            <div>
              <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.55)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Current match</p>
              <p style={{ ...S.score, color: '#0a66c2' }}>{suggestion.current_match_score}</p>
            </div>
            <div>
              <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.55)', textTransform: 'uppercase', letterSpacing: 0.5 }}>If you improve</p>
              <p style={{ ...S.score, color: '#057642' }}>{suggestion.match_score_if_improved}</p>
            </div>
            <div>
              <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.55)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Potential gain</p>
              <p style={{ ...S.score, color: suggestion.score_delta > 0 ? '#057642' : 'rgba(0,0,0,0.4)' }}>
                {suggestion.score_delta > 0 ? `+${suggestion.score_delta}` : suggestion.score_delta}
              </p>
            </div>
            <div>
              <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.55)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Source</p>
              <p style={{ fontSize: 14, fontWeight: 600, marginTop: 6 }}>{suggestion.provider}</p>
            </div>
          </div>

          <div className="li-card" style={{ padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Suggested headline</h3>
            <p style={{ fontSize: 16, color: 'rgba(0,0,0,0.85)', marginBottom: 20, fontStyle: 'italic' }}>
              "{suggestion.suggested_headline}"
            </p>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Skills to add</h3>
            <div style={{ marginBottom: 20 }}>
              {(suggestion.skills_to_add || []).length === 0 ? (
                <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.5)' }}>You already have every skill this job lists. 🎉</p>
              ) : (
                (suggestion.skills_to_add || []).map((skill) => (
                  <span key={skill} style={S.chipMissing}>{skill}</span>
                ))
              )}
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Resume tips</h3>
            <ul style={{ paddingLeft: 20 }}>
              {(suggestion.resume_tips || []).map((tip, idx) => (
                <li key={idx} style={S.tipLi}>{tip}</li>
              ))}
            </ul>
            {suggestion.rationale && (
              <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.5)', marginTop: 20, borderTop: '1px solid rgba(0,0,0,0.08)', paddingTop: 12 }}>
                <strong>Why this score:</strong> {suggestion.rationale}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
