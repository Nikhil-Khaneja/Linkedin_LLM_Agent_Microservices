import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';

const CACHE_KEY = 'coach_history_v1';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 min

function timeAgo(d) {
  if (!d) return '';
  const diff = Date.now() - new Date(d);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(d).toLocaleDateString();
}

export default function CareerCoachPage() {
  const { user } = useAuth();
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [selectedTile, setSelectedTile] = useState(null);

  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  const loadHistory = async (forceRefresh = false) => {
    if (!token) { setHistoryLoading(false); return; }

    if (!forceRefresh) {
      try {
        const raw = sessionStorage.getItem(CACHE_KEY);
        if (raw) {
          const { items, ts } = JSON.parse(raw);
          if (Date.now() - ts < CACHE_TTL_MS) {
            setHistory(items);
            setHistoryLoading(false);
            return;
          }
        }
      } catch {}
    }

    setHistoryLoading(true);
    try {
      const { data } = await axios.get(`${BASE.ai}/ai/coach/history`, authCfg);
      const items = data?.data?.items || [];
      setHistory(items);
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ items, ts: Date.now() }));
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => { loadHistory(); }, [token]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 600 }}>Career Coach</h1>
          <p style={{ fontSize: 15, color: 'rgba(0,0,0,0.6)', marginTop: 2 }}>
            Your AI match history — click any tile for full analysis. Run a new score via <strong>✨ AI Score</strong> on the{' '}
            <Link to="/jobs" style={{ color: '#0a66c2' }}>Jobs page</Link>.
          </p>
        </div>
        <button
          onClick={() => loadHistory(true)}
          disabled={historyLoading}
          style={{ padding: '8px 16px', border: '1.5px solid rgba(0,0,0,0.2)', borderRadius: 20, background: '#fff', cursor: historyLoading ? 'default' : 'pointer', fontSize: 14, fontFamily: 'inherit', color: 'rgba(0,0,0,0.7)', opacity: historyLoading ? 0.5 : 1, flexShrink: 0 }}
        >
          {historyLoading ? '⟳ Loading…' : '↺ Refresh'}
        </button>
      </div>

      {historyLoading ? (
        <div className="li-card" style={{ padding: 60, textAlign: 'center', color: 'rgba(0,0,0,0.5)' }}>
          <div style={{ width: 32, height: 32, border: '3px solid #e5e7eb', borderTopColor: '#7c3aed', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 14px' }} />
          Loading your AI match history…
        </div>
      ) : history.length === 0 ? (
        <div className="li-card" style={{ padding: 60, textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🤖</div>
          <p style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No AI scores yet</p>
          <p style={{ color: 'rgba(0,0,0,0.55)', marginBottom: 20 }}>
            Click <strong>✨ AI Score</strong> on any job listing to get your first match analysis.
          </p>
          <Link to="/jobs" className="li-btn-primary" style={{ display: 'inline-block', padding: '10px 24px', borderRadius: 24, textDecoration: 'none', fontSize: 15, fontWeight: 700 }}>
            Browse Jobs →
          </Link>
        </div>
      ) : (
        <div>
          <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)', marginBottom: 14 }}>
            {history.length} job{history.length !== 1 ? 's' : ''} analyzed · click any tile to expand
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: 14 }}>
            {history.map((h) => (
              <HistoryTile key={h.history_id} h={h} onClick={() => setSelectedTile(h)} />
            ))}
          </div>
        </div>
      )}

      {selectedTile && <DetailsModal tile={selectedTile} onClose={() => setSelectedTile(null)} />}
    </div>
  );
}

function HistoryTile({ h, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{ background: '#fff', borderRadius: 10, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', padding: '16px', cursor: 'pointer', transition: 'box-shadow 0.15s, transform 0.1s' }}
      onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.15)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '0 0 0 1px rgba(0,0,0,0.1)'; e.currentTarget.style.transform = 'none'; }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={{ flex: 1, minWidth: 0, paddingRight: 8 }}>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#0a66c2', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {h.job_title || 'Untitled Job'}
          </p>
          {h.company_name && (
            <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.5)' }}>{h.company_name}</p>
          )}
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <p style={{ fontSize: 26, fontWeight: 800, color: '#0a66c2', lineHeight: 1 }}>{h.current_match_score}</p>
          {h.score_delta > 0 && (
            <p style={{ fontSize: 11, color: '#057642', fontWeight: 600, marginTop: 1 }}>+{h.score_delta} gain</p>
          )}
        </div>
      </div>

      {h.skills_to_add?.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          {h.skills_to_add.slice(0, 3).map((s) => (
            <span key={s} style={{ display: 'inline-block', fontSize: 11, fontWeight: 600, color: '#b45309', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 999, padding: '1px 7px', marginRight: 4, marginBottom: 3 }}>{s}</span>
          ))}
          {h.skills_to_add.length > 3 && (
            <span style={{ fontSize: 11, color: 'rgba(0,0,0,0.4)' }}>+{h.skills_to_add.length - 3} more</span>
          )}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
        <span style={{ fontSize: 11, color: 'rgba(0,0,0,0.4)' }}>{timeAgo(h.searched_at)}</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: h.provider === 'heuristic' ? 'rgba(0,0,0,0.35)' : '#7c3aed' }}>
          {h.provider === 'heuristic' ? '⚙️ Rules' : '✨ AI'}
        </span>
      </div>
    </div>
  );
}

function DetailsModal({ tile, onClose }) {
  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.52)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      onClick={onClose}
    >
      <div
        style={{ background: '#fff', borderRadius: 14, padding: '28px 32px', maxWidth: 560, width: '100%', maxHeight: '88vh', overflowY: 'auto', boxShadow: '0 12px 48px rgba(0,0,0,0.25)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div style={{ flex: 1, paddingRight: 12 }}>
            <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, color: 'rgba(0,0,0,0.9)' }}>{tile.job_title}</h3>
            <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)' }}>
              {[tile.company_name, timeAgo(tile.searched_at)].filter(Boolean).join(' · ')}
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 22, color: '#aaa', lineHeight: 1, padding: 0, flexShrink: 0 }}>✕</button>
        </div>

        {/* Scores */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 24, background: '#f8f9fa', borderRadius: 10, overflow: 'hidden' }}>
          <ScoreBlock label="Current match" value={tile.current_match_score} color="#0a66c2" />
          <ScoreBlock label="If improved" value={tile.match_score_if_improved} color="#057642" />
          {tile.score_delta > 0 && (
            <ScoreBlock label="Potential gain" value={`+${tile.score_delta}`} color="#057642" />
          )}
        </div>

        {/* Suggested headline */}
        {tile.suggested_headline && (
          <Section label="Suggested Headline">
            <p style={{ fontSize: 15, color: 'rgba(0,0,0,0.85)', fontStyle: 'italic', background: '#f0f4ff', borderRadius: 8, padding: '12px 14px', borderLeft: '3px solid #0a66c2', margin: 0 }}>
              "{tile.suggested_headline}"
            </p>
          </Section>
        )}

        {/* Skills to add */}
        {tile.skills_to_add?.length > 0 && (
          <Section label="Skills to Add">
            <div>
              {tile.skills_to_add.map((s) => (
                <span key={s} style={{ display: 'inline-block', padding: '4px 12px', borderRadius: 999, background: '#fff7ed', color: '#b45309', fontSize: 13, fontWeight: 600, marginRight: 6, marginBottom: 6, border: '1px solid #fed7aa' }}>{s}</span>
              ))}
            </div>
          </Section>
        )}

        {/* Resume tips */}
        {tile.resume_tips?.length > 0 && (
          <Section label="Resume Tips">
            <ul style={{ paddingLeft: 18, margin: 0 }}>
              {tile.resume_tips.map((tip, i) => (
                <li key={i} style={{ fontSize: 14, color: 'rgba(0,0,0,0.8)', marginBottom: 10, lineHeight: 1.55 }}>{tip}</li>
              ))}
            </ul>
          </Section>
        )}

        {/* Rationale */}
        {tile.rationale && (
          <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', background: '#f8f9fa', borderRadius: 6, padding: '10px 12px', lineHeight: 1.55, marginBottom: 20 }}>
            <strong>Why this score: </strong>{tile.rationale}
          </p>
        )}

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 16, borderTop: '1px solid rgba(0,0,0,0.08)' }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: tile.provider === 'heuristic' ? 'rgba(0,0,0,0.4)' : '#7c3aed' }}>
            {tile.provider === 'heuristic' ? '⚙️ Rules-based scoring' : '✨ AI-generated (OpenRouter)'}
          </span>
          <button onClick={onClose} style={{ padding: '9px 22px', background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 24, cursor: 'pointer', fontSize: 14, fontWeight: 700, fontFamily: 'inherit' }}>Close</button>
        </div>
      </div>
    </div>
  );
}

function ScoreBlock({ label, value, color }) {
  return (
    <div style={{ flex: 1, textAlign: 'center', padding: '16px 8px', borderRight: '1px solid rgba(0,0,0,0.06)' }}>
      <p style={{ fontSize: 10, color: 'rgba(0,0,0,0.45)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 }}>{label}</p>
      <p style={{ fontSize: 40, fontWeight: 800, color, lineHeight: 1 }}>{value}</p>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <p style={{ fontSize: 11, fontWeight: 700, color: 'rgba(0,0,0,0.55)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 10 }}>{label}</p>
      {children}
    </div>
  );
}
