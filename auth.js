import express from 'express';
import { uploadJson } from '../controllers/adminController.js';
import { authenticateJWT, requireAdmin } from '../middleware/authMiddleware.js';

const router = express.Router();

// Upload JSON data (admin only)
router.post('/upload-json', authenticateJWT, requireAdmin, uploadJson);

export default router; 