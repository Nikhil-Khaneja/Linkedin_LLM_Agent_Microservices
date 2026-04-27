export default function Button({ children, onClick, variant='primary', disabled=false, style={}, type='button', size='md' }) {
  const base = { cursor: disabled?'not-allowed':'pointer', border: 'none', borderRadius: 20, fontWeight: 600, fontFamily: 'inherit', transition: 'all 0.15s', display:'inline-flex', alignItems:'center', justifyContent:'center', gap:6 };
  const sizes = { sm: { padding:'5px 14px', fontSize:13 }, md: { padding:'8px 20px', fontSize:14 }, lg: { padding:'12px 28px', fontSize:15 } };
  const variants = {
    primary: { background: disabled?'#ccc':'#0a66c2', color: '#fff' },
    secondary: { background: 'transparent', border: '1.5px solid #0a66c2', color: '#0a66c2' },
    danger: { background: disabled?'#ccc':'#cc1016', color: '#fff' },
    ghost: { background: 'transparent', color: '#666' },
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled} style={{ ...base, ...sizes[size], ...variants[variant], ...style }}>
      {children}
    </button>
  );
}