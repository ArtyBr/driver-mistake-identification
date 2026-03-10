import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useAnalysesList } from '../hooks/useAnalysesList';
import AnalysisListItem from '../components/common/AnalysisListItem';
import { updateJobName, deleteJob } from '../services/api';
import { groupAnalyses } from '../utils/groupAnalyses';

const Home = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const { analyses, getEtaMs, refetch: refetchAnalyses } = useAnalysesList();
  const demoAnalyses = analyses.filter(a => a.is_demo);
  const myAnalyses   = analyses.filter(a => !a.is_demo);

  const myAnalysesGroups = groupAnalyses(myAnalyses);
  const demoAnalysesGroups = groupAnalyses(demoAnalyses);

  const handleLoadDemo = (analysisId) => {
    navigate(`/view/${analysisId}`);
  };

  const handleItemClick = (analysis) => {
    if (analysis.status === 'COMPLETED' || analysis.status === 'FAILED') {
      navigate(`/view/${analysis.id}`);
    } else {
      navigate(`/job/${analysis.id}`);
    }
  };

  const handleRename = async (analysis) => {
    const newName = window.prompt('Enter new name:', analysis.name || '');
    if (newName && newName.trim()) {
      try {
        await updateJobName(analysis.id, newName.trim());
        refetchAnalyses();
      } catch { /* ignore */ }
    }
  };

  const handleDelete = async (analysis) => {
    const isLast = myAnalyses.filter(a => 
      (a.road_path === analysis.road_path && analysis.road_path) || 
      (a.face_path === analysis.face_path && analysis.face_path)
    ).length === 1;

    const message = isLast && (analysis.road_path || analysis.face_path)
      ? `Delete "${analysis.name || 'this analysis'}"? This is the final analysis for these videos; deleting it will also delete the corresponding videos from storage. This cannot be undone.`
      : `Delete "${analysis.name || 'this analysis'}"? This cannot be undone.`;

    if (!window.confirm(message)) return;
    try {
      await deleteJob(analysis.id);
      refetchAnalyses();
    } catch { /* ignore */ }
  };

  const features = [
    {
      title: "Intelligent Lane Tracking",
      desc: "Real-time detection of lane drift and departures using advanced computer vision."
    },
    {
      title: "Driver State Monitoring",
      desc: "AI-powered analysis of gaze, head pose, and distraction levels to ensure focus."
    },
    {
      title: "Unified Event Timeline",
      desc: "A synchronized chronological view of safety events and driver behavior metrics."
    },
    {
      title: "Dual-Camera Correlation",
      desc: "Simultaneous analysis of road environment and driver behavior for deep insights."
    }
  ];

  return (
    <div className="container py-5">
      {/* Hero Section */}
      <div className="mb-5 pb-3">
        <h1 className="display-3 fw-bold mb-3 text-white">SafeDrive AI Analysis</h1>
        <p className="lead text-muted mb-0" style={{ maxWidth: '900px', fontSize: '1.4rem' }}>
          Experience our advanced AI-powered system designed to identify driver mistakes and enhance road safety through real-time dashcam analysis.
        </p>
      </div>

      {/* Platform Overview */}
      <div className="row justify-content-center mb-5">
        <div className="col-lg-12">
          <div className="alert-cyber-info p-4 rounded shadow-sm border-left-blue">
            <div className="row g-0 align-items-center">
              <div className="col-md-5">
                <div>
                  <div className="text-white fw-bold mb-1">Public Access</div>
                  <p className="text-muted small mb-0">Explore the platform immediately! Anyone can view our pre-uploaded <strong>demo videos</strong> to see the AI analysis in action without an account.</p>
                </div>
              </div>

              <div className="col-md-2 d-none d-md-flex justify-content-center">
                <div className="vr bg-secondary opacity-25" style={{ height: '80px', width: '1px' }}></div>
              </div>

              <div className="col-md-5">
                <div>
                  <div className="text-white fw-bold mb-1">Private Analysis</div>
                  <p className="text-muted small mb-0">To upload your own dashcam footage or to view your previous personal results, you'll need to <Link to="/login" className="text-highlight-cyan fw-bold text-decoration-none">Login</Link> or <Link to="/signup" className="text-highlight-cyan fw-bold text-decoration-none">Sign Up</Link>.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* My Analyses Section (logged-in users only) */}
      {user && (
        <div className="mb-5">
          <div className="d-flex align-items-center justify-content-between mb-3 border-bottom border-secondary pb-2">
            <h3 className="mb-0 fw-bold text-white">My Analyses</h3>
            <Link to="/analyze" className="btn btn-sm btn-outline-cyber fw-bold">
              + New Analysis
            </Link>
          </div>

          {myAnalysesGroups.length === 0 ? (
            <div className="p-4 rounded card-cyber">
              <p className="text-muted small mb-1">You haven't uploaded any analyses yet.</p>
              <p className="text-muted small mb-3">
                Not sure where to start?{' '}
                <Link to="/guide" className="text-decoration-none" style={{ color: 'var(--accent-primary)' }}>
                  Read the Getting Started Guide
                </Link>{' '}
                to learn how to set up your cameras and record your first session.
              </p>
              <Link to="/analyze" className="btn btn-sm btn-cyber">Upload your first video</Link>
            </div>
          ) : (
            <div className="my-analyses-list">
              {myAnalysesGroups.map(group => (
                <div key={group[0].id} className="mb-3">
                  <AnalysisListItem
                    analysis={group[0]}
                    onClick={() => handleItemClick(group[0])}
                    onView={() => handleItemClick(group[0])}
                    onRename={() => handleRename(group[0])}
                    onDelete={() => handleDelete(group[0])}
                    etaMs={getEtaMs(group[0].id, group[0].progress || 0)}
                  />
                  {group.length > 1 && (
                    <div className="accordion mt-2" id={`accordion-${group[0].id}`}>
                      <div className="accordion-item accordion-item-dark">
                        <h2 className="accordion-header">
                          <button className="accordion-button collapsed py-2 px-3 text-muted accordion-button-dark" type="button" data-bs-toggle="collapse" data-bs-target={`#collapse-${group[0].id}`} style={{ fontSize: '0.85rem' }}>
                            Show {group.length - 1} other re-analyses
                          </button>
                        </h2>
                        <div id={`collapse-${group[0].id}`} className="accordion-collapse collapse" data-bs-parent={`#accordion-${group[0].id}`}>
                          <div className="accordion-body p-2 bg-dark">
                            {group.slice(1).map(analysis => (
                              <AnalysisListItem
                                key={analysis.id}
                                analysis={analysis}
                                onClick={() => handleItemClick(analysis)}
                                onView={() => handleItemClick(analysis)}
                                onRename={() => handleRename(analysis)}
                                onDelete={() => handleDelete(analysis)}
                                etaMs={getEtaMs(analysis.id, analysis.progress || 0)}
                              />
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
      )}

      <div className="row g-5 align-items-start">
        {/* Left Column: Action Card */}
        <div className="col-lg-7">
          <div className="card card-cyber p-4 h-100 shadow-lg border-top-primary">
            <h3 className="mb-4 fw-bold text-white">Analyze Your Driving</h3>
            <p className="text-muted mb-4 lead" style={{ fontSize: '1rem' }}>
              Upload your own dashcam footage to receive a detailed AI-driven safety report.
            </p>

            <div className="feature-list mb-5">
              {features.map((f, i) => (
                <div key={i} className="mb-4 ps-3 border-start border-highlight-cyan">
                  <div className="text-white fw-bold mb-1" style={{ fontSize: '1rem' }}>{f.title}</div>
                  <p className="text-muted small mb-0" style={{ lineHeight: '1.4' }}>{f.desc}</p>
                </div>
              ))}
            </div>

            <div className="mt-auto">
              {user ? (
                <Link to="/analyze" className="btn btn-cyber-primary btn-lg w-100 py-3 fw-bold">
                  GO TO UPLOADER <i className="bi bi-chevron-right ms-2"></i>
                </Link>
              ) : (
                <div className="d-grid gap-3">
                  <Link to="/login" className="btn btn-cyber-primary btn-lg py-3 fw-bold">
                    LOGIN TO UPLOAD <i className="bi bi-lock-fill ms-2"></i>
                  </Link>
                  <Link to="/signup" className="btn btn-outline-cyber btn-lg py-3 fw-bold">
                    CREATE ACCOUNT
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Demo Section */}
        <div className="col-lg-5">
          <div className="d-flex align-items-center mb-4 border-bottom border-secondary pb-2">
            <h3 className="mb-0 fw-bold text-white">Demo Analyses</h3>
          </div>

          <div className="demo-list-container">
            {demoAnalysesGroups.length > 0 ? (
              demoAnalysesGroups.map(group => (
                <div key={group[0].id} className="mb-3">
                  <AnalysisListItem
                    analysis={group[0]}
                    onClick={() => handleLoadDemo(group[0].id)}
                    onView={() => handleLoadDemo(group[0].id)}
                  />
                  {group.length > 1 && (
                    <div className="accordion mt-2" id={`accordion-demo-${group[0].id}`}>
                      <div className="accordion-item accordion-item-dark">
                        <h2 className="accordion-header">
                          <button className="accordion-button collapsed py-2 px-3 text-muted accordion-button-dark" type="button" data-bs-toggle="collapse" data-bs-target={`#collapse-demo-${group[0].id}`} style={{ fontSize: '0.85rem' }}>
                            Show {group.length - 1} other re-analyses
                          </button>
                        </h2>
                        <div id={`collapse-demo-${group[0].id}`} className="accordion-collapse collapse" data-bs-parent={`#accordion-demo-${group[0].id}`}>
                          <div className="accordion-body p-2 bg-dark">
                            {group.slice(1).map(analysis => (
                              <AnalysisListItem
                                key={analysis.id}
                                analysis={analysis}
                                onClick={() => handleLoadDemo(analysis.id)}
                                onView={() => handleLoadDemo(analysis.id)}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-5 border border-secondary rounded" style={{ backgroundColor: 'var(--bg-panel-lighter)' }}>
                <div className="spinner-border text-highlight-cyan mb-3" role="status"></div>
                <p className="text-muted small">Loading demos...</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .demo-list-container {
          max-height: 550px;
          overflow-y: auto;
        }
        .my-analyses-list {
          max-height: 400px;
          overflow-y: auto;
        }
        .analysis-item-modern {
          background-color: var(--bg-panel-lighter);
          border: 1px solid var(--border-color);
          transition: all 0.2s ease;
        }
        .analysis-item-modern:hover {
          border-color: var(--accent-primary);
          background-color: var(--bg-panel);
        }
        .alert-cyber-info {
          background-color: rgba(13, 110, 253, 0.08);
          border: 1px solid rgba(13, 110, 253, 0.2);
        }
        .border-left-blue {
          border-left: 5px solid var(--highlight-cyan) !important;
        }
        .border-start.border-highlight-cyan {
          border-left: 3px solid var(--highlight-cyan) !important;
        }
        .border-top-primary {
          border-top: 4px solid var(--accent-primary) !important;
        }
      `}} />
    </div>
  );
};

export default Home;
