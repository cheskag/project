import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { clearSession, isSessionActive, recordActivity } from '../utils/session';

const hasToken = () => {
  const token = localStorage.getItem('token');
  return !!token && token !== 'undefined' && token !== 'null';
};

const isAdmin = () => {
  const adminStatus = localStorage.getItem('isAdmin');
  return adminStatus === 'true';
};

/**
 * Protected Route Component
 * Wraps routes that require authentication. Re-checks auth on every render
 * to support browser back/forward navigation properly.
 * 
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Child components to render if authenticated
 * @param {boolean} props.requireAdmin - If true, also requires admin privileges
 * @returns {React.ReactElement} - Either children or Navigate component
 */
export const ProtectedRoute = ({ children, requireAdmin = false }) => {
  const location = useLocation();
  
  // Re-check auth on every render (when location changes via browser navigation)
  // This ensures back/forward buttons work correctly
  const authenticated = hasToken() && isSessionActive();
  const adminStatus = isAdmin();
  
  if (!authenticated) {
    clearSession();
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }
  
  recordActivity();

  if (requireAdmin && !adminStatus) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
};

export default ProtectedRoute;

