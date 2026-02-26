import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const VerifiedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '50vh' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!user.is_verified) {
    // If not verified, redirect to home (where they will see the banner)
    // or we could show a specific "please verify" page.
    // For now, let's just let them see the home page with the banner.
    return <Navigate to="/" replace />;
  }

  return children;
};

export default VerifiedRoute;
