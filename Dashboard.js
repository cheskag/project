// src/pages/AuthLanding.js
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Login from './Login';
import Register from './Register';

const slides = [
  {
    title: "Welcome to CRYPTOGAUGE",
    desc: "Unlock Crypto Confidence. Discover the easiest way to predict, learn, and grow in crypto — even if you're just starting. No experience needed.",
    img: "/Images/cryptochart.jpg"
  },
  {
    title: "Smart Predictions. Simple Learning. Real Growth.",
    desc: "Our beginner-friendly platform helps you understand trading and make informed crypto predictions with ease.",
    img: "/Images/cryptochart2.jpg"
  },
  {
    title: "Start Your Crypto Journey Today.",
    desc: "Learn the ropes, predict with confidence, and take your first step into the world of crypto — all in one app.",
    img: "/Images/cryptochart3.jpg"
  },
  {
    title: "Community Forum",
    desc: "Join a vibrant community where you can share experiences, collaborate, and learn from fellow crypto enthusiasts. Grow together!",
    img: "/Images/community.avif"
  },
  {
    title: "Prediction",
    desc: "Make your mark! Predict if coins will go up or down and see how your insights stack up against the crowd.",
    img: "/Images/cryptochart4.jpg"
  },
  {
    title: "FAQ & Tools",
    desc: "Never feel lost! Our accessible, beginner-friendly UI and clear terms make crypto easy for everyone.",
    img: "/Images/cryptochart5.jpg"
  },
  {
    title: "Crypto Data",
    desc: "Stay ahead with real-time data on XRP, Bitcoin, and Ethereum. Make decisions with the latest info at your fingertips.",
    img: "/Images/cryptochart2.jpg"
  }
];

const AuthLanding = () => {
  const navigate = useNavigate();
  const [index, setIndex] = useState(0);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showRegisterModal, setShowRegisterModal] = useState(false);

  // Check if user is already authenticated and redirect
  useEffect(() => {
    const token = localStorage.getItem('token');
    const isAdmin = localStorage.getItem('isAdmin') === 'true';
    
    if (token && token !== 'undefined' && token !== 'null') {
      // User is logged in, redirect to appropriate page
      if (isAdmin) {
        navigate('/admin', { replace: true });
      } else {
        navigate('/dashboard', { replace: true });
      }
    }
  }, [navigate]);

  // Auto-slide every 10s unless user interacts
  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((prev) => (prev + 1) % slides.length);
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Modal handlers
  const handleLoginClick = () => {
    setShowLoginModal(true);
    setShowRegisterModal(false);
    document.body.style.overflow = 'hidden';
  };

  const handleRegisterClick = () => {
    setShowRegisterModal(true);
    setShowLoginModal(false);
    document.body.style.overflow = 'hidden';
  };

  const closeModals = () => {
    setShowLoginModal(false);
    setShowRegisterModal(false);
    document.body.style.overflow = '';
  };

  // Close modals on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        closeModals();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f172a, #3b82f6 80%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Crossfade Images */}
      <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0 }}>
        <AnimatePresence mode="wait">
          <motion.img
            key={index}
            src={slides[index].img}
            alt=""
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.25 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.7, ease: 'easeInOut' }}
            style={{
              position: 'absolute',
              top: 0, left: 0, width: '100%', height: '100%',
              objectFit: 'cover',
              pointerEvents: 'none',
              zIndex: 0
            }}
          />
        </AnimatePresence>
      </div>
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          zIndex: 2,
          pointerEvents: 'none'
        }}
      >
        <motion.img
          src="/mainCryptologo-noBG.png"
          alt="CryptoGauge logo"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          style={{
            marginTop: '-10vh',
            width: 'clamp(220px, 28vw, 360px)'
          }}
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.6 }}
          style={{
            marginTop: '6vh',
    width: 'min(98vw, 1040px)',
            textAlign: 'center',
            pointerEvents: 'auto',
            minHeight: '300px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '1.2rem'
          }}
          >
            <motion.h1 
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.5 }}
            style={{
              color: '#fff',
              fontSize: 'clamp(2.8rem, 6vw, 4rem)',
              letterSpacing: '-0.01em',
              fontWeight: 600,
              fontFamily: "'Poppins', 'Segoe UI', sans-serif"
            }}
            >
              {slides[index].title}
            </motion.h1>
            <motion.p 
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            style={{
              color: '#cbd5e1',
              fontSize: 'clamp(1.2rem, 2.7vw, 1.6rem)',
              margin: '0 auto 44px',
              maxWidth: '96%',
              lineHeight: 1.7,
              fontWeight: 400,
              fontFamily: "'IBM Plex Sans', 'Segoe UI', sans-serif"
            }}
            >
              {slides[index].desc}
            </motion.p>
        </motion.div>
      </div>
      {/* Main Action Buttons */}
      <div style={{
        position: 'absolute', bottom: 120, left: 0, width: '100%',
        display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 3, gap: 32
      }}>
        <motion.button
          onClick={handleLoginClick}
          whileHover={{ scale: 1.05, boxShadow: '0 8px 35px rgba(59,130,246,0.4)' }}
          whileTap={{ scale: 0.95 }}
          style={{
            padding: '16px 40px',
            fontSize: 20,
            borderRadius: 12,
            border: 'none',
            background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
            color: '#fff',
            fontWeight: '600',
            cursor: 'pointer',
            boxShadow: '0 6px 30px rgba(59,130,246,0.3)',
            transition: 'all 0.3s ease',
            letterSpacing: '0.5px'
          }}
        >
          Log In
        </motion.button>
        <motion.button
          onClick={handleRegisterClick}
          whileHover={{ scale: 1.05, boxShadow: '0 8px 35px rgba(255,255,255,0.4)' }}
          whileTap={{ scale: 0.95 }}
          style={{
            padding: '16px 40px',
            fontSize: 20,
            borderRadius: 12,
            border: 'none',
            background: 'linear-gradient(135deg, #ffffff, #f8fafc)',
            color: '#3b82f6',
            fontWeight: '600',
            cursor: 'pointer',
            boxShadow: '0 6px 30px rgba(59,130,246,0.3)',
            transition: 'all 0.3s ease',
            letterSpacing: '0.5px'
          }}
        >
          Create Account
        </motion.button>
      </div>
      {/* Login Modal */}
      <AnimatePresence>
        {showLoginModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              background: 'rgba(0, 0, 0, 0.8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 1000,
              backdropFilter: 'blur(4px)',
              overflow: 'visible',
              padding: '20px'
            }}
            onClick={closeModals}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.8, y: 50 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.8, y: 50 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              onClick={(e) => e.stopPropagation()}
              style={{
                background: '#1e293b',
                borderRadius: '16px',
                padding: '2rem',
                maxWidth: '450px',
                width: '90%',
                maxHeight: '90vh',
                overflow: 'visible',
                position: 'relative',
                zIndex: 1001
              }}
            >
              <button
                onClick={closeModals}
                style={{
                  position: 'absolute',
                  top: '1rem',
                  right: '1rem',
                  background: 'rgba(255, 255, 255, 0.1)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#fff',
                  fontSize: '28px',
                  cursor: 'pointer',
                  padding: '0.5rem',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '40px',
                  height: '40px',
                  transition: 'all 0.2s ease',
                  lineHeight: '1',
                  zIndex: 1002
                }}
                onMouseEnter={(e) => {
                  e.target.style.background = 'rgba(239, 68, 68, 0.8)';
                  e.target.style.borderColor = '#ef4444';
                  e.target.style.transform = 'rotate(90deg)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.background = 'rgba(255, 255, 255, 0.1)';
                  e.target.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                  e.target.style.transform = 'rotate(0deg)';
                }}
              >
                ×
              </button>
                <Login onClose={closeModals} onSwitchToRegister={handleRegisterClick} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Register Modal */}
      <AnimatePresence>
        {showRegisterModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              background: 'rgba(0, 0, 0, 0.8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 1000,
              backdropFilter: 'blur(4px)',
              overflow: 'visible',
              padding: '20px'
            }}
            onClick={closeModals}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.8, y: 50 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.8, y: 50 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#1e293b',
              borderRadius: '16px',
              padding: '2rem',
              maxWidth: '450px',
              width: '90%',
              maxHeight: '90vh',
              overflow: 'visible',
              position: 'relative',
              zIndex: 1001
            }}
            >
              <button
                onClick={closeModals}
                style={{
                  position: 'absolute',
                  top: '1rem',
                  right: '1rem',
                  background: 'rgba(255, 255, 255, 0.1)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#fff',
                  fontSize: '28px',
                  cursor: 'pointer',
                  padding: '0.5rem',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '40px',
                  height: '40px',
                  transition: 'all 0.2s ease',
                  lineHeight: '1',
                  zIndex: 1002
                }}
                onMouseEnter={(e) => {
                  e.target.style.background = 'rgba(239, 68, 68, 0.8)';
                  e.target.style.borderColor = '#ef4444';
                  e.target.style.transform = 'rotate(90deg)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.background = 'rgba(255, 255, 255, 0.1)';
                  e.target.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                  e.target.style.transform = 'rotate(0deg)';
                }}
              >
                ×
              </button>
              <Register onClose={closeModals} onSwitchToLogin={handleLoginClick} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default AuthLanding;



