import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ first_name:'', last_name:'', email:'', password:'', user_type:'member', company_name:'', company_industry:'', company_size:'medium', access_level:'admin' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const set = k => e => { setForm(p => ({...p, [k]: e.target.value})); setError(''); };

  const submit = async (e) => {
    e.preventDefault();
    if (form.password.length < 6) { setError('Password must be at least 6 characters.'); return; }
    if (form.user_type === 'recruiter' && !form.company_name.trim()) { setError('Recruiter sign up requires a company name.'); return; }
    setError(''); setLoading(true);
    try {
      await register(form);
      navigate('/');
    } catch (err) {
      const code = err.response?.data?.error?.code;
      const msg  = err.response?.data?.error?.message;
      if (code === 'duplicate_email') {
        setError('An account with this email already exists. Try signing in instead.');
      } else if (code === 'validation_error') {
        setError(msg || 'Please check your details and try again.');
      } else {
        setError(msg || 'Registration failed. Please try again.');
      }
    } finally { setLoading(false); }
  };

  return (
    <div style={S.page}>
      <div style={S.box}>
        <div style={{ textAlign:'center', marginBottom:20 }}>
          <svg viewBox="0 0 34 34" width="48" height="48" xmlns="http://www.w3.org/2000/svg">
            <path fill="#0a66c2" d="M34 2.5v29A2.5 2.5 0 0131.5 34h-29A2.5 2.5 0 010 31.5v-29A2.5 2.5 0 012.5 0h29A2.5 2.5 0 0134 2.5z"/>
            <path fill="#fff" d="M7.5 12h4v14h-4zm2-6.5a2.5 2.5 0 110 5 2.5 2.5 0 010-5zm6 6.5h3.8v1.9h.1c.5-1 1.8-2.1 3.7-2.1 4 0 4.7 2.6 4.7 6v7.2h-4v-6.4c0-1.5 0-3.4-2.1-3.4s-2.4 1.6-2.4 3.3v6.5h-4V12z"/>
          </svg>
        </div>

        <h1 style={S.title}>Make the most of your professional life</h1>

        {error && (
          <div style={S.errBox}>
            <span>⚠️</span>
            <span>{error}</span>
            {error.includes('already exists') && (
              <Link to="/login" style={{ color:'#0a66c2', fontWeight:700, whiteSpace:'nowrap' }}>Sign in →</Link>
            )}
          </div>
        )}

        <form onSubmit={submit} style={S.form}>
          <div style={S.row}>
            <Field label="First name" value={form.first_name} onChange={set('first_name')} required />
            <Field label="Last name" value={form.last_name} onChange={set('last_name')} required />
          </div>
          <Field label="Email" type="email" value={form.email} onChange={set('email')} required />
          <Field label="Password (6+ characters)" type="password" value={form.password} onChange={set('password')} required />

          <div>
            <label style={S.label}>I am a</label>
            <div style={S.typeRow}>
              {[{v:'member',label:'👤 Job Seeker',desc:'Find opportunities'},{v:'recruiter',label:'🏢 Recruiter',desc:'Hire talent'}].map(t => (
                <button key={t.v} type="button" onClick={() => setForm(p=>({...p,user_type:t.v}))}
                  style={{ ...S.typeBtn, ...(form.user_type===t.v ? S.typeActive : {}) }}>
                  <span style={{ fontSize:16, fontWeight:700 }}>{t.label}</span>
                  <span style={{ fontSize:12, color: form.user_type===t.v?'#0a66c2':'rgba(0,0,0,0.5)' }}>{t.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {form.user_type === 'recruiter' && (
            <div style={{ ...S.recruiterBox }}>
              <p style={{ fontSize:14, fontWeight:700, marginBottom:10 }}>Recruiter company details</p>
              <Field label="Company name" value={form.company_name} onChange={set('company_name')} required />
              <div style={S.row}>
                <Field label="Industry" value={form.company_industry} onChange={set('company_industry')} placeholder="Software" />
                <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
                  <label style={{ fontSize:15, fontWeight:600, color:'rgba(0,0,0,0.85)' }}>Company size</label>
                  <select value={form.company_size} onChange={set('company_size')} style={S.select}>
                    <option value="startup">Startup</option>
                    <option value="small">Small</option>
                    <option value="medium">Medium</option>
                    <option value="large">Large</option>
                    <option value="enterprise">Enterprise</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          <p style={S.terms}>By clicking Agree &amp; Join, you agree to the <span style={{color:'#0a66c2'}}>User Agreement</span> and <span style={{color:'#0a66c2'}}>Privacy Policy</span>.</p>

          <button type="submit" disabled={loading} style={{ ...S.btn, opacity:loading?0.7:1 }}>
            {loading ? 'Creating account…' : 'Agree & Join'}
          </button>
        </form>

        <div style={S.divRow}><div style={S.divLine}/><span style={S.divOr}>or</span><div style={S.divLine}/></div>
        <p style={S.signIn}>Already on LinkedIn DS? <Link to="/login" style={S.link}>Sign in</Link></p>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type='text', required, placeholder }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
      <label style={{ fontSize:15, fontWeight:600, color:'rgba(0,0,0,0.85)' }}>{label}</label>
      <input type={type} value={value} onChange={onChange} required={required} placeholder={placeholder}
        style={{ padding:'13px 14px', border:'1.5px solid rgba(0,0,0,0.4)', borderRadius:6, fontSize:16, fontFamily:'inherit', outline:'none', width:'100%', boxSizing:'border-box' }} />
    </div>
  );
}

const S = {
  page: { minHeight:'100vh', background:'#fff', display:'flex', alignItems:'center', justifyContent:'center', padding:'24px 16px' },
  box: { width:'100%', maxWidth:500, background:'#fff', borderRadius:12, boxShadow:'0 4px 24px rgba(0,0,0,0.15)', padding:'32px 28px 24px' },
  title: { fontSize:22, fontWeight:600, color:'rgba(0,0,0,0.9)', marginBottom:20, textAlign:'center', lineHeight:1.3 },
  errBox: { display:'flex', gap:10, alignItems:'flex-start', background:'#fff0f0', border:'1.5px solid #cc1016', borderRadius:6, padding:'12px 14px', marginBottom:16, fontSize:13, color:'#cc1016', lineHeight:1.5 },
  form: { display:'flex', flexDirection:'column', gap:14 },
  row: { display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 },
  label: { display:'block', fontSize:15, fontWeight:600, color:'rgba(0,0,0,0.85)', marginBottom:6 },
  typeRow: { display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginTop:4 },
  typeBtn: { display:'flex', flexDirection:'column', gap:3, padding:'12px 14px', border:'1.5px solid rgba(0,0,0,0.25)', borderRadius:6, background:'#fff', cursor:'pointer', textAlign:'left', transition:'all 0.15s' },
  typeActive: { border:'2px solid #0a66c2', background:'#f0f7ff' },
  recruiterBox: { background:'#f8fbff', border:'1px solid rgba(10,102,194,0.15)', borderRadius:8, padding:14 },
  select: { padding:'13px 14px', border:'1.5px solid rgba(0,0,0,0.4)', borderRadius:6, fontSize:16, fontFamily:'inherit', outline:'none', width:'100%', boxSizing:'border-box', background:'#fff' },
  terms: { fontSize:12, color:'rgba(0,0,0,0.55)', lineHeight:1.6 },
  btn: { padding:'14px', background:'#0a66c2', color:'#fff', border:'none', borderRadius:28, fontSize:18, fontWeight:700, fontFamily:'inherit', cursor:'pointer', letterSpacing:0.3 },
  divRow: { display:'flex', alignItems:'center', gap:10, margin:'18px 0' },
  divLine: { flex:1, height:1, background:'rgba(0,0,0,0.12)' },
  divOr: { fontSize:13, fontWeight:600, color:'rgba(0,0,0,0.4)' },
  signIn: { textAlign:'center', fontSize:18, color:'rgba(0,0,0,0.55)' },
  link: { color:'#0a66c2', fontWeight:700, textDecoration:'none' },
};
