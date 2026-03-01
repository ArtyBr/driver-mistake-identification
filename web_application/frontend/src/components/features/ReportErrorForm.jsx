import React, { useState, useEffect } from 'react';
import { submitErrorReport } from '../../services/api';

const ReportErrorForm = ({ jobId, currentTime, onClose, onSuccess }) => {
  const [eventType, setEventType] = useState('');
  const [reportType, setReportType] = useState('');
  const [description, setDescription] = useState('');
  const [reportTime, setReportTime] = useState(currentTime.toFixed(2));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Allow the form to track current time until the user manually changes it
  // or syncs it. Actually, a static initial time + "Sync" button is usually better
  // so we don't overwrite their typed value if the video plays.

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!eventType || !reportType) {
      setError("Please select both an event type and a report type.");
      return;
    }

    const parsedTime = parseFloat(reportTime);
    if (isNaN(parsedTime) || parsedTime < 0) {
      setError("Please enter a valid timestamp.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await submitErrorReport(jobId, {
        timestamp: parsedTime,
        event_type: eventType,
        report_type: reportType,
        description: description
      });
      if (onSuccess) onSuccess();
    } catch (err) {
      console.error("Error submitting report:", err);
      setError("Failed to submit report. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card card-cyber mt-3 border-warning shadow" data-bs-theme="dark">
      <div className="card-header border-bottom border-secondary d-flex justify-content-between align-items-center bg-dark">
        <h5 className="mb-0 text-white fs-6">
          <i className="bi bi-flag-fill text-warning me-2"></i>
          Report Model/Detection Error
        </h5>
        <button type="button" className="btn-close btn-close-white" style={{ fontSize: '0.8rem' }} onClick={onClose} aria-label="Close"></button>
      </div>
      
      <div className="card-body bg-panel text-white">
        {error && (
          <div className="alert alert-danger py-2 px-3 mb-3" style={{ fontSize: '0.9rem' }}>
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="form-label fw-bold">1. Error Timestamp</label>
            <div className="d-flex align-items-center gap-2">
              <input 
                type="number" 
                step="0.1" 
                className="form-control bg-dark text-white border-secondary w-auto" 
                value={reportTime}
                onChange={(e) => setReportTime(e.target.value)}
                style={{ maxWidth: '100px' }}
                required
              />
              <span className="text-muted small">seconds</span>
              <button 
                type="button" 
                className="btn btn-sm btn-outline-info ms-2"
                onClick={() => setReportTime(currentTime.toFixed(2))}
                title="Update to current video timestamp"
              >
                Sync with Video
              </button>
            </div>
            <div className="form-text text-muted small mt-1">
              You can play or scrub through the video above to find the exact moment, then click "Sync".
            </div>
          </div>

          <div className="mb-4">
            <label className="form-label fw-bold">2. What kind of event is this regarding?</label>
            <select 
              className="form-select bg-dark text-white border-secondary" 
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              required
            >
              <option value="" disabled>Select event type...</option>
              <option value="left_lane_change">Left Lane Change</option>
              <option value="right_lane_change">Right Lane Change</option>
              <option value="left_turn">Left Turn</option>
              <option value="right_turn">Right Turn</option>
              <option value="other">Other / Unknown</option>
            </select>
          </div>

          <div className="mb-4">
            <label className="form-label fw-bold">3. What type of error is this?</label>
            <div className="d-flex flex-column gap-2">
              <div 
                className={`p-2 rounded border ${reportType === 'false_positive' ? 'border-warning bg-warning bg-opacity-10' : 'border-secondary'}`}
                style={{ cursor: 'pointer' }}
                onClick={() => setReportType('false_positive')}
              >
                <div className="form-check m-0">
                  <input 
                    className="form-check-input" 
                    type="radio" 
                    name="reportType" 
                    id="false_positive" 
                    checked={reportType === 'false_positive'}
                    onChange={() => setReportType('false_positive')}
                  />
                  <label className="form-check-label fw-bold d-block" htmlFor="false_positive">
                    False Positive (System imagined it)
                  </label>
                  <small className="text-muted d-block mt-1">
                    System detected an event or an error that didn't happen (e.g. flagged a missing mirror check, but you checked it).
                  </small>
                </div>
              </div>

              <div 
                className={`p-2 rounded border ${reportType === 'false_negative' ? 'border-info bg-info bg-opacity-10' : 'border-secondary'}`}
                style={{ cursor: 'pointer' }}
                onClick={() => setReportType('false_negative')}
              >
                <div className="form-check m-0">
                  <input 
                    className="form-check-input" 
                    type="radio" 
                    name="reportType" 
                    id="false_negative" 
                    checked={reportType === 'false_negative'}
                    onChange={() => setReportType('false_negative')}
                  />
                  <label className="form-check-label fw-bold d-block" htmlFor="false_negative">
                    False Negative (System missed it)
                  </label>
                  <small className="text-muted d-block mt-1">
                    System completely missed a real event or failed to flag a genuine mistake (e.g. you made a turn, but system didn't notice).
                  </small>
                </div>
              </div>
            </div>
          </div>

          <div className="mb-3">
            <label className="form-label fw-bold">4. Additional Details (Optional)</label>
            <textarea 
              className="form-control bg-dark text-white border-secondary" 
              rows="2" 
              placeholder="Explain what went wrong..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            ></textarea>
          </div>

          <div className="d-flex justify-content-end gap-2 mt-3">
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-sm btn-warning text-dark fw-bold" disabled={submitting}>
              {submitting ? (
                <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Submitting...</>
              ) : (
                <><i className="bi bi-send-fill me-1"></i> Submit Report</>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ReportErrorForm;