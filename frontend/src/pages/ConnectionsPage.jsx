import React, { useEffect, useState } from 'react';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

export default function ConnectionsPage() {
  const { user } = useAuth();
  const [connections, setConnections] = useState([]);
  const [searchQuery,  setSearchQuery]  = useState('');
  const [searchResults,setSearchResults]= useState([]);
  const [sent, setSent]                 = useState(new Set());
  const [loading, setLoading]           = useState(true);
  const [searching, setSearching]       = useState(false);

  useEffect(() => { loadConnections(); }, []);

  const loadConnections = async () => {
    setLoading(true);
    try {
      const { data } = await axios.post(`${BASE.messaging}/connections/list`, { user_id: user?.userId });
      setConnections(data.data?.connections || []);
    } catch {}
    setLoading(false);
  };

  const searchPeople = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const { data } = await axios.post(`${BASE.member}/members/search`, {
        keyword: searchQuery.trim(), page_size: 12
      });
      setSearchResults(data.data?.members || []);
      if ((data.data?.members||[]).length === 0) toast('No members found for that search', { icon: '🔍' });
    } catch { toast.error('Search failed'); }
    finally { setSearching(false); }
  };

  const connect = async (memberId, firstName) => {
    try {
      await axios.post(`${BASE.messaging}/connections/request`, {
        receiver_id: memberId,
        message: `Hi ${firstName}, I would like to connect!`
      });
      setSent(prev => new Set([...prev, memberId]));
      toast.success(`Request sent to ${firstName}! 🎉`);
    } catch (err) {
      const msg = err.response?.data?.error?.message || '';
      if (msg.includes('already')) {
        setSent(prev => new Set([...prev, memberId]));
        toast('Request already sent to this person', { icon: '✓' });
      } else {
        toast.error(msg || 'Failed to send request');
      }
    }
  };

  return (
    <div style={{ maxWidth:820, margin:'0 auto' }}>
      <h1 style={{ fontSize:24, fontWeight:700, marginBottom:4 }}>My Network</h1>
      <p style={{ color:'rgba(0,0,0,0.55)', marginBottom:20, fontSize:15 }}>
        {connections.length} connection{connections.length !== 1 ? 's' : ''}
      </p>

      {/* Search card */}
      <div style={S.card}>
        <h3 style={{ fontSize:16, fontWeight:700, marginBottom:12 }}>
          🔍 Find people to connect with
        </h3>
        <div style={{ display:'flex', gap:10, marginBottom: searchResults.length > 0 ? 16 : 0 }}>
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search by name, headline, or skill…"
            style={S.input}
            onKeyDown={e => e.key === 'Enter' && searchPeople()}
          />
          <button onClick={searchPeople} disabled={searching || !searchQuery.trim()} style={S.searchBtn}>
            {searching ? 'Searching…' : 'Search'}
          </button>
        </div>

        {/* Results grid */}
        {searchResults.length > 0 && (
          <div>
            <p style={{ fontSize:13, color:'rgba(0,0,0,0.45)', marginBottom:12 }}>
              {searchResults.length} people found
            </p>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(220px,1fr))', gap:10 }}>
              {searchResults.map(m => {
                const alreadySent = sent.has(m.member_id);
                return (
                  <div key={m.member_id} style={S.personCard}>
                    <div style={S.personAvatar}>{(m.first_name||'?')[0].toUpperCase()}</div>
                    <div style={{ flex:1, minWidth:0, textAlign:'center' }}>
                      <p style={{ fontSize:14, fontWeight:700, marginBottom:2, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                        {m.first_name} {m.last_name}
                      </p>
                      <p style={{ fontSize:11, color:'rgba(0,0,0,0.5)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', marginBottom:4 }}>
                        {m.headline || 'LinkedIn Member'}
                      </p>
                      {m.city && <p style={{ fontSize:11, color:'rgba(0,0,0,0.4)', marginBottom:8 }}>📍 {m.city}</p>}
                    </div>
                    <button
                      onClick={() => !alreadySent && connect(m.member_id, m.first_name)}
                      disabled={alreadySent}
                      style={{ ...S.connectBtn, ...(alreadySent ? S.sentBtn : {}) }}>
                      {alreadySent ? '✓ Sent' : '+ Connect'}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Connections list */}
      <div style={{ marginTop:8 }}>
        <h3 style={{ fontSize:16, fontWeight:700, marginBottom:12, paddingLeft:4 }}>
          Connections ({connections.length})
        </h3>

        {loading ? (
          <div style={{ ...S.card, padding:40, textAlign:'center', color:'rgba(0,0,0,0.4)' }}>Loading…</div>
        ) : connections.length === 0 ? (
          <div style={{ ...S.card, padding:52, textAlign:'center' }}>
            <div style={{ fontSize:52, marginBottom:12 }}>🤝</div>
            <p style={{ fontSize:18, fontWeight:700, marginBottom:8 }}>No connections yet</p>
            <p style={{ color:'rgba(0,0,0,0.55)', fontSize:15 }}>
              Search for people above, then click + Connect to send a request.
            </p>
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {connections.map((conn, i) => (
              <div key={i} style={{ ...S.card, display:'flex', alignItems:'center', gap:14, padding:'14px 18px' }}>
                <div style={S.bigAvatar}>
                  {(conn.first_name || conn.user_id || 'U')[0].toUpperCase()}
                </div>
                <div style={{ flex:1 }}>
                  <p style={{ fontSize:16, fontWeight:700 }}>
                    {conn.first_name ? `${conn.first_name} ${conn.last_name || ''}` : conn.user_id}
                  </p>
                  <p style={{ fontSize:13, color:'rgba(0,0,0,0.5)' }}>
                    Connected {new Date(conn.connected_at).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})}
                  </p>
                </div>
                <button onClick={() => window.location.href='/messages'} style={S.msgBtn}>
                  💬 Message
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const S = {
  card:       { background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.1)', padding:'18px 20px', marginBottom:10 },
  input:      { flex:1, padding:'11px 14px', border:'1.5px solid rgba(0,0,0,0.25)', borderRadius:4, fontSize:15, fontFamily:'inherit', outline:'none' },
  searchBtn:  { padding:'11px 24px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:4, fontSize:15, fontWeight:700, cursor:'pointer', fontFamily:'inherit', whiteSpace:'nowrap' },
  personCard: { display:'flex', flexDirection:'column', alignItems:'center', gap:8, padding:'16px 12px', background:'#f8f9fa', border:'1px solid rgba(0,0,0,0.08)', borderRadius:8 },
  personAvatar: { width:56, height:56, borderRadius:'50%', background:'linear-gradient(135deg,#0a66c2,#7c3aed)', color:'#fff', fontSize:22, fontWeight:800, display:'flex', alignItems:'center', justifyContent:'center' },
  connectBtn: { padding:'7px 20px', border:'1.5px solid #0a66c2', borderRadius:20, background:'#fff', color:'#0a66c2', fontSize:13, fontWeight:700, cursor:'pointer', fontFamily:'inherit', width:'100%', textAlign:'center' },
  sentBtn:    { background:'#f0f0f0', color:'rgba(0,0,0,0.4)', borderColor:'rgba(0,0,0,0.15)', cursor:'default' },
  bigAvatar:  { width:52, height:52, borderRadius:'50%', background:'linear-gradient(135deg,#0a66c2,#004182)', color:'#fff', fontSize:20, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
  msgBtn:     { padding:'7px 18px', border:'1.5px solid #0a66c2', borderRadius:20, background:'#fff', color:'#0a66c2', fontSize:14, fontWeight:700, cursor:'pointer', fontFamily:'inherit' },
};
