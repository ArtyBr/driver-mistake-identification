import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getAdminUsers, getAdminUserJobs, getAdminJobs,
  updateAdminUser, updateAdminJob, adminAssignJob, deleteAdminUser, deleteAdminJob,
  getAdminReports, getAdminReportStats, adminReanalyzeJob, getFileUrl
} from '../services/api';
import AnalysisListItem from '../components/common/AnalysisListItem';
import { groupAnalyses } from '../utils/groupAnalyses';

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
    // Only count events from the most recent analysis of each unique video pair
    const latestJobs = groupAnalyses(jobs).map(group => group[0]);
    let tTotal = 0, tSafe = 0, lcTotal = 0, lcSafe = 0;
    latestJobs.forEach(j => {
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
// Demo Videos section
// ---------------------------------------------------------------------------

function DemoSection({ demoKey, onRefresh }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const [demoJobs, setDemoJobs] = useState(null);
  const [removingId, setRemovingId] = useState(null);

  useEffect(() => {
    getAdminJobs({ is_demo: true })
      .then(jobs => setDemoJobs(jobs))
      .catch(() => setDemoJobs([]));
  }, [demoKey]);

  const handleRemoveDemo = async (jobId) => {
    if (window.confirm("Remove this video from the demo list?")) {
      setRemovingId(jobId);
      try {
        await updateAdminJob(jobId, { is_demo: false });
        setDemoJobs(prev => prev.filter(j => j.id !== jobId));
        if (onRefresh) onRefresh();
      } catch (err) {
        alert("Failed to update job: " + err.message);
      } finally {
        setRemovingId(null);
      }
    }
  };

  const handleRenameDemo = async (jobId, currentName) => {
    const newName = prompt("Enter new name for this demo video:", currentName || "");
    if (newName && newName.trim() !== "" && newName !== currentName) {
      try {
        await updateAdminJob(jobId, { name: newName });
        // Update local state to show new name immediately
        setDemoJobs(prev => prev.map(j => j.id === jobId ? { ...j, name: newName } : j));
        if (onRefresh) onRefresh();
      } catch (err) {
        alert("Failed to rename video: " + err.message);
      }
    }
  };

  const demoGroups = useMemo(() => demoJobs ? groupAnalyses(demoJobs) : null, [demoJobs]);

  const count = demoJobs ? demoJobs.length : null;

  return (
    <div
      className="card card-cyber mb-3"
      style={{
        borderLeft: expanded ? '4px solid var(--highlight-cyan)' : '4px solid transparent',
        transition: 'border-left-color 0.15s',
      }}
    >
      {/* Header */}
      <div
        className="d-flex align-items-center gap-2 p-3"
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: 'pointer', userSelect: 'none' }}
      >
        <span style={{
          display: 'inline-block',
          fontSize: '0.8rem',
          transition: 'transform 0.2s',
          transform: expanded ? 'rotate(90deg)' : 'none',
          color: 'var(--text-muted)',
          flexShrink: 0,
          width: 14,
        }}>▶</span>

        <i className="bi bi-star-fill" style={{ color: 'var(--highlight-cyan)', fontSize: '0.9rem' }}></i>
        <span className="fw-bold text-white me-auto">Demo Videos</span>

        <span style={{
          fontSize: '0.72rem', color: 'var(--highlight-cyan)',
          border: '1px solid var(--highlight-cyan)', borderRadius: 4, padding: '1px 7px',
        }}>
          {count == null ? '…' : `${count} demo video${count !== 1 ? 's' : ''}`}
        </span>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="bg-panel-lighter px-3 pb-3 pt-1" style={{ borderTop: '1px solid var(--border-color)' }}>
          {demoGroups == null && (
            <div className="d-flex align-items-center gap-2 mt-2 text-muted small">
              <div className="spinner-border spinner-border-sm" role="status" />
              Loading…
            </div>
          )}
          {demoGroups && demoGroups.length === 0 && (
            <p className="text-muted small mt-2 mb-0">No demo videos configured.</p>
          )}
          {demoGroups && demoGroups.map(group => (
            <div key={group[0].id} className="mt-2">
              <div className="d-flex align-items-center gap-2">
                <div className="flex-grow-1">
                  <AnalysisListItem
                    analysis={group[0]}
                    events={null}
                    onClick={() => navigate(`/view/${group[0].id}`)}
                    groupSize={group.length}
                  />
                </div>

                {/* 3-dot menu */}
                <div className="dropdown">
                  <button
                    className="btn btn-link text-white p-1 opacity-75"
                    type="button"
                    data-bs-toggle="dropdown"
                    aria-expanded="false"
                    style={{ fontSize: '1rem', lineHeight: 1 }}
                  >
                    <i className="bi bi-three-dots-vertical"></i>
                  </button>
                  <ul className="dropdown-menu dropdown-menu-dark dropdown-menu-end shadow-lg dropdown-menu-panel">
                    <li>
                      <button
                        className="dropdown-item py-2 text-white"
                        onClick={() => handleRemoveDemo(group[0].id)}
                        disabled={removingId === group[0].id}
                      >
                        <i className="bi bi-star me-2"></i>
                        {removingId === group[0].id ? 'Removing…' : 'Remove from Demo'}
                      </button>
                    </li>
                    <li>
                      <button
                        className="dropdown-item py-2 text-white"
                        onClick={() => handleRenameDemo(group[0].id, group[0].name)}
                      >
                        <i className="bi bi-pencil me-2"></i> Rename Video
                      </button>
                    </li>
                  </ul>
                </div>
              </div>
              {group.length > 1 && (
                <div className="accordion mt-2 ms-4" id={`accordion-demo-${group[0].id}`}>
                  <div className="accordion-item accordion-item-dark">
                    <h2 className="accordion-header">
                      <button className="accordion-button collapsed py-1 px-3 text-muted accordion-button-dark" type="button" data-bs-toggle="collapse" data-bs-target={`#collapse-demo-${group[0].id}`} style={{ fontSize: '0.8rem' }}>
                        <i className="bi bi-arrow-repeat me-1"></i>Show {group.length - 1} previous {group.length - 1 === 1 ? 'run' : 'runs'}
                      </button>
                    </h2>
                    <div id={`collapse-demo-${group[0].id}`} className="accordion-collapse collapse" data-bs-parent={`#accordion-demo-${group[0].id}`}>
                      <div className="accordion-body p-2 bg-dark">
                        {group.slice(1).map((job, idx) => (
                          <div key={job.id} className="mt-2 d-flex align-items-center gap-2">
                            <div className="flex-grow-1">
                              <AnalysisListItem
                                analysis={job}
                                events={null}
                                onClick={() => navigate(`/view/${job.id}`)}
                                reanalysisIndex={group.length - 1 - idx}
                              />
                            </div>
                            <div className="dropdown">
                              <button
                                className="btn btn-link text-white p-1 opacity-75"
                                type="button"
                                data-bs-toggle="dropdown"
                                aria-expanded="false"
                                style={{ fontSize: '1rem', lineHeight: 1 }}
                              >
                                <i className="bi bi-three-dots-vertical"></i>
                              </button>
                              <ul className="dropdown-menu dropdown-menu-dark dropdown-menu-end shadow-lg dropdown-menu-panel">
                                <li>
                                  <button
                                    className="dropdown-item py-2 text-white"
                                    onClick={() => handleRemoveDemo(job.id)}
                                    disabled={removingId === job.id}
                                  >
                                    <i className="bi bi-star me-2"></i>
                                    {removingId === job.id ? 'Removing…' : 'Remove from Demo'}
                                  </button>
                                </li>
                                <li>
                                  <button
                                    className="dropdown-item py-2 text-white"
                                    onClick={() => handleRenameDemo(job.id, job.name)}
                                  >
                                    <i className="bi bi-pencil me-2"></i> Rename Video
                                  </button>
                                </li>
                              </ul>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-user accordion row
// ---------------------------------------------------------------------------

function UserRow({ user, jobs, onVerify, onDelete, onJobAction, onDemoChange }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deletingJobId, setDeletingJobId] = useState(null);

  const handleVerify = async (e) => {
    e.stopPropagation(); // Don't expand accordion
    if (window.confirm(`Verify user ${user.email}?`)) {
      setIsVerifying(true);
      try {
        await updateAdminUser(user.id, { is_verified: true });
        if (onVerify) onVerify();
      } catch (err) {
        alert("Failed to verify user: " + err.message);
      } finally {
        setIsVerifying(false);
      }
    }
  };

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (window.confirm(`PERMANENTLY DELETE user ${user.email} and ALL their data (videos, results, sessions)? This cannot be undone.`)) {
      setIsDeleting(true);
      try {
        await deleteAdminUser(user.id, true); // true = delete jobs/data
        if (onDelete) onDelete();
      } catch (err) {
        alert("Failed to delete user: " + err.message);
        setIsDeleting(false);
      }
    }
  };

  const handleDeleteJob = async (jobId) => {
    const job = jobs?.find(j => j.id === jobId);
    const isLast = job && jobs.filter(j => 
      (j.road_path === job.road_path && job.road_path) || 
      (j.face_path === job.face_path && job.face_path)
    ).length === 1;

    const message = isLast && (job.road_path || job.face_path)
      ? "PERMANENTLY DELETE this analysis? This is the final analysis for these videos for this user; deleting it may also delete the corresponding videos from storage. This cannot be undone."
      : "PERMANENTLY DELETE this analysis and all associated data? This cannot be undone.";

    if (window.confirm(message)) {
      setDeletingJobId(jobId);
      try {
        await deleteAdminJob(jobId);
        if (onJobAction) onJobAction(user.id);
      } catch (err) {
        alert("Failed to delete video: " + err.message);
      } finally {
        setDeletingJobId(null);
      }
    }
  };

  const handleSetDemo = async (jobId) => {
    if (window.confirm("Make this video publicly visible as a demo?")) {
      try {
        await updateAdminJob(jobId, { is_demo: true });
        if (onJobAction) onJobAction(user.id);
        if (onDemoChange) onDemoChange();
      } catch (err) {
        alert("Failed to update job: " + err.message);
      }
    }
  };

  const handleRenameJob = async (jobId, currentName) => {
    const newName = prompt("Enter new name for this video:", currentName || "");
    if (newName && newName.trim() !== "" && newName !== currentName) {
      try {
        await updateAdminJob(jobId, { name: newName });
        if (onJobAction) onJobAction(user.id);
        if (onDemoChange) onDemoChange();
      } catch (err) {
        alert("Failed to rename video: " + err.message);
      }
    }
  };

  const handleReassignJob = async (jobId) => {
    const newEmail = prompt("Enter the email of the user to assign this video to:");
    if (newEmail && newEmail.trim() !== "") {
      try {
        await adminAssignJob(jobId, newEmail.trim());
        if (onJobAction) onJobAction(user.id);
        if (onVerify) onVerify(); // loadData is passed as onVerify to refresh everything
      } catch (err) {
        alert("Failed to reassign video: " + (err.response?.data?.detail || err.message));
      }
    }
  };

  const userGroups = useMemo(() => jobs ? groupAnalyses(jobs) : null, [jobs]);

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
          {user.is_verified ? (
            <span className="badge bg-success" style={{ fontSize: '0.7rem' }}>Verified</span>
          ) : (
            <span className="badge bg-warning text-dark" style={{ fontSize: '0.7rem' }}>Unverified</span>
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

        {/* User Actions 3-dot Menu */}
        <div className="dropdown ms-2">
          <button
            className="btn btn-link text-white p-0 opacity-75"
            type="button"
            data-bs-toggle="dropdown"
            aria-expanded="false"
            onClick={(e) => e.stopPropagation()}
            style={{ fontSize: '1.2rem', lineHeight: 1 }}
          >
            <i className="bi bi-three-dots-vertical"></i>
          </button>
          <ul className="dropdown-menu dropdown-menu-dark dropdown-menu-end shadow-lg dropdown-menu-panel" style={{ zIndex: 1050 }}>
            {!user.is_verified && (
              <li>
                <button className="dropdown-item py-2" onClick={handleVerify} disabled={isVerifying || isDeleting}>
                  <i className="bi bi-check-circle me-2 text-success"></i> Verify User
                </button>
              </li>
            )}
            <li>
              <button className="dropdown-item py-2 text-white" onClick={handleDelete} disabled={isDeleting || isVerifying}>
                <i className="bi bi-trash me-2"></i> Delete Account
              </button>
            </li>
          </ul>
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="bg-panel-lighter px-3 pb-3 pt-1" style={{ borderTop: '1px solid var(--border-color)' }}>
          {!userGroups && (
            <div className="d-flex align-items-center gap-2 mt-2 text-muted small">
              <div className="spinner-border spinner-border-sm" role="status" />
              Loading…
            </div>
          )}
          {userGroups && userGroups.length === 0 && (
            <p className="text-muted small mt-2 mb-0">No analyses yet.</p>
          )}
          {userGroups && userGroups.map(group => (
            <div key={group[0].id} className="mt-2">
              <div className="d-flex align-items-center gap-2">
                <div className="flex-grow-1">
                  <AnalysisListItem
                    analysis={group[0]}
                    events={group[0].events ?? null}
                    onClick={() => navigate(`/view/${group[0].id}`)}
                    groupSize={group.length}
                  />
                </div>

                {/* Video Actions 3-dot Menu */}
                <div className="dropdown">
                  <button
                    className="btn btn-link text-white p-1 opacity-75"
                    type="button"
                    data-bs-toggle="dropdown"
                    aria-expanded="false"
                    style={{ fontSize: '1rem', lineHeight: 1 }}
                  >
                    <i className="bi bi-three-dots-vertical"></i>
                  </button>
                  <ul className="dropdown-menu dropdown-menu-dark dropdown-menu-end shadow-lg dropdown-menu-panel">
                    <li>
                      <button
                        className="dropdown-item py-2 text-white"
                        onClick={() => handleSetDemo(group[0].id)}
                      >
                        <i className="bi bi-star me-2"></i> Set as Demo
                      </button>
                    </li>
                    <li>
                      <button
                        className="dropdown-item py-2 text-white"
                        onClick={() => handleRenameJob(group[0].id, group[0].name)}
                      >
                        <i className="bi bi-pencil me-2"></i> Rename Video
                      </button>
                    </li>
                    <li>
                      <button
                        className="dropdown-item py-2 text-white"
                        onClick={() => handleReassignJob(group[0].id)}
                      >
                        <i className="bi bi-person-up me-2"></i> Reassign Video
                      </button>
                    </li>
                    <li>
                      <button
                        className="dropdown-item py-2 text-white"
                        onClick={() => handleDeleteJob(group[0].id)}
                        disabled={deletingJobId === group[0].id}
                      >
                        <i className="bi bi-trash me-2"></i>
                        {deletingJobId === group[0].id ? 'Deleting...' : 'Delete Video'}
                      </button>
                    </li>
                  </ul>
                </div>
              </div>

              {group.length > 1 && (
                <div className="accordion mt-2 ms-4" id={`accordion-user-${group[0].id}`}>
                  <div className="accordion-item accordion-item-dark">
                    <h2 className="accordion-header">
                      <button className="accordion-button collapsed py-1 px-3 text-muted accordion-button-dark" type="button" data-bs-toggle="collapse" data-bs-target={`#collapse-user-${group[0].id}`} style={{ fontSize: '0.8rem' }}>
                        <i className="bi bi-arrow-repeat me-1"></i>Show {group.length - 1} previous {group.length - 1 === 1 ? 'run' : 'runs'}
                      </button>
                    </h2>
                    <div id={`collapse-user-${group[0].id}`} className="accordion-collapse collapse" data-bs-parent={`#accordion-user-${group[0].id}`}>
                      <div className="accordion-body p-2 bg-dark">
                        {group.slice(1).map((job, idx) => (
                          <div key={job.id} className="mt-2 d-flex align-items-center gap-2">
                            <div className="flex-grow-1">
                              <AnalysisListItem
                                analysis={job}
                                events={job.events ?? null}
                                onClick={() => navigate(`/view/${job.id}`)}
                                reanalysisIndex={group.length - 1 - idx}
                              />
                            </div>
                            <div className="dropdown">
                              <button
                                className="btn btn-link text-white p-1 opacity-75"
                                type="button"
                                data-bs-toggle="dropdown"
                                aria-expanded="false"
                                style={{ fontSize: '1rem', lineHeight: 1 }}
                              >
                                <i className="bi bi-three-dots-vertical"></i>
                              </button>
                              <ul className="dropdown-menu dropdown-menu-dark dropdown-menu-end shadow-lg dropdown-menu-panel">
                                <li>
                                  <button
                                    className="dropdown-item py-2 text-white"
                                    onClick={() => handleSetDemo(job.id)}
                                  >
                                    <i className="bi bi-star me-2"></i> Set as Demo
                                  </button>
                                </li>
                                <li>
                                  <button
                                    className="dropdown-item py-2 text-white"
                                    onClick={() => handleRenameJob(job.id, job.name)}
                                  >
                                    <i className="bi bi-pencil me-2"></i> Rename Video
                                  </button>
                                </li>
                                <li>
                                  <button
                                    className="dropdown-item py-2 text-white"
                                    onClick={() => handleReassignJob(job.id)}
                                  >
                                    <i className="bi bi-person-up me-2"></i> Reassign Video
                                  </button>
                                </li>
                                <li>
                                  <button
                                    className="dropdown-item py-2 text-white"
                                    onClick={() => handleDeleteJob(job.id)}
                                    disabled={deletingJobId === job.id}
                                  >
                                    <i className="bi bi-trash me-2"></i>
                                    {deletingJobId === job.id ? 'Deleting...' : 'Delete Video'}
                                  </button>
                                </li>
                              </ul>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reports Section
// ---------------------------------------------------------------------------

function ReportsSection({ onRefresh }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const [reports, setReports] = useState(null);
  const [stats, setStats] = useState(null);
  const [loadingAction, setLoadingAction] = useState(null);
  
  // Filter states
  const [filterType, setFilterType] = useState('all');
  const [filterEvent, setFilterEvent] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (expanded && reports === null) {
      loadReports();
    }
  }, [expanded, reports]);

  const loadReports = async () => {
    try {
      const [reps, s] = await Promise.all([
        getAdminReports(),
        getAdminReportStats()
      ]);
      setReports(reps);
      setStats(s);
    } catch (err) {
      alert("Failed to load reports: " + err.message);
    }
  };

  const handleReanalyze = async (jobId) => {
    if (window.confirm("Start re-analysis for this job? This will queue a new background task.")) {
      setLoadingAction(jobId);
      try {
        const result = await adminReanalyzeJob(jobId);
        alert("Re-analysis started. New Job ID: " + result.job_id);
        if (onRefresh) onRefresh();
      } catch (err) {
        alert("Failed to start re-analysis: " + err.message);
      } finally {
        setLoadingAction(null);
      }
    }
  };

  const filteredReports = useMemo(() => {
    if (!reports) return null;
    return reports.filter(r => {
      if (filterType !== 'all' && r.report_type !== filterType) return false;
      if (filterEvent !== 'all' && r.event_type !== filterEvent) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!r.user_email?.toLowerCase().includes(q) && 
            !r.job_name?.toLowerCase().includes(q) && 
            !(r.description && r.description.toLowerCase().includes(q))) {
          return false;
        }
      }
      return true;
    });
  }, [reports, filterType, filterEvent, searchQuery]);

  const count = stats ? stats.total : (reports ? reports.length : null);
  const eventTypes = stats ? Object.keys(stats.by_event) : [];

  return (
    <div
      className="card card-cyber mb-4 border-warning"
      style={{
        borderLeft: expanded ? '4px solid var(--bs-warning)' : '4px solid transparent',
        transition: 'border-left-color 0.15s',
      }}
    >
      <div
        className="d-flex align-items-center gap-2 p-3"
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: 'pointer', userSelect: 'none' }}
      >
        <span style={{
          display: 'inline-block',
          fontSize: '0.8rem',
          transition: 'transform 0.2s',
          transform: expanded ? 'rotate(90deg)' : 'none',
          color: 'var(--text-muted)',
          flexShrink: 0,
          width: 14,
        }}>▶</span>

        <i className="bi bi-flag-fill text-warning" style={{ fontSize: '0.9rem' }}></i>
        <span className="fw-bold text-white me-auto">User Error Reports</span>

        <span style={{
          fontSize: '0.72rem', color: 'var(--bs-warning)',
          border: '1px solid var(--bs-warning)', borderRadius: 4, padding: '1px 7px',
        }}>
          {count == null ? '…' : `${count} report${count !== 1 ? 's' : ''}`}
        </span>
      </div>

      {expanded && (
        <div className="bg-panel-lighter px-3 pb-3 pt-1" style={{ borderTop: '1px solid var(--border-color)' }}>
          {!reports && (
            <div className="d-flex align-items-center gap-2 mt-2 text-muted small">
              <div className="spinner-border spinner-border-sm" role="status" />
              Loading…
            </div>
          )}
          
          {stats && (
            <div className="d-flex flex-wrap gap-3 mb-3 mt-2 pb-3 border-bottom border-secondary">
              <div className="small">
                <span className="text-muted d-block">Error Types</span>
                <span className="badge bg-warning text-dark me-1">FP: {stats.by_type.false_positive || 0}</span>
                <span className="badge bg-warning text-dark">FN: {stats.by_type.false_negative || 0}</span>
              </div>
              <div className="small">
                <span className="text-muted d-block">Event Types</span>
                {Object.entries(stats.by_event).map(([k, v]) => (
                  <span key={k} className="badge bg-secondary me-1">{k.replace(/_/g, ' ')}: {v}</span>
                ))}
              </div>
            </div>
          )}

          {reports && reports.length > 0 && (
            <div className="mb-3 d-flex flex-wrap gap-2 align-items-center">
              <input
                type="text"
                className="form-control form-control-sm bg-dark text-white border-secondary"
                placeholder="Search email, job, or description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ maxWidth: '250px' }}
              />
              <select 
                className="form-select form-select-sm bg-dark text-white border-secondary w-auto"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
              >
                <option value="all">All Types</option>
                <option value="false_positive">False Positive</option>
                <option value="false_negative">False Negative</option>
              </select>
              <select 
                className="form-select form-select-sm bg-dark text-white border-secondary w-auto"
                value={filterEvent}
                onChange={(e) => setFilterEvent(e.target.value)}
              >
                <option value="all">All Events</option>
                {eventTypes.map(k => (
                  <option key={k} value={k}>{k.replace(/_/g, ' ').toUpperCase()}</option>
                ))}
              </select>
            </div>
          )}

          {reports && reports.length === 0 && (
            <p className="text-muted small mt-2 mb-0">No error reports submitted yet.</p>
          )}
          
          {filteredReports && filteredReports.length === 0 && reports.length > 0 && (
            <p className="text-muted small mt-2 mb-0">No reports match the current filters.</p>
          )}

          {filteredReports && filteredReports.map(r => (
            <div key={r.id} className="card bg-dark border-secondary mb-2 p-3">
              <div className="d-flex justify-content-between align-items-start flex-wrap gap-2">
                <div>
                  <div className="d-flex align-items-center gap-2 mb-1">
                    <span className="fw-bold text-white" style={{ fontSize: '0.9rem' }}>{r.user_email}</span>
                    <span className="text-muted small">reported on {new Date(r.created_at).toLocaleString()}</span>
                  </div>
                  <div className="small mb-2">
                    <span className="text-muted me-1">Job:</span> 
                    <span className="text-info cursor-pointer text-decoration-underline" onClick={() => navigate(`/view/${r.job_id}`)}>
                      {r.job_name}
                    </span>
                    <span className="text-muted ms-3 me-1">Time:</span> 
                    <span className="text-white">{r.timestamp.toFixed(2)}s</span>
                  </div>
                  <div className="d-flex gap-2 mb-2">
                    <span className={`badge bg-warning text-dark`}>
                      {r.report_type === 'false_positive' ? 'False Positive' : 'False Negative'}
                    </span>
                    <span className="badge border border-secondary text-light">
                      {r.event_type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                  {r.description && (
                    <p className="small text-muted mb-0 fst-italic">"{r.description}"</p>
                  )}
                </div>
                
                <div className="d-flex flex-column gap-2 align-items-end">
                  <div className="dropdown">
                     <button className="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
                        <i className="bi bi-download me-1"></i> Video
                     </button>
                     <ul className="dropdown-menu dropdown-menu-dark shadow">
                        <li>
                          <a className="dropdown-item" href={getFileUrl(`/video/remote/${r.job_id}/road.mp4`)} target="_blank" rel="noopener noreferrer" download>
                            Road Video
                          </a>
                        </li>
                        <li>
                          <a className="dropdown-item" href={getFileUrl(`/video/remote/${r.job_id}/face.mp4`)} target="_blank" rel="noopener noreferrer" download>
                            Face Video
                          </a>
                        </li>
                     </ul>
                  </div>
                  <button 
                    className="btn btn-sm btn-outline-info"
                    onClick={() => handleReanalyze(r.job_id)}
                    disabled={loadingAction === r.job_id}
                  >
                    {loadingAction === r.job_id ? 'Starting...' : 'Re-analyze Job'}
                  </button>
                </div>
              </div>
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
  const [demoKey, setDemoKey] = useState(0);

  const loadData = () => {
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
  };

  const refreshUserJobs = (userId) => {
    getAdminUserJobs(userId)
      .then(jobs => {
        setJobsByUser(prev => ({
          ...prev,
          [userId]: jobs
        }));
      });
  };

  useEffect(() => {
    loadData();
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

      <DemoSection
        demoKey={demoKey}
        onRefresh={() => {
          loadData();
          setDemoKey(k => k + 1);
        }}
      />

      <ReportsSection onRefresh={loadData} />

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
          onVerify={loadData}
          onDelete={loadData}
          onJobAction={refreshUserJobs}
          onDemoChange={() => setDemoKey(k => k + 1)}
        />
      ))}
    </div>
  );
}
