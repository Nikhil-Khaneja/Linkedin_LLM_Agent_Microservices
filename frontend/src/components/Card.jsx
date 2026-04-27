export default function Card({ children, style={} }) {
  return (
    <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e0dcd8', padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.06)', ...style }}>
      {children}
    </div>
  );
}