import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add a request interceptor to add the auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Uploads road and face videos to start a new analysis.
 * @param {FormData} formData - Contains 'video_road' and 'video_face'.
 * @param {function} onProgress - Callback for upload progress (percentage).
 * @returns {Promise<Object>} Response containing job_id.
 */
export const uploadVideos = async (formData, onProgress) => {
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percentCompleted);
      }
    },
  });
  return response.data;
};

/**
 * Lists available completed analyses.
 * @returns {Promise<Array<{id: string, name: string, video_count: number, duration_seconds: number, created_at: string}>>} List of analyses with metadata.
 */
export const listAnalyses = async () => {
  const response = await api.get('/list_analyses');
  return response.data?.analyses || [];
};

/**
 * Updates the name of a job.
 * @param {string} jobId
 * @param {string} name
 * @returns {Promise<Object>} Updated job status.
 */
export const updateJobName = async (jobId, name) => {
  const response = await api.put(`/job/${jobId}/name`, { name });
  return response.data;
};

/**
 * Starts a test analysis or loads an existing one.
 * @param {string} [analysisId] - Optional existing analysis ID to load.
 * @returns {Promise<Object>} Response containing job_id.
 */
export const runTestAnalysis = async (analysisId) => {
  const url = analysisId ? `/run_test?analysis_id=${analysisId}` : '/run_test';
  const response = await api.post(url);
  return response.data;
};

/**
 * Gets the current status of a job.
 * @param {string} jobId 
 * @returns {Promise<Object>} Job status, progress, and URLs.
 */
export const getJobStatus = async (jobId) => {
  const response = await api.get(`/status/${jobId}`);
  return response.data;
};

/**
 * Gets the full results of a completed job.
 * @param {string} jobId 
 * @returns {Promise<Object>} Analysis results.
 */
export const getJobResults = async (jobId) => {
  const response = await api.get(`/results/${jobId}`);
  return response.data;
};

/**
 * Constructs a full URL for a file served by the backend.
 * @param {string} relativePath 
 * @returns {string} Full URL.
 */
export const getFileUrl = (relativePath) => {
  if (!relativePath) return '';
  if (relativePath.startsWith('http') || relativePath.startsWith('blob:')) return relativePath;
  
  // Remove trailing slash from base if present
  const base = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  // Ensure leading slash on path
  const path = relativePath.startsWith('/') ? relativePath : `/${relativePath}`;
  
  return `${base}${path}`;
};

export default api;
