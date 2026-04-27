import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

// ── Resize image to max 200x200 and return base64 ──────────
function resizeImage(file, maxSize = 200) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let w = img.width, h = img.height;
        if (w > h) { h = Math.round(h * maxSize / w); w = maxSize; }
        else        { w = Math.round(w * maxSize / h); h = maxSize; }
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL('image/jpeg', 0.85));
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

export default function ProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile]       = useState(null);
  const [editing, setEditing]       = useState(false);
  const [form, setForm]             = useState({});
  const [saving, setSaving]         = useState(false);
  const [skillInput, setSkillInput] = useState('');
  const [photo, setPhoto]           = useState(null); // base64
  const [uploading, setUploading]   = useState(false);
  const fileRef                     = useRef();
  const initial = ((user?.email || 'U')[0]).toUpperCase();

  // Load photo from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(`photo_${user?.userId}`);
    if (saved) setPhoto(saved);
  }, [user]);

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const { data } = await axios.post(`${BASE.member}/members/get`, { member_id: user?.userId });
      setProfile(data.data);
      setForm(data.data);
      // Also check if photo stored in profile_photo_url
      if (data.data?.profile_photo_url && data.data.profile_photo_url.startsWith('data:')) {
        setPhoto(data.data.profile_photo_url);
        localStorage.setItem(`photo_${user?.userId}`, data.data.profile_photo_url);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setEditing(true);
        setForm({
          first_name: user?.email?.split('@')[0] || '',
          last_name: '', email: user?.email || '',
          phone: '', city: '', state: '',
          headline: '', about_summary: '', skills: [],
        });
      }
    }
  };

  // ── Handle photo upload ────────────────────────────────────
  const handlePhotoChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) { toast.error('Please select an image file'); return; }
    if (file.size > 10 * 1024 * 1024) { toast.error('Image must be under 10MB'); return; }

    setUploading(true);
    try {
      const base64 = await resizeImage(file, 300);
      setPhoto(base64);
      // Save to localStorage immediately
      localStorage.setItem(`photo_${user?.userId}`, base64);
      // Also update form so it saves with profile
      setForm(p => ({ ...p, profile_photo_url: base64 }));
      toast.success('Photo updated! Click Save to keep changes.');
    } catch (err) {
      toast.error('Failed to process image');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const removePhoto = () => {
    setPhoto(null);
    localStorage.removeItem(`photo_${user?.userId}`);
    setForm(p => ({ ...p, profile_photo_url: '' }));
    toast.success('Photo removed');
  };

  // ── Save profile ───────────────────────────────────────────
  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form, profile_photo_url: photo || '' };
      if (profile?.member_id) {
        await axios.post(`${BASE.member}/members/update`, { member_id: profile.member_id, ...payload });
        toast.success('✅ Profile saved!');
      } else {
        await axios.post(`${BASE.member}/members/create`, { ...payload, email: form.email || user?.email });
        toast.success('✅ Profile created!');
      }
      setEditing(false);
      load();
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Save failed. Please try again.');
    } finally { setSaving(false); }
  };

  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const addSkill = () => {
    if (!skillInput.trim()) return;
    setForm(p => ({ ...p, skills: [...(p.skills || []), skillInput.trim()] }));
    setSkillInput('');
  };

  const removeSkill = (i) => setForm(p => ({ ...p, skills: p.skills.filter((_, j) => j !== i) }));

  const completeness = [
    photo,
    profile?.first_name,
    profile?.headline,
    profile?.about_summary,
    profile?.skills?.length > 0,
    profile?.city,
  ].filter(Boolean).length;

  return (
    <div style={S.layout}>
      {/* ── Main column ── */}
      <div>
        {/* Profile header card */}
        <div style={S.card}>
          {/* Banner */}
          <div style={S.banner} />

          {/* Avatar + edit button */}
          <div style={{ padding: '0 24px 20px', position: 'relative' }}>
            <div style={S.avatarRow}>
              {/* Clickable avatar */}
              <div style={{ position: 'relative', display: 'inline-block' }}>
                <div
                  style={S.avatar}
                  onClick={() => fileRef.current?.click()}
                  title="Click to change photo"
                >
                  {photo
                    ? <img src={photo} alt="Profile" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
                    : <span style={{ fontSize: 44, fontWeight: 800, color: '#fff' }}>{initial}</span>
                  }
                  {/* Camera overlay on hover */}
                  <div style={S.cameraOverlay}>
                    {uploading ? '⏳' : '📷'}
                  </div>
                </div>
                {/* Hidden file input */}
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoChange}
                  style={{ display: 'none' }}
                />
              </div>

              {/* Edit button */}
              {!editing && (
                <button onClick={() => setEditing(true)} style={S.editBtn}>
                  ✏️ Edit profile
                </button>
              )}
            </div>

            {/* Photo action buttons */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 12, marginTop: 4 }}>
              <button onClick={() => fileRef.current?.click()} style={S.photoBtn}>
                {uploading ? 'Processing…' : photo ? '🔄 Change photo' : '📷 Add photo'}
              </button>
              {photo && (
                <button onClick={removePhoto} style={S.removePhotoBtn}>
                  🗑️ Remove
                </button>
              )}
            </div>

            {/* Name + headline */}
            {!editing && (
              <>
                <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>
                  {profile ? `${profile.first_name} ${profile.last_name}` : 'Your Name'}
                </h1>
                <p style={{ fontSize: 16, color: 'rgba(0,0,0,0.75)', marginBottom: 4 }}>
                  {profile?.headline || 'Add a headline'}
                </p>
                {profile?.city && (
                  <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.55)' }}>
                    📍 {profile.city}{profile.state ? `, ${profile.state}` : ''}
                  </p>
                )}
                <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
                  <button onClick={() => setEditing(true)} style={S.primaryBtn}>Open to</button>
                  <button onClick={() => setEditing(true)} style={S.outlineBtn}>Add profile section</button>
                </div>
              </>
            )}
          </div>
        </div>

        {/* ── Edit form ── */}
        {editing && (
          <div style={{ ...S.card, padding: 28, marginTop: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <h2 style={{ fontSize: 20, fontWeight: 700 }}>Edit intro</h2>
              <button onClick={() => setEditing(false)} style={S.closeBtn}>✕</button>
            </div>

            <div style={S.grid}>
              <Field label="First name *" value={form.first_name || ''} onChange={set('first_name')} />
              <Field label="Last name *" value={form.last_name || ''} onChange={set('last_name')} />
              <Field label="Email *" type="email" value={form.email || user?.email || ''} onChange={set('email')} />
              <Field label="Phone" value={form.phone || ''} onChange={set('phone')} placeholder="+1 (555) 000-0000" />
              <Field label="City" value={form.city || ''} onChange={set('city')} placeholder="San Jose" />
              <Field label="State" value={form.state || ''} onChange={set('state')} placeholder="CA" />
              <div style={{ gridColumn: '1/-1' }}>
                <Field label="Headline" value={form.headline || ''} onChange={set('headline')} placeholder="Senior Engineer at Acme Corp" />
              </div>
              <div style={{ gridColumn: '1/-1' }}>
                <label style={S.label}>About / Summary</label>
                <textarea
                  rows={4} value={form.about_summary || ''} onChange={set('about_summary')}
                  placeholder="Tell your professional story…"
                  style={{ ...S.input, resize: 'vertical', fontFamily: 'inherit' }}
                />
              </div>

              {/* Skills */}
              <div style={{ gridColumn: '1/-1' }}>
                <label style={S.label}>Skills</label>
                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                  <input
                    style={{ ...S.input, flex: 1 }} value={skillInput}
                    onChange={e => setSkillInput(e.target.value)}
                    placeholder="e.g. Python, React, SQL…"
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
                  />
                  <button onClick={addSkill} style={S.addSkillBtn}>+ Add</button>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {(form.skills || []).map((sk, i) => (
                    <span key={i} style={S.skillChip}>
                      {sk}
                      <button onClick={() => removeSkill(i)} style={S.removeSkillBtn}>✕</button>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24, paddingTop: 20, borderTop: '1px solid rgba(0,0,0,0.08)' }}>
              <button onClick={() => setEditing(false)} style={S.cancelBtn}>Cancel</button>
              <button onClick={save} disabled={saving} style={S.saveBtn}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        )}

        {/* Skills section */}
        {!editing && profile?.skills?.length > 0 && (
          <div style={{ ...S.card, padding: 24, marginTop: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h2 style={{ fontSize: 20, fontWeight: 700 }}>Skills</h2>
              <button onClick={() => setEditing(true)} style={S.pencil}>✏️</button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {profile.skills.map((sk, i) => (
                <span key={i} style={S.skillDisplay}>{sk.skill_name || sk}</span>
              ))}
            </div>
          </div>
        )}

        {/* Experience */}
        {!editing && profile?.experience?.length > 0 && (
          <div style={{ ...S.card, padding: 24, marginTop: 10 }}>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>Experience</h2>
            {profile.experience.map((ex, i) => (
              <div key={i} style={{ display: 'flex', gap: 14, padding: '12px 0', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                <div style={S.expLogo}>🏢</div>
                <div>
                  <p style={{ fontSize: 16, fontWeight: 700 }}>{ex.title}</p>
                  <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.8)' }}>{ex.company_name}</p>
                  <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.5)' }}>
                    {ex.start_date} – {ex.is_current ? 'Present' : ex.end_date}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Right sidebar ── */}
      <aside style={{ position: 'sticky', top: 72 }}>
        {/* Profile completeness */}
        <div style={S.card}>
          <div style={{ padding: 20 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 14 }}>Profile completeness</h3>
            <div style={{ background: 'rgba(0,0,0,0.08)', borderRadius: 4, height: 6, overflow: 'hidden', marginBottom: 12 }}>
              <div style={{ height: '100%', background: completeness >= 5 ? '#057642' : '#0a66c2', width: `${completeness / 6 * 100}%`, borderRadius: 4, transition: 'width 0.5s' }} />
            </div>
            <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.6)', marginBottom: 14 }}>{completeness}/6 sections complete</p>

            {[
              ['📷', 'Profile photo', !!photo],
              ['✍️', 'Headline', !!(profile?.headline)],
              ['📝', 'About', !!(profile?.about_summary)],
              ['💡', 'Skills', profile?.skills?.length > 0],
              ['📍', 'Location', !!(profile?.city)],
              ['👤', 'Name', !!(profile?.first_name)],
            ].map(([icon, label, done]) => (
              <div key={label} style={{ display: 'flex', gap: 10, padding: '7px 0', borderBottom: '1px solid rgba(0,0,0,0.05)', alignItems: 'center' }}>
                <span style={{ fontSize: 16 }}>{icon}</span>
                <span style={{ flex: 1, fontSize: 14, color: done ? 'rgba(0,0,0,0.85)' : 'rgba(0,0,0,0.45)' }}>{label}</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: done ? '#057642' : '#0a66c2' }}>
                  {done ? '✓' : '+'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Photo tips */}
        <div style={{ ...S.card, padding: 16, marginTop: 10, background: '#f0f7ff', border: '1px solid #c8dff5' }}>
          <p style={{ fontSize: 14, fontWeight: 700, color: '#0a66c2', marginBottom: 6 }}>📷 Adding a photo</p>
          <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.65)', lineHeight: 1.5 }}>
            Click the avatar circle or the "Add photo" button to upload your profile picture.
            Supports JPG, PNG, GIF — auto-resized to fit perfectly.
          </p>
        </div>
      </aside>
    </div>
  );
}

function Field({ label, value, onChange, type = 'text', placeholder = '' }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: 14, fontWeight: 600, color: 'rgba(0,0,0,0.75)', marginBottom: 5 }}>{label}</label>
      <input
        type={type} value={value} onChange={onChange} placeholder={placeholder}
        style={{ width: '100%', padding: '11px 14px', border: '1.5px solid rgba(0,0,0,0.25)', borderRadius: 4, fontSize: 15, fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box', transition: 'border-color 0.15s' }}
        onFocus={e => e.target.style.borderColor = '#0a66c2'}
        onBlur={e => e.target.style.borderColor = 'rgba(0,0,0,0.25)'}
      />
    </div>
  );
}

const S = {
  layout:  { display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20, alignItems: 'start' },
  card:    { background: '#fff', borderRadius: 8, boxShadow: '0 0 0 1px rgba(0,0,0,0.1)', overflow: 'hidden' },
  banner:  { height: 120, background: 'linear-gradient(135deg, #0a66c2 0%, #004182 60%, #7c3aed 100%)' },
  avatarRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: -52, marginBottom: 12 },
  avatar: {
    width: 112, height: 112, borderRadius: '50%',
    background: '#0a66c2', border: '4px solid #fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    cursor: 'pointer', position: 'relative', overflow: 'hidden',
    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
  },
  cameraOverlay: {
    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 24, opacity: 0, transition: 'opacity 0.2s',
    // Note: hover handled inline via CSS class not available here
    // so we always show a hint at bottom
    borderRadius: '50%',
  },
  photoBtn: {
    padding: '7px 16px', border: '1.5px solid #0a66c2', borderRadius: 20,
    background: '#fff', color: '#0a66c2', fontSize: 14, fontWeight: 600,
    cursor: 'pointer', fontFamily: 'inherit',
  },
  removePhotoBtn: {
    padding: '7px 16px', border: '1.5px solid #cc1016', borderRadius: 20,
    background: '#fff', color: '#cc1016', fontSize: 14, fontWeight: 600,
    cursor: 'pointer', fontFamily: 'inherit',
  },
  editBtn: {
    padding: '8px 18px', border: '1.5px solid rgba(0,0,0,0.5)', borderRadius: 24,
    background: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
  },
  primaryBtn: {
    padding: '8px 20px', background: '#0a66c2', color: '#fff', border: 'none',
    borderRadius: 24, fontSize: 15, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
  },
  outlineBtn: {
    padding: '7px 18px', border: '1.5px solid rgba(0,0,0,0.5)', borderRadius: 24,
    background: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
  },
  closeBtn: { background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: 'rgba(0,0,0,0.5)', padding: 4 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  label: { display: 'block', fontSize: 14, fontWeight: 600, color: 'rgba(0,0,0,0.75)', marginBottom: 5 },
  input: { width: '100%', padding: '11px 14px', border: '1.5px solid rgba(0,0,0,0.25)', borderRadius: 4, fontSize: 15, outline: 'none', boxSizing: 'border-box' },
  addSkillBtn: { padding: '11px 18px', background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 4, fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap' },
  skillChip: { display: 'inline-flex', alignItems: 'center', gap: 6, background: '#e8f0fe', color: '#0a66c2', padding: '5px 12px', borderRadius: 20, fontSize: 13, fontWeight: 600 },
  removeSkillBtn: { background: 'none', border: 'none', cursor: 'pointer', color: '#0a66c2', fontSize: 14, padding: 0, lineHeight: 1, fontWeight: 700 },
  cancelBtn: { padding: '10px 20px', border: '1.5px solid rgba(0,0,0,0.35)', borderRadius: 4, background: '#fff', fontSize: 15, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' },
  saveBtn: { padding: '10px 28px', background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 4, fontSize: 16, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' },
  pencil: { background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', padding: 4 },
  skillDisplay: { background: '#f3f2ef', border: '1px solid rgba(0,0,0,0.15)', color: 'rgba(0,0,0,0.8)', padding: '5px 14px', borderRadius: 20, fontSize: 14, fontWeight: 500 },
  expLogo: { width: 44, height: 44, background: '#f3f2ef', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 },
};
