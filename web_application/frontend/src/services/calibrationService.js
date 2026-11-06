import api from './api';

/**
 * Lists all calibrations for the current user.
 * @returns {Promise<Array>}
 */
export const listCalibrations = async () => {
  const response = await api.get('/calibration/list');
  return response.data;
};

/**
 * Creates a new calibration.
 * @param {string} [name]
 * @returns {Promise<Object>}
 */
export const createCalibration = async (name) => {
  const response = await api.post('/calibration/create', { name });
  return response.data;
};

/**
 * Renames a calibration.
 * @param {string} calId
 * @param {string} name
 * @returns {Promise<Object>}
 */
export const renameCalibration = async (calId, name) => {
  const response = await api.patch(`/calibration/${calId}/rename`, { name });
  return response.data;
};

/**
 * Duplicates a calibration under a new name (Save As).
 * @param {string} calId
 * @param {string} name
 * @returns {Promise<Object>}
 */
export const duplicateCalibration = async (calId, name) => {
  const response = await api.post(`/calibration/${calId}/duplicate`, { name });
  return response.data;
};

/**
 * Deletes a calibration.
 * @param {string} calId
 * @returns {Promise<Object>}
 */
export const deleteCalibration = async (calId) => {
  const response = await api.delete(`/calibration/${calId}`);
  return response.data;
};

/**
 * Gets the status of a specific calibration.
 * @param {string} calId
 * @returns {Promise<Object>}
 */
export const getCalibrationStatus = async (calId) => {
  const response = await api.get('/calibration/status', { params: { cal_id: calId } });
  return response.data;
};

/**
 * Submits samples for a specific calibration.
 * @param {string} calId
 * @param {Array} samples
 * @returns {Promise<Object>}
 */
export const submitSamples = async (calId, samples) => {
  const response = await api.post('/calibration/samples', { cal_id: calId, samples });
  return response.data;
};

/**
 * Gets stored samples for a specific calibration.
 * @param {string} calId
 * @returns {Promise<Object>}
 */
export const getStoredSamples = async (calId) => {
  const response = await api.get('/calibration/samples', { params: { cal_id: calId } });
  return response.data;
};

/**
 * Resets samples for a specific calibration.
 * @param {string} calId
 * @returns {Promise<Object>}
 */
export const resetSamples = async (calId) => {
  const response = await api.delete('/calibration/samples', { params: { cal_id: calId } });
  return response.data;
};

/**
 * Trains a specific calibration model.
 * @param {string} calId
 * @returns {Promise<Object>}
 */
export const trainModel = async (calId) => {
  const response = await api.post('/calibration/train', null, { params: { cal_id: calId } });
  return response.data;
};

/**
 * Fetches diagnostic plots for a specific calibration.
 * @param {string} calId
 * @returns {Promise<Object>}
 */
export const getCalibrationPlots = async (calId) => {
  const response = await api.get('/calibration/plots', { params: { cal_id: calId } });
  return response.data;
};

/**
 * Requests re-analysis of a job using a specific calibration model.
 * @param {string} jobId
 * @param {string} calId
 * @returns {Promise<Object>}
 */
export const requestReanalysis = async (jobId, calId) => {
  const params = calId ? { cal_id: calId } : {};
  const response = await api.post(`/calibration/reanalyze/${jobId}`, null, { params });
  return response.data;
};

/**
 * Submits a gaze correction.
 * @param {string} jobId
 * @param {number} startTime
 * @param {number} endTime
 * @param {string} correctLabel
 * @param {string} [calId]
 * @returns {Promise<Object>}
 */
export const submitCorrection = async (jobId, startTime, endTime, correctLabel, calId) => {
  const response = await api.post('/calibration/correct', {
    job_id: jobId,
    start_time: startTime,
    end_time: endTime,
    correct_label: correctLabel,
    cal_id: calId,
  });
  return response.data;
};
