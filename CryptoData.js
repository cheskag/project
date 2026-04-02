import React, { useState } from 'react';
import Navbar from '../components/Navbar';
import axios from 'axios';
import { motion } from 'framer-motion';

const AdminDashboard = () => {
  const [json, setJson] = useState('');
  const [result, setResult] = useState('');

  const handleUpload = async () => {
    setResult('');

    let parsed;
    try {
      parsed = JSON.parse(json);
    } catch (parseErr) {
      setResult('Error: Invalid JSON format. Please double-check your data.');
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const res = await axios.post('/api/admin/upload-json', { data: parsed }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setResult('Success: ' + res.data.message);
    } catch (err) {
      if (err.response && err.response.data && err.response.data.error) {
        setResult('Error: ' + err.response.data.error);
      } else if (err.message) {
        setResult('Error: ' + err.message);
      } else {
        setResult('Error: Upload failed');
      }
    }
  };

  return (
    <>
      <Navbar />
      <motion.section
        className="page-shell"
        initial={{ opacity: 0, y: 36 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        aria-labelledby="admin-dashboard-heading"
      >
        <header className="page-header" style={{ textAlign: 'left' }}>
          <span className="page-header__eyebrow">Admin control center</span>
          <h1 id="admin-dashboard-heading" className="page-header__title">Admin Dashboard</h1>
          <p className="page-header__subtitle" style={{ margin: 0 }}>
            Manage trusted datasets, trigger secure uploads, and review the status of your JSON ingestion pipeline.
          </p>
        </header>

        <section className="glass-card content-panel">
          <div className="input-group">
            <label htmlFor="json-upload" className="input-label">Upload JSON dataset</label>
            <textarea
              id="json-upload"
              className="textarea-control"
              value={json}
              onChange={e => setJson(e.target.value)}
              placeholder='Paste JSON here e.g. { "items": [] }'
              rows={12}
              aria-describedby="json-helptext"
            />
            <span id="json-helptext" className="content-panel__text">
              Data never leaves our secure server without encryption. Validate structure before uploading.
            </span>
          </div>
          <div className="page-actions" style={{ justifyContent: 'flex-start' }}>
            <button type="button" className="btn btn-primary" onClick={handleUpload}>
              Upload JSON
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setJson('')}
              aria-label="Clear JSON field"
            >
              Clear field
            </button>
          </div>
          {result && (
            <div
              role="status"
              className="badge"
              style={{ color: result.startsWith('Success') ? '#22c55e' : '#f97316', background: 'rgba(34, 197, 94, 0.12)' }}
            >
              {result}
            </div>
          )}
        </section>

        <section className="glass-card glass-card--muted content-panel">
          <h2 className="content-panel__title">Admin handbook</h2>
          <p className="content-panel__text">
            Paste your JSON dataset above and click <strong>Upload JSON</strong> to persist it in the database. Only admins can access this secure endpoint. Keys and sensitive fields should already be encrypted before paste.
          </p>
          <div className="section-divider" />
          <ul className="content-panel__text" style={{ listStyle: 'disc', paddingLeft: '1.25rem', margin: 0 }}>
            <li>Ensure your JSON is valid—parsing runs before upload.</li>
            <li>Use staging datasets for previews, production for live dashboards.</li>
            <li>Log successful uploads in your team channel for traceability.</li>
          </ul>
        </section>
      </motion.section>
    </>
  );
};

export default AdminDashboard; 