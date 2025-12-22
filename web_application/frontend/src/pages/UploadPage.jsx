import React from 'react';
import { useNavigate } from 'react-router-dom';
import Uploader from '../components/Uploader';

const UploadPage = () => {
  const navigate = useNavigate();

  const handleUploadSuccess = (jobId, jobData) => {
    navigate(`/status/${jobId}`);
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
