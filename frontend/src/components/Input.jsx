export default function Input({ label, value, onChange, type='text', placeholder='', required=false, style={} }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
      {label && <label style={{ fontSize:13, fontWeight:500, color:'#333' }}>{label}{required&&<span style={{color:'#cc1016'}}>*</span>}</label>}
      <input
        type={type} value={value} onChange={onChange} placeholder={placeholder} required={required}
        style={{ padding:'9px 12px', border:'1px solid #ccc', borderRadius:8, fontSize:14, fontFamily:'inherit', outline:'none', transition:'border 0.15s', ...style }}
        onFocus={e=>e.target.style.border='1px solid #0a66c2'}
        onBlur={e=>e.target.style.border='1px solid #ccc'}
      />
    </div>
  );
}