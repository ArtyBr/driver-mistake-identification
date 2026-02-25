import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { getCalibrationStatus } from '../services/calibrationService';

const DISMISSED_KEY = 'calibration_banner_dismissed';

/**
 * Shows a nudge banner prompting users to set up their personal gaze model.
 * Only shown when the user is logged in and has not yet trained a calibration model.
 * Dismissible (stored in localStorage).
 */
const CalibrationBanner = () => {
  const { user } = useAuth();
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (localStorage.getItem(DISMISSED_KEY)) return;

    getCalibrationStatus()
      .then(status => { if (!status.is_trained) setShow(true); })
      .catch(() => {});
  }, [user]);

  if (!show || !user) return null;

  const handleDismiss = () => {
    localStorage.setItem(DISMISSED_KEY, '1');
    setShow(false);
  };

  return (
    <div
      className="alert alert-cyber d-flex justify-content-between align-items-center mb-4"
      style={{ borderLeft: '4px solid var(--accent-info)' }}
      role="alert"
    >
      <div className="d-flex align-items-center">
        <div className="bg-info-subtle p-2 rounded-circle me-3 d-none d-md-flex" style={{ width: 40, height: 40, alignItems: 'center', justifyContent: 'center' }}>
          <i className="bi bi-info-circle text-info fs-5"></i>
        </div>
        <div>
          <strong className="text-white d-block mb-1">Optimise Analysis Accuracy</strong>
          <span className="small text-muted">
            The default gaze model may not account for your specific camera placement. 
            Create a personal calibration for more precise results.
          </span>
        </div>
      </div>
      <div className="d-flex gap-2 ms-3 flex-shrink-0">
        <Link to="/calibrate" className="btn btn-cyber-primary btn-sm fw-bold px-3">
          CALIBRATE NOW
        </Link>
        <button
          className="btn btn-outline-cyber btn-sm"
          onClick={handleDismiss}
          aria-label="Dismiss"
        >
          DISMISS
        </button>
      </div>
    </div>
  );
};

export default CalibrationBanner;
