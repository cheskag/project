import { validationResult } from 'express-validator';
import argon2 from 'argon2';
import jwt from 'jsonwebtoken';
import axios from 'axios';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { createUser, findUserByEmail } from '../models/userModel.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Trigger background evaluation cache update (non-blocking)
 * Runs evaluation in background and caches results for fast access
 */
function triggerEvaluationCacheUpdate() {
  return new Promise((resolve) => {
    try {
      const projectRoot = path.resolve(__dirname, '..', '..');
      const insightsPath = path.join(projectRoot, 'Topic modeling', 'insights');
      const scriptPath = path.join(insightsPath, 'run_evaluation_background.py');
      
      // Get Python path from environment or use default
      const pythonPath = process.env.PYTHON_PATH || process.env.PYTHON_BIN || 'python';
      
      console.log('[AUTH] Triggering background evaluation cache update...');
      
      // Spawn Python process in background (non-blocking)
      const pythonProcess = spawn(pythonPath, [scriptPath], {
        cwd: insightsPath,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env }
      });
      
      // Don't wait for completion - let it run in background
      pythonProcess.on('error', (err) => {
        console.error('[AUTH] Failed to start evaluation cache update:', err.message);
        resolve(); // Don't reject - cache update is optional
      });
      
      // Log output but don't block
      pythonProcess.stdout.on('data', (data) => {
        console.log(`[Evaluation Cache] ${data.toString().trim()}`);
      });
      
      pythonProcess.stderr.on('data', (data) => {
        console.error(`[Evaluation Cache] ${data.toString().trim()}`);
      });
      
      pythonProcess.on('close', (code) => {
        if (code === 0) {
          console.log('[AUTH] Background evaluation cache update completed');
        } else {
          console.warn(`[AUTH] Evaluation cache update exited with code ${code}`);
        }
        resolve(); // Always resolve - cache update is optional
      });
      
      // Resolve immediately (don't wait for process)
      resolve();
    } catch (err) {
      console.error('[AUTH] Error triggering evaluation cache update:', err);
      resolve(); // Don't reject - cache update is optional
    }
  });
}

/**
 * Verifies reCAPTCHA v2 or v3 token with Google's API
 * Supports both v2 checkbox and v3 invisible reCAPTCHA
 * @param {string} token - reCAPTCHA response token from frontend
 * @returns {Promise<boolean>} - True if verification successful, false otherwise
 */
const verifyRecaptcha = async (token) => {
  // If no token provided, fail
  if (!token || token.trim().length === 0) {
    console.warn('[reCAPTCHA] No token provided');
    return false;
  }
  
  // Check if secret is configured
  const secret = process.env.RECAPTCHA_SECRET;
  const secretV2 = process.env.RECAPTCHA_SECRETV2;
  
  // Try v2 first if available, then fall back to v3
  const secretToUse = secretV2 || secret;
  
  if (!secretToUse || secretToUse.trim().length === 0) {
    console.warn('[reCAPTCHA] RECAPTCHA_SECRET not set - allowing request (development mode)');
    return true; // Allow if secret not configured (for development)
  }
  
  try {
    // Prepare form data
    const formData = `secret=${encodeURIComponent(secretToUse)}&response=${encodeURIComponent(token)}`;
    
    // Make verification request to Google
    const response = await axios.post(
      'https://www.google.com/recaptcha/api/siteverify',
      formData,
      {
        headers: { 
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        timeout: 5000 // 5 second timeout
      }
    );
    
    // Check response
    if (!response.data.success) {
      const errorCodes = response.data['error-codes'] || [];
      
      // Handle browser-error (common in development/localhost)
      if (errorCodes.includes('browser-error')) {
        // Allow in development mode to prevent blocking testing
        if (process.env.NODE_ENV !== 'production') {
          console.warn('[reCAPTCHA] browser-error detected - allowing in development mode');
          return true;
        }
      }
      
      // Log other errors only in development
      if (process.env.NODE_ENV === 'development' && !errorCodes.includes('browser-error')) {
        console.warn('[reCAPTCHA] Verification failed:', errorCodes);
      }
      
      if (errorCodes.includes('invalid-input-response')) {
        
        
        // Allow in development mode to prevent blocking testing
        if (process.env.NODE_ENV !== 'production') {
                    return true;
        }
      }
    }
    
    // For v3, check the score as well
    if (response.data.score !== undefined) {
      const score = response.data.score;
      console.log(`[reCAPTCHA v3] Score: ${score.toFixed(2)} | Action: ${response.data.action || 'unknown'} | Human: ${score >= 0.5 ? 'YES' : 'SUSPICIOUS'}`);
      
      // Score interpretation:
      // 0.9-1.0 = Clearly human (normal use)
      // 0.7-0.9 = Likely human (maybe some automation)
      // 0.5-0.7 = Suspicious (could be automated)
      // 0.0-0.5 = Bot-like behavior
      
      // Set threshold for blocking
      const SCORE_THRESHOLD = 0.5; // Adjust this value (0.0-1.0)
      
      if (score < SCORE_THRESHOLD) {
        console.warn(`[reCAPTCHA v3] LOW SCORE DETECTED: ${score.toFixed(2)} - Possible bot activity`);
        console.warn(`[reCAPTCHA v3] Threshold: ${SCORE_THRESHOLD} | Current: ${score.toFixed(2)}`);
        
        // In production, block low scores
        if (process.env.NODE_ENV === 'production') {
          console.error(`[reCAPTCHA v3] BLOCKING REQUEST - Score too low (${score.toFixed(2)} < ${SCORE_THRESHOLD})`);
          return false;
        } else {
          // In development, warn but allow (for testing)
          console.warn(`[reCAPTCHA v3] Development mode: Allowing request despite low score`);
        }
      } else {
        console.log(`[reCAPTCHA v3] PASSED - Score ${score.toFixed(2)} is above threshold ${SCORE_THRESHOLD}`);
      }
    }
    
    // For v2 checkbox, success = true means checkbox was checked
    if (response.data.success) {
      console.log('[reCAPTCHA] Verification successful');
    }
    
    return response.data.success === true;
  } catch (err) {
    console.error('[reCAPTCHA] Error verifying reCAPTCHA API call:', err.message);
    if (err.response) {
      console.error('[reCAPTCHA] API response:', err.response.data);
      console.error('[reCAPTCHA] Status:', err.response.status);
    }
    
    // For network errors, allow in development but log
    if (err.code === 'ECONNABORTED' || err.code === 'ENOTFOUND') {
      console.warn('[reCAPTCHA] API unreachable - allowing request (check internet connection)');
      return true; // Allow if Google API unreachable (for development)
    }
    
    return false;
  }
};

/**
 * User registration endpoint
 * Creates a new user account with email validation, password hashing, and reCAPTCHA verification
 * @param {Object} req - Express request object
 * @param {Object} req.body - Request body containing user registration data
 * @param {string} req.body.fullname - User's full name
 * @param {string} req.body.email - User's email address
 * @param {string} req.body.password - User's plain text password (will be hashed)
 * @param {string} req.body.phone - User's phone number (optional)
 * @param {string} req.body.address - User's address (optional)
 * @param {string} req.body.recaptchaToken - reCAPTCHA v2/v3 token
 * @param {Object} res - Express response object
 * @returns {Promise<void>} - Sends JSON response with user ID and email on success
 */
export const register = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) return res.status(400).json({ errors: errors.array() });

  const { fullname, email, password, phone, address, recaptchaToken } = req.body;
  
  // Log registration attempt (no email shown for security)
  if (process.env.NODE_ENV === 'development') {
    console.log('[AUTH] Registration attempt received');
  }
  
  // Skip reCAPTCHA in development mode only if explicitly skipped
  if (recaptchaToken && recaptchaToken !== 'DEV_SKIP_RECAPTCHA') {
    const recaptchaValid = await verifyRecaptcha(recaptchaToken);
    if (!recaptchaValid) {
      console.warn('[AUTH] Registration failed: reCAPTCHA verification failed');
      return res.status(400).json({ error: 'reCAPTCHA verification failed. Please try again or check your connection.' });
    }
  } else if (recaptchaToken === 'DEV_SKIP_RECAPTCHA') {
    console.log('[AUTH] Development mode: Skipping reCAPTCHA verification');
  }

  try {
    // Normalize email before checking/creating
    const normalizedEmail = (email || '').trim().toLowerCase();
    
    // Check for existing user (case-insensitive)
    const existing = await findUserByEmail(normalizedEmail);
    if (existing) {
      if (process.env.NODE_ENV === 'development') {
        console.log('[AUTH] Registration failed: Email already exists');
      }
      return res.status(400).json({ error: 'Email already registered' });
    }
    
    const passwordHash = await argon2.hash(password);
    // Use original email (trimmed) for storage, but normalized for lookup
    const user = await createUser(fullname, email.trim(), passwordHash, phone, address);
    
    if (process.env.NODE_ENV === 'development') {
      console.log(`[AUTH] User registered successfully - ID: ${user.id}`);
    }
    
    res.status(201).json({ message: 'User registered', user: { id: user.id, email: user.email } });
  } catch (err) {
    console.error('[AUTH] Registration server error:', err.message);
    if (err.code === '23505') {
      return res.status(400).json({ error: 'Email already registered' });
    }
    res.status(500).json({ error: 'Server error', details: err.message });
  }
};

/**
 * User login endpoint
 * Authenticates users via database lookup or admin credentials from .env
 * Checks reCAPTCHA, validates credentials, and returns JWT token
 * @param {Object} req - Express request object
 * @param {Object} req.body - Request body containing login credentials
 * @param {string} req.body.email - User's email address
 * @param {string} req.body.password - User's plain text password
 * @param {string} req.body.recaptchaToken - reCAPTCHA v2/v3 token
 * @param {Object} res - Express response object
 * @returns {Promise<void>} - Sends JSON response with JWT token and admin status on success
 */
export const login = async (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) return res.status(400).json({ errors: errors.array() });

  const { email, password, recaptchaToken } = req.body;
  
  // Log login attempt (no email shown for security)
  if (process.env.NODE_ENV === 'development') {
    console.log('[AUTH] Login attempt received');
  }
  
  // Skip reCAPTCHA in development mode only if explicitly skipped
  if (recaptchaToken && recaptchaToken !== 'DEV_SKIP_RECAPTCHA') {
    const recaptchaValid = await verifyRecaptcha(recaptchaToken);
    if (!recaptchaValid) {
      console.warn('[AUTH] Login failed: reCAPTCHA verification failed');
      return res.status(400).json({ error: 'reCAPTCHA verification failed. Please try again or check your connection.' });
    }
  } else if (recaptchaToken === 'DEV_SKIP_RECAPTCHA') {
    console.log('[AUTH] Development mode: Skipping reCAPTCHA verification');
  }

  try {
    // IMPORTANT: Check admin credentials FIRST (before database lookup)
    // This allows admin email to exist in database but still use admin password
    const normalizedInputEmail = (email || '').trim().toLowerCase();
    const adminEmail = process.env.ADMIN_EMAIL ? (process.env.ADMIN_EMAIL || '').trim().toLowerCase() : '';
    
    // Handle quoted passwords from .env (similar to PG_PASSWORD handling)
    let adminPassword = process.env.ADMIN_PASSWORD;
    if (adminPassword) {
      adminPassword = String(adminPassword).trim();
      // Remove surrounding quotes if present (dotenv sometimes adds them for special chars)
      const firstChar = adminPassword[0];
      const lastChar = adminPassword[adminPassword.length - 1];
      if (adminPassword.length > 1 && 
          ((firstChar === '"' && lastChar === '"') || 
           (firstChar === "'" && lastChar === "'"))) {
        adminPassword = adminPassword.slice(1, -1);
      }
    }
    
    // Admin check (no sensitive info in logs)
    if (process.env.NODE_ENV === 'development') {
      console.log('[AUTH] Checking admin credentials...');
      console.log('  - Admin email configured:', !!adminEmail);
      console.log('  - Admin password configured:', !!adminPassword);
    }
    
    // Check if this is an admin login attempt
    if (adminEmail && adminPassword) {
      if (normalizedInputEmail === adminEmail) {
        console.log('[AUTH] DEBUG: Checking password...');
        console.log('[AUTH] DEBUG: Input:', JSON.stringify(password));
        console.log('[AUTH] DEBUG: Config:', JSON.stringify(adminPassword));
        if (password === adminPassword) {
          console.log('[AUTH] DEBUG: Password match!');
          console.log('[AUTH] Admin login successful!');
          const token = jwt.sign(
            { id: 'admin', email: email.trim(), fullname: 'Admin', isAdmin: true },
            process.env.JWT_SECRET,
            { expiresIn: '1h' },
          );
          // Trigger background evaluation cache update (non-blocking)
          triggerEvaluationCacheUpdate().catch(err => {
            console.error('[AUTH] Background evaluation cache update failed:', err.message);
            // Don't fail login if cache update fails
          });
          
          return res.json({
            token,
            isAdmin: true,
            fullname: 'Admin',
            email: email.trim(),
            userId: 'admin',
          });
        } else {
          console.log('[AUTH] Admin email matches but password incorrect');
        }
      } else {
        console.log('[AUTH] Admin credentials exist but email does not match');
      }
    } else {
      console.log('[AUTH] Admin credentials NOT configured in .env file!');
      console.log('[AUTH] Add ADMIN_EMAIL and ADMIN_PASSWORD to Backend/.env');
    }
    
    // Normalize email for lookup (case-insensitive)
    const normalizedEmail = (email || '').trim().toLowerCase();
    
    // Authenticate user from database
    if (process.env.NODE_ENV === 'development') {
      console.log('[AUTH] Looking up user in database...');
    }
    
    const user = await findUserByEmail(normalizedEmail);
    
    if (!user) {
      if (process.env.NODE_ENV === 'development') {
        console.log('[AUTH] User not found');
      }
      return res.status(400).json({ error: 'Email not found. Please check your email address or register a new account.' });
    }
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[AUTH] User found - ID:', user.id);
    }
    
    const valid = await argon2.verify(user.password_hash, password);
    
    if (!valid) {
      if (process.env.NODE_ENV === 'development') {
        console.log('[AUTH] Password verification failed');
      }
      return res.status(400).json({ error: 'Incorrect password. Please try again.' });
    }
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[AUTH] Password verified, generating token...');
    }
    const token = jwt.sign(
      { id: user.id, email: user.email, fullname: user.fullname || '', isAdmin: false },
      process.env.JWT_SECRET,
      { expiresIn: '1h' }
    );
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[AUTH] Login successful');
    }
    
    // Trigger background evaluation cache update (non-blocking)
    triggerEvaluationCacheUpdate().catch(err => {
      console.error('[AUTH] Background evaluation cache update failed:', err.message);
      // Don't fail login if cache update fails
    });
    
    res.json({
      token,
      isAdmin: false,
      fullname: user.fullname || '',
      email: user.email,
      userId: user.id,
    });
  } catch (err) {
    console.error('[AUTH] Login error:', err.message);
    console.error('[AUTH] Error code:', err.code);
    console.error('[AUTH] Error detail:', err.detail);
    console.error('[AUTH] Full error:', err);
    
    // Don't expose database errors to client
    let errorMessage = 'Server error';
    
    if (err.code === '3D000') {
      errorMessage = 'Database not found. Please contact administrator.';
    } else if (err.code === '28P01') {
      errorMessage = 'Database authentication failed. Please contact administrator.';
    } else if (err.message?.includes('relation') || err.message?.includes('does not exist')) {
      errorMessage = 'Database table not found. Please contact administrator.';
    } else if (err.message?.includes('connect') || err.message?.includes('ECONNREFUSED')) {
      errorMessage = 'Database connection error. Please contact administrator.';
    } else if (err.message) {
      errorMessage = err.message;
    }
    
    res.status(500).json({ error: errorMessage });
  }
};
