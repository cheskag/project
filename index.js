import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import authRoutes from './routes/auth.js';
import adminRoutes from './routes/admin.js';
import insightsRoutes from './routes/insights.js';
import securityRoutes from './routes/security.js';
import communityRoutes from './routes/community.js';
import pool from './config/db.js';
import connectMongo from './config/mongo.js';

// Load environment variables
dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// Connect MongoDB
connectMongo();

// Middleware to set Content-Security-Policy
app.use((req, res, next) => {
  res.setHeader(
    "Content-Security-Policy",
    "frame-src 'self' https://www.google.com/ https://www.recaptcha.net/; script-src 'self' https://www.google.com/ https://www.gstatic.com/ https://www.recaptcha.net/;"
  );
  next();
});

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/insights', insightsRoutes);
app.use('/api/security', securityRoutes);
app.use('/api/community', communityRoutes);

// Health check
app.get('/', (req, res) => res.send('API Running'));

app.get('/api/test-db', async (req, res) => {
  try {
    const result = await pool.query('SELECT NOW()');
    res.json({ success: true, time: result.rows[0].now });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

const PORT = process.env.PORT || 5000;

// Handle port already in use error gracefully
const server = app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`\n❌ ERROR: Port ${PORT} is already in use!\n`);
    console.error('To fix this, run one of these commands:\n');
    console.error('Windows PowerShell:');
    console.error('  .\\kill-port.ps1');
    console.error('\nOr manually:');
    console.error('  1. Find the process: netstat -ano | findstr :5000');
    console.error('  2. Kill it: taskkill /PID <pid> /F\n');
    console.error('Or change the port in .env file: PORT=5001\n');
    process.exit(1);
  } else {
    throw err;
  }
}); 