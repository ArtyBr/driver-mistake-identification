import React from 'react';

const ACTIVE_STATUSES = new Set(['PENDING', 'SUBMITTED', 'RUNNING']);

const STATUS_MAP = {
  COMPLETED: { cls: 'bg-success',        label: 'Completed' },
  RUNNING:   { cls: 'bg-primary',        label: 'Running'   },
  SUBMITTED: { cls: 'bg-info text-dark', label: 'Queued'    },
  PENDING:   { cls: 'bg-secondary',      label: 'Pending'   },
  FAILED:    { cls: 'bg-danger',         label: 'Failed'    },
};

const formatDuration = (seconds) => {
  if (!seconds) return 'Unknown duration';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
};

const formatDate = (dateString) => {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
};

const formatEta = (ms) => {
  if (ms == null || ms <= 0) return null;
  const mins = Math.round(ms / 60000);
  return mins < 1 ? '< 1m remaining' : `~${mins}m remaining`;
};

/**
 * Shared list item for displaying an analysis in any context.
 *
 * Props:
 *   analysis  – AnalysisItem object (id, name, status, progress, video_count,
 *               duration_seconds, created_at)
 *   selected  – boolean; when true shows a checkmark and highlight
 *   onClick   – click handler (navigation or selection, depending on context)
 *   etaMs     – estimated milliseconds remaining (from useAnalysesList.getEtaMs)
 */
const AnalysisListItem = ({ analysis, selected, onClick, etaMs }) => {
  const isActive = ACTIVE_STATUSES.has(analysis.status);
  const { cls, label } = STATUS_MAP[analysis.status] || { cls: 'bg-secondary', label: analysis.status };
  const eta = isActive ? formatEta(etaMs) : null;

  return (
    <div
      className={`analysis-item-modern mb-2 p-3 rounded ${selected ? 'selected-analysis' : ''}`}
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      {/* Row 1: name + badge + optional checkmark */}
      <div className="d-flex justify-content-between align-items-start">
        <div className="d-flex align-items-center flex-wrap gap-1">
          <span className="fw-bold text-white">{analysis.name}</span>
          {analysis.status && (
            <span className={`badge ${cls} ms-1`} style={{ fontSize: '0.7rem' }}>{label}</span>
          )}
        </div>
        {selected && <i className="bi bi-check-circle-fill text-accent-primary" />}
      </div>

      {/* Row 2: metadata */}
      <div className="small text-muted d-flex justify-content-between mt-1">
        <span>
          <i className="bi bi-files me-1" />
          {analysis.video_count} videos &bull; {formatDuration(analysis.duration_seconds)}
        </span>
        <span className="opacity-75">{formatDate(analysis.created_at)}</span>
      </div>

      {/* Row 3: progress bar + ETA (active jobs only) */}
      {isActive && (
        <div className="mt-2">
          <div className="progress" style={{ height: '6px', borderRadius: '3px' }}>
            <div
              className="progress-bar progress-bar-striped progress-bar-animated"
              role="progressbar"
              style={{ width: `${analysis.progress || 0}%` }}
              aria-valuenow={analysis.progress || 0}
              aria-valuemin="0"
              aria-valuemax="100"
            />
          </div>
          <div className="d-flex justify-content-between text-muted mt-1" style={{ fontSize: '0.75rem' }}>
            <span>{analysis.progress || 0}% complete</span>
            {eta
              ? <span>{eta}</span>
              : <span className="fst-italic opacity-75">Estimating time remaining…</span>
            }
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisListItem;
