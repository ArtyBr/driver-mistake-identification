import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useJobStatus } from '../hooks/useJob';
import { uploadRoadVideo } from '../services/api';
import { Button, ProgressBar, Alert } from 'react-bootstrap';
import FileDropZone from '../components/common/FileDropZone';

const StatusPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  
  const { status, progress, error, data } = useJobStatus(jobId);
  const [roadFiles, setRoadFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  useEffect(() => {
    if (status === 'COMPLETED') {
      navigate(`/results/${jobId}`, { state: location.state });
    }
  }, [status, jobId, navigate, location.state]);

  const handleUpload = async (e) => {
    if (roadFiles.length === 0) return;

    setIsUploading(true);
    setUploadError(null);
    const formData = new FormData();
    // Using the same key 'video' as expected by the backend save_road_video
    formData.append('video', roadFiles[0]);

    try {
      await uploadRoadVideo(jobId, formData);
      // Status will switch automatically
    } catch (err) {
      setUploadError('Failed to upload road video. ' + err.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-lg-8">
          <div className="card-cyber shadow-sm p-5">
            <h2 className="mb-4 text-white text-center">Session Analysis</h2>
            
            {error || uploadError ? (
              <Alert variant="danger">{error || uploadError}</Alert>
            ) : null}

            {status === 'RECORDING' ? (
              <div className="text-center">
                <div className="alert alert-info border-info bg-dark text-info mb-4">
                  <i className="bi bi-person-video me-2"></i>
                  <strong>Face Recording Saved!</strong> Your cabin footage and calibration are stored under this session ID.
                </div>
                
                <h4 className="text-warning mb-3">Upload Road Footage</h4>
                <p className="text-muted mb-4">
                  To complete the analysis, upload the corresponding road-facing dash-cam video (.mp4).
                </p>
                
                <div className="text-start mb-4">
                  <FileDropZone 
                    label="External Road Video (Front Facing)" 
                    files={roadFiles} 
                    setFiles={setRoadFiles} 
                    accept="video/mp4"
                    helperText="Select the .mp4 file from your external dash-cam."
                    multiple={false}
                  />
                </div>

                <div className="d-grid">
                  <button 
                    className="btn btn-cyber-primary btn-lg" 
                    onClick={handleUpload} 
                    disabled={isUploading || roadFiles.length === 0}
                  >
                    {isUploading ? (
                      <span><span className="spinner-border spinner-border-sm me-2"></span>UPLOADING...</span>
                    ) : 'START SYNC & ANALYSIS'}
                  </button>
                </div>
                
                <div className="mt-4 pt-3 border-top border-secondary">
                  <small className="text-muted d-block mb-2">You can close this page and return later using the Session ID:</small>
                  <code className="bg-dark p-2 rounded text-cyber-blue">{jobId}</code>
                </div>
              </div>
            ) : (
              <div className="text-center py-4">
                <div className="status-badge mb-4">
                  <span className={`badge ${status === 'PROCESSING' ? 'bg-primary' : 'bg-secondary'} p-2 px-4 fs-5`}>
                    {status}
                  </span>
                </div>
                
                <p className="lead text-muted mb-4">
                   {status === 'PENDING' ? 'Waiting for sync engine...' : 'AI is analyzing your mirrors and lane changes...'}
                </p>
                
                <div className="progress mb-3" style={{ height: '35px', backgroundColor: 'rgba(0,0,0,0.3)', border: '1px solid #333' }}>
                  <div 
                    className="progress-bar progress-bar-striped progress-bar-animated bg-cyber-blue" 
                    role="progressbar" 
                    style={{ width: `${progress}%` }} 
                    aria-valuenow={progress} 
                    aria-valuemin="0" 
                    aria-valuemax="100"
                  >
                    {progress}%
                  </div>
                </div>
                
                <div className="d-flex justify-content-between text-muted mt-2">
                  <small>Job ID: {jobId}</small>
                  <small>Please keep this tab open</small>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatusPage;