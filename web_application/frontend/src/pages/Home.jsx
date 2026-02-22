import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { runTestAnalysis } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { useAnalysesList } from '../hooks/useAnalysesList';
import AnalysisListItem from '../components/common/AnalysisListItem';

const Home = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const { analyses, getEtaMs } = useAnalysesList();
  const demoAnalyses = analyses.filter(a => a.is_demo);
  const myAnalyses   = analyses.filter(a => !a.is_demo);

  const handleLoadDemo = async (analysisId) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await runTestAnalysis(analysisId);
      navigate(`/status/${data.job_id}`);
    } catch (err) {
      console.error("Failed to load demo:", err);
      setError("Failed to load demo analysis.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleItemClick = (analysis) => {
    if (analysis.status === 'COMPLETED' || analysis.status === 'FAILED') {
      navigate(`/results/${analysis.id}`);
    } else {
      navigate(`/status/${analysis.id}`);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return "Unknown duration";
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
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
                  <p className="text-muted small mb-0">To upload your own dashcam footage or to view your previous personal results, you'll need to <Link to="/login" className="text-cyber-blue fw-bold text-decoration-none">Login</Link> or <Link to="/signup" className="text-cyber-blue fw-bold text-decoration-none">Sign Up</Link>.</p>
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

          {myAnalyses.length === 0 ? (
            <div className="text-center py-4 border border-color rounded bg-panel-lighter">
              <p className="text-muted small mb-2">No analyses yet.</p>
              <Link to="/analyze" className="btn btn-sm btn-cyber">Upload your first video</Link>
            </div>
          ) : (
            <div className="my-analyses-list">
              {myAnalyses.map(analysis => (
                <AnalysisListItem
                  key={analysis.id}
                  analysis={analysis}
                  onClick={() => handleItemClick(analysis)}
                  etaMs={getEtaMs(analysis.id, analysis.progress || 0)}
                />
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
                <div key={i} className="mb-4 ps-3 border-start border-cyber-blue">
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

          {error && <div className="alert alert-cyber-danger py-2 mb-3">{error}</div>}

          <div className="demo-list-container">
            {demoAnalyses.length > 0 ? (
              demoAnalyses.map(analysis => (
                <div key={analysis.id} className="analysis-item-modern mb-2 d-flex justify-content-between align-items-center p-3 rounded">
                  <div className="d-flex align-items-center">
                    <div>
                      <div className="fw-bold text-white mb-0" style={{ lineHeight: '1.2' }}>{analysis.name}</div>
                      <div className="d-flex gap-3 small text-muted mt-1">
                        <span>{analysis.video_count} files</span>
                        <span>{formatDuration(analysis.duration_seconds)}</span>
                      </div>
                    </div>
                  </div>
                  <button
                    className="btn btn-sm btn-cyber px-4 py-2 fw-bold"
                    onClick={() => handleLoadDemo(analysis.id)}
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <span className="spinner-border spinner-border-sm" role="status"></span>
                    ) : (
                      <>VIEW <i className="bi bi-arrow-right ms-1"></i></>
                    )}
                  </button>
                </div>
              ))
            ) : (
              <div className="text-center py-5 border border-color rounded bg-panel-lighter">
                <div className="spinner-border text-cyber-blue mb-3" role="status"></div>
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
          border-left: 5px solid var(--cyber-cyan) !important;
        }
        .border-start.border-cyber-blue {
          border-left: 3px solid var(--cyber-cyan) !important;
        }
        .border-top-primary {
          border-top: 4px solid var(--accent-primary) !important;
        }
        .text-cyber-blue {
          color: var(--cyber-cyan) !important;
        }
      `}} />
    </div>
  );
};

export default Home;
