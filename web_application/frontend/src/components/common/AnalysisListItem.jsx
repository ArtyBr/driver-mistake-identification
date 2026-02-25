import React, { useState, useEffect } from 'react';
import { getJobEvents } from '../../services/api';

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

// ---------------------------------------------------------------------------
// Event display helpers
// ---------------------------------------------------------------------------

function pctColor(pct) {
  if (pct == null) return 'var(--text-muted)';
  if (pct >= 75) return 'var(--accent-success)';
  if (pct >= 40) return '#e5a500';
  return 'var(--accent-danger)';
}

/**
 * Shows one event type (Turns or Lane Changes) with optional left/right expansion.
 * stopPropagation prevents the parent AnalysisListItem click from firing.
 */
function TypeSection({ label, data }) {
  const [open, setOpen] = useState(false);
  if (!data || data.total === 0) return null;

  const hasDirections = (data.left?.total || 0) + (data.right?.total || 0) > 0;

  const toggle = (e) => {
    e.stopPropagation();
    if (hasDirections) setOpen(o => !o);
  };

  return (
    <div className="me-4">
      {/* Summary row */}
      <div
        className="d-flex align-items-center gap-1"
        onClick={toggle}
        style={{ cursor: hasDirections ? 'pointer' : 'default', userSelect: 'none' }}
      >
        {hasDirections && (
          <span style={{
            display: 'inline-block',
            fontSize: '0.6rem',
            transition: 'transform 0.15s',
            transform: open ? 'rotate(90deg)' : 'none',
            color: 'var(--text-muted)',
            marginRight: 2,
          }}>▶</span>
        )}
        <span className="small text-muted">{label}:</span>
        <span className="small fw-semibold text-white">{data.total}</span>
        {data.pct_safe != null && (
          <span className="small fw-semibold" style={{ color: pctColor(data.pct_safe) }}>
            ({data.pct_safe}% safe)
          </span>
        )}
        <span className="small text-muted">{data.safe} ✓ · {data.unsafe} ✗</span>
      </div>

      {/* Direction breakdown (expanded) */}
      {open && hasDirections && (
        <div className="mt-1 ms-3 d-flex flex-wrap gap-3" onClick={e => e.stopPropagation()}>
          {['left', 'right'].map(dir => {
            const d = data[dir];
            if (!d || d.total === 0) return null;
            return (
              <div key={dir} className="small">
                <span className="text-muted text-capitalize">{dir}: </span>
                <span className="text-white">{d.total}</span>
                {d.pct_safe != null && (
                  <span className="ms-1 fw-semibold" style={{ color: pctColor(d.pct_safe) }}>
                    {d.pct_safe}%
                  </span>
                )}
                <span className="text-muted ms-1">({d.safe} ✓ · {d.unsafe} ✗)</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EventDisplay({ events }) {
  if (!events) return null;
  const hasData = (events.turns?.total || 0) + (events.lane_changes?.total || 0) > 0;
  if (!hasData) {
    return (
      <div className="small text-muted mt-2 pt-2" style={{ borderTop: '1px solid var(--border-color)' }}>
        No manoeuvre events recorded.
      </div>
    );
  }
  return (
    <div className="mt-2 pt-2 d-flex flex-wrap gap-0" style={{ borderTop: '1px solid var(--border-color)' }}>
      <TypeSection label="Turns" data={events.turns} />
      <TypeSection label="Lane Changes" data={events.lane_changes} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Shared list item for displaying an analysis in any context.
 *
 * Props:
 *   analysis  – AnalysisItem object (id, name, status, progress, video_count,
 *               duration_seconds, created_at)
 *   selected  – boolean; when true shows a checkmark and highlight
 *   onClick   – click handler (navigation or selection, depending on context)
 *   etaMs     – estimated milliseconds remaining (from useAnalysesList.getEtaMs)
 *   events    – pre-loaded event stats object (from admin endpoint).
 *               If omitted, auto-fetched for COMPLETED jobs.
 *               Pass null to suppress the fetch entirely.
 */
const AnalysisListItem = ({ analysis, selected, onClick, etaMs, events: propEvents }) => {
  const isActive = ACTIVE_STATUSES.has(analysis.status);
  const { cls, label } = STATUS_MAP[analysis.status] || { cls: 'bg-secondary', label: analysis.status };
  const eta = isActive ? formatEta(etaMs) : null;

  // If propEvents is explicitly provided (including null), use it.
  // Otherwise auto-fetch for COMPLETED jobs.
  const controlled = propEvents !== undefined;
  const [fetchedEvents, setFetchedEvents] = useState(null);

  useEffect(() => {
    if (controlled) return;
    if (analysis.status !== 'COMPLETED') return;
    let cancelled = false;
    getJobEvents(analysis.id)
      .then(data => { if (!cancelled) setFetchedEvents(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [analysis.id, analysis.status, controlled]);

  const events = controlled ? propEvents : fetchedEvents;

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
          {analysis.video_count != null && (
            <><i className="bi bi-files me-1" />{analysis.video_count} videos &bull; {formatDuration(analysis.duration_seconds)}</>
          )}
        </span>
        {analysis.created_at && (
          <span className="opacity-75">
            Analysed {formatDate(analysis.created_at)}
          </span>
        )}
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

      {/* Row 4: Event stats (completed jobs only) */}
      {!isActive && analysis.status === 'COMPLETED' && (
        <EventDisplay events={events} />
      )}
    </div>
  );
};

export default AnalysisListItem;
