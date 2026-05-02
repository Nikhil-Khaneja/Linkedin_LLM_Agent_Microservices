import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import BASE from '../config/api';
import { useAuth } from '../context/AuthContext';

export default function NotificationsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const currentId = user?.principalId || user?.userId;
  const token = localStorage.getItem('access_token');
  const authCfg = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const normalizeTarget = (notification) => {
    if (!notification) return '/notifications';
    if (notification.target_url) return notification.target_url;
    if (notification.type === 'message.received' && notification.data?.thread_id) return `/messages?thread=${encodeURIComponent(notification.data.thread_id)}`;
    if ((notification.type === 'profile.viewed' || notification.type === 'connection.accepted') && notification.actor_id) return `/profile/${notification.actor_id}`;
    if (notification.type && notification.type.startsWith('connection.')) return '/connections';
    if (notification.type === 'candidate.selected' || notification.type === 'application.status.updated') return '/applications';
    return '/notifications';
  };

  const load = async () => {
    if (!currentId || !token) return;
    setLoading(true);
    try {
      const { data } = await axios.post(`${BASE.member}/members/notifications/list`, { page_size: 50 }, authCfg);
      setItems(data?.data?.items || []);
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to load notifications');
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [currentId, token]);

  const markRead = async (notificationId) => {
    await axios.post(`${BASE.member}/members/notifications/markRead`, { notification_id: notificationId }, authCfg);
    setItems((prev) => prev.map((n) => n.notification_id === notificationId ? { ...n, is_read: true } : n));
  };

  const openNotification = async (notification) => {
    try {
      if (!notification?.is_read && notification?.notification_id) {
        await markRead(notification.notification_id);
      }
      navigate(normalizeTarget(notification));
    } catch {
      toast.error('Failed to open notification');
    }
  };

  const iconFor = (type) => {
    if (type === 'profile.viewed') return '👀';
    if (type === 'connection.requested' || type === 'connection.accepted') return '🤝';
    if (type === 'application.status.updated') return '📄';
    if (type === 'candidate.selected') return '⭐';
    if (type === 'message.received') return '💬';
    return '🔔';
  };

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <div className="li-card" style={{ padding: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 12 }}>Notifications</h1>
        {loading ? (
          <div style={{ padding: 30, textAlign: 'center' }}>Loading…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: 30, textAlign: 'center', color: 'rgba(0,0,0,0.55)' }}>No notifications yet</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map((n) => (
              <button
                key={n.notification_id}
                onClick={() => openNotification(n)}
                style={{
                  padding: 14,
                  border: '1px solid rgba(0,0,0,0.08)',
                  borderRadius: 8,
                  background: n.is_read ? '#fff' : '#eef6ff',
                  textAlign: 'left',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <span style={{ fontSize: 24 }}>{iconFor(n.type)}</span>
                    <div>
                      <p style={{ fontWeight: 700, marginBottom: 4 }}>{n.title || 'Notification'}</p>
                      <p style={{ color: 'rgba(0,0,0,0.7)', marginBottom: 6 }}>{n.body}</p>
                      <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{n.created_at ? new Date(n.created_at).toLocaleString() : ''}</p>
                    </div>
                  </div>
                  {!n.is_read && <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#0a66c2', flexShrink: 0, marginTop: 4 }} />}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
