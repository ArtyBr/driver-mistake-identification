import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import VideoPlayer from '../components/VideoPlayer';
import '../App.css'; // Import the custom styles for VideoPlayer

const API_BASE = 'http://localhost:8000';

const ResultPage = () => {
  const { jobId } = useParams();
  const [results, setResults] = useState(null);
  const [jobData, setJobData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Fetch status to get URLs
        const statusRes = await axios.get(`${API_BASE}/status/${jobId}`);
        setJobData(statusRes.data);

        // Fetch results
        const resultRes = await axios.get(`${API_BASE}/results/${jobId}`);
        setResults(resultRes.data);
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
      <div className="alert alert-danger mt-5">
        <h4>Error</h4>
        <p>{error}</p>
        <Link to="/analyze" className="btn btn-outline-danger">Try Again</Link>
      </div>
    );
  }

  return (
    <div className="container-fluid">
       <div className="d-flex justify-content-between align-items-center mb-4">
          <h2 className="mb-0 page-title">Analysis Results</h2>
          <Link to="/analyze" className="btn btn-cyber">New Analysis</Link>
       </div>

       {results && jobData && (
          <VideoPlayer 
            results={results} 
            roadUrl={`${API_BASE}${jobData.road_url}`}
            faceUrl={`${API_BASE}${jobData.face_url}`}
          />
       )}
    </div>
  );
};

export default ResultPage;
