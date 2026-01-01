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

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-lg-8">
          <div className="card-cyber shadow-sm text-center p-5">
            <h2 className="mb-4 text-white">Processing Video</h2>
            
            {error ? (
              <div className="alert alert-danger">{error}</div>
            ) : (
              <>
                <p className="lead text-muted mb-4">
                   {status === 'PENDING' ? 'Initializing...' : 'Analyzing frames... This may take a few minutes.'}
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
                <small className="text-muted">Job ID: {jobId}</small>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatusPage;