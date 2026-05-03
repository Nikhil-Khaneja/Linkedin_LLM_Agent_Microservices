import React, { useState, useEffect, useRef } from 'react';
import { Outlet, NavLink, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import BASE from '../config/api';

const HomeIcon  = () => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M23 9v2h-2v7a3 3 0 01-3 3h-4v-6h-4v6H6a3 3 0 01-3-3v-7H1V9l11-7z"/></svg>;
const JobIcon   = () => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M17 6V5a3 3 0 00-3-3h-4a3 3 0 00-3 3v1H2v4a3 3 0 003 3h14a3 3 0 003-3V6h-5zm-8-1a1 1 0 011-1h4a1 1 0 011 1v1H9V5zm-2 9v6h2v-5h6v5h2v-6H7z"/></svg>;
const MsgIcon   = () => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M16 4H8a5 5 0 00-5 5v4a5 5 0 005 5h.5l3.5 3 3.5-3H16a5 5 0 005-5V9a5 5 0 00-5-5z"/></svg>;
const BriefIcon = () => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M20 7h-4V5l-2-2h-4L8 5v2H4c-1.1 0-2 .9-2 2v5c0 .75.4 1.43 1 1.8V19c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-3.2c.6-.37 1-1.05 1-1.8V9c0-1.1-.9-2-2-2zm-8-1h4v1h-4V6zm5 14H7v-3h10v3zm2-5H5V9h14v6z"/></svg>;
const NetIcon   = () => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12 16v6M6 16v6M18 16v6M2 9l10-7 10 7v11H2z"/><path d="M9 21v-6h6v6"/></svg>;
const ChartIcon = () => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>;
const AIIcon    = () => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M21 11.18V10a2 2 0 00-.9-1.67L12 3 3.9 8.33A2 2 0 003 10v1.18A3 3 0 001 14v2a3 3 0 002 2.82V20a1 1 0 001 1h1a1 1 0 001-1v-1h12v1a1 1 0 001 1h1a1 1 0 001-1v-1.18A3 3 0 0023 16v-2a3 3 0 00-2-2.82z"/></svg>;
const BellIcon  = () => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M12 22a2 2 0 002-2H10a2 2 0 002 2zm6-6V11a6 6 0 00-5-5.91V4a1 1 0 00-2 0v1.09A6 6 0 006 11v5l-2 2v1h16v-1l-2-2z"/></svg>;

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch]           = useState('');
  const [dropResults, setDropResults] = useState(null);
  const [showDrop, setShowDrop]       = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [showNotif, setShowNotif]     = useState(false);
  const [unread, setUnread]           = useState(0);
  const [searching, setSearching]     = useState(false);
  const searchRef = useRef(null);
  const notifRef  = useRef(null);
  const searchTimer = useRef(null);

  const initial = ((user?.email || 'U')[0]).toUpperCase();
  const photo   = localStorage.getItem(`photo_${user?.principalId || user?.userId}`);
  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
  const currentId = user?.principalId || user?.userId;

  const normalizeNotificationTarget = (notification) => {
    if (!notification) return '/notifications';
    const raw = notification.target_url || '';
    if (notification.type === 'message.received' && notification.data?.thread_id) return `/messages?thread=${encodeURIComponent(notification.data.thread_id)}`;
    if ((notification.type === 'profile.viewed' || notification.type === 'connection.accepted') && notification.actor_id) return `/profile/${notification.actor_id}`;
    if (raw) return raw;
    if (notification.type && notification.type.startsWith('connection.')) return '/connections';
    if (notification.type === 'candidate.selected' || notification.type === 'application.status.updated') return '/applications';
    return '/notifications';
  };

  const handleNotificationClick = async (notification) => {
    try {
      if (notification?.notification_id && notification?.unread) {
        await axios.post(`${BASE.member}/members/notifications/markRead`, { notification_id: notification.notification_id }, authCfg);
      }
    } catch {}
    setNotifications(prev => prev.map(n => n.notification_id === notification?.notification_id ? { ...n, unread: false } : n));
    setUnread(prev => Math.max(0, prev - (notification?.unread ? 1 : 0)));
    setShowNotif(false);
    navigate(normalizeNotificationTarget(notification));
  };

  useEffect(() => {
    const handler = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) setShowDrop(false);
      if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotif(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    if (!token || !currentId) return;
    const loadNotifications = async () => {
      try {
        const { data } = await axios.post(`${BASE.member}/members/notifications/list`, { page_size: 10 }, authCfg);
        const items = data?.data?.items || [];
        setNotifications(items.map((n, idx) => ({
          id: n.notification_id || idx,
          notification_id: n.notification_id || idx,
          icon: n.type === 'profile.viewed' ? '👀' : n.type === 'connection.requested' ? '🤝' : n.type === 'application.status.updated' ? '📄' : n.type === 'candidate.selected' ? '⭐' : n.type === 'message.received' ? '💬' : '🔔',
          text: n.body || n.title || 'Notification',
          time: n.created_at ? new Date(n.created_at).toLocaleString() : '',
          unread: !n.is_read,
          type: n.type,
          actor_id: n.actor_id,
          data: n.data || {},
          target_url: n.target_url || '',
        })));
        setUnread(items.filter((n) => !n.is_read).length);
      } catch {
        setNotifications([]);
        setUnread(0);
      }
    };
    loadNotifications();
    const timer = setInterval(loadNotifications, 10000);
    return () => clearInterval(timer);
  }, [token, currentId]);

  // Debounced live search
  const handleSearch = (val) => {
    setSearch(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (val.length < 2) { setShowDrop(false); setDropResults(null); return; }
    setSearching(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const [jobsRes, membersRes] = await Promise.allSettled([
          axios.post(`${BASE.job}/jobs/search`,       { keyword:val, page_size:5 }, authCfg),
          axios.post(`${BASE.member}/members/search`, { keyword:val, page_size:3, media_public_base: BASE.member }, authCfg),
        ]);
        const jobs    = jobsRes.status    === 'fulfilled' ? jobsRes.value.data.data?.items || [] : [];
        const memberItems = membersRes.status === 'fulfilled' ? membersRes.value.data.data?.items || [] : [];
        const members = memberItems.filter(m => m.member_id !== (user?.principalId || user?.userId) && m.email !== user?.email);
        // Extract unique companies from jobs
        const seen = new Set();
        const companies = [];
        jobs.forEach(j => { if (j.company_name && !seen.has(j.company_name)) { seen.add(j.company_name); companies.push(j); }});
        setDropResults({ jobs: jobs.slice(0,4), members: members.slice(0,3), companies: companies.slice(0,3) });
        setShowDrop(true);
      } catch {}
      finally { setSearching(false); }
    }, 300);
  };

  const goSearch = () => {
    if (search.trim()) { navigate(`/jobs?q=${encodeURIComponent(search)}`); setShowDrop(false); }
  };

  const memberNav = [
    { to:'/',            label:'Home',      icon:<HomeIcon /> },
    { to:'/jobs',        label:'Jobs',      icon:<JobIcon /> },
    { to:'/applications',label:'My Jobs',   icon:<BriefIcon /> },
    { to:'/analytics',   label:'Analytics', icon:<ChartIcon /> },
    { to:'/connections', label:'Network',   icon:<NetIcon /> },
    { to:'/messages',    label:'Messaging', icon:<MsgIcon /> },
  ];
  const recruiterNav = [
    { to:'/ai',        label:'Home',      icon:<HomeIcon /> },
    { to:'/recruiter', label:'Manage',    icon:<BriefIcon /> },
    { to:'/ai',        label:'AI Copilot',icon:<AIIcon /> },
    { to:'/analytics', label:'Analytics', icon:<ChartIcon /> },
    { to:'/connections', label:'Network', icon:<NetIcon /> },
    { to:'/messages',  label:'Messaging', icon:<MsgIcon /> },
  ];
  const navItems = user?.userType === 'recruiter' ? recruiterNav : memberNav;
  const defaultHome = user?.userType === 'recruiter' ? '/ai' : '/';

  return (
    <div style={{ minHeight:'100vh', background:'#f3f2ef' }}>
      <header style={S.header}>
        <div style={S.inner}>
          {/* LinkedIn logo */}
          <Link to={defaultHome} style={{ display:'flex', alignItems:'center', flexShrink:0 }}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 34 34" width="40" height="40">
              <path fill="#0a66c2" d="M34 2.5v29A2.5 2.5 0 0131.5 34h-29A2.5 2.5 0 010 31.5v-29A2.5 2.5 0 012.5 0h29A2.5 2.5 0 0134 2.5z"/>
              <path fill="#fff" d="M7.5 12h4v14h-4zm2-6.5a2.5 2.5 0 110 5 2.5 2.5 0 010-5zm6 6.5h3.8v1.9h.1c.5-1 1.8-2.1 3.7-2.1 4 0 4.7 2.6 4.7 6v7.2h-4v-6.4c0-1.5 0-3.4-2.1-3.4s-2.4 1.6-2.4 3.3v6.5h-4V12z"/>
            </svg>
          </Link>

          {/* ── Live Search ── */}
          <div ref={searchRef} style={{ position:'relative', flexShrink:0 }}>
            <div style={S.searchBox}>
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="#666" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
              <input style={S.searchInput} placeholder="Search jobs, people, companies…"
                value={search} onChange={e => handleSearch(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && goSearch()}
                onFocus={() => dropResults && setShowDrop(true)}
              />
              {search && <button onClick={() => { setSearch(''); setShowDrop(false); setDropResults(null); }}
                style={{ background:'none', border:'none', cursor:'pointer', color:'#999', fontSize:14, padding:0, lineHeight:1 }}>✕</button>}
            </div>

            {showDrop && dropResults && (
              <div style={S.dropdown}>
                {/* Companies */}
                {dropResults.companies.length > 0 && <>
                  <div style={S.dSection}>🏢 Companies</div>
                  {dropResults.companies.map(c => (
                    <div key={c.company_name} style={S.dItem}
                      onClick={() => { navigate(`/jobs?q=${encodeURIComponent(c.company_name)}`); setShowDrop(false); setSearch(''); }}>
                      <div style={{ ...S.dAvatar, background:'#7c3aed' }}>{c.company_name[0]}</div>
                      <div>
                        <p style={S.dTitle}>{c.company_name}</p>
                        <p style={S.dSub}>{c.company_industry || 'Company'} · See all jobs</p>
                      </div>
                    </div>
                  ))}
                </>}
                {/* Jobs */}
                {dropResults.jobs.length > 0 && <>
                  <div style={S.dSection}>💼 Jobs</div>
                  {dropResults.jobs.map(j => (
                    <div key={j.job_id} style={S.dItem}
                      onClick={() => { navigate(`/jobs/${j.job_id}`); setShowDrop(false); setSearch(''); }}>
                      <div style={S.dAvatar}>{(j.company_name||'J')[0]}</div>
                      <div>
                        <p style={S.dTitle}>{j.title}</p>
                        <p style={S.dSub}>{j.company_name} · {j.location||j.city||'Remote'}</p>
                      </div>
                    </div>
                  ))}
                </>}
                {/* People */}
                {dropResults.members.length > 0 && <>
                  <div style={S.dSection}>👤 People</div>
                  {dropResults.members.map(m => (
                    <div key={m.member_id} style={S.dItem}
                      onClick={() => { navigate(`/profile/${m.member_id}`); setShowDrop(false); setSearch(''); }}>
                      <div style={{ ...S.dAvatar, background:'#057642' }}>{(m.first_name||'?')[0]}</div>
                      <div>
                        <p style={S.dTitle}>{`${m.first_name || ''} ${m.last_name || ''}`.trim() || m.member_id}</p>
                        <p style={S.dSub}>{m.headline || 'LinkedIn Member'} {m.location ? `· ${m.location}` : ''}</p>
                      </div>
                    </div>
                  ))}
                </>}
                {/* See all */}
                <div style={{ ...S.dItem, borderTop:'1px solid rgba(0,0,0,0.08)', justifyContent:'center' }}
                  onClick={goSearch}>
                  <p style={{ fontSize:14, fontWeight:700, color:'#0a66c2' }}>See all results for "{search}" →</p>
                </div>
              </div>
            )}
          </div>

          {/* ── Nav links ── */}
          <nav style={S.nav}>
            {navItems.map(item => (
              <NavLink key={item.to} to={item.to} end={item.to === '/'}
                style={({ isActive }) => ({ ...S.navItem, ...(isActive ? S.navActive : {}) })}>
                <span style={{ lineHeight:1, display:'flex' }}>{item.icon}</span>
                <span style={S.navLabel}>{item.label}</span>
              </NavLink>
            ))}

            {/* ── Notifications ── */}
            <div ref={notifRef} style={{ position:'relative', display:'flex' }}>
              <button onClick={() => { setShowNotif(!showNotif); }}
                style={{ ...S.navItem, cursor:'pointer' }}>
                <span style={{ position:'relative', lineHeight:1, display:'flex' }}>
                  <BellIcon />
                  {unread > 0 && <span style={S.badge}>{unread}</span>}
                </span>
                <span style={S.navLabel}>Notifications</span>
              </button>

              {showNotif && (
                <div style={S.notifBox}>
                  <div style={{ padding:'14px 16px 10px', borderBottom:'1px solid rgba(0,0,0,0.08)', display:'flex', justifyContent:'space-between' }}>
                    <h3 style={{ fontSize:16, fontWeight:700 }}>Notifications</h3>
                    <button onClick={() => setShowNotif(false)} style={{ background:'none', border:'none', cursor:'pointer', fontSize:18, color:'#666' }}>✕</button>
                  </div>
                  {notifications.map(n => (
                    <button key={n.id} type="button" style={{ ...S.notifItem, background: n.unread ? '#f0f7ff' : '#fff', width: '100%', textAlign: 'left', fontFamily: 'inherit' }}
                      onClick={() => handleNotificationClick(n)}>
                      <span style={{ fontSize:24, flexShrink:0 }}>{n.icon}</span>
                      <div style={{ flex:1 }}>
                        <p style={{ fontSize:13, color:'rgba(0,0,0,0.85)', lineHeight:1.45, marginBottom:2 }}>{n.text}</p>
                        <p style={{ fontSize:11, color:'rgba(0,0,0,0.4)' }}>{n.time}</p>
                      </div>
                      {n.unread && <div style={{ width:8, height:8, borderRadius:'50%', background:'#0a66c2', flexShrink:0, marginTop:3 }} />}
                    </button>
                  ))}
                  <div style={{ padding:'10px 16px', textAlign:'center', borderTop:'1px solid rgba(0,0,0,0.06)' }}>
                    <button onClick={() => { setShowNotif(false); navigate('/notifications'); }} style={{ background:'none', border:'none', color:'#0a66c2', fontWeight:700, cursor:'pointer', fontFamily:'inherit' }}>View all notifications</button>
                  </div>
                </div>
              )}
            </div>

            {/* ── Me (profile) ── */}
            <NavLink to={user?.userType === 'recruiter' ? '/recruiter' : '/profile'}
              style={({ isActive }) => ({ ...S.navItem, ...(isActive ? S.navActive : {}) })}>
              <div style={S.meAvatar}>
                {photo
                  ? <img src={photo} alt="" style={{ width:'100%', height:'100%', objectFit:'cover', borderRadius:'50%' }} />
                  : initial
                }
              </div>
              <span style={S.navLabel}>Me ▾</span>
            </NavLink>

            <div style={S.divider} />
            <button onClick={async () => { await logout(); navigate('/login'); }} style={S.signout}>
              Sign out
            </button>
          </nav>
        </div>
      </header>

      <main style={{ maxWidth:1128, margin:'0 auto', padding:'24px 8px' }}>
        <Outlet />
      </main>
    </div>
  );
}

const S = {
  header:      { background:'#fff', borderBottom:'1px solid rgba(0,0,0,0.12)', position:'sticky', top:0, zIndex:200, boxShadow:'0 1px 3px rgba(0,0,0,0.07)' },
  inner:       { maxWidth:1128, margin:'0 auto', height:56, display:'flex', alignItems:'stretch', padding:'0 12px', gap:8 },
  searchBox:   { display:'flex', alignItems:'center', gap:8, background:'#eef3f8', borderRadius:4, padding:'0 12px', width:300, height:38, alignSelf:'center' },
  searchInput: { background:'transparent', border:'none', outline:'none', fontSize:14, color:'#000', width:'100%', fontFamily:'inherit' },
  dropdown:    { position:'absolute', top:42, left:0, width:380, background:'#fff', borderRadius:8, boxShadow:'0 4px 24px rgba(0,0,0,0.16)', zIndex:1000, maxHeight:500, overflowY:'auto', border:'1px solid rgba(0,0,0,0.08)' },
  dSection:    { fontSize:11, fontWeight:700, color:'rgba(0,0,0,0.45)', padding:'10px 16px 4px', textTransform:'uppercase', letterSpacing:'0.07em', background:'#fafafa' },
  dItem:       { display:'flex', gap:12, alignItems:'center', padding:'10px 16px', cursor:'pointer', borderBottom:'1px solid rgba(0,0,0,0.04)', transition:'background 0.1s' },
  dAvatar:     { width:38, height:38, borderRadius:4, background:'#0a66c2', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize:15, fontWeight:700, flexShrink:0 },
  dTitle:      { fontSize:14, fontWeight:600, color:'rgba(0,0,0,0.9)', marginBottom:2 },
  dSub:        { fontSize:12, color:'rgba(0,0,0,0.5)' },
  nav:         { display:'flex', alignItems:'stretch', marginLeft:'auto' },
  navItem:     { display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:2, padding:'0 10px', minWidth:62, color:'rgba(0,0,0,0.55)', textDecoration:'none', borderBottom:'2px solid transparent', background:'none', border:'none', fontFamily:'inherit', cursor:'pointer', position:'relative' },
  navActive:   { color:'rgba(0,0,0,0.9)', borderBottomColor:'rgba(0,0,0,0.9)' },
  navLabel:    { fontSize:11, whiteSpace:'nowrap' },
  meAvatar:    { width:24, height:24, borderRadius:'50%', background:'#0a66c2', color:'#fff', fontSize:11, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', overflow:'hidden' },
  divider:     { width:1, background:'rgba(0,0,0,0.12)', margin:'10px 6px', alignSelf:'stretch' },
  signout:     { background:'none', border:'none', color:'rgba(0,0,0,0.6)', fontSize:13, padding:'0 8px', cursor:'pointer', fontFamily:'inherit', alignSelf:'center' },
  badge:       { position:'absolute', top:-5, right:-5, background:'#cc1016', color:'#fff', borderRadius:'50%', minWidth:16, height:16, fontSize:9, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', border:'1.5px solid #fff', padding:'0 2px' },
  notifBox:    { position:'absolute', top:54, right:-60, width:360, background:'#fff', borderRadius:8, boxShadow:'0 4px 24px rgba(0,0,0,0.16)', zIndex:1000, border:'1px solid rgba(0,0,0,0.08)', maxHeight:440, overflowY:'auto' },
  notifItem:   { display:'flex', gap:12, alignItems:'flex-start', padding:'12px 16px', cursor:'pointer', borderBottom:'1px solid rgba(0,0,0,0.05)' },
};
