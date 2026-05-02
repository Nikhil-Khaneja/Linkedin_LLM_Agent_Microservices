import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';

const blankExperience = () => ({
  title: '',
  company: '',
  location: '',
  employment_type: '',
  start_month: '',
  start_year: '',
  end_month: '',
  end_year: '',
  is_current: false,
  description: '',
});

const blankEducation = () => ({
  school: '',
  degree: '',
  field_of_study: '',
  start_year: '',
  end_year: '',
  description: '',
});

const monthLabel = (value) => {
  const n = Number(value || 0);
  if (!n) return '';
  return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][n - 1] || '';
};

const experiencePeriod = (exp) => {
  const start = [monthLabel(exp?.start_month), exp?.start_year].filter(Boolean).join(' ');
  const end = exp?.is_current ? 'Present' : [monthLabel(exp?.end_month), exp?.end_year].filter(Boolean).join(' ');
  if (!start && !end) return '';
  return `${start || 'Start'} - ${end || 'Present'}`;
};

export default function ProfilePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { memberId } = useParams();

  const currentId = user?.principalId || user?.userId;
  const viewedId = memberId || currentId;
  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  const [profile, setProfile] = useState(null);
  const [profileType, setProfileType] = useState('member');
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    headline: '',
    about_summary: '',
    city: '',
    state: '',
    skillsText: '',
    experience: [blankExperience()],
    education: [blankEducation()],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [mutuals, setMutuals] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [requestSent, setRequestSent] = useState(false);
  const [sentRequestId, setSentRequestId] = useState('');
  const [analytics, setAnalytics] = useState(null);

  const isOwnProfile = !memberId || viewedId === currentId;
  const isMemberProfile = profileType === 'member';

  const displayName = useMemo(() => {
    if (!profile) return '';
    if (profileType === 'recruiter') return profile.name || profile.recruiter_id || '';
    return `${profile.first_name || ''} ${profile.last_name || ''}`.trim() || profile.email || profile.member_id || '';
  }, [profile, profileType]);

  useEffect(() => {
    if (!viewedId || !token) return;
    loadProfile();
  }, [viewedId, token]);

  useEffect(() => {
    if (!viewedId || !token || !isMemberProfile || !isOwnProfile) {
      setAnalytics(null);
      return;
    }
    loadAnalytics();
  }, [viewedId, token, isMemberProfile]);

  useEffect(() => {
    if (isOwnProfile || !currentId || !viewedId || !token) return;
    loadConnectionMeta();
  }, [isOwnProfile, currentId, viewedId, token, profileType]);

  const hydrateMemberForm = (p) => {
    const experience = Array.isArray(p?.experience) && p.experience.length ? p.experience : [blankExperience()];
    const education = Array.isArray(p?.education) && p.education.length ? p.education : [blankEducation()];
    setForm({
      first_name: p?.first_name || '',
      last_name: p?.last_name || '',
      headline: p?.headline || '',
      about_summary: p?.about_summary || '',
      city: p?.city || '',
      state: p?.state || '',
      skillsText: Array.isArray(p?.skills) ? p.skills.join(', ') : '',
      experience,
      education,
    });
  };

  const loadProfile = async () => {
    setLoading(true);
    try {
      try {
        const { data } = await axios.post(`${BASE.member}/members/get`, { member_id: viewedId }, authCfg);
        const p = data?.data?.profile || null;
        setProfileType('member');
        setProfile(p);
        if (p) hydrateMemberForm(p);
        return;
      } catch (err) {
        const code = err?.response?.data?.error?.code;
        if (code && code !== 'member_not_found') {
          // continue to recruiter fallback before showing an error
        }
      }

      const { data } = await axios.post(`${BASE.recruiter}/recruiters/publicGet`, { recruiter_id: viewedId }, authCfg);
      const recruiter = data?.data?.recruiter || null;
      setProfileType('recruiter');
      setProfile(recruiter);
      setAnalytics(null);
    } catch (err) {
      setProfile(null);
      toast.error(err.response?.data?.error?.message || 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const loadAnalytics = async () => {
    try {
      const { data } = await axios.post(`${BASE.analytics}/analytics/member/dashboard`, { member_id: viewedId }, authCfg);
      setAnalytics(data?.data || null);
    } catch {
      setAnalytics(null);
    }
  };

  const loadConnectionMeta = async () => {
    try {
      const [connRes, mutualRes, sentRes] = await Promise.all([
        axios.post(`${BASE.messaging}/connections/list`, { user_id: currentId }, authCfg),
        axios.post(`${BASE.messaging}/connections/mutual`, { user_id: currentId, other_id: viewedId }, authCfg),
        axios.post(`${BASE.messaging}/connections/sent`, { user_id: currentId }, authCfg),
      ]);
      const connections = connRes?.data?.data?.items || [];
      const sentItems = sentRes?.data?.data?.items || [];
      const sentReq = sentItems.find((req) => req.receiver_id === viewedId);
      setIsConnected(connections.some((c) => (c.other_user_id || c.user_id) === viewedId));
      setRequestSent(!!sentReq);
      setSentRequestId(sentReq?.request_id || '');
      setMutuals(mutualRes?.data?.data?.items || []);
    } catch {
      setIsConnected(false);
      setRequestSent(false);
      setSentRequestId('');
      setMutuals([]);
    }
  };

  const waitForUpload = async (uploadId) => {
    for (let i = 0; i < 30; i += 1) {
      const { data } = await axios.get(`${BASE.member}/members/upload-status/${uploadId}`, authCfg);
      const item = data?.data || {};
      if (item.status === 'completed') return item;
      if (item.status === 'failed') throw new Error(item.error || 'Upload failed');
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error('Upload is still processing. Please refresh in a moment.');
  };

  const saveProfile = async () => {
    if (!isMemberProfile) return;
    const payload = {
      member_id: currentId,
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      headline: form.headline.trim(),
      about_summary: form.about_summary,
      city: form.city.trim(),
      state: form.state.trim(),
      skills: form.skillsText.split(',').map((s) => s.trim()).filter(Boolean),
      experience: (form.experience || []).filter((exp) => exp && (exp.title || exp.company || exp.description || exp.start_year || exp.end_year)).map((exp) => ({
        ...exp,
        is_current: !!exp.is_current,
      })),
      education: (form.education || []).filter((edu) => edu && (edu.school || edu.degree || edu.field_of_study || edu.start_year || edu.end_year)).map((edu) => ({ ...edu })),
    };
    setSaving(true);
    try {
      const { data } = await axios.post(`${BASE.member}/members/update`, payload, authCfg);
      const next = data?.data?.profile || null;
      setProfileType('member');
      setProfile(next);
      if (next) hydrateMemberForm(next);
      toast.success('Profile saved');
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  const uploadMedia = async (mediaType, file) => {
    if (!file) return;
    const setUploading = mediaType === 'profile_photo' ? setUploadingPhoto : setUploadingResume;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('member_id', currentId);
      fd.append('media_type', mediaType);
      fd.append('file', file);
      const { data } = await axios.post(`${BASE.member}/members/upload-media`, fd, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
      });
      const uploadId = data?.data?.upload_id;
      const item = uploadId ? await waitForUpload(uploadId) : null;
      const next = item?.profile || null;
      if (next) {
        setProfile(next);
        if (isMemberProfile) hydrateMemberForm(next);
      } else {
        await loadProfile();
      }
      toast.success(mediaType === 'resume' ? 'Resume uploaded and parsed' : 'Profile photo uploaded');
    } catch (err) {
      toast.error(err?.message || err.response?.data?.error?.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const sendConnectionRequest = async () => {
    try {
      const { data } = await axios.post(`${BASE.messaging}/connections/request`, {
        requester_id: currentId,
        receiver_id: viewedId,
        message: `Hi ${(displayName || 'there')}, I would like to connect!`,
      }, authCfg);
      setRequestSent(true);
      setSentRequestId(data?.data?.request_id || '');
      toast.success('Connection request sent');
    } catch (err) {
      const msg = err.response?.data?.error?.message || 'Failed to send request';
      if (/already connected|pending request|already/i.test(msg)) loadConnectionMeta();
      toast.error(msg);
    }
  };

  const withdrawConnectionRequest = async () => {
    if (!sentRequestId) return;
    try {
      await axios.post(`${BASE.messaging}/connections/withdraw`, { request_id: sentRequestId }, authCfg);
      setRequestSent(false);
      setSentRequestId('');
      toast.success('Connection request withdrawn');
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to withdraw request');
    }
  };

  const updateExperience = (idx, key, value) => {
    setForm((prev) => ({
      ...prev,
      experience: prev.experience.map((item, i) => (i === idx ? { ...item, [key]: value } : item)),
    }));
  };

  const updateEducation = (idx, key, value) => {
    setForm((prev) => ({
      ...prev,
      education: prev.education.map((item, i) => (i === idx ? { ...item, [key]: value } : item)),
    }));
  };

  const avatarLetter = (displayName || profile?.email || profile?.member_id || profile?.recruiter_id || 'U')[0].toUpperCase();
  const resumeUrl = profile?.resume_url;
  const experienceItems = Array.isArray(profile?.experience) ? profile.experience : [];
  const educationItems = Array.isArray(profile?.education) ? profile.education : [];
  const skills = Array.isArray(profile?.skills) ? profile.skills : [];

  if (loading) return <div className="li-card" style={{ padding: 40, textAlign: 'center' }}>Loading profile…</div>;
  if (!profile) return <div className="li-card" style={{ padding: 40, textAlign: 'center' }}>Profile not found</div>;

  return (
    <div style={{ maxWidth: 1020, margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="li-card" style={{ padding: 24 }}>
          <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
            <div style={S.avatarWrap}>
              {profile.profile_photo_url ? <img src={profile.profile_photo_url} alt="" style={S.avatarImg} /> : <div style={S.avatarFallback}>{avatarLetter}</div>}
            </div>
            <div style={{ flex: 1, minWidth: 240 }}>
              <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 4 }}>{displayName || 'Profile'}</h1>
              <p style={{ color: 'rgba(0,0,0,0.68)', marginBottom: 6 }}>{profile.headline || profile.access_level || 'Add a headline'}</p>
              <p style={{ color: 'rgba(0,0,0,0.5)', marginBottom: 6 }}>
                {profileType === 'recruiter'
                  ? [profile.company_name, profile.company_industry].filter(Boolean).join(' · ') || 'Recruiter'
                  : [profile.city, profile.state].filter(Boolean).join(', ') || profile.location || 'Location not set'}
              </p>
              {isMemberProfile && (profile.current_title || profile.current_company) && (
                <p style={{ color: 'rgba(0,0,0,0.58)', fontSize: 14 }}>{[profile.current_title, profile.current_company].filter(Boolean).join(' at ')}</p>
              )}
            </div>
            {!isOwnProfile && (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <button onClick={() => navigate(`/messages?user=${encodeURIComponent(viewedId || '')}`)} style={S.primaryBtn}>Message</button>
                {!isConnected && !requestSent && <button onClick={sendConnectionRequest} style={S.secondaryBtn}>Connect</button>}
                {isConnected && <span style={S.badge}>Connected</span>}
                {!isConnected && requestSent && <button onClick={withdrawConnectionRequest} style={S.withdrawBtn}>Withdraw request</button>}
              </div>
            )}
          </div>

          {isOwnProfile && isMemberProfile ? (
            <>
              <div style={S.sectionHeader}><h3 style={S.sectionTitle}>Top card</h3></div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <input value={form.first_name} onChange={(e) => setForm((p) => ({ ...p, first_name: e.target.value }))} placeholder="First name" style={S.input} />
                <input value={form.last_name} onChange={(e) => setForm((p) => ({ ...p, last_name: e.target.value }))} placeholder="Last name" style={S.input} />
                <input value={form.headline} onChange={(e) => setForm((p) => ({ ...p, headline: e.target.value }))} placeholder="Headline" style={S.input} />
                <input value={form.city} onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))} placeholder="City" style={S.input} />
                <input value={form.state} onChange={(e) => setForm((p) => ({ ...p, state: e.target.value }))} placeholder="State" style={S.input} />
                <input value={form.skillsText} onChange={(e) => setForm((p) => ({ ...p, skillsText: e.target.value }))} placeholder="Skills (comma separated)" style={S.input} />
              </div>
              <textarea value={form.about_summary} onChange={(e) => setForm((p) => ({ ...p, about_summary: e.target.value }))} placeholder="About" style={S.textarea} />
              <div style={{ display: 'flex', gap: 12, marginTop: 16, alignItems: 'center', flexWrap: 'wrap' }}>
                <label style={S.secondaryBtn}>
                  {uploadingPhoto ? 'Uploading photo…' : 'Upload photo'}
                  <input type="file" accept="image/*" onChange={(e) => uploadMedia('profile_photo', e.target.files?.[0])} style={{ display: 'none' }} />
                </label>
                <label style={S.secondaryBtn}>
                  {uploadingResume ? 'Uploading resume…' : 'Upload resume (PDF/TXT)'}
                  <input type="file" accept=".pdf,.txt" onChange={(e) => uploadMedia('resume', e.target.files?.[0])} style={{ display: 'none' }} />
                </label>
                <button onClick={saveProfile} disabled={saving} style={S.primaryBtn}>{saving ? 'Saving…' : 'Save profile'}</button>
              </div>
              {resumeUrl && (
                <div style={{ marginTop: 12, fontSize: 14, color: 'rgba(0,0,0,0.6)' }}>
                  Resume ready for jobs and AI parsing. <a href={resumeUrl} target="_blank" rel="noreferrer" style={{ color: '#0a66c2', fontWeight: 700 }}>View uploaded resume</a>
                </div>
              )}
            </>
          ) : (
            <>
              <h3 style={S.sectionTitle}>About</h3>
              <p style={{ color: 'rgba(0,0,0,0.75)', lineHeight: 1.6 }}>{profile.about_summary || `${displayName || 'This user'} has not added a summary yet.`}</p>
              {profileType === 'recruiter' && (
                <div style={{ marginTop: 14, display: 'grid', gap: 8, fontSize: 14, color: 'rgba(0,0,0,0.72)' }}>
                  <div><strong>Company:</strong> {profile.company_name || 'Not set'}</div>
                  <div><strong>Industry:</strong> {profile.company_industry || 'Not set'}</div>
                  <div><strong>Company size:</strong> {profile.company_size || 'Not set'}</div>
                  <div><strong>Role:</strong> {profile.access_level || 'Recruiter'}</div>
                </div>
              )}
            </>
          )}
        </div>

        {isMemberProfile && isOwnProfile && (
          <div className="li-card" style={{ padding: 24 }}>
            <div style={S.sectionHeader}>
              <h3 style={S.sectionTitle}>Experience</h3>
              <button onClick={() => setForm((prev) => ({ ...prev, experience: [...prev.experience, blankExperience()] }))} style={S.secondaryBtnSmall}>Add experience</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {form.experience.map((exp, idx) => (
                <div key={`exp-${idx}`} style={S.itemCard}>
                  <div style={S.itemHeader}>
                    <strong>Experience #{idx + 1}</strong>
                    {form.experience.length > 1 && <button onClick={() => setForm((prev) => ({ ...prev, experience: prev.experience.filter((_, i) => i !== idx) }))} style={S.linkBtn}>Remove</button>}
                  </div>
                  <div style={S.grid2}>
                    <input value={exp.title || ''} onChange={(e) => updateExperience(idx, 'title', e.target.value)} placeholder="Title" style={S.input} />
                    <input value={exp.company || ''} onChange={(e) => updateExperience(idx, 'company', e.target.value)} placeholder="Company" style={S.input} />
                    <input value={exp.location || ''} onChange={(e) => updateExperience(idx, 'location', e.target.value)} placeholder="Location" style={S.input} />
                    <input value={exp.employment_type || ''} onChange={(e) => updateExperience(idx, 'employment_type', e.target.value)} placeholder="Employment type" style={S.input} />
                    <input value={exp.start_month || ''} onChange={(e) => updateExperience(idx, 'start_month', e.target.value)} placeholder="Start month (1-12)" style={S.input} />
                    <input value={exp.start_year || ''} onChange={(e) => updateExperience(idx, 'start_year', e.target.value)} placeholder="Start year" style={S.input} />
                    <input value={exp.end_month || ''} onChange={(e) => updateExperience(idx, 'end_month', e.target.value)} placeholder="End month (1-12)" style={S.input} disabled={!!exp.is_current} />
                    <input value={exp.end_year || ''} onChange={(e) => updateExperience(idx, 'end_year', e.target.value)} placeholder="End year" style={S.input} disabled={!!exp.is_current} />
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, color: 'rgba(0,0,0,0.72)', marginTop: 10 }}>
                    <input type="checkbox" checked={!!exp.is_current} onChange={(e) => updateExperience(idx, 'is_current', e.target.checked)} /> I currently work here
                  </label>
                  <textarea value={exp.description || ''} onChange={(e) => updateExperience(idx, 'description', e.target.value)} placeholder="Describe your work, impact, tools, and achievements" style={{ ...S.textarea, minHeight: 100, marginTop: 10 }} />
                </div>
              ))}
            </div>
          </div>
        )}

        {isMemberProfile && !isOwnProfile && experienceItems.length > 0 && (
          <div className="li-card" style={{ padding: 24 }}>
            <h3 style={S.sectionTitle}>Experience</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {experienceItems.map((exp, idx) => (
                <div key={`read-exp-${idx}`} style={idx < experienceItems.length - 1 ? S.readItemBorder : undefined}>
                  <p style={{ fontSize: 18, fontWeight: 700 }}>{exp.title || 'Role'}</p>
                  <p style={{ fontSize: 15, color: 'rgba(0,0,0,0.76)', marginTop: 2 }}>{[exp.company, exp.employment_type].filter(Boolean).join(' · ')}</p>
                  <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.5)', marginTop: 4 }}>{[experiencePeriod(exp), exp.location].filter(Boolean).join(' · ')}</p>
                  {exp.description && <p style={{ marginTop: 10, color: 'rgba(0,0,0,0.74)', lineHeight: 1.6 }}>{exp.description}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {isMemberProfile && isOwnProfile && (
          <div className="li-card" style={{ padding: 24 }}>
            <div style={S.sectionHeader}>
              <h3 style={S.sectionTitle}>Education</h3>
              <button onClick={() => setForm((prev) => ({ ...prev, education: [...prev.education, blankEducation()] }))} style={S.secondaryBtnSmall}>Add education</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {form.education.map((edu, idx) => (
                <div key={`edu-${idx}`} style={S.itemCard}>
                  <div style={S.itemHeader}>
                    <strong>Education #{idx + 1}</strong>
                    {form.education.length > 1 && <button onClick={() => setForm((prev) => ({ ...prev, education: prev.education.filter((_, i) => i !== idx) }))} style={S.linkBtn}>Remove</button>}
                  </div>
                  <div style={S.grid2}>
                    <input value={edu.school || ''} onChange={(e) => updateEducation(idx, 'school', e.target.value)} placeholder="School" style={S.input} />
                    <input value={edu.degree || ''} onChange={(e) => updateEducation(idx, 'degree', e.target.value)} placeholder="Degree" style={S.input} />
                    <input value={edu.field_of_study || ''} onChange={(e) => updateEducation(idx, 'field_of_study', e.target.value)} placeholder="Field of study" style={S.input} />
                    <input value={edu.start_year || ''} onChange={(e) => updateEducation(idx, 'start_year', e.target.value)} placeholder="Start year" style={S.input} />
                    <input value={edu.end_year || ''} onChange={(e) => updateEducation(idx, 'end_year', e.target.value)} placeholder="End year" style={S.input} />
                  </div>
                  <textarea value={edu.description || ''} onChange={(e) => updateEducation(idx, 'description', e.target.value)} placeholder="Activities, achievements, or notes" style={{ ...S.textarea, minHeight: 90, marginTop: 10 }} />
                </div>
              ))}
            </div>
          </div>
        )}

        {isMemberProfile && !isOwnProfile && educationItems.length > 0 && (
          <div className="li-card" style={{ padding: 24 }}>
            <h3 style={S.sectionTitle}>Education</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {educationItems.map((edu, idx) => (
                <div key={`read-edu-${idx}`} style={idx < educationItems.length - 1 ? S.readItemBorder : undefined}>
                  <p style={{ fontSize: 17, fontWeight: 700 }}>{edu.school || 'School'}</p>
                  <p style={{ fontSize: 14, color: 'rgba(0,0,0,0.74)', marginTop: 4 }}>{[edu.degree, edu.field_of_study].filter(Boolean).join(', ')}</p>
                  <p style={{ fontSize: 13, color: 'rgba(0,0,0,0.5)', marginTop: 4 }}>{[edu.start_year, edu.end_year].filter(Boolean).join(' - ')}</p>
                  {edu.description && <p style={{ marginTop: 8, color: 'rgba(0,0,0,0.72)', lineHeight: 1.6 }}>{edu.description}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {isMemberProfile && skills.length > 0 && (
          <div className="li-card" style={{ padding: 24 }}>
            <h3 style={S.sectionTitle}>Skills</h3>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {skills.map((skill) => <span key={skill} style={S.skillChip}>{skill}</span>)}
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="li-card" style={{ padding: 20, height: 'fit-content' }}>
          <h3 style={S.sectionTitle}>{isOwnProfile ? 'Profile insights' : 'Public profile'}</h3>
          {isOwnProfile ? (
            <>
              <div style={S.statRow}><span>Total profile views</span><strong>{analytics?.total_profile_views ?? profile.profile_views ?? 0}</strong></div>
              <div style={S.statRow}><span>Connections</span><strong>{profile.connections_count || 0}</strong></div>
              <div style={S.statRow}><span>Applications tracked</span><strong>{analytics?.status_total ?? 0}</strong></div>
              {resumeUrl && <div style={{ marginTop: 14 }}><a href={resumeUrl} target="_blank" rel="noreferrer" style={{ ...S.secondaryBtn, display: 'inline-block', textDecoration: 'none' }}>View resume</a></div>}
              {profile?.resume_text && <p style={{ marginTop: 12, fontSize: 13, color: 'rgba(0,0,0,0.55)' }}>Parsed resume text ready for AI ranking.</p>}
              {analytics?.profile_views?.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <p style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: 'rgba(0,0,0,0.65)' }}>Recent profile views</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {analytics.profile_views.slice(-5).reverse().map((entry) => (
                      <div key={entry.date} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: 'rgba(0,0,0,0.65)' }}>
                        <span>{entry.date}</span>
                        <strong>{entry.count}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {analytics?.application_status_breakdown && Object.keys(analytics.application_status_breakdown).length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <p style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: 'rgba(0,0,0,0.65)' }}>Application status summary</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {Object.entries(analytics.application_status_breakdown).map(([status, count]) => (
                      <div key={status} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: 'rgba(0,0,0,0.65)' }}>
                        <span style={{ textTransform: 'capitalize' }}>{status.replace(/_/g, ' ')}</span>
                        <strong>{count}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <Link to="/notifications" style={{ ...S.secondaryBtn, display: 'inline-block', marginTop: 12, textDecoration: 'none' }}>View notifications</Link>
            </>
          ) : (
            <>
              <div style={S.statRow}><span>Connections</span><strong>{profile.connections_count || 0}</strong></div>
              <p style={{ marginTop: 12, fontSize: 13, color: 'rgba(0,0,0,0.55)', lineHeight: 1.5 }}>Private analytics such as profile views and application stats are visible only to the profile owner.</p>
            </>
          )}
        </div>

        {!isOwnProfile && (
          <div className="li-card" style={{ padding: 20 }}>
            <h3 style={S.sectionTitle}>{mutuals.length} mutual connection{mutuals.length !== 1 ? 's' : ''}</h3>
            {mutuals.length === 0 ? (
              <p style={{ color: 'rgba(0,0,0,0.55)' }}>No mutual connections yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {mutuals.slice(0, 5).map((m) => (
                  <div key={m.user_id || m.member_id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={S.smallAvatar}>{(m.display_name || m.first_name || 'U')[0].toUpperCase()}</div>
                    <div>
                      <p style={{ fontWeight: 700 }}>{m.display_name || `${m.first_name || ''} ${m.last_name || ''}`.trim() || m.user_id}</p>
                      <p style={{ color: 'rgba(0,0,0,0.55)', fontSize: 13 }}>{m.headline || 'LinkedIn Member'}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const S = {
  avatarWrap: { width: 104, height: 104, borderRadius: '50%', overflow: 'hidden', flexShrink: 0 },
  avatarImg: { width: '100%', height: '100%', objectFit: 'cover' },
  avatarFallback: { width: '100%', height: '100%', borderRadius: '50%', background: '#0a66c2', color: '#fff', fontSize: 36, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center' },
  smallAvatar: { width: 38, height: 38, borderRadius: '50%', background: '#0a66c2', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flexShrink: 0 },
  sectionHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, gap: 10 },
  sectionTitle: { fontSize: 18, fontWeight: 700, marginBottom: 12 },
  input: { width: '100%', padding: '10px 12px', border: '1px solid rgba(0,0,0,0.2)', borderRadius: 6, fontFamily: 'inherit' },
  textarea: { width: '100%', minHeight: 120, padding: '12px', border: '1px solid rgba(0,0,0,0.2)', borderRadius: 6, fontFamily: 'inherit', resize: 'vertical' },
  primaryBtn: { padding: '10px 18px', background: '#0a66c2', color: '#fff', border: 'none', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  secondaryBtn: { padding: '10px 18px', background: '#fff', color: '#0a66c2', border: '1px solid #0a66c2', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  secondaryBtnSmall: { padding: '8px 14px', background: '#fff', color: '#0a66c2', border: '1px solid #0a66c2', borderRadius: 999, fontWeight: 700, cursor: 'pointer', fontSize: 13 },
  withdrawBtn: { padding: '10px 18px', background: '#fff', color: '#b42318', border: '1px solid #b42318', borderRadius: 999, fontWeight: 700, cursor: 'pointer' },
  badge: { padding: '10px 14px', background: '#e8f3ff', color: '#0a66c2', borderRadius: 999, fontWeight: 700 },
  statRow: { display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid rgba(0,0,0,0.08)' },
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 },
  itemCard: { border: '1px solid rgba(0,0,0,0.08)', borderRadius: 12, padding: 16, background: '#fcfcfc' },
  itemHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  linkBtn: { border: 'none', background: 'none', color: '#0a66c2', fontWeight: 700, cursor: 'pointer' },
  readItemBorder: { paddingBottom: 14, borderBottom: '1px solid rgba(0,0,0,0.08)' },
  skillChip: { padding: '8px 12px', borderRadius: 999, background: '#eef3f8', color: '#0a66c2', fontWeight: 700, fontSize: 13 },
};
