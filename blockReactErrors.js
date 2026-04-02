import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Footer from './components/Footer';
import './App.css';
import { clearSession, getLastActivity, isSessionActive, recordActivity, SESSION_TIMEOUT_MS } from './utils/session';

const AuthLanding = lazy(() => import('./pages/AuthLanding'));
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Community = lazy(() => import('./pages/Community'));
const Prediction = lazy(() => import('./pages/Prediction'));
const FAQ = lazy(() => import('./pages/FAQ'));
const CryptoData = lazy(() => import('./pages/CryptoData'));
const News = lazy(() => import('./pages/News'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const UserDashboard = lazy(() => import('./pages/UserDashboard'));

const LoadingScreen = () => (
  <div className="app-loading" role="status" aria-live="polite">
    <div className="app-loading__spinner" />
    <p className="app-loading__text">Loading CryptoGauge…</p>
  </div>
);

const SessionManager = () => {
  const navigate = useNavigate();
  const hasLoggedOutRef = useRef(false);
  const [timeLeft, setTimeLeft] = useState(null);
  const [showCountdown, setShowCountdown] = useState(false);

  useEffect(() => {
    const tokenPresent = () => {
      const token = localStorage.getItem('token');
      return !!token && token !== 'undefined' && token !== 'null';
    };

    const syncCountdown = () => {
      if (!tokenPresent()) {
        setShowCountdown(false);
        setTimeLeft(null);
        return;
      }

      const lastActivity = getLastActivity();

      if (!lastActivity) {
        recordActivity();
        setShowCountdown(true);
        setTimeLeft(SESSION_TIMEOUT_MS);
        return;
      }

      const remaining = SESSION_TIMEOUT_MS - (Date.now() - lastActivity);
      setShowCountdown(true);
      setTimeLeft(Math.max(0, remaining));
    };

    const markActivity = () => {
      recordActivity();
      syncCountdown();
    };

    const events = ['click', 'keydown', 'mousemove', 'scroll', 'touchstart'];
    events.forEach((eventName) => {
      window.addEventListener(eventName, markActivity, { passive: true });
    });

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        markActivity();
      }
    };

    const handleStorage = (event) => {
      if (event.key === 'lastActivity' || event.key === 'token') {
        checkSession();
      }
    };

    const checkSession = () => {
      if (!tokenPresent()) {
        hasLoggedOutRef.current = false;
        setShowCountdown(false);
        setTimeLeft(null);
        return;
      }

      if (!isSessionActive()) {
        if (!hasLoggedOutRef.current) {
          hasLoggedOutRef.current = true;
          clearSession();
          setShowCountdown(false);
          setTimeLeft(null);
          navigate('/auth', { replace: true });
        }
      } else {
        hasLoggedOutRef.current = false;
        syncCountdown();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('storage', handleStorage);

    // Initial touch & validation
    markActivity();
    checkSession();

    const countdownInterval = setInterval(syncCountdown, 1000);
    const intervalId = setInterval(checkSession, 30000);

    return () => {
      events.forEach((eventName) => {
        window.removeEventListener(eventName, markActivity);
      });
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('storage', handleStorage);
      clearInterval(countdownInterval);
      clearInterval(intervalId);
    };
  }, [navigate]);

  if (!showCountdown || timeLeft === null) {
    return null;
  }

  const secondsRemaining = Math.max(0, Math.floor(timeLeft / 1000));
  const minutes = Math.floor(secondsRemaining / 60);
  const seconds = secondsRemaining % 60;
  const formatted = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  let urgency = 'default';
  if (timeLeft <= 60_000) {
    urgency = 'critical';
  } else if (timeLeft <= 3 * 60_000) {
    urgency = 'warning';
  }

  return (
    <div className={`session-indicator session-indicator--${urgency}`} role="status" aria-live="polite">
      <span className="session-indicator__label">Session expires in</span>
      <span className="session-indicator__timer">{formatted}</span>
    </div>
  );
};

function App() {
  return (
    <Router>
      <SessionManager />
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route path="/" element={<Navigate to="/auth" replace />} />
          <Route path="/auth" element={<AuthLanding />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/community" 
            element={
              <ProtectedRoute>
                <Community />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/news" 
            element={
              <ProtectedRoute>
                <News />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/prediction" 
            element={
              <ProtectedRoute>
                <Prediction />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/faq" 
            element={
              <ProtectedRoute>
                <FAQ />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/crypto-data" 
            element={
              <ProtectedRoute>
                <CryptoData />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/user-dashboard" 
            element={
              <ProtectedRoute>
                <UserDashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin" 
            element={
              <ProtectedRoute requireAdmin={true}>
                <AdminDashboard />
              </ProtectedRoute>
            } 
          />
        </Routes>
      </Suspense>
      <Footer />
    </Router>
  );
}

export default App;
