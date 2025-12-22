import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

const StatusPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('PENDING');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => {
    let interval;
    if (jobId && (status !== 'COMPLETED' && status !== 'FAILED')) {
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE}/status/${jobId}`);
          console.log(`Polling status for ${jobId}:`, res.data);
          
          setStatus(res.data.status);
          if (res.data.progress) {
            setProgress(res.data.progress);
          }
          if (res.data.status === 'COMPLETED') {
            clearInterval(interval);
            navigate(`/results/${jobId}`);
          } else if (res.data.status === 'FAILED') {
            setError(res.data.error || "Analysis failed due to an unknown error.");
            clearInterval(interval);
          }
        } catch (err) {
          console.error("Error polling status:", err);
          setError("Connection error. Retrying...");
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [jobId, status, navigate]);

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-lg-8">
          <div className="card shadow-sm text-center p-5">
            <h2 className="mb-4">Processing Video</h2>
            
            {error ? (
              <div className="alert alert-danger">{error}</div>
            ) : (
              <>
                <p className="lead text-muted mb-4">
                   {status === 'PENDING' ? 'Initializing...' : 'Analyzing frames... This may take a few minutes.'}
                </p>
                <div className="progress mb-3" style={{ height: '30px' }}>
                  <div 
                    className="progress-bar progress-bar-striped progress-bar-animated bg-primary" 
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
