import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { recordActivity } from '../utils/session';

// Configure axios with a timeout
axios.defaults.timeout = 10000; // 10 seconds
axios.defaults.baseURL = 'http://localhost:5000';

const Login = ({ onClose, onSwitchToRegister }) => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [recaptchaToken, setRecaptchaToken] = useState('');
  const [error, setError] = useState('');
  const recaptchaRef = useRef(null);
  const recaptchaWidgetId = useRef(null);

  // Initialize reCAPTCHA v2 checkbox
  useEffect(() => {
    const loadRecaptcha = () => {
      if (window.grecaptcha && typeof window.grecaptcha.render === 'function' && recaptchaRef.current) {
        try {
          // ALWAYS reset existing widget (handles refresh)
          if (recaptchaWidgetId.current !== null && window.grecaptcha.reset) {
            console.log('Resetting existing reCAPTCHA widget');
            window.grecaptcha.reset(recaptchaWidgetId.current);
          }
          
          recaptchaWidgetId.current = window.grecaptcha.render(recaptchaRef.current, {
            'sitekey': '6LcIG_0rAAAAAP8EchuEwUAYSEbI8IN2vVaIejQq',
            'theme': 'dark',
            'size': 'normal',
            'callback': (token) => {
              setRecaptchaToken(token);
              console.log('reCAPTCHA v2 token received');
            },
            'expired-callback': () => {
              setRecaptchaToken('');
              console.log('reCAPTCHA v2 expired');
            }
          });
        } catch (err) {
          console.error('reCAPTCHA render error:', err);
        }
      } else {
        setTimeout(loadRecaptcha, 500);
      }
    };

    loadRecaptcha();
    
    // Cleanup: reset widget on unmount
    return () => {
      if (recaptchaWidgetId.current !== null && window.grecaptcha && window.grecaptcha.reset) {
        window.grecaptcha.reset(recaptchaWidgetId.current);
      }
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    // Check if reCAPTCHA v2 checkbox is checked (skip in development on localhost)
    if (!recaptchaToken) {
      setError('Please complete the reCAPTCHA verification');
      return;
    }

    try {
      const res = await axios.post('/api/auth/login', { 
        email, 
        password, 
        recaptchaToken
      });
      
      // Store authentication data
      if (res && res.data) {
        localStorage.setItem('token', res.data.token || '');
        localStorage.setItem('isAdmin', res.data.isAdmin ? 'true' : 'false');
        localStorage.setItem('userEmail', res.data.email || email);
        localStorage.setItem('userFullname', res.data.fullname || '');
        localStorage.setItem('userId', res.data.userId || '');
        recordActivity();
        
        // Clear any errors before redirect
        setError('');
        setRecaptchaToken('');
        
        // Reset reCAPTCHA widget for next use
        if (recaptchaWidgetId.current !== null && window.grecaptcha && window.grecaptcha.reset) {
          window.grecaptcha.reset(recaptchaWidgetId.current);
        }
        
        // Use React Router navigation to preserve browser history
        // Small delay to ensure localStorage is written
        setTimeout(() => {
          if (res.data.isAdmin) {
            navigate('/admin', { replace: true });
          } else {
            navigate('/dashboard', { replace: true });
          }
        }, 50);
        
        // Return early to prevent any further execution that could cause errors
        return;
      }
    } catch (err) {
      setRecaptchaToken('');
      
      // Better error messages with null checks
      if (!err || !err.response) {
        setError('Cannot connect to server. Is the backend running?');
      } else if (err.response.status === 400) {
        setError(err.response.data?.error || 'Invalid credentials or reCAPTCHA failed');
      } else if (err.response.status === 500) {
        setError(err.response.data?.error || 'Server error. Please try again later.');
      } else {
        setError(err.response?.data?.error || 'Login failed. Please try again.');
      }
      
      // Only log if it's not a handled error
      if (process.env.NODE_ENV === 'development' && err.response) {
        console.warn('[Login] Error handled:', err.response.data?.error || err.message);
      }
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card" role="dialog" aria-modal="true" aria-labelledby="login-heading">
        <header style={{ display: 'grid', gap: '0.4rem', textAlign: 'left', marginTop: '2rem' }}>
          <span className="page-header__eyebrow" style={{ justifySelf: 'flex-start' }}>
            Member access
          </span>
          <h2 id="login-heading" style={{ fontSize: '1.9rem', margin: 0, fontWeight: 700 }}>
            Welcome back
          </h2>
          <p style={{ color: 'var(--text-muted)', margin: 0 }}>
            Sign in to your premium account
          </p>
        </header>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="input-group">
            <label htmlFor="login-email" className="input-label">Email address</label>
            <input
              id="login-email"
              className="auth-input"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />
          </div>
          <div className="input-group">
            <label htmlFor="login-password" className="input-label">Password</label>
            <input
              id="login-password"
              className="auth-input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </div>
          <div className="auth-recaptcha" aria-live="polite">
            <div className="auth-recaptcha__inner" ref={recaptchaRef} />
          </div>
          <div className="auth-actions">
            <button type="submit" className="btn btn-primary">Sign in</button>
          </div>
        </form>

        {error && (
          <div className="empty-state" style={{ borderStyle: 'solid', color: '#f87171', background: 'rgba(248,113,113,0.1)' }}>
            {error}
          </div>
        )}

        <p style={{ color: 'var(--text-subtle)', fontSize: '0.9rem', margin: 0, textAlign: 'center' }}>
          Don’t have an account?{' '}
          <button type="button" className="auth-switch" onClick={onSwitchToRegister}>
            Create account
          </button>
        </p>
      </div>
    </div>
  );
};

export default Login;
