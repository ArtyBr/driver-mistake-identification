import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import VideoPlayer from '../components/features/VideoPlayer';
import MissingVideosUploader from '../components/features/MissingVideosUploader';
import GazeCorrectionModal from '../components/GazeCorrectionModal';
import { getJobStatus, getJobResults, getFileUrl } from '../services/api';
import '../App.css'; // Import the custom styles for VideoPlayer

const ResultPage = () => {
  const { jobId } = useParams();
  const location = useLocation();
  const [results, setResults] = useState(null);
  const [jobData, setJobData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [correctionModal, setCorrectionModal] = useState(null);

  // Locally provided files if server files are missing
  const [localRoadFiles, setLocalRoadFiles] = useState([]);
  const [localFaceFiles, setLocalFaceFiles] = useState([]);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(jobId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Fetch status to get URLs and metadata
        const statusData = await getJobStatus(jobId);
        setJobData(statusData);

        // Fetch results
        const resultsData = await getJobResults(jobId);
        setResults(resultsData);
      } catch (err) {
        console.error("Error fetching data:", err);
        setError("Failed to load results. They might not be ready or the ID is invalid.");
      } finally {
        setLoading(false);
      }
    };

    if (jobId) {
      fetchData();
    }
  }, [jobId]);

  const videoUrls = useMemo(() => {
      let rUrls = [];
      let fUrls = [];

      // Priority:
      // 1. Server URLs (spliced video) - Preferred to avoid CSP blob: issues
      // 2. Manually provided local files in this page
      // 3. Local files passed via navigation state (from Uploader)

      if (jobData?.road_url) {
          rUrls = [getFileUrl(jobData.road_url)];
      } else if (localRoadFiles.length > 0) {
          rUrls = localRoadFiles.map(f => URL.createObjectURL(f));
      } else if (location.state?.roadFiles && location.state.roadFiles.length > 0) {
          rUrls = location.state.roadFiles.map(f => URL.createObjectURL(f));
      }

      if (jobData?.face_url) {
          fUrls = [getFileUrl(jobData.face_url)];
      } else if (localFaceFiles.length > 0) {
          fUrls = localFaceFiles.map(f => URL.createObjectURL(f));
      } else if (location.state?.faceFiles && location.state.faceFiles.length > 0) {
          fUrls = location.state.faceFiles.map(f => URL.createObjectURL(f));
      }

      return { road: rUrls, face: fUrls };
  }, [jobData, location.state, localRoadFiles, localFaceFiles]);

  // Cleanup Blob URLs when unmounting or changing
  useEffect(() => {
      return () => {
          if (videoUrls.road) {
              videoUrls.road.forEach(url => {
                  if (url.startsWith('blob:')) URL.revokeObjectURL(url);
              });
          }
          if (videoUrls.face) {
              videoUrls.face.forEach(url => {
                  if (url.startsWith('blob:')) URL.revokeObjectURL(url);
              });
          }
      }
  }, [videoUrls]);

  const handleMissingFiles = (road, face) => {
    console.log("Setting local files:", road.length, face.length);
    setLocalRoadFiles(road);
    setLocalFaceFiles(face);
  };

  const hasVideos = videoUrls.road.length > 0 && videoUrls.face.length > 0;

  if (loading) {
    return (
      <div className="text-center mt-5">
        <div className="spinner-border" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
        <p className="mt-2 text-muted">Loading results...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-cyber-danger mt-5">
        <h4>Error</h4>
        <p>{error}</p>
        <Link to="/analyze" className="btn btn-cyber">Try Again</Link>
      </div>
    );
  }

  return (
    <div className="container-fluid">
       <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
          <div className="d-flex align-items-center gap-3">
            <h2 className="mb-0 page-title">Analysis Results</h2>
            <div className="d-flex align-items-center gap-2 bg-panel-lighter px-3 py-1 border border-secondary rounded">
               <small className="text-muted text-uppercase fw-bold" style={{ fontSize: '0.7rem', letterSpacing: '0.5px' }}>Job ID: {jobId}</small>
               <button 
                  className={`btn btn-sm p-0 border-0 ${copied ? 'text-success' : 'text-muted'}`}
                  onClick={copyToClipboard}
                  title="Copy Job ID"
                  style={{ background: 'transparent' }}
                >
                  {copied ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  )}
                </button>
            </div>
          </div>
          <Link to="/analyze" className="btn btn-cyber">New Analysis</Link>
       </div>

       {results && !hasVideos && jobData && (
         <MissingVideosUploader 
            roadMeta={jobData.road_metadata}
            faceMeta={jobData.face_metadata}
            results={results}
            onFilesUploaded={handleMissingFiles}
         />
       )}

       {results && hasVideos && (
          <VideoPlayer
            results={results}
            roadUrls={videoUrls.road}
            faceUrls={videoUrls.face}
            jobId={jobId}
          />
       )}

       {correctionModal && (
         <GazeCorrectionModal
           jobId={jobId}
           detectedLabel={correctionModal.detectedLabel}
           startTime={correctionModal.startTime}
           endTime={correctionModal.endTime}
           onClose={() => setCorrectionModal(null)}
           onSuccess={() => setCorrectionModal(null)}
         />
       )}
    </div>
  );
};

export default ResultPage;
