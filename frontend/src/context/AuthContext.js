import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import axios from 'axios';
import BASE from '../config/api';

const AuthContext = createContext(null);

// Axios interceptor — auto-refresh expired token
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(p => error ? p.reject(error) : p.resolve(token));
  failedQueue = [];
};

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);
  const refreshTimer          = useRef(null);

  // Setup axios interceptor once
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      res => res,
      async err => {
        const original = err.config;
        // If 401 and not already retrying and not the refresh endpoint itself
        if (err.response?.status === 401 && !original._retry && !original.url?.includes('/auth/refresh')) {
          if (isRefreshing) {
            return new Promise((resolve, reject) => {
              failedQueue.push({ resolve, reject });
            }).then(token => {
              original.headers['Authorization'] = 'Bearer ' + token;
              return axios(original);
            });
          }
          original._retry = true;
          isRefreshing = true;
          try {
            const refreshToken = localStorage.getItem('refresh_token');
            if (!refreshToken) throw new Error('No refresh token');
            const { data } = await axios.post(`${BASE.auth}/auth/refresh`, { refresh_token: refreshToken });
            const newToken = data.data.access_token;
            localStorage.setItem('access_token', newToken);
            if (data.data.refresh_token) localStorage.setItem('refresh_token', data.data.refresh_token);
            axios.defaults.headers.common['Authorization'] = 'Bearer ' + newToken;
            processQueue(null, newToken);
            original.headers['Authorization'] = 'Bearer ' + newToken;
            return axios(original);
          } catch (refreshErr) {
            processQueue(refreshErr, null);
            // Refresh failed — logout
            localStorage.clear();
            delete axios.defaults.headers.common['Authorization'];
            setUser(null);
            window.location.href = '/login';
            return Promise.reject(refreshErr);
          } finally {
            isRefreshing = false;
          }
        }
        return Promise.reject(err);
      }
    );
    return () => axios.interceptors.response.eject(interceptor);
  }, []);

  useEffect(() => {
    const token   = localStorage.getItem('access_token');
    const refresh = localStorage.getItem('refresh_token');
    const stored  = localStorage.getItem('user_data');
    if (token && stored) {
      setUser(JSON.parse(stored));
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      // Schedule proactive refresh at 50 min (token is 1h)
      scheduleRefresh(refresh);
    }
    setLoading(false);
  }, []);

  const scheduleRefresh = (refreshToken) => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    if (!refreshToken) return;
    // Refresh 10 min before expiry (50 min = 3,000,000 ms)
    refreshTimer.current = setTimeout(async () => {
      try {
        const { data } = await axios.post(`${BASE.auth}/auth/refresh`, { refresh_token: refreshToken });
        const newToken = data.data.access_token;
        localStorage.setItem('access_token', newToken);
        if (data.data.refresh_token) {
          localStorage.setItem('refresh_token', data.data.refresh_token);
          scheduleRefresh(data.data.refresh_token);
        }
        axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
      } catch {}
    }, 50 * 60 * 1000);
  };

  const login = async (email, password) => {
    const { data } = await axios.post(`${BASE.auth}/auth/login`, { email, password });
    const { access_token, refresh_token, user_id, user_type } = data.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token || '');
    const userData = { userId: user_id, userType: user_type, email };
    localStorage.setItem('user_data', JSON.stringify(userData));
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(userData);
    scheduleRefresh(refresh_token);
    return userData;
  };

  const register = async (form) => {
    const { data } = await axios.post(`${BASE.auth}/auth/register`, form);
    const { access_token, refresh_token, user_id } = data.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token || '');
    const userData = { userId: user_id, userType: form.user_type, email: form.email };
    localStorage.setItem('user_data', JSON.stringify(userData));
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(userData);
    scheduleRefresh(refresh_token);
    return { userData };
  };

  const logout = async () => {
    const refresh_token = localStorage.getItem('refresh_token');
    await axios.post(`${BASE.auth}/auth/logout`, { refresh_token }).catch(() => {});
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    localStorage.clear();
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
