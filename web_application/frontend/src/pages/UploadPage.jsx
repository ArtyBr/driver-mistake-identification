import React, { useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAnalysesList } from '../hooks/useAnalysesList';
import Uploader from '../components/features/Uploader';

const UploadPage = () => {
  const navigate = useNavigate();
  const { analyses, loading } = useAnalysesList();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  const hasAnalyses = !loading && analyses.some(a => !a.is_demo);

  const handleUploadSuccess = (jobId, jobData, localFiles) => {
    navigate(`/job/${jobId}`, { state: localFiles });
  };

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-lg-10">
          {!hasAnalyses && (
            <div
              className="mb-4 d-flex align-items-center gap-3 p-3 rounded"
              style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-color)' }}
            >
              <i className="bi bi-book-half flex-shrink-0" style={{ color: 'var(--accent-primary)' }}></i>
              <p className="mb-0 small text-muted">
                <strong className="text-white">First time here?</strong> Check the{' '}
                <Link to="/guide" className="text-decoration-none" style={{ color: 'var(--accent-primary)' }}>
                  Getting Started Guide
                </Link>{' '}
                to learn how to set up your cameras and record a session before uploading.
              </p>
            </div>
          )}
          <Uploader onUploadSuccess={handleUploadSuccess} />
        </div>
      </div>
    </div>
  );
};

export default UploadPage;
