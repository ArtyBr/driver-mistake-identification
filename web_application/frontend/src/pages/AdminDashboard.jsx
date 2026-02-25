import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAdminUsers, getAdminUserJobs } from '../services/api';
import AnalysisListItem from '../components/common/AnalysisListItem';

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

function pctColor(pct) {
  if (pct == null) return 'var(--text-muted)';
  if (pct >= 75) return 'var(--accent-success)';
  if (pct >= 40) return '#e5a500';
  return 'var(--accent-danger)';
}

// ---------------------------------------------------------------------------
// Aggregate chips shown in the user header row
// ---------------------------------------------------------------------------

function AggregateChips({ jobs }) {
  const agg = useMemo(() => {
    if (!jobs) return null;
    let tTotal = 0, tSafe = 0, lcTotal = 0, lcSafe = 0;
    jobs.forEach(j => {
      if (j.events) {
        tTotal  += j.events.turns?.total  || 0;
        tSafe   += j.events.turns?.safe   || 0;
        lcTotal += j.events.lane_changes?.total || 0;
        lcSafe  += j.events.lane_changes?.safe  || 0;
      }
    });
    return {
      tTotal,  tPct:  tTotal  > 0 ? Math.round(tSafe  / tTotal  * 100) : null,
      lcTotal, lcPct: lcTotal > 0 ? Math.round(lcSafe / lcTotal * 100) : null,
    };
  }, [jobs]);

  if (!agg || (agg.tTotal === 0 && agg.lcTotal === 0)) {
    return (
      <span style={{
        fontSize: '0.72rem', color: 'var(--text-muted)',
        border: '1px solid var(--border-color)', borderRadius: 4, padding: '1px 7px',
      }}>
        {jobs ? 'No events' : '…'}
      </span>
    );
  }

  return (
    <div className="d-flex align-items-center gap-1 flex-wrap">
      {agg.tTotal > 0 && (
        <span style={{
          fontSize: '0.72rem', borderRadius: 4, padding: '1px 7px', fontWeight: 500,
          border: `1px solid ${pctColor(agg.tPct)}`,
          color: pctColor(agg.tPct),
        }}>
          {agg.tTotal} turn{agg.tTotal !== 1 ? 's' : ''}
          {agg.tPct != null && <> · {agg.tPct}% safe</>}
        </span>
      )}
      {agg.lcTotal > 0 && (
        <span style={{
          fontSize: '0.72rem', borderRadius: 4, padding: '1px 7px', fontWeight: 500,
          border: `1px solid ${pctColor(agg.lcPct)}`,
          color: pctColor(agg.lcPct),
        }}>
          {agg.lcTotal} lane change{agg.lcTotal !== 1 ? 's' : ''}
          {agg.lcPct != null && <> · {agg.lcPct}% safe</>}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-user accordion row
// ---------------------------------------------------------------------------

function UserRow({ user, jobs }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="card card-cyber mb-2"
      style={{
        borderLeft: expanded ? '4px solid var(--accent-primary)' : '4px solid transparent',
        transition: 'border-left-color 0.15s',
      }}
    >
      {/* Header — always visible */}
      <div
        className="d-flex align-items-center gap-2 p-3 flex-wrap"
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: 'pointer', userSelect: 'none' }}
      >
        {/* Chevron */}
        <span style={{
          display: 'inline-block',
          fontSize: '0.8rem',
          transition: 'transform 0.2s',
          transform: expanded ? 'rotate(90deg)' : 'none',
          color: 'var(--text-muted)',
          flexShrink: 0,
          width: 14,
        }}>▶</span>

        {/* Email + Admin badge */}
        <div className="d-flex align-items-center gap-2 me-auto flex-wrap">
          <span className="fw-bold text-white">{user.email}</span>
          {user.is_admin && (
            <span className="badge bg-primary" style={{ fontSize: '0.7rem' }}>Admin</span>
          )}
          <span style={{
            fontSize: '0.72rem', color: 'var(--text-muted)',
            border: '1px solid var(--border-color)', borderRadius: 4, padding: '1px 7px',
          }}>
            {user.job_count} video{user.job_count !== 1 ? 's' : ''}
          </span>
          {user.created_at && (
            <span className="small text-muted">
              joined {new Date(user.created_at).toLocaleDateString(undefined, {
                year: 'numeric', month: 'short', day: 'numeric',
              })}
            </span>
          )}
        </div>

        {/* Aggregate event chips */}
        <AggregateChips jobs={jobs} />
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="bg-panel-lighter px-3 pb-3 pt-1" style={{ borderTop: '1px solid var(--border-color)' }}>
          {!jobs && (
            <div className="d-flex align-items-center gap-2 mt-2 text-muted small">
              <div className="spinner-border spinner-border-sm" role="status" />
              Loading…
            </div>
          )}
          {jobs && jobs.length === 0 && (
            <p className="text-muted small mt-2 mb-0">No analyses yet.</p>
          )}
          {jobs && jobs.map(job => (
            <div key={job.id} className="mt-2">
              <AnalysisListItem
                analysis={job}
                events={job.events ?? null}
                onClick={() => navigate(`/results/${job.id}`)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminDashboard() {
  const [users, setUsers] = useState([]);
  const [jobsByUser, setJobsByUser] = useState({});
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    getAdminUsers()
      .then((loadedUsers) => {
        setUsers(loadedUsers);
        // Pre-fetch all users' jobs in parallel
        Promise.all(
          loadedUsers.map(u =>
            getAdminUserJobs(u.id)
              .then(jobs => ({ userId: u.id, jobs }))
              .catch(() => ({ userId: u.id, jobs: [] }))
          )
        ).then(results => {
          const map = {};
          results.forEach(({ userId, jobs }) => { map[userId] = jobs; });
          setJobsByUser(map);
        });
      })
      .catch(e => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return users;
    const q = search.toLowerCase();
    return users.filter(u => u.email.toLowerCase().includes(q));
  }, [users, search]);

  return (
    <div>
      <div className="page-header mb-4">
        <h1 className="page-title">Admin Dashboard</h1>
        <p className="page-subtitle">User accounts, analyses, and safety event breakdowns</p>
      </div>

      {error && (
        <div className="alert alert-cyber-danger py-2 mb-3">{error}</div>
      )}

      <div className="mb-3">
        <input
          className="form-control"
          placeholder="Search users by email…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ maxWidth: 380 }}
        />
      </div>

      {filtered.length === 0 && !error && (
        <p className="text-muted">No users found.</p>
      )}

      {filtered.map(user => (
        <UserRow
          key={user.id}
          user={user}
          jobs={jobsByUser[user.id] ?? null}
        />
      ))}
    </div>
  );
}
