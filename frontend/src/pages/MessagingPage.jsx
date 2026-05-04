import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';

export default function MessagingPage() {
  const { user } = useAuth();
  const currentId = user?.principalId || user?.userId;
  const [threads, setThreads] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [connections, setConnections] = useState([]);
  const [query, setQuery] = useState('');
  const [connectionSearch, setConnectionSearch] = useState([]);
  const [searchingConnections, setSearchingConnections] = useState(false);
  const messagesRef = useRef(null);
  const stickToBottomRef = useRef(true);
  const prevThreadRef = useRef('');
  const [searchParams, setSearchParams] = useSearchParams();
  const targetUserId = searchParams.get('user') || '';
  const targetThreadId = searchParams.get('thread') || '';
  const draftText = searchParams.get('draft') || '';
  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  useEffect(() => {
    if (!currentId || !token) return;
    loadThreads();
    loadConnections();
  }, [currentId, token, targetUserId, targetThreadId]);

  useEffect(() => {
    const threadChanged = prevThreadRef.current !== (active?.thread_id || '');
    if (threadChanged) {
      prevThreadRef.current = active?.thread_id || '';
      stickToBottomRef.current = true;
    }
    if (!stickToBottomRef.current) return;
    const el = messagesRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, active?.thread_id]);

  useEffect(() => {
    if (draftText && !text) setText(draftText);
  }, [draftText]);

  useEffect(() => {
    if (!currentId || !active?.thread_id || !token) return undefined;
    const timer = setInterval(() => {
      loadMessages(active.thread_id, false);
      loadThreads(false);
    }, 2500);
    return () => clearInterval(timer);
  }, [currentId, active?.thread_id, token]);

  const activeMessages = useMemo(
    () => ([...messages].sort((a, b) => {
      const left = String(a.sent_at || a.created_at || '');
      const right = String(b.sent_at || b.created_at || '');
      return left.localeCompare(right);
    })),
    [messages],
  );
  const currentUserIds = useMemo(
    () => new Set([user?.principalId, user?.userId, currentId].filter(Boolean).map((v) => String(v))),
    [user?.principalId, user?.userId, currentId],
  );

  const resolveUserPreview = async (userId) => {
    if (!userId) return { other_display_name: 'Unknown', other_profile_photo_url: null, other_headline: '' };

    const recruiterFirst = String(userId).startsWith('rec_');

    const fetchRecruiterPreview = async () => {
      const { data } = await axios.post(`${BASE.recruiter}/recruiters/publicGet`, { recruiter_id: userId }, authCfg);
      const recruiter = data?.data?.recruiter;
      if (!recruiter) throw new Error('recruiter_not_found');
      return {
        other_display_name: recruiter?.name || userId,
        other_profile_photo_url: recruiter?.profile_photo_url || null,
        other_headline: recruiter?.company_name ? `${recruiter?.headline || 'Recruiter'} · ${recruiter.company_name}` : (recruiter?.headline || 'Recruiter'),
      };
    };

    const fetchMemberPreview = async () => {
      const { data } = await axios.post(`${BASE.member}/members/get`, { member_id: userId, media_public_base: BASE.member }, authCfg);
      const profile = data?.data?.profile;
      if (!profile) throw new Error('member_not_found');
      return {
        other_display_name: [profile?.first_name, profile?.last_name].filter(Boolean).join(' ') || userId,
        other_profile_photo_url: profile?.profile_photo_url || null,
        other_headline: profile?.headline || '',
      };
    };

    try {
      return recruiterFirst ? await fetchRecruiterPreview() : await fetchMemberPreview();
    } catch {
      try {
        return recruiterFirst ? await fetchMemberPreview() : await fetchRecruiterPreview();
      } catch {
        return { other_display_name: userId, other_profile_photo_url: null, other_headline: '' };
      }
    }
  };

  const enrichThreadPreviews = async (items) => Promise.all((items || []).map(async (item) => {
    const isRecruiter = String(item?.other_participant || '').startsWith('rec_');
    const headline = String(item?.other_headline || '').trim();
    const needsPreview = !item?.other_display_name
      || item.other_display_name === item.other_participant
      || item.other_display_name === 'Unknown'
      || item.other_display_name === 'LinkedIn Member'
      || (isRecruiter && (!headline || headline === 'Recruiter' || headline === 'admin' || !headline.includes('·')));
    if (!needsPreview || !item?.other_participant) return item;
    const preview = await resolveUserPreview(item.other_participant);
    return { ...item, ...preview };
  }));

  const displayConnectionName = (conn) => {
    if (!conn) return '';
    const combined = [conn.first_name, conn.last_name].filter(Boolean).join(' ').trim();
    return combined || conn.display_name || conn.other_display_name || conn.other_user_id || conn.user_id || '';
  };

  const normalizeConnectionUserId = (conn) => conn?.other_user_id || conn?.user_id || conn?.member_id || '';

  const loadConnections = async () => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/connections/list`, { user_id: currentId }, authCfg);
      const items = Array.isArray(data?.data?.items) ? data.data.items : [];
      setConnections(items);
      setConnectionSearch(items.slice(0, 12));
    } catch {
      setConnections([]);
      setConnectionSearch([]);
    }
  };

  const loadThreads = async (resolveTarget = true) => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/threads/byUser`, { user_id: currentId }, authCfg);
      const rawItems = Array.isArray(data?.data?.items) ? data.data.items : [];
      const items = await enrichThreadPreviews(rawItems);
      setThreads(items);
      if (active?.thread_id) {
        const refreshed = items.find((item) => item.thread_id === active.thread_id);
        if (refreshed) setActive(refreshed);
      }
      if (!resolveTarget) return;
      if (targetThreadId) {
        const existing = items.find((item) => item.thread_id === targetThreadId);
        if (existing) {
          if (active?.thread_id !== existing.thread_id) await openThread(existing);
        } else {
          await openThreadById(targetThreadId);
        }
      } else if (targetUserId) {
        const existing = items.find((item) => item.other_participant === targetUserId);
        if (existing) {
          if (active?.thread_id !== existing.thread_id) await openThread(existing);
        } else {
          await createOrOpenThread(targetUserId, false);
        }
      } else if (!active && items[0]) {
        await openThread(items[0]);
      }
    } catch {
      setThreads([]);
    }
  };

  const openThreadById = async (threadId) => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/threads/get`, { thread_id: threadId }, authCfg);
      const thread = data?.data?.thread;
      if (!thread) return;
      const otherId = (thread.participant_ids || []).find((id) => id !== currentId);
      const preview = await resolveUserPreview(otherId);
      const threadObj = {
        thread_id: thread.thread_id,
        other_participant: otherId,
        other_display_name: preview.other_display_name,
        other_profile_photo_url: preview.other_profile_photo_url,
        other_headline: preview.other_headline,
      };
      setThreads((prev) => prev.some((item) => item.thread_id === thread.thread_id) ? prev : [threadObj, ...prev]);
      await openThread(threadObj);
    } catch {
      toast.error('Could not open that conversation');
    }
  };

  const loadMessages = async (threadId, resetUnread = true) => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/messages/list`, { thread_id: threadId, page_size: 100 }, authCfg);
      setMessages(Array.isArray(data?.data?.items) ? data.data.items : []);
      if (resetUnread) {
        setThreads((prev) => prev.map((thread) => (thread.thread_id === threadId ? { ...thread, unread_count: 0 } : thread)));
      }
    } catch {
      toast.error('Failed to load messages');
    }
  };

  const openThread = async (thread) => {
    setActive(thread);
    await loadMessages(thread.thread_id, true);
  };

  const send = async () => {
    if (!text.trim() || !active) return;
    setSending(true);
    stickToBottomRef.current = true;
    try {
      const optimistic = { sender_id: currentId, text: text.trim(), sent_at: new Date().toISOString() };
      setMessages((prev) => [...prev, optimistic]);
      const clientMessageId = `web-${Date.now()}`;
      await axios.post(`${BASE.messaging}/messages/send`, { thread_id: active.thread_id, text: text.trim(), client_message_id: clientMessageId }, authCfg);
      setText('');
      await loadMessages(active.thread_id, false);
      await loadThreads(false);
    } catch {
      toast.error('Failed to send');
    } finally {
      setSending(false);
    }
  };

  const createOrOpenThread = async (otherUserId, clearInput = true) => {
    if (!otherUserId?.trim() || !currentId) return;
    try {
      const trimmed = otherUserId.trim();
      const { data } = await axios.post(`${BASE.messaging}/threads/open`, { participant_ids: [currentId, trimmed] }, authCfg);
      const threadId = data?.data?.thread_id;
      const preview = await resolveUserPreview(trimmed);
      const threadObj = {
        thread_id: threadId,
        other_participant: trimmed,
        other_display_name: preview.other_display_name,
        other_profile_photo_url: preview.other_profile_photo_url,
        other_headline: preview.other_headline,
      };
      if (clearInput) setQuery('');
      setThreads((prev) => prev.some((item) => item.thread_id === threadId) ? prev : [threadObj, ...prev]);
      await openThread(threadObj);
      if (draftText) setText(draftText);
      setSearchParams({});
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Could not open thread');
    }
  };

  const searchConnections = () => {
    const q = query.trim().toLowerCase();
    if (!q) {
      setConnectionSearch(connections.slice(0, 12));
      return;
    }
    setSearchingConnections(true);
    const filtered = connections.filter((conn) => {
      const hay = [
        displayConnectionName(conn),
        conn?.headline || '',
        normalizeConnectionUserId(conn),
      ]
        .join(' ')
        .toLowerCase();
      return hay.includes(q);
    });
    setConnectionSearch(filtered);
    setSearchingConnections(false);
  };

  const getFilteredConnections = () => {
    const q = query.trim().toLowerCase();
    if (!q) return connections.slice(0, 12);
    return connections.filter((conn) => {
      const hay = [
        displayConnectionName(conn),
        conn?.headline || '',
        normalizeConnectionUserId(conn),
      ]
        .join(' ')
        .toLowerCase();
      return hay.includes(q);
    });
  };

  const displayedConnections = useMemo(() => {
    if (query.trim()) return getFilteredConnections().slice(0, 50);
    if (connectionSearch.length) return connectionSearch.slice(0, 50);
    return connections.slice(0, 50);
  }, [connections, query, connectionSearch]);

  const isMessageMine = (message) => {
    const sender = String(
      message?.sender_id
      || message?.sender_user_id
      || message?.sender_principal_id
      || '',
    );
    return !!sender && currentUserIds.has(sender);
  };

  const handleMessagesScroll = () => {
    const el = messagesRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottomRef.current = distanceFromBottom < 80;
  };

  const searchOpen = query.trim().length > 0;

  return (
    <div style={S.page}>
      <div style={S.sidebar}>
        <div style={S.sideHeader}><h2 style={{ fontSize: 20, fontWeight: 600 }}>Messaging</h2></div>
        <div style={S.newMsg}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search connections..."
            style={S.newInput}
            onKeyDown={(e) => e.key === 'Enter' && searchConnections()}
          />
          <button onClick={searchConnections} style={S.searchBtn}>🔍</button>
        </div>
        {searchOpen && (
          <div style={S.connectionResults}>
            <p style={S.connectionResultMeta}>
              {searchingConnections ? 'Searching...' : `${displayedConnections.length} connection${displayedConnections.length === 1 ? '' : 's'} found`}
            </p>
            {displayedConnections.length === 0 ? (
              <p style={{ padding: '8px 16px 14px', fontSize: 13, color: 'rgba(0,0,0,0.5)' }}>No matching connections</p>
            ) : (
              displayedConnections.map((conn) => {
                const userId = normalizeConnectionUserId(conn);
                if (!userId) return null;
                return (
                  <button
                    type="button"
                    key={`conn-${userId}`}
                    onClick={() => createOrOpenThread(userId, true)}
                    style={S.connectionResultBtn}
                  >
                    <span style={S.connectionResultName}>{displayConnectionName(conn) || userId}</span>
                    <span style={S.connectionResultSub}>{conn?.headline || userId}</span>
                  </button>
                );
              })
            )}
          </div>
        )}
        <div style={S.threadList}>
          <p style={S.sectionMeta}>Conversations</p>
          {threads.length === 0 ? (
            <p style={{ padding: 24, color: 'rgba(0,0,0,0.45)', fontSize: 14, textAlign: 'center' }}>No conversations yet</p>
          ) : threads.map((thread) => (
            <div key={thread.thread_id} onClick={() => openThread(thread)} style={{ ...S.threadItem, background: active?.thread_id === thread.thread_id ? '#eef3f8' : 'transparent' }}>
              <div style={S.threadAvatar}>{thread.other_profile_photo_url ? <img src={thread.other_profile_photo_url} alt="" style={S.avatarImg} /> : (thread.other_display_name || '?')[0]}</div>
              <div style={{ minWidth: 0 }}>
                <p style={S.threadTitle}>{thread.other_display_name || thread.other_participant || `Thread ${thread.thread_id}`}</p>
                <p style={S.threadSubtitle}>{thread.other_headline || (thread.latest_message_at ? new Date(thread.latest_message_at).toLocaleString() : '')}</p>
              </div>
              {thread.unread_count > 0 && <span style={S.unread}>{thread.unread_count}</span>}
            </div>
          ))}
        </div>
      </div>

      <div style={S.chat}>
        {active ? (
          <>
            <div style={S.chatHeader}>
              <h3 style={{ fontSize: 16, fontWeight: 600 }}>{active.other_display_name || active.other_participant || `Thread ${active.thread_id}`}</h3>
              {(active.other_headline || active.other_participant) && (
                <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)', marginTop: 4 }}>
                  {active.other_headline || active.other_participant}
                </p>
              )}
            </div>
            <div ref={messagesRef} style={S.messages} onScroll={handleMessagesScroll}>
              {activeMessages.map((message, idx) => {
                const mine = isMessageMine(message);
                return (
                  <div key={`${message.message_id || idx}-${message.sent_at || idx}`} style={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start', marginBottom: 8 }}>
                    <div style={{ ...S.bubble, background: mine ? '#0a66c2' : '#f3f2ef', color: mine ? '#fff' : 'rgba(0,0,0,0.9)', borderRadius: mine ? '18px 18px 4px 18px' : '18px 18px 18px 4px' }}>
                      <p style={{ fontSize: 15, lineHeight: 1.5 }}>{message.text}</p>
                      <p style={{ fontSize: 11, opacity: 0.7, marginTop: 3, textAlign: 'right' }}>{new Date(message.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={S.composer}>
              <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a message…" onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} style={S.composeInput} />
              <button onClick={send} disabled={sending || !text.trim()} style={S.sendBtn}>{sending ? '…' : '➤'}</button>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'rgba(0,0,0,0.5)', gap: 12 }}>
            <span style={{ fontSize: 48 }}>💬</span>
            <p style={{ fontSize: 18, fontWeight: 600 }}>Select a message</p>
            <p style={{ fontSize: 14 }}>Choose from your existing conversations or start a new one.</p>
          </div>
        )}
      </div>
    </div>
  );
}

const S = {
  page: { display: 'grid', gridTemplateColumns: '320px 1fr', height: 'calc(100vh - 130px)', minHeight: 520, background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.08)', overflow: 'hidden' },
  sidebar: { borderRight: '1px solid rgba(0,0,0,0.12)', display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' },
  sideHeader: { padding: '16px 20px', borderBottom: '1px solid rgba(0,0,0,0.08)' },
  newMsg: { padding: '10px 16px', display: 'flex', gap: 8, borderBottom: '1px solid rgba(0,0,0,0.08)' },
  newInput: { flex: 1, padding: '8px 12px', border: '1px solid rgba(0,0,0,0.3)', borderRadius: 4, fontSize: 14, outline: 'none', fontFamily: 'inherit' },
  searchBtn: { width: 36, height: 36, background: '#fff', color: '#0a66c2', border: '1px solid rgba(10,102,194,0.6)', borderRadius: '50%', fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  connectionResults: { maxHeight: 220, overflowY: 'auto', borderBottom: '1px solid rgba(0,0,0,0.08)', flexShrink: 0 },
  sectionMeta: { padding: '8px 16px 2px', fontSize: 11, fontWeight: 700, color: 'rgba(0,0,0,0.45)', textTransform: 'uppercase', letterSpacing: '0.04em' },
  connectionResultMeta: { padding: '8px 16px 4px', fontSize: 12, color: 'rgba(0,0,0,0.5)' },
  connectionResultBtn: { width: '100%', border: 'none', background: '#fff', textAlign: 'left', padding: '8px 16px', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2, borderTop: '1px solid rgba(0,0,0,0.04)' },
  connectionResultName: { fontSize: 13, fontWeight: 700, color: 'rgba(0,0,0,0.85)' },
  connectionResultSub: { fontSize: 12, color: 'rgba(0,0,0,0.55)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
  threadList: { overflowY: 'auto', flex: 1, minHeight: 0 },
  threadItem: { display: 'flex', gap: 12, padding: '12px 16px', cursor: 'pointer', borderBottom: '1px solid rgba(0,0,0,0.06)', alignItems: 'center' },
  threadAvatar: { width: 40, height: 40, borderRadius: '50%', background: '#0a66c2', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0, overflow: 'hidden', fontWeight: 700 },
  avatarImg: { width: '100%', height: '100%', objectFit: 'cover' },
  unread: { background: '#0a66c2', color: '#fff', borderRadius: '50%', padding: '2px 7px', fontSize: 11, fontWeight: 700, marginLeft: 'auto' },
  threadTitle: { fontSize: 15, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
  threadSubtitle: { fontSize: 13, color: 'rgba(0,0,0,0.5)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
  chat: { display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' },
  chatHeader: { padding: '16px 20px', borderBottom: '1px solid rgba(0,0,0,0.08)', flexShrink: 0 },
  // Top-aligned column so overflow scroll works; bottom stickiness handled via scrollTop in effect.
  messages: { flex: 1, minHeight: 0, overflowY: 'auto', WebkitOverflowScrolling: 'touch', padding: '16px 20px', display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', gap: 0 },
  bubble: { maxWidth: '70%', padding: '10px 16px' },
  composer: { padding: '12px 16px', borderTop: '1px solid rgba(0,0,0,0.08)', display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0 },
  composeInput: { flex: 1, padding: '12px 16px', border: '1px solid rgba(0,0,0,0.3)', borderRadius: 24, fontSize: 15, fontFamily: 'inherit', outline: 'none' },
  sendBtn: { width: 44, height: 44, background: '#0a66c2', color: '#fff', border: 'none', borderRadius: '50%', fontSize: 18, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
};
