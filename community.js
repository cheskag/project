import express from 'express';
import { register, login } from '../controllers/authController.js';
import { body } from 'express-validator';

const router = express.Router();

// Registration route
router.post('/register', [
  body('email').isEmail().withMessage('Invalid email'),
  body('password')
    .isLength({ min: 8 })
    .matches(/[a-z]/).withMessage('Must contain a lowercase letter')
    .matches(/[A-Z]/).withMessage('Must contain an uppercase letter')
    .matches(/[0-9]/).withMessage('Must contain a number')
    .matches(/[^A-Za-z0-9]/).withMessage('Must contain a special character'),
  body('recaptchaToken').notEmpty().withMessage('reCAPTCHA required')
], register);

// Login route
router.post('/login', [
  body('email').isEmail().withMessage('Invalid email'),
  body('password').notEmpty().withMessage('Password required'),
  body('recaptchaToken').notEmpty().withMessage('reCAPTCHA required')
], login);

export default router; 