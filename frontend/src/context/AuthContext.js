import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import axios from 'axios';
import BASE from '../config/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null);
  const [loading, setLoading] = useState(true);
  const refreshTimer          = useRef(null);

  // On app load — just trust whatever is in localStorage
  useEffect(() => {
    const token  = localStorage.getItem('access_token');
    const stored = localStorage.getItem('user_data');
    if (token && stored) {
      setUser(JSON.parse(stored));
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const { data } = await axios.post(`${BASE.auth}/auth/login`, { email, password });
    const { access_token, refresh_token, user_id, user_type } = data.data;
    localStorage.setItem('access_token',  access_token);
    localStorage.setItem('refresh_token', refresh_token || '');
    const userData = { userId: user_id, userType: user_type, email };
    localStorage.setItem('user_data', JSON.stringify(userData));
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(userData);
    return userData;
  };

  const register = async (form) => {
    const { data } = await axios.post(`${BASE.auth}/auth/register`, form);
    const { access_token, refresh_token, user_id } = data.data;
    localStorage.setItem('access_token',  access_token);
    localStorage.setItem('refresh_token', refresh_token || '');
    const userData = { userId: user_id, userType: form.user_type, email: form.email };
    localStorage.setItem('user_data', JSON.stringify(userData));
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(userData);
    return { userData };
  };

  const logout = () => {
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
