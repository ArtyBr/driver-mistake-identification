import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useJobStatus } from '../hooks/useJob';

const StatusPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [copied, setCopied] = useState(false);
  
  const { status, progress, error, data } = useJobStatus(jobId);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(jobId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  useEffect(() => {
    if (status === 'COMPLETED') {
      const navState = { 
        ...location.state, 
        calibrationId: data?.calibration_id 
      };
      navigate(`/view/${jobId}`, { state: navState, replace: true });
    }
  }, [status, jobId, navigate, location.state, data]);

  // Fallback for failed jobs that might actually have results (late-stage crashes)
  useEffect(() => {
    let interval;
    if (status === 'FAILED') {
      // Re-check every 5 seconds even if failed, just in case results.json exists
      interval = setInterval(() => {
        // useJobStatus should handle the polling, but we might need to force it
        // For now, we rely on the hook's internal polling if it continues on failure
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [status]);

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-lg-8">
          <div className="card-cyber shadow-sm text-center p-5">
            <h2 className="mb-4 text-white">Processing Video</h2>
            
            <p className="lead text-muted mb-4">
                {status === 'PENDING' && 'Initializing...'}
                {status === 'SUBMITTED' && 'Job submitted to cluster. Waiting for resources...'}
                {status === 'RUNNING' && 'Analyzing frames... This may take a few minutes.'}
                {status === 'FAILED' && 'Job reported an error, but results may still be available.'}
                {status === 'UNKNOWN' && 'Checking job status...'}
            </p>

            <div className="progress mb-3" style={{ height: '30px' }}>
                <div 
                className="progress-bar progress-bar-striped progress-bar-animated" 
                role="progressbar" 
                style={{ width: `${progress}%` }} 
                aria-valuenow={progress} 
                aria-valuemin="0" 
                aria-valuemax="100"
                >
                {progress}%
                </div>
            </div>

            {error && (
                <div className="alert alert-cyber-danger mt-4">
                <p className="small mb-0">{error}</p>
                <button 
                    className="btn btn-cyber btn-sm mt-3"
                    onClick={() => navigate(`/view/${jobId}`, { state: location.state, replace: true })}
                >
                    Try Viewing Results Anyway
                </button>
                </div>
            )}
            
            <div className="mt-3 d-flex align-items-center justify-content-center gap-2">
                <small className="text-muted">Job ID: {jobId}</small>
                <button 
                  className={`btn btn-sm ${copied ? 'btn-success' : 'btn-outline-cyber'}`}
                  onClick={copyToClipboard}
                  title="Copy Job ID"
                >
                  {copied ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  )}
                </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatusPage;