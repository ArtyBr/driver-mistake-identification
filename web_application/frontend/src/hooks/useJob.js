import { useState, useEffect, useCallback, useRef } from 'react';
import { uploadVideos, getJobStatus, runTestAnalysis } from '../services/api';

export const useJobUpload = () => {
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  const upload = useCallback(async (roadFiles, faceFiles, keepVideos, name, calibrationId) => {
    setIsUploading(true);
    setProgress(0);
    setError(null);

    const formData = new FormData();
    roadFiles.forEach(file => formData.append('video_road', file));
    faceFiles.forEach(file => formData.append('video_face', file));
    formData.append('keep_videos', keepVideos);
    if (name) {
        formData.append('name', name);
    }
    if (calibrationId) {
        formData.append('calibration_id', calibrationId);
    }

    try {
      const data = await uploadVideos(formData, setProgress);
      // Wait for initial status check to confirm job exists
      await getJobStatus(data.job_id);
      return data.job_id;
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed. Check your connection or file size.");
      throw err;
    } finally {
      setIsUploading(false);
    }
  }, []);

  const loadAnalysis = useCallback(async (analysisId) => {
      setIsUploading(true);
      setError(null);
      try {
          const data = await runTestAnalysis(analysisId);
          await getJobStatus(data.job_id);
          return data.job_id;
      } catch(err) {
          setError(err.response?.data?.detail || "Failed to load analysis.");
          throw err;
      } finally {
          setIsUploading(false);
      }
  }, []);

  return { upload, loadAnalysis, progress, isUploading, error };
};

export const useJobStatus = (jobId) => {
  const [status, setStatus] = useState('PENDING');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const intervalRef = useRef(null);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const res = await getJobStatus(jobId);
        setStatus(res.status);
        if (res.progress !== undefined) setProgress(res.progress);
        setData(res);

        if (res.status === 'COMPLETED') {
           setError(null); // Clear any transient errors if it finally completes
           clearInterval(intervalRef.current);
        } else if (res.status === 'FAILED') {
           setError(res.error);
           // We DON'T clear interval here anymore, to allow recovery if results appear
        } else {
           setError(null);
        }
      } catch (err) {
        console.error("Polling error:", err);
        // Don't set error immediately on transient network fail
      }
    };

    // Initial call
    poll();
    
    intervalRef.current = setInterval(poll, 2000);

    return () => clearInterval(intervalRef.current);
  }, [jobId]);

  return { status, progress, error, data };
};
