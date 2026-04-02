import React from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { motion } from 'framer-motion';
import { clearSession } from '../utils/session';

const quickLinks = [
  { label: 'Community Forum', description: 'Share insights & learn from peers', href: '/community' },
  { label: 'Prediction Lab', description: 'View market-driven outlooks', href: '/prediction' },
  { label: 'Crypto Data', description: 'Analyse live market pricing', href: '/crypto-data' },
];

const UserDashboard = () => {
  const navigate = useNavigate();
  const handleLogout = () => {
    clearSession();
    navigate('/auth', { replace: true });
  };

  const userEmail = localStorage.getItem('userEmail') || 'member@cryptogauge.app';

  return (
    <>
      <Navbar />
      <motion.section
        className="page-shell"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        aria-labelledby="user-dashboard-heading"
      >
        <header className="page-header" style={{ textAlign: 'left' }}>
          <span className="page-header__eyebrow">User workspace</span>
          <h1 id="user-dashboard-heading" className="page-header__title">Welcome back</h1>
          <p className="page-header__subtitle" style={{ margin: 0 }}>
            Signed in as <strong>{userEmail}</strong>. Your personalised hub for learning, market signals, and predictive insights.
          </p>
          <div className="page-actions" style={{ justifyContent: 'flex-start' }}>
            <button type="button" className="btn btn-primary" onClick={() => navigate('/crypto-data')}>
              View Live Markets
            </button>
            <button type="button" className="btn btn-ghost" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </header>

        <section className="card-grid card-grid--two" aria-label="Getting started">
          <article className="glass-card content-panel">
            <h2 className="content-panel__title">Today’s checklist</h2>
            <div className="timeline">
              <div className="timeline-item">
                <h3>Review your watchlist</h3>
                <p className="content-panel__text">
                  Track price swings for your favourite assets with the latest CoinGecko data integrations.
                </p>
              </div>
              <div className="timeline-item">
                <h3>Explore predictions</h3>
                <p className="content-panel__text">
                  Compare forecasts with real-world sentiment. Adjust interval and backtracking for deeper analysis.
                </p>
              </div>
              <div className="timeline-item">
                <h3>Grow your knowledge</h3>
                <p className="content-panel__text">
                  Learn from curated FAQ resources and join the community to stay ahead of market changes.
                </p>
              </div>
            </div>
          </article>

          <article className="glass-card glass-card--muted content-panel">
            <h2 className="content-panel__title">Quick navigation</h2>
            <p className="content-panel__text">
              Hop between tools in a single click. We keep everything organised, fast, and easy to find.
            </p>
            <div className="card-grid card-grid--two">
              {quickLinks.map(link => (
                <button
                  key={link.label}
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => navigate(link.href)}
                  style={{ textAlign: 'left', width: '100%' }}
                >
                  <strong>{link.label}</strong>
                  <br />
                  <span style={{ fontWeight: 400, fontSize: '0.85rem' }}>{link.description}</span>
                </button>
              ))}
            </div>
          </article>
        </section>

        <section className="glass-card content-panel">
          <h2 className="content-panel__title">Need a refresher?</h2>
          <p className="content-panel__text">
            Visit the learning curriculum for step-by-step guides, or open the FAQ & Tools page to find definitions, templates, and jargon busters tailored for crypto beginners.
          </p>
          <div className="page-actions" style={{ justifyContent: 'flex-start' }}>
            <button type="button" className="btn btn-primary" onClick={() => navigate('/faq')}>
              Explore FAQ & Tools
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => window.open('https://plvdjowxldieieyuzxfh.supabase.co', '_blank', 'noopener')}>
              Open Curriculum Workspace
            </button>
          </div>
        </section>
      </motion.section>
    </>
  );
};

export default UserDashboard;