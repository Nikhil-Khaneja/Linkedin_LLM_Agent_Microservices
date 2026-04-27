import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      const code = err.response?.data?.error?.code;
      const msg  = err.response?.data?.error?.message;
      if (code === 'auth_required' || err.response?.status === 401) {
        setError('The email or password you entered is incorrect. Please try again.');
      } else if (err.response?.status === 404 || msg?.includes('not found') || msg?.includes('exist')) {
        setError('No account found with that email address. Please check your email or join now.');
      } else if (!navigator.onLine) {
        setError('No internet connection. Please check your network and try again.');
      } else {
        setError(msg || 'Something went wrong. Please try again.');
      }
    } finally { setLoading(false); }
  };

  return (
    <div style={S.page}>
      <div style={S.box}>
        {/* LinkedIn logo */}
        <div style={{ textAlign:'center', marginBottom:24 }}>
          <svg viewBox="0 0 34 34" width="52" height="52" xmlns="http://www.w3.org/2000/svg">
            <path fill="#0a66c2" d="M34 2.5v29A2.5 2.5 0 0131.5 34h-29A2.5 2.5 0 010 31.5v-29A2.5 2.5 0 012.5 0h29A2.5 2.5 0 0134 2.5z"/>
            <path fill="#fff" d="M7.5 12h4v14h-4zm2-6.5a2.5 2.5 0 110 5 2.5 2.5 0 010-5zm6 6.5h3.8v1.9h.1c.5-1 1.8-2.1 3.7-2.1 4 0 4.7 2.6 4.7 6v7.2h-4v-6.4c0-1.5 0-3.4-2.1-3.4s-2.4 1.6-2.4 3.3v6.5h-4V12z"/>
          </svg>
        </div>

        <h1 style={S.title}>Sign in</h1>
        <p style={S.sub}>Stay updated on your professional world</p>

        {/* Error box */}
        {error && (
          <div style={S.errBox}>
            <span style={S.errIcon}>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={submit} style={S.form}>
          <div style={S.field}>
            <label style={S.label}>Email</label>
            <input
              type="email" value={email} autoComplete="email"
              onChange={e => { setEmail(e.target.value); setError(''); }}
              style={{ ...S.input, borderColor: error ? '#cc1016' : 'rgba(0,0,0,0.4)' }}
              placeholder="Enter your email" required
            />
          </div>

          <div style={S.field}>
            <label style={S.label}>Password</label>
            <input
              type="password" value={password} autoComplete="current-password"
              onChange={e => { setPassword(e.target.value); setError(''); }}
              style={{ ...S.input, borderColor: error ? '#cc1016' : 'rgba(0,0,0,0.4)' }}
              placeholder="Enter your password" required
            />
          </div>

          <button type="submit" disabled={loading || !email || !password} style={{
            ...S.btn, opacity: loading || !email || !password ? 0.7 : 1
          }}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div style={S.divRow}>
          <div style={S.divLine}/><span style={S.divOr}>or</span><div style={S.divLine}/>
        </div>

        <p style={S.joinTxt}>
          New to LinkedIn DS?{' '}
          <Link to="/register" style={S.joinLink}>Join now</Link>
        </p>
      </div>
    </div>
  );
}

const S = {
  page: { minHeight:'100vh', background:'#fff', display:'flex', alignItems:'center', justifyContent:'center', padding:16 },
  box: { width:'100%', maxWidth:400, background:'#fff', borderRadius:12, boxShadow:'0 4px 24px rgba(0,0,0,0.15)', padding:'32px 28px 28px' },
  title: { fontSize:28, fontWeight:700, color:'rgba(0,0,0,0.9)', marginBottom:4, textAlign:'center' },
  sub: { fontSize:15, color:'rgba(0,0,0,0.55)', marginBottom:20, textAlign:'center' },
  errBox: { display:'flex', gap:10, alignItems:'flex-start', background:'#fff0f0', border:'1.5px solid #cc1016', borderRadius:6, padding:'12px 14px', marginBottom:16, fontSize:14, color:'#cc1016', lineHeight:1.5 },
  errIcon: { fontSize:16, flexShrink:0, marginTop:1 },
  form: { display:'flex', flexDirection:'column', gap:16 },
  field: { display:'flex', flexDirection:'column', gap:6 },
  label: { fontSize:15, fontWeight:600, color:'rgba(0,0,0,0.85)' },
  input: { padding:'13px 14px', border:'1.5px solid', borderRadius:6, fontSize:16, fontFamily:'inherit', outline:'none', transition:'border-color 0.15s', width:'100%', boxSizing:'border-box' },
  btn: { padding:'14px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:28, fontSize:18, fontWeight:700, fontFamily:'inherit', cursor:'pointer', marginTop:4, letterSpacing:0.3 },
  divRow: { display:'flex', alignItems:'center', gap:10, margin:'20px 0' },
  divLine: { flex:1, height:1, background:'rgba(0,0,0,0.15)' },
  divOr: { fontSize:14, fontWeight:600, color:'rgba(0,0,0,0.4)' },
  joinTxt: { textAlign:'center', fontSize:18, color:'rgba(0,0,0,0.55)' },
  joinLink: { color:'#0a66c2', fontWeight:700, textDecoration:'none' },
};
