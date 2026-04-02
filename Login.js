import React from 'react';
import { motion } from 'framer-motion';
import Navbar from '../components/Navbar';

const Dashboard = () => (
  <>
    <Navbar />
    <motion.section
      className="page-shell page-shell--wide"
      initial={{ opacity: 0, y: 32 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.65, ease: [0.25, 0.8, 0.25, 1] }}
      aria-labelledby="dashboard-heading"
    >
      <header className="page-header">
        <span className="page-header__eyebrow">Welcome back</span>
        <h1 id="dashboard-heading" className="page-header__title">
          JADC System Dashboard
        </h1>
        <p className="page-header__subtitle">
          Securely manage, analyse, and predict crypto trends with real-time insights tailored for newcomers traders.
        </p>
        <div className="page-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => alert('Explore more features coming soon!')}
          >
            Explore Features
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })}
          >
            View What’s New
          </button>
        </div>
      </header>

      <section className="card-grid card-grid--three" aria-label="Performance stats">
        <article className="glass-card stat" aria-live="polite">
          <span className="stat__label">Realtime Security</span>
          <span className="stat__value">Argon2 Shield</span>
          <span className="stat__delta">Bank-level encryption active</span>
        </article>
        <article className="glass-card stat">
          <span className="stat__label">Predictive Accuracy</span>
          <span className="stat__value">92.4%</span>
          <span className="pill">Powered by hybrid model ensembles</span>
        </article>
        <article className="glass-card stat">
          <span className="stat__label">Community Growth</span>
          <span className="stat__value">+348</span>
          <span className="stat__delta">new members this month</span>
        </article>
      </section>

      <section className="card-grid card-grid--two">
        <article className="glass-card content-panel">
          <div>
            <h2 className="content-panel__title">Platform Highlights</h2>
            <p className="content-panel__text">
              CryptoGauge combines intelligent prediction models, curated market research, and a supportive community to keep you ahead of market shifts. Access real-time analytics, sentiment insights, and collaborative learning—all inside a calm, focused workspace.
            </p>
          </div>
          <div className="chip-row" role="list">
            <span className="chip" role="listitem">Argon2 Password Vault</span>
            <span className="chip" role="listitem">Realtime Market Feeds</span>
            <span className="chip" role="listitem">Beginner-Friendly Journeys</span>
            <span className="chip" role="listitem">Expert Forecast Playbooks</span>
          </div>
        </article>

        <article className="glass-card glass-card--muted timeline">
          <h2 className="content-panel__title">Today’s Flow</h2>
          <div className="timeline-item">
            <h3>Check Market Pulse</h3>
            <p className="content-panel__text">Review live data dashboards and fine-tune alerts for BTC, ETH, and XRP to stay synced with market momentum.</p>
          </div>
          <div className="timeline-item">
            <h3>Explore Predictions</h3>
            <p className="content-panel__text">Dive into the prediction lab for tailored insights, accuracy metrics, and custom backtesting windows.</p>
          </div>
          <div className="timeline-item">
            <h3>Connect & Learn</h3>
            <p className="content-panel__text">Share strategies in the community forum, join peer discussions, and browse curated learning boosters.</p>
          </div>
        </article>
      </section>

      <section className="glass-card content-panel">
        <h2 className="content-panel__title">Why users choose CryptoGauge</h2>
        <div className="card-grid card-grid--two">
          <div>
            <h3 className="content-panel__title">Goal</h3>
            <p className="content-panel__text">
              Empower every crypto learner to make confident decisions with clarity, accuracy, and secure access to their data.
            </p>
          </div>
          <div>
            <h3 className="content-panel__title">Benefits</h3>
            <ul className="content-panel__text" style={{ listStyle: 'disc', paddingLeft: '1.25rem', margin: 0 }}>
              <li>Bank-level security with Argon2 password protection</li>
              <li>Fast, intuitive, and modern interface designed for focus</li>
              <li>Realtime analytics, sentiment checks, and predictive dashboards</li>
              <li>Personalised learning journeys for every skill level</li>
            </ul>
          </div>
        </div>
      </section>
    </motion.section>
  </>
);

export default Dashboard; 