import React, { useState } from 'react';
import { GAZE_STATES } from '../constants/videoConstants';
import { submitCorrection } from '../services/calibrationService';

const GAZE_CLASS_NAMES = ['Looking Ahead', 'Left Mirror', 'Right Mirror', 'Rear Mirror'];

/**
 * Modal that lets the user correct a mislabelled gaze segment.
 * On submission it calls the backend, which adds the correction and immediately
 * retrains the user's personal model.
 *
 * Props:
 *   jobId         — the analysis job ID
 *   detectedLabel — what the model currently predicts for this segment
 *   startTime     — segment start time (seconds)
 *   endTime       — segment end time (seconds)
 *   onClose       — called when the modal should close without saving
 *   onSuccess     — called(correctLabel) after a successful submission
 */
const GazeCorrectionModal = ({
  jobId,
  detectedLabel,
  startTime,
  endTime,
  calibrationId,
  onClose,
  onSuccess,
}) => {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSelect = async (correctLabel) => {
    setSubmitting(true);
    setError(null);
    try {
      await submitCorrection(jobId, startTime, endTime, correctLabel, calibrationId);
      onSuccess(correctLabel);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to submit correction. Please try again.');
      setSubmitting(false);
    }
  };

  return (
    /* Backdrop */
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={onClose}
    >
      {/* Panel */}
      <div
        className="card card-cyber shadow-lg"
        style={{ minWidth: 320, maxWidth: 420, width: '90%' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="card-header">
          <h4>Correct Gaze Label</h4>
          <p className="text-muted small mb-0">
            Detected:{' '}
            <strong style={{ color: GAZE_STATES[detectedLabel]?.color }}>
              {detectedLabel || 'N/A'}
            </strong>
            <span className="ms-2 opacity-75">
              ({startTime.toFixed(1)}s – {endTime.toFixed(1)}s)
            </span>
          </p>
        </div>

        <div className="card-body">
          <p className="text-muted small mb-3" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.75rem' }}>
            Select the correct label:
          </p>

          <div className="d-grid gap-2 mb-3">
            {GAZE_CLASS_NAMES.map(cls => (
              <button
                key={cls}
                className="btn btn-cyber"
                style={{
                  borderColor: GAZE_STATES[cls]?.color,
                  color: GAZE_STATES[cls]?.color,
                  textAlign: 'left',
                  background: cls === detectedLabel ? 'rgba(255,255,255,0.04)' : undefined,
                }}
                disabled={submitting}
                onClick={() => handleSelect(cls)}
              >
                {GAZE_STATES[cls]?.icon}{' '}
                {cls}
                {cls === detectedLabel && (
                  <span className="ms-2 text-muted" style={{ fontSize: '0.75rem', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>
                    (current)
                  </span>
                )}
              </button>
            ))}
          </div>

          {error && (
            <div className="alert alert-cyber-danger py-2 mb-3" style={{ fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          {submitting && (
            <p className="text-muted text-center small mb-3">
              <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
              Saving correction and retraining model…
            </p>
          )}

          <button
            className="btn btn-cyber w-100"
            onClick={onClose}
            disabled={submitting}
          >
            CANCEL
          </button>
        </div>
      </div>
    </div>
  );
};

export default GazeCorrectionModal;
