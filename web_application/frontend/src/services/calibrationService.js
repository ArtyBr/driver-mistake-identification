import api from './api';

/**
 * Gets the current user's calibration status and per-class sample counts.
 * @returns {Promise<{has_calibration, is_trained, sample_counts, total_samples}>}
 */
export const getCalibrationStatus = async () => {
  const response = await api.get('/calibration/status');
  return response.data;
};

/**
 * Submits pre-computed {yaw, pitch, roll, label} data points directly.
 * These are exactly the points shown in the live scatter plot on the calibration page,
 * ensuring what the user sees is precisely what gets trained.
 * @param {Array<{yaw: number, pitch: number, roll: number, label: string}>} samples
 * @returns {Promise<{added: number, status: object}>}
 */
export const submitSamples = async (samples) => {
  const response = await api.post('/calibration/samples', { samples });
  return response.data;
};

/**
 * Returns the raw stored training samples [{yaw, pitch, roll, label}] for the current user.
 * @returns {Promise<{samples: Array<{yaw: number, pitch: number, roll: number, label: string}>}>}
 */
export const getStoredSamples = async () => {
  const response = await api.get('/calibration/samples');
  return response.data;
};

/**
 * Clears all calibration training data for the current user.
 * @returns {Promise<{message: string}>}
 */
export const resetSamples = async () => {
  const response = await api.delete('/calibration/samples');
  return response.data;
};

/**
 * Triggers training of the user's personal PCA+SVM model from saved samples.
 * @returns {Promise<{success: boolean, message: string}>}
 */
export const trainModel = async () => {
  const response = await api.post('/calibration/train');
  return response.data;
};

/**
 * Submits a gaze correction for a time segment and immediately retrains the model.
 * @param {string} jobId
 * @param {number} startTime
 * @param {number} endTime
 * @param {string} correctLabel  One of: 'Left Mirror', 'Right Mirror', 'Looking Ahead', 'Rear Mirror'
 * @returns {Promise<{added: number, retrained: boolean, message: string}>}
 */
export const submitCorrection = async (jobId, startTime, endTime, correctLabel) => {
  const response = await api.post('/calibration/correct', {
    job_id: jobId,
    start_time: startTime,
    end_time: endTime,
    correct_label: correctLabel,
  });
  return response.data;
};

/**
 * Fetches the diagnostic plot images (base64 data URLs) from the last training run.
 * @returns {Promise<{plots: {head_pose: string, pca: string, decision_boundary: string}}>}
 */
export const getCalibrationPlots = async () => {
  const response = await api.get('/calibration/plots');
  return response.data;
};

/**
 * Requests re-analysis of a job using the user's personal calibration model.
 * @param {string} jobId
 * @returns {Promise<{job_id: string}>}
 */
export const requestReanalysis = async (jobId) => {
  const response = await api.post(`/calibration/reanalyze/${jobId}`);
  return response.data;
};
