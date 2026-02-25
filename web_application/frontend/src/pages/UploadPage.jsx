import React from 'react';
import { useNavigate } from 'react-router-dom';
import Uploader from '../components/features/Uploader';

const UploadPage = () => {
  const navigate = useNavigate();

  const handleUploadSuccess = (jobId, jobData, localFiles) => {
    navigate(`/job/${jobId}`, { state: localFiles });
  };

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-lg-10">
            <Uploader onUploadSuccess={handleUploadSuccess} />
        </div>
      </div>
    </div>
  );
};

export default UploadPage;
