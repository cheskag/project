import express from 'express';
import insightsController from '../controllers/insightsController.js';
import { authenticateJWT } from '../middleware/authMiddleware.js';

const router = express.Router();

// Health check - no auth required for system check
router.get('/health', insightsController.healthCheck);

// All insights routes (except health) require authentication
router.use(authenticateJWT);

// Get general insights
router.get('/', insightsController.getGeneralInsights);

// Get insights for a specific date
router.get('/date/:date', insightsController.getDateInsights);

// Get available dates for analysis
router.get('/dates', insightsController.getAvailableDates);

// Get sentiment analysis
router.get('/sentiment', insightsController.getSentimentAnalysis);

// Get accuracy metrics (reads from cache for fast response)
router.get('/accuracy', insightsController.getAccuracyMetrics);

// Refresh accuracy cache manually (for testing or forced refresh)
router.post('/accuracy/refresh', insightsController.refreshAccuracyCache);

// Get trend forecast
router.get('/trend', insightsController.getTrendForecast);

// Chat with the insights bot
router.post('/chat', insightsController.chatWithBot);

export default router;
