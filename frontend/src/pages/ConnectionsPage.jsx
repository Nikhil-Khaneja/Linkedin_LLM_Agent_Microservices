import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

export default function ConnectionsPage() {
  const { user } = useAuth();
  const [connections, setConnections] = useState([]);
  const [pendingIncoming, setPendingIncoming] = useState([]);
  const [pendingSent, setPendingSent] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [recruiterSearchResults, setRecruiterSearchResults] = useState([]);
  const [mutualCounts, setMutualCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  const currentId = user?.principalId || user?.userId;
  const isRecruiterUser = user?.userType === 'recruiter';
  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  useEffect(() => {
    if (!currentId || !token) return;
    loadAll();
  }, [currentId, token]);

  useEffect(() => {
    if (!currentId || !token) return undefined;
    const tick = () => {
      if (typeof document !== 'undefined' && document.hidden) return;
      loadConnections();
      loadPendingIncoming();
      loadPendingSent();
    };
    const timer = setInterval(tick, 25000);
    return () => clearInterval(timer);
  }, [currentId, token]);

  useEffect(() => {
    if (!currentId || !token || connections.length === 0) {
      setMutualCounts({});
      return;
    }
    Promise.all(
      connections.map(async (conn) => {
        const otherId = conn.other_user_id || conn.user_id;
        if (!otherId) return [otherId, 0];
        try {
          const { data } = await axios.post(`${BASE.messaging}/connections/mutual`, { user_id: currentId, other_id: otherId }, authCfg);
          return [otherId, (data?.data?.items || []).length];
        } catch {
          return [otherId, 0];
        }
      })
    ).then((entries) => setMutualCounts(Object.fromEntries(entries.filter(([k]) => !!k))));
  }, [connections, currentId, token]);

  const sentReceiverIds = useMemo(() => new Set((pendingSent || []).map((req) => req.receiver_id)), [pendingSent]);
  const connectedIds = useMemo(() => new Set((connections || []).map((conn) => conn.other_user_id || conn.user_id)), [connections]);
  const filteredSearchResults = useMemo(
    () => (searchResults || []).filter(
      (m) => m.member_id
        && String(m.member_id).startsWith('mem_')
        && m.member_id !== currentId
        && m.email !== user?.email,
    ),
    [searchResults, currentId, user?.email]
  );

  const filteredRecruiterResults = useMemo(
    () => (recruiterSearchResults || []).filter(
      (r) => r.recruiter_id && String(r.recruiter_id).startsWith('rec_') && r.recruiter_id !== currentId,
    ),
    [recruiterSearchResults, currentId],
  );

  const totalSearchHits = filteredSearchResults.length + filteredRecruiterResults.length;

  const loadAll = async () => {
    setLoading(true);
    await Promise.all([loadConnections(), loadPendingIncoming(), loadPendingSent()]);
    setLoading(false);
  };

  const loadPendingIncoming = async () => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/connections/pending`, { user_id: currentId }, authCfg);
      setPendingIncoming(data?.data?.items || []);
    } catch {
      setPendingIncoming([]);
    }
  };

  const loadPendingSent = async () => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/connections/sent`, { user_id: currentId }, authCfg);
      setPendingSent(data?.data?.items || []);
    } catch {
      setPendingSent([]);
    }
  };

  const loadConnections = async () => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/connections/list`, { user_id: currentId }, authCfg);
      setConnections(data?.data?.items || []);
    } catch (err) {
      setConnections([]);
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        toast.error('Your session expired. Please sign in again.');
      }
    }
  };

  const decideRequest = async (requestId, action) => {
    try {
      await axios.post(`${BASE.messaging}/connections/${action}`, { request_id: requestId }, authCfg);
      toast.success(action === 'accept' ? 'Connection accepted' : 'Connection rejected');
      loadAll();
    } catch (err) {
      toast.error(err.response?.data?.error?.message || `Failed to ${action} request`);
    }
  };

  const withdrawRequest = async (requestId) => {
    try {
      await axios.post(`${BASE.messaging}/connections/withdraw`, { request_id: requestId }, authCfg);
      toast.success('Connection request withdrawn');
      loadPendingSent();
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to withdraw request');
    }
  };

  const searchPeople = async () => {
    if (!searchQuery.trim()) return;
    if (!token) return toast.error('Please sign in first');
    setSearching(true);
    setRecruiterSearchResults([]);
    try {
      const kw = searchQuery.trim();
      const memberReq = axios.post(`${BASE.member}/members/search`, { keyword: kw, page: 1, page_size: 800, media_public_base: BASE.member }, authCfg);
      if (!isRecruiterUser) {
        const recReq = axios.post(`${BASE.recruiter}/recruiters/search`, { keyword: kw, page: 1, page_size: 100 }, authCfg);
        const [memRes, recRes] = await Promise.allSettled([memberReq, recReq]);
        if (memRes.status === 'fulfilled') {
          setSearchResults(memRes.value.data?.data?.items || []);
        } else {
          setSearchResults([]);
          toast.error(memRes.reason?.response?.data?.error?.message || 'Member search failed');
        }
        if (recRes.status === 'fulfilled') {
          setRecruiterSearchResults(recRes.value.data?.data?.items || []);
        } else {
          setRecruiterSearchResults([]);
        }
      } else {
        const { data } = await memberReq;
        setSearchResults(data?.data?.items || []);
      }
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const connect = async (receiverId, displayName) => {
    const first = (displayName || 'there').split(/\s+/)[0] || 'there';
    try {
      await axios.post(`${BASE.messaging}/connections/request`, { requester_id: currentId, receiver_id: receiverId, message: `Hi ${first}, I would like to connect!` }, authCfg);
      toast.success(`Request sent to ${displayName || 'user'}!`);
      loadPendingSent();
    } catch (err) {
      const msg = err.response?.data?.error?.message || '';
      if (msg.includes('already')) {
        toast('Request already sent to this person', { icon: '✓' });
        loadPendingSent();
      } else {
        toast.error(msg || 'Failed to send request');
      }
    }
  };

  const removeConnection = async (otherUserId) => {
    try {
      await axios.post(`${BASE.messaging}/connections/remove`, { other_user_id: otherUserId }, authCfg);
      toast.success('Connection removed');
      loadAll();
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to remove connection');
    }
  };

  return (
    <div style={{ maxWidth: 920, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>My Network</h1>
      <p style={{ color: 'rgba(0,0,0,0.55)', marginBottom: 20, fontSize: 15 }}>
        {connections.length} connection{connections.length !== 1 ? 's' : ''} · {pendingIncoming.length} incoming · {pendingSent.length} sent pending
      </p>

      <div style={S.card}>
        <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>Find people to connect with</h3>
        <div style={{ display: 'flex', gap: 10, marginBottom: totalSearchHits > 0 ? 16 : 0 }}>
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by name, headline, or skill…"
            style={S.input}
            onKeyDown={(e) => e.key === 'Enter' && searchPeople()}
          />
          <button type="button" onClick={searchPeople} disabled={searching || !searchQuery.trim()} style={S.searchBtn}>{searching ? 'Searching…' : 'Search'}</button>
        </div>

        {totalSearchHits > 0 && (
          <div>
            <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)', marginBottom: 12 }}>{totalSearchHits} people found</p>
            {filteredSearchResults.length > 0 && (
              <>
                {!isRecruiterUser && <p style={{ fontSize: 12, fontWeight: 700, color: 'rgba(0,0,0,0.5)', marginBottom: 8 }}>Members</p>}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 10, marginBottom: filteredRecruiterResults.length > 0 ? 16 : 0 }}>
                  {filteredSearchResults.map((m) => {
                    const alreadySent = sentReceiverIds.has(m.member_id);
                    const alreadyConnected = connectedIds.has(m.member_id);
                    const pendingReq = pendingSent.find((req) => req.receiver_id === m.member_id);
                    const initials = `${(m.first_name || '?')[0] || '?'}${(m.last_name || '')[0] || ''}`.toUpperCase();
                    const name = `${m.first_name || ''} ${m.last_name || ''}`.trim() || m.member_id;
                    return (
                      <div key={m.member_id} style={S.personCard}>
                        <Link to={`/profile/${m.member_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                          <div style={S.personAvatar}>{m.profile_photo_url ? <img src={m.profile_photo_url} alt="" style={S.avatarImg} /> : initials}</div>
                        </Link>
                        <div style={{ flex: 1, minWidth: 0, textAlign: 'center' }}>
                          <Link to={`/profile/${m.member_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                            <p style={{ fontSize: 14, fontWeight: 700, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</p>
                          </Link>
                          <p style={{ fontSize: 11, color: 'rgba(0,0,0,0.5)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 4 }}>{m.headline || [m.current_title, m.current_company].filter(Boolean).join(' · ') || 'LinkedIn Member'}</p>
                          {m.city && <p style={{ fontSize: 11, color: 'rgba(0,0,0,0.4)', marginBottom: 8 }}>📍 {m.city}</p>}
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
                          <Link to={`/profile/${m.member_id}`}><button type="button" style={S.secondaryBtn}>View</button></Link>
                          <Link to={`/messages?user=${encodeURIComponent(m.member_id)}`}>
                            <button type="button" style={S.messageBtn}>Message</button>
                          </Link>
                          {alreadyConnected ? (
                            <>
                              <span style={S.sentChip}>Connected</span>
                              <button type="button" onClick={() => removeConnection(m.member_id)} style={S.withdrawBtn}>Remove</button>
                            </>
                          ) : alreadySent ? (
                            <button type="button" onClick={() => withdrawRequest(pendingReq?.request_id)} style={S.withdrawBtn}>Withdraw</button>
                          ) : (
                            <button type="button" onClick={() => connect(m.member_id, name)} style={S.connectBtn}>+ Connect</button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
            {filteredRecruiterResults.length > 0 && (
              <>
                <p style={{ fontSize: 12, fontWeight: 700, color: 'rgba(0,0,0,0.5)', marginBottom: 8 }}>Recruiters</p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 10 }}>
                  {filteredRecruiterResults.map((r) => {
                    const rid = r.recruiter_id;
                    const alreadySent = sentReceiverIds.has(rid);
                    const alreadyConnected = connectedIds.has(rid);
                    const pendingReq = pendingSent.find((req) => req.receiver_id === rid);
                    const name = r.name || rid;
                    const sub = [r.headline, r.company_name].filter(Boolean).join(' · ') || 'Recruiter';
                    const initials = (name || '?')[0].toUpperCase();
                    return (
                      <div key={rid} style={S.personCard}>
                        <Link to={`/profile/${rid}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                          <div style={S.personAvatar}>{r.profile_photo_url ? <img src={r.profile_photo_url} alt="" style={S.avatarImg} /> : initials}</div>
                        </Link>
                        <div style={{ flex: 1, minWidth: 0, textAlign: 'center' }}>
                          <Link to={`/profile/${rid}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                            <p style={{ fontSize: 14, fontWeight: 700, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</p>
                          </Link>
                          <p style={{ fontSize: 11, color: 'rgba(0,0,0,0.5)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 4 }}>{sub}</p>
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
                          <Link to={`/profile/${rid}`}><button type="button" style={S.secondaryBtn}>View</button></Link>
                          <Link to={`/messages?user=${encodeURIComponent(rid)}`}>
                            <button type="button" style={S.messageBtn}>Message</button>
                          </Link>
                          {alreadyConnected ? (
                            <>
                              <span style={S.sentChip}>Connected</span>
                              <button type="button" onClick={() => removeConnection(rid)} style={S.withdrawBtn}>Remove</button>
                            </>
                          ) : alreadySent ? (
                            <button type="button" onClick={() => withdrawRequest(pendingReq?.request_id)} style={S.withdrawBtn}>Withdraw</button>
                          ) : (
                            <button type="button" onClick={() => connect(rid, name)} style={S.connectBtn}>+ Connect</button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {pendingIncoming.length > 0 && (
        <div style={{ ...S.card, marginTop: 8 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>Pending requests ({pendingIncoming.length})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {pendingIncoming.map((req) => (
              <div key={req.request_id} style={S.requestRow}>
                <Link to={`/profile/${req.requester_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div style={S.bigAvatar}>{req.profile_photo_url ? <img src={req.profile_photo_url} alt="" style={S.avatarImg} /> : (req.first_name || req.requester_id || 'U')[0].toUpperCase()}</div>
                </Link>
                <div style={{ flex: 1 }}>
                  <Link to={`/profile/${req.requester_id}`} style={{ textDecoration: 'none', color: 'inherit' }}><p style={{ fontSize: 15, fontWeight: 700 }}>{req.first_name ? `${req.first_name} ${req.last_name || ''}` : req.requester_id}</p></Link>
                  <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.55)' }}>{req.headline || req.message || 'Wants to connect'}</p>
                </div>
                <button onClick={() => decideRequest(req.request_id, 'accept')} style={S.acceptBtn}>Accept</button>
                <button onClick={() => decideRequest(req.request_id, 'reject')} style={S.rejectBtn}>Reject</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {pendingSent.length > 0 && (
        <div style={{ ...S.card, marginTop: 8 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>Sent requests ({pendingSent.length})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {pendingSent.map((req) => (
              <div key={req.request_id} style={S.requestRow}>
                <Link to={`/profile/${req.receiver_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div style={S.bigAvatar}>{req.profile_photo_url ? <img src={req.profile_photo_url} alt="" style={S.avatarImg} /> : (req.first_name || req.receiver_id || 'U')[0].toUpperCase()}</div>
                </Link>
                <div style={{ flex: 1 }}>
                  <Link to={`/profile/${req.receiver_id}`} style={{ textDecoration: 'none', color: 'inherit' }}><p style={{ fontSize: 15, fontWeight: 700 }}>{req.first_name ? `${req.first_name} ${req.last_name || ''}` : req.receiver_id}</p></Link>
                  <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.55)' }}>{req.headline || req.message || 'Awaiting response'}</p>
                </div>
                <button onClick={() => withdrawRequest(req.request_id)} style={S.withdrawBtn}>Withdraw</button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 8 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, paddingLeft: 4 }}>Connections ({connections.length})</h3>
        {loading ? (
          <div style={{ ...S.card, padding: 40, textAlign: 'center', color: 'rgba(0,0,0,0.4)' }}>Loading…</div>
        ) : connections.length === 0 ? (
          <div style={{ ...S.card, padding: 52, textAlign: 'center' }}>
            <div style={{ fontSize: 52, marginBottom: 12 }}>🤝</div>
            <p style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>No connections yet</p>
            <p style={{ color: 'rgba(0,0,0,0.5)' }}>Search above to start growing your network.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 10 }}>
            {connections.map((conn) => {
              const otherId = conn.other_user_id || conn.user_id;
              const initials = `${(conn.first_name || '?')[0] || '?'}${(conn.last_name || '')[0] || ''}`.toUpperCase();
              return (
                <div key={conn.connection_id} style={{ ...S.card, display: 'flex', alignItems: 'center', gap: 14 }}>
                  <Link to={`/profile/${otherId}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    <div style={S.bigAvatar}>{conn.profile_photo_url ? <img src={conn.profile_photo_url} alt="" style={S.avatarImg} /> : initials}</div>
                  </Link>
                  <div style={{ flex: 1 }}>
                    <Link to={`/profile/${otherId}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      <p style={{ fontSize: 16, fontWeight: 700 }}>{conn.first_name} {conn.last_name}</p>
                    </Link>
                    <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.55)' }}>{conn.headline || 'LinkedIn Member'}</p>
                    <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.42)' }}>{mutualCounts[otherId] || 0} mutual connections</p>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Link to={`/messages?user=${encodeURIComponent(otherId)}`}><button type="button" style={S.secondaryBtn}>Message</button></Link>
                    <button type="button" onClick={() => removeConnection(otherId)} style={S.withdrawBtn}>Remove</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

const S = {
  card: { background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', padding: 16 },
  input: { flex: 1, padding: '10px 12px', border: '1px solid rgba(0,0,0,0.2)', borderRadius: 6, fontFamily: 'inherit' },
  searchBtn: { padding: '10px 16px', borderRadius: 999, border: 'none', background: '#0a66c2', color: '#fff', fontWeight: 700, cursor: 'pointer' },
  personCard: { background: '#fff', border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 14, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 },
  personAvatar: { width: 72, height: 72, borderRadius: '50%', background: '#0a66c2', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, overflow: 'hidden' },
  bigAvatar: { width: 54, height: 54, borderRadius: '50%', background: '#0a66c2', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, overflow: 'hidden', flexShrink: 0 },
  avatarImg: { width: '100%', height: '100%', objectFit: 'cover' },
  secondaryBtn: { padding: '8px 14px', background: '#fff', color: '#0a66c2', border: '1px solid #0a66c2', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  connectBtn: { padding: '8px 14px', background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  messageBtn: { padding: '8px 14px', background: '#fff', color: '#0a66c2', border: '1px solid #0a66c2', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  withdrawBtn: { padding: '8px 14px', background: '#fff', color: '#b42318', border: '1px solid #b42318', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  sentChip: { padding: '8px 12px', background: '#e8f3ff', color: '#0a66c2', borderRadius: 999, fontWeight: 700, fontSize: 13 },
  requestRow: { display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid rgba(0,0,0,0.06)' },
  acceptBtn: { padding: '8px 14px', borderRadius: 999, border: 'none', background: '#0a66c2', color: '#fff', fontWeight: 700, cursor: 'pointer' },
  rejectBtn: { padding: '8px 14px', borderRadius: 999, border: '1px solid rgba(0,0,0,0.2)', background: '#fff', color: 'rgba(0,0,0,0.75)', fontWeight: 700, cursor: 'pointer' },
};
