import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

const VerificationBanner = () => {
  const { user } = useAuth();

  if (!user || user.is_verified) {
    return null;
  }

  return (
    <div className="alert mb-4 py-3 d-flex flex-column flex-md-row align-items-md-center justify-content-between shadow-sm" 
         style={{ 
           backgroundColor: 'rgba(255, 193, 7, 0.1)', 
           border: '1px solid var(--accent-warning)',
           borderLeft: '5px solid var(--accent-warning)', 
           borderRadius: '4px' 
         }}>
      <div className="d-flex align-items-center mb-2 mb-md-0">
        <i className="bi bi-person-fill-lock me-3 fs-4 text-warning"></i>
        <div>
          <h6 className="mb-0 fw-bold text-white">Account Pending Approval</h6>
          <p className="mb-0 small text-white opacity-75">
            Your account is waiting for administrator verification. Some features may be restricted until then.
          </p>
        </div>
      </div>
    </div>
  );
};

export default VerificationBanner;
