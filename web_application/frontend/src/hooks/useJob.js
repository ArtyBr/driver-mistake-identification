import { useState, useEffect, useCallback, useRef } from 'react';
import { 
  getJobStatus, 
  initUpload, 
  uploadJobFile, 
  finalizeUpload 
} from '../services/api';

export const useJobUpload = () => {
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  const upload = useCallback(async (roadFiles, faceFiles, keepVideos, name, calibrationId) => {
    setIsUploading(true);
    setProgress(0);
    setError(null);

    try {
      // 1. Initialize the job record
      const initFormData = new FormData();
      if (name) initFormData.append('name', name);
      if (calibrationId) initFormData.append('calibration_id', calibrationId);
      initFormData.append('keep_videos', keepVideos);

      const { job_id } = await initUpload(initFormData);

      const totalFiles = roadFiles.length + faceFiles.length;
      let completedFiles = 0;

      // 2. Upload road videos one by one
      for (const file of roadFiles) {
        await uploadJobFile(job_id, 'road', file, (p) => {
          const overall = Math.round(((completedFiles + p / 100) / totalFiles) * 100);
          setProgress(Math.min(overall, 99)); // Keep at 99 until finalize
        });
        completedFiles++;
      }

      // 3. Upload face videos one by one
      for (const file of faceFiles) {
        await uploadJobFile(job_id, 'face', file, (p) => {
          const overall = Math.round(((completedFiles + p / 100) / totalFiles) * 100);
          setProgress(Math.min(overall, 99));
        });
        completedFiles++;
      }

      // 4. Finalize the upload to start analysis
      await finalizeUpload(job_id);
      setProgress(100);
      
      return job_id;
    } catch (err) {
      console.error("Upload process failed:", err);
      setError(err.response?.data?.detail || "Upload failed. Check your connection or file size.");
      throw err;
    } finally {
      setIsUploading(false);
    }
  }, []);

  return { upload, progress, isUploading, error };
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
