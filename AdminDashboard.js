// IMPORTANT: These must be the FIRST imports to ensure error suppression loads before React
import './minimizeErrorOverlay'; // Show small notification instead of large popup
import './blockReactErrors';
import './suppressReactErrors';

import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import './styles/layout.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
