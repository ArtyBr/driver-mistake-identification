import React, { useState } from 'react';
import { submitErrorReport } from '../../services/api';

const ReportErrorModal = ({ jobId, timestamp, onClose, onSuccess }) => {
  const [eventType, setEventType] = useState('');
  const [reportType, setReportType] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!eventType || !reportType) {
      setError("Please select both an event type and a report type.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await submitErrorReport(jobId, {
        timestamp: timestamp,
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
    <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.8)' }} tabIndex="-1">
      <div className="modal-dialog modal-dialog-centered modal-lg">
        <div className="modal-content bg-panel border-info-subtle shadow-lg">
          <div className="modal-header border-bottom border-secondary">
            <h5 className="modal-title text-white">
              <i className="bi bi-flag-fill text-warning me-2"></i>
              Report an Error
            </h5>
            <button type="button" className="btn-close btn-close-white" onClick={onClose} aria-label="Close"></button>
          </div>
          
          <div className="modal-body text-white">
            {error && (
              <div className="alert alert-danger py-2 px-3 mb-3" style={{ fontSize: '0.9rem' }}>
                {error}
              </div>
            )}
            
            <div className="mb-3 d-flex align-items-center gap-2">
              <span className="badge bg-secondary">Timestamp: {timestamp.toFixed(2)}s</span>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="mb-4">
                <label className="form-label fw-bold">1. What kind of event is this regarding?</label>
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
                <div className="form-text text-muted mt-2" style={{ fontSize: '0.85rem' }}>
                  <strong>Lane Change:</strong> Moving from one lane to an adjacent lane moving in the same direction.<br/>
                  <strong>Turn:</strong> Changing roads at an intersection or turning into a driveway.
                </div>
              </div>

              <div className="mb-4">
                <label className="form-label fw-bold">2. What type of error is this?</label>
                <div className="d-flex flex-column gap-3">
                  <div 
                    className={`p-3 rounded border ${reportType === 'false_positive' ? 'border-warning bg-warning bg-opacity-10' : 'border-secondary'}`}
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
                        The system detected an event or an error that didn't actually happen. For example, it flagged a "Left Lane Change" when you were just driving straight, or it said you didn't check your mirrors when you actually did.
                      </small>
                    </div>
                  </div>

                  <div 
                    className={`p-3 rounded border ${reportType === 'false_negative' ? 'border-info bg-info bg-opacity-10' : 'border-secondary'}`}
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
                        The system completely missed a real event or failed to flag a genuine mistake. For example, you made a lane change but the system didn't notice, or you forgot to check your mirrors but the system marked it as "safe".
                      </small>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mb-3">
                <label className="form-label fw-bold">3. Additional Details (Optional)</label>
                <textarea 
                  className="form-control bg-dark text-white border-secondary" 
                  rows="3" 
                  placeholder="Explain what exactly went wrong so the admin can review it..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                ></textarea>
              </div>

              <div className="d-flex justify-content-end gap-2 mt-4">
                <button type="button" className="btn btn-outline-secondary" onClick={onClose} disabled={submitting}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-warning text-dark fw-bold" disabled={submitting}>
                  {submitting ? (
                    <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Submitting...</>
                  ) : (
                    <><i className="bi bi-send-fill me-2"></i> Submit Report</>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportErrorModal;