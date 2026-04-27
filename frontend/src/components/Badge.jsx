const colorMap = {
  submitted: '#0a66c2', reviewing: '#e68a00', interview: '#057642', offer: '#057642',
  rejected: '#cc1016', withdrawn: '#666', open: '#057642', closed: '#cc1016',
  approved: '#057642', failed: '#cc1016', queued: '#888', running: '#e68a00',
  waiting_approval: '#e68a00', member: '#0a66c2', recruiter: '#7c3aed',
};
export default function Badge({ label, type }) {
  const color = colorMap[type] || '#666';
  return (
    <span style={{ background: color+'20', color, border:`1px solid ${color}40`, padding:'2px 10px', borderRadius:20, fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:'0.04em' }}>
      {label}
    </span>
  );
}