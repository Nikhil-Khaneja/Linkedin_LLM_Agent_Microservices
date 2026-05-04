import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';

// Pages
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import JobsPage from './pages/JobsPage';
import JobDetailPage from './pages/JobDetailPage';
import ProfilePage from './pages/ProfilePage';
import ApplicationsPage from './pages/ApplicationsPage';
import MessagingPage from './pages/MessagingPage';
import RecruiterDashboard from './pages/RecruiterDashboard';
import AIDashboard from './pages/AIDashboard';
import AnalyticsPage from './pages/AnalyticsPage';
import ConnectionsPage from './pages/ConnectionsPage';
import NotificationsPage from './pages/NotificationsPage';
import CareerCoachPage from './pages/CareerCoachPage';
import PerformancePage from './pages/PerformancePage';
import Layout from './components/Layout';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading-screen"><div className="spinner" /></div>;
  return user ? children : <Navigate to="/login" />;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login"    element={user ? <Navigate to="/" /> : <LoginPage />} />
      <Route path="/register" element={user ? <Navigate to="/" /> : <RegisterPage />} />
      <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route index element={user?.userType === 'recruiter' ? <Navigate to="/ai" replace /> : <Navigate to="/jobs" replace />} />
        <Route path="jobs"            element={<JobsPage />} />
        <Route path="jobs/:jobId"     element={<JobDetailPage />} />
        <Route path="profile"         element={<ProfilePage />} />
        <Route path="profile/:memberId" element={<ProfilePage />} />
        <Route path="applications"    element={<ApplicationsPage />} />
        <Route path="messages"        element={<MessagingPage />} />
        <Route path="recruiter"       element={<RecruiterDashboard />} />
        <Route path="ai"              element={<AIDashboard />} />
        <Route path="analytics"       element={<AnalyticsPage />} />
        <Route path="connections"     element={<ConnectionsPage />} />
        <Route path="notifications"   element={<NotificationsPage />} />
        <Route path="coach"           element={<CareerCoachPage />} />
        <Route path="performance"     element={<PerformancePage />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Toaster position="top-right" toastOptions={{ duration: 3500 }} />
      <AppRoutes />
      <style>{`
        .loading-screen {
          display: flex; align-items: center; justify-content: center;
          height: 100vh; background: #f3f2ef;
        }
        .spinner {
          width: 40px; height: 40px; border: 3px solid #e5e7eb;
          border-top-color: #0a66c2; border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </AuthProvider>
  );
}
