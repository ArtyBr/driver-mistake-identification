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
    // 30-minute ceiling: prevents a stalled connection hanging indefinitely
    // while still accommodating very large video uploads over slow links.
    timeout: 30 * 60 * 1000,
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
 * Sequential Upload API
 */

export const initUpload = async (formData) => {
  const response = await api.post('/upload/init', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

export const uploadJobFile = async (jobId, videoType, file, onProgress) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post(`/upload/${jobId}/file/${videoType}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percentCompleted);
      }
    },
    timeout: 15 * 60 * 1000, // 15 mins per file
  });
  return response.data;
};

export const finalizeUpload = async (jobId) => {
  const response = await api.post(`/upload/${jobId}/finalize`);
  return response.data;
};

/**
 * Sequential Sync Upload API
 */

export const initSync = async () => {
  const response = await api.post('/sync/init');
  return response.data;
};

export const uploadSyncFile = async (sessionId, videoType, file, onProgress) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post(`/sync/${sessionId}/file/${videoType}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percentCompleted);
      }
    },
    timeout: 15 * 60 * 1000,
  });
  return response.data;
};

export const finalizeSync = async (sessionId) => {
  const response = await api.post(`/sync/${sessionId}/finalize`);
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

export const deleteJob = async (jobId) => {
  const response = await api.delete(`/job/${jobId}`);
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

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

export const getJobEvents = (jobId) => api.get(`/job/${jobId}/events`).then(r => r.data);

export const getAdminStats = () => api.get('/admin/stats').then(r => r.data);
export const getAdminUsers = () => api.get('/admin/users').then(r => r.data);
export const getAdminUserJobs = (userId) => api.get(`/admin/users/${userId}/jobs`).then(r => r.data);
export const updateAdminUser = (userId, data) => api.put(`/admin/users/${userId}`, data).then(r => r.data);
export const deleteAdminUser = (userId, deleteJobs = false) =>
  api.delete(`/admin/users/${userId}`, { params: { delete_jobs: deleteJobs } }).then(r => r.data);

export const getAdminJobs = (params = {}) => api.get('/admin/jobs', { params }).then(r => r.data);
export const updateAdminJob = (jobId, data) => api.put(`/admin/jobs/${jobId}`, data).then(r => r.data);
export const adminAssignJob = (jobId, userEmail) => api.put(`/admin/jobs/${jobId}/assign`, { user_email: userEmail }).then(r => r.data);
export const deleteAdminJob = (jobId) => api.delete(`/admin/jobs/${jobId}`).then(r => r.data);

export const getAdminSessions = () => api.get('/admin/sessions').then(r => r.data);
export const deleteAdminSession = (sessionId) => api.delete(`/admin/sessions/${sessionId}`).then(r => r.data);

export const getAdminCalibrations = () => api.get('/admin/calibrations').then(r => r.data);
export const deleteAdminCalibration = (userId) => api.delete(`/admin/calibrations/${userId}`).then(r => r.data);

// ---------------------------------------------------------------------------
// Error Reporting API
// ---------------------------------------------------------------------------

export const submitErrorReport = (jobId, reportData) => api.post(`/jobs/${jobId}/report`, reportData).then(r => r.data);

export const getAdminReports = (params = {}) => api.get('/admin/reports', { params }).then(r => r.data);
export const getAdminJobReports = (jobId) => api.get('/admin/reports', { params: { job_id: jobId } }).then(r => r.data);
export const getAdminReportStats = () => api.get('/admin/reports/stats').then(r => r.data);
export const adminReanalyzeJob = (jobId) => api.post(`/admin/jobs/${jobId}/reanalyze`).then(r => r.data);

/**
 * Downloads a 15-second clip (road + face) centered on `timestamp` as a ZIP.
 * Admin-only.
 */
export const downloadClip = async (jobId, timestamp) => {
  const response = await api.get(`/job/${jobId}/clip`, {
    params: { timestamp },
    responseType: 'blob',
    timeout: 120_000,
  });
  const url = URL.createObjectURL(response.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = `clip_${jobId}_${timestamp.toFixed(1)}s.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};

export default api;
