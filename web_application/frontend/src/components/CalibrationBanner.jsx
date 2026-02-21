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
      <span className="small">
        <strong className="text-white">Improve accuracy —</strong>
        {' '}Your camera angle may differ from the default model.
        Set up your personal gaze model for better results.
      </span>
      <div className="d-flex gap-2 ms-3 flex-shrink-0">
        <Link to="/calibrate" className="btn btn-cyber btn-sm fw-bold">
          CALIBRATE
        </Link>
        <button
          className="btn btn-cyber btn-sm"
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
