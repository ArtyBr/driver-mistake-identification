import React, { useState } from 'react';
import { submitJobReport } from '../services/api';

/**
 * Modal for reporting an issue in analysis results.
 * Accepts free-form notes and an optional list of video timestamps.
 *
 * Props:
 *   jobId     — the analysis job ID
 *   onClose   — called when modal should close without saving
 *   onSuccess — called(reportId) after successful submission
 */
const ReportIssueModal = ({ jobId, onClose, onSuccess }) => {
  const [notes, setNotes] = useState('');
  const [timestamps, setTimestamps] = useState(['']);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const addTimestamp = () => setTimestamps(ts => [...ts, '']);

  const removeTimestamp = (i) =>
    setTimestamps(ts => ts.length === 1 ? [''] : ts.filter((_, idx) => idx !== i));

  const updateTimestamp = (i, val) =>
    setTimestamps(ts => ts.map((t, idx) => idx === i ? val : t));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const validTs = timestamps
        .map(t => t.trim())
        .filter(Boolean)
        .map(Number)
        .filter(n => !isNaN(n) && n >= 0);
      const payload = {
        notes: notes.trim() || null,
        timestamps: validTs.length > 0 ? validTs : null,
      };
      const result = await submitJobReport(jobId, payload);
      onSuccess(result.report_id);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to submit report. Please try again.');
      setSubmitting(false);
    }
  };

  return (
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
      <div
        className="card card-cyber shadow-lg"
        style={{ minWidth: 340, maxWidth: 460, width: '90%' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="card-header">
          <h4><i className="bi bi-flag me-2" />Report Issue</h4>
          <p className="text-muted small mb-0">
            Describe any false positives or missed detections in this analysis.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="card-body d-flex flex-column gap-3">

            {/* Notes */}
            <div>
              <label
                className="form-label text-muted small text-uppercase"
                style={{ letterSpacing: '0.5px', fontSize: '0.75rem' }}
              >
                Notes
              </label>
              <textarea
                className="form-control form-control-sm"
                rows={4}
                placeholder="Describe the issue…"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                disabled={submitting}
                style={{
                  background: 'var(--bg-panel)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  resize: 'vertical',
                }}
              />
            </div>

            {/* Timestamps */}
            <div>
              <div className="d-flex align-items-center justify-content-between mb-1">
                <label
                  className="form-label text-muted small text-uppercase mb-0"
                  style={{ letterSpacing: '0.5px', fontSize: '0.75rem' }}
                >
                  Timestamps (s) <span className="text-muted fw-normal" style={{ textTransform: 'none' }}>— optional</span>
                </label>
                <button
                  type="button"
                  className="btn btn-cyber btn-sm py-0 px-2"
                  style={{ fontSize: '0.75rem' }}
                  onClick={addTimestamp}
                  disabled={submitting}
                >
                  <i className="bi bi-plus" /> Add
                </button>
              </div>
              <div className="d-flex flex-column gap-1">
                {timestamps.map((t, i) => (
                  <div key={i} className="d-flex gap-1 align-items-center">
                    <input
                      type="number"
                      className="form-control form-control-sm"
                      placeholder="e.g. 12.5"
                      value={t}
                      onChange={e => updateTimestamp(i, e.target.value)}
                      min="0"
                      step="0.1"
                      disabled={submitting}
                      style={{
                        background: 'var(--bg-panel)',
                        color: 'var(--text-primary)',
                        border: '1px solid var(--border-color)',
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-link text-muted p-0 flex-shrink-0"
                      style={{ fontSize: '1rem', lineHeight: 1 }}
                      onClick={() => removeTimestamp(i)}
                      disabled={submitting}
                      title="Remove"
                    >
                      <i className="bi bi-x" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {error && (
              <div className="alert alert-cyber-danger py-2 mb-0" style={{ fontSize: '0.85rem' }}>
                {error}
              </div>
            )}

            <div className="d-flex gap-2">
              <button
                type="submit"
                className="btn btn-cyber-primary flex-grow-1"
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                    Submitting…
                  </>
                ) : (
                  <><i className="bi bi-flag me-1" />Submit Report</>
                )}
              </button>
              <button
                type="button"
                className="btn btn-cyber"
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ReportIssueModal;
