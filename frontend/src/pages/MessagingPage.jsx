import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

export default function MessagingPage() {
  const { user } = useAuth();
  const [threads, setThreads] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [newUserId, setNewUserId] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => { loadThreads(); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }); }, [messages]);

  const loadThreads = async () => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/threads/byUser`, { user_id: user?.userId });
      setThreads(data.data?.threads || []);
    } catch {}
  };

  const openThread = async (t) => {
    setActive(t);
    try {
      const { data } = await axios.post(`${BASE.messaging}/messages/list`, { thread_id: t.thread_id, page_size: 50 });
      setMessages(data.data?.messages || []);
    } catch { toast.error('Failed to load messages'); }
  };

  const send = async () => {
    if (!text.trim() || !active) return;
    setSending(true);
    try {
      await axios.post(`${BASE.messaging}/messages/send`, { thread_id: active.thread_id, content: text.trim() });
      setMessages(p => [...p, { sender_id: user?.userId, content: text.trim(), sent_at: new Date().toISOString() }]);
      setText('');
    } catch { toast.error('Failed to send'); }
    finally { setSending(false); }
  };

  const newThread = async () => {
    if (!newUserId.trim()) return;
    try {
      const { data } = await axios.post(`${BASE.messaging}/threads/open`, { participant_ids: [user?.userId, newUserId.trim()] });
      setNewUserId('');
      loadThreads();
      openThread({ thread_id: data.data.thread_id });
    } catch { toast.error('Could not open thread'); }
  };

  return (
    <div style={S.page}>
      {/* Sidebar */}
      <div style={S.sidebar}>
        <div style={S.sideHeader}>
          <h2 style={{ fontSize:20, fontWeight:600 }}>Messaging</h2>
        </div>
        <div style={S.newMsg}>
          <input value={newUserId} onChange={e=>setNewUserId(e.target.value)} placeholder="Enter user ID…"
            style={{ flex:1, padding:'8px 12px', border:'1px solid rgba(0,0,0,0.3)', borderRadius:4, fontSize:14, outline:'none', fontFamily:'inherit' }} />
          <button onClick={newThread} style={S.newBtn}>+</button>
        </div>
        <div style={{ overflowY:'auto', flex:1 }}>
          {threads.length === 0
            ? <p style={{ padding:24, color:'rgba(0,0,0,0.45)', fontSize:14, textAlign:'center' }}>No conversations yet</p>
            : threads.map(t => (
              <div key={t.thread_id} onClick={() => openThread(t)}
                style={{ ...S.threadItem, background: active?.thread_id===t.thread_id ? '#eef3f8' : 'transparent' }}>
                <div style={S.threadAvatar}>💬</div>
                <div>
                  <p style={{ fontSize:15, fontWeight:600 }}>Thread …{t.thread_id.slice(-6)}</p>
                  <p style={{ fontSize:13, color:'rgba(0,0,0,0.5)' }}>{new Date(t.last_message_at).toLocaleDateString()}</p>
                </div>
                {t.unread_count > 0 && <span style={S.unread}>{t.unread_count}</span>}
              </div>
            ))
          }
        </div>
      </div>

      {/* Chat */}
      <div style={S.chat}>
        {active ? (
          <>
            <div style={S.chatHeader}>
              <h3 style={{ fontSize:16, fontWeight:600 }}>Thread {active.thread_id.slice(-8)}</h3>
            </div>
            <div style={S.messages}>
              {messages.map((m, i) => {
                const mine = m.sender_id === user?.userId;
                return (
                  <div key={i} style={{ display:'flex', justifyContent: mine?'flex-end':'flex-start', marginBottom:8 }}>
                    <div style={{ ...S.bubble, background: mine?'#0a66c2':'#f3f2ef', color: mine?'#fff':'rgba(0,0,0,0.9)', borderRadius: mine?'18px 18px 4px 18px':'18px 18px 18px 4px' }}>
                      <p style={{ fontSize:15, lineHeight:1.5 }}>{m.content}</p>
                      <p style={{ fontSize:11, opacity:0.7, marginTop:3, textAlign:'right' }}>{new Date(m.sent_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</p>
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>
            <div style={S.composer}>
              <input value={text} onChange={e=>setText(e.target.value)} placeholder="Write a message…"
                onKeyDown={e=>e.key==='Enter'&&!e.shiftKey&&send()}
                style={{ flex:1, padding:'12px 16px', border:'1px solid rgba(0,0,0,0.3)', borderRadius:24, fontSize:15, fontFamily:'inherit', outline:'none' }} />
              <button onClick={send} disabled={sending||!text.trim()} style={S.sendBtn}>
                {sending ? '…' : '➤'}
              </button>
            </div>
          </>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', flex:1, color:'rgba(0,0,0,0.5)', gap:12 }}>
            <span style={{ fontSize:48 }}>💬</span>
            <p style={{ fontSize:18, fontWeight:600 }}>Select a message</p>
            <p style={{ fontSize:14 }}>Choose from your existing conversations or start a new one.</p>
          </div>
        )}
      </div>
    </div>
  );
}

const S = {
  page: { display:'grid', gridTemplateColumns:'320px 1fr', height:'calc(100vh - 100px)', background:'#fff', borderRadius:8, boxShadow:'0 0 0 1px rgba(0,0,0,0.08)', overflow:'hidden' },
  sidebar: { borderRight:'1px solid rgba(0,0,0,0.12)', display:'flex', flexDirection:'column' },
  sideHeader: { padding:'16px 20px', borderBottom:'1px solid rgba(0,0,0,0.08)' },
  newMsg: { padding:'10px 16px', display:'flex', gap:8, borderBottom:'1px solid rgba(0,0,0,0.08)' },
  newBtn: { width:36, height:36, background:'#0a66c2', color:'#fff', border:'none', borderRadius:'50%', fontSize:20, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
  threadItem: { display:'flex', gap:12, padding:'12px 16px', cursor:'pointer', borderBottom:'1px solid rgba(0,0,0,0.06)', alignItems:'center' },
  threadAvatar: { fontSize:28, flexShrink:0 },
  unread: { background:'#0a66c2', color:'#fff', borderRadius:'50%', padding:'2px 7px', fontSize:11, fontWeight:700, marginLeft:'auto' },
  chat: { display:'flex', flexDirection:'column' },
  chatHeader: { padding:'16px 20px', borderBottom:'1px solid rgba(0,0,0,0.08)' },
  messages: { flex:1, overflowY:'auto', padding:'16px 20px', display:'flex', flexDirection:'column' },
  bubble: { maxWidth:'70%', padding:'10px 16px' },
  composer: { padding:'12px 16px', borderTop:'1px solid rgba(0,0,0,0.08)', display:'flex', gap:10, alignItems:'center' },
  sendBtn: { width:44, height:44, background:'#0a66c2', color:'#fff', border:'none', borderRadius:'50%', fontSize:18, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
};
