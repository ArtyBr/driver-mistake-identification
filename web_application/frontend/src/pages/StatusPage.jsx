import React, { useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useJobStatus } from '../hooks/useJob';

const StatusPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  
  const { status, progress, error } = useJobStatus(jobId);

  useEffect(() => {
    if (status === 'COMPLETED') {
      navigate(`/results/${jobId}`, { state: location.state });
    }
  }, [status, jobId, navigate, location.state]);

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
                <div className="alert alert-danger mt-4">
                <p className="small mb-0">{error}</p>
                <button 
                    className="btn btn-outline-light btn-sm mt-3"
                    onClick={() => navigate(`/results/${jobId}`, { state: location.state })}
                >
                    Try Viewing Results Anyway
                </button>
                </div>
            )}
            
            <div className="mt-3">
                <small className="text-muted">Job ID: {jobId}</small>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatusPage;