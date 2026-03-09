import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import './Uploader.css'
import api, { 
  updateJobName, 
  deleteJob, 
  initSync, 
  uploadSyncFile, 
  finalizeSync 
} from '../../services/api'
import FileDropZone from '../common/FileDropZone'
import SyncConfirmStep from './SyncConfirmStep'
import { useJobUpload } from '../../hooks/useJob'
import { useAuth } from '../../hooks/useAuth'
import { useAnalysesList } from '../../hooks/useAnalysesList'
import AnalysisListItem from '../common/AnalysisListItem'
import { listCalibrations, renameCalibration } from '../../services/calibrationService'
import { groupAnalyses } from '../../utils/groupAnalyses'

function Uploader({ onUploadSuccess }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [roadFiles, setRoadFiles] = useState([])
  const [faceFiles, setFaceFiles] = useState([])
  const [keepVideos, setKeepVideos] = useState(false)
  const [alreadySynced, setAlreadySynced] = useState(false)
  const [uploadName, setUploadName] = useState("")
  const [calibrations, setCalibrations] = useState([])
  const [selectedCalId, setSelectedCalId] = useState("")

  // Sync flow state
  const [syncStep,           setSyncStep]           = useState('upload') // 'upload' | 'sync_confirm'
  const [syncData,           setSyncData]           = useState(null)
  const [manualOffset,       setManualOffset]       = useState(0)
  const [isSyncAnalyzing,    setIsSyncAnalyzing]    = useState(false)
  const [syncUploadProgress, setSyncUploadProgress] = useState(0)
  const [isSubmitting,       setIsSubmitting]       = useState(false)
  const [pollingSessionId,   setPollingSessionId]   = useState(null)
  const pollIntervalRef = useRef(null)
  const pollAttemptsRef = useRef(0)
  const MAX_POLL_ATTEMPTS = 150 // 150 × 2 s = 5 minutes

  const { upload, progress, isUploading, error: uploadError } = useJobUpload();
  const [localError, setLocalError] = useState(null);

  const { analyses, refetch: refetchAnalyses, getEtaMs } = useAnalysesList();
  
  const myAnalyses = analyses.filter(a => !a.is_demo);
  const myAnalysesGroups = groupAnalyses(myAnalyses);

  useEffect(() => {
    if (user) {
      listCalibrations().then(data => {
        const trained = data.filter(c => c.is_trained);
        setCalibrations(trained);
        if (trained.length > 0) {
          setSelectedCalId(trained[0].id);
        }
      }).catch(err => console.error("Failed to load calibrations", err));
    }
  }, [user]);

  useEffect(() => {
    if (!pollingSessionId) return
    pollAttemptsRef.current = 0
    const poll = async () => {
      pollAttemptsRef.current += 1
      if (pollAttemptsRef.current > MAX_POLL_ATTEMPTS) {
        clearInterval(pollIntervalRef.current)
        setPollingSessionId(null)
        setLocalError('Sync analysis timed out. The server may be under load — please try again.')
        setIsSyncAnalyzing(false)
        return
      }
      try {
        const res = await api.get(`/sync/status/${pollingSessionId}`)
        const { status, ...data } = res.data
        if (status === 'done') {
          clearInterval(pollIntervalRef.current)
          setPollingSessionId(null)
          setSyncData(data)
          setManualOffset(data.offset_seconds ?? 0)
          setSyncStep('sync_confirm')
          setIsSyncAnalyzing(false)
        } else if (status === 'error') {
          clearInterval(pollIntervalRef.current)
          setPollingSessionId(null)
          setLocalError(data.detail || 'Sync analysis failed.')
          setIsSyncAnalyzing(false)
        }
      } catch {
        clearInterval(pollIntervalRef.current)
        setPollingSessionId(null)
        setLocalError('Sync analysis failed — could not get status.')
        setIsSyncAnalyzing(false)
      }
    }
    poll()
    pollIntervalRef.current = setInterval(poll, 2000)
    return () => clearInterval(pollIntervalRef.current)
  }, [pollingSessionId])

  const validateFile = (file) => {
    const validTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo'];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(mp4|avi|mov)$/i)) {
      return `Invalid file type: ${file.name}. Please upload MP4, AVI, or MOV.`;
    }
    return null;
  }

  const handleUpload = async () => {
    setLocalError(null);

    if (!roadFiles || roadFiles.length === 0 || !faceFiles || faceFiles.length === 0) {
      setLocalError("Please select both road and face videos.")
      return
    }

    for (const file of roadFiles) {
      const err = validateFile(file);
      if (err) { setLocalError(`Road Video Error: ${err}`); return; }
    }
    for (const file of faceFiles) {
      const err = validateFile(file);
      if (err) { setLocalError(`Driver Video Error: ${err}`); return; }
    }

    if (alreadySynced) {
      // Existing upload path — unchanged
      try {
        const jobId = await upload(roadFiles, faceFiles, keepVideos, uploadName, selectedCalId);
        onUploadSuccess(jobId, {}, { roadFiles, faceFiles });
      } catch {
        // Error handled in hook
      }
      return;
    }

    // Sync analysis path
    setIsSyncAnalyzing(true);
    setSyncUploadProgress(0);
    try {
      const { session_id } = await initSync();

      const totalFiles = roadFiles.length + faceFiles.length;
      let completedFiles = 0;

      for (const file of roadFiles) {
        await uploadSyncFile(session_id, 'road', file, (p) => {
          const overall = Math.round(((completedFiles + p / 100) / totalFiles) * 100);
          setSyncUploadProgress(overall);
        });
        completedFiles++;
      }

      for (const file of faceFiles) {
        await uploadSyncFile(session_id, 'face', file, (p) => {
          const overall = Math.round(((completedFiles + p / 100) / totalFiles) * 100);
          setSyncUploadProgress(overall);
        });
        completedFiles++;
      }

      const res = await finalizeSync(session_id);

      // Backend returns immediately with session_id; polling useEffect takes over
      setPollingSessionId(res.session_id);
    } catch (err) {
      setLocalError(
        err.response?.data?.detail || 'Sync analysis failed. Check your videos and try again.'
      );
      setIsSyncAnalyzing(false);
    }
  }

  const handleConfirmSync = async () => {
    setIsSubmitting(true);
    try {
      const res = await api.post('/sync/submit', {
        session_id: syncData.session_id,
        offset: manualOffset,
        name: uploadName || undefined,
        keep_videos: keepVideos,
        calibration_id: selectedCalId || undefined,
      });
      onUploadSuccess(res.data.job_id, {}, {});
    } catch (err) {
      setLocalError(err.response?.data?.detail || 'Submission failed.');
      setSyncStep('upload');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleView = (analysis) => {
    if (analysis.status === 'COMPLETED' || analysis.status === 'FAILED') {
      navigate(`/view/${analysis.id}`);
    } else {
      navigate(`/job/${analysis.id}`);
    }
  };

  const handleDeleteItem = async (analysis) => {
    const isLast = myAnalyses.filter(a => 
      (a.road_path === analysis.road_path && analysis.road_path) || 
      (a.face_path === analysis.face_path && analysis.face_path)
    ).length === 1;

    const message = isLast && (analysis.road_path || analysis.face_path)
      ? `Delete "${analysis.name || 'this analysis'}"? This is the final analysis for these videos; deleting it will also delete the corresponding videos from storage. This cannot be undone.`
      : `Delete "${analysis.name || 'this analysis'}"? This cannot be undone.`;

    if (!window.confirm(message)) return;
    try {
      await deleteJob(analysis.id);
      await refetchAnalyses();
    } catch (e) {
      setLocalError(e.response?.data?.detail || 'Failed to delete analysis.');
    }
  };

  const handleRenameItem = async (analysis) => {
    const newName = window.prompt('Enter new name:', analysis.name || '');
    if (newName && newName.trim()) {
      try {
        await updateJobName(analysis.id, newName.trim());
        await refetchAnalyses();
      } catch {
        setLocalError('Failed to update name.');
      }
    }
  };

  const displayError = localError || uploadError;

  // ── Sync confirm step ──────────────────────────────────────────────
  if (syncStep === 'sync_confirm') {
    return (
      <SyncConfirmStep
        syncData={syncData}
        manualOffset={manualOffset}
        setManualOffset={setManualOffset}
        onConfirm={handleConfirmSync}
        onBack={() => { setSyncStep('upload'); setLocalError(null); }}
        isSubmitting={isSubmitting}
      />
    );
  }

  // ── Upload step ────────────────────────────────────────────────────
  const isBusy = isUploading || isSyncAnalyzing;

  return (
    <div className="card-cyber shadow-sm">
      {user ? (
        <>
          <div className="card-header">
            <h4 className="mb-0">Upload New Analysis</h4>
          </div>
          <div className="card-body">
            {displayError && <div className="alert alert-danger">{displayError}</div>}

            <div className="row">
              <div className="col-md-6 mb-3">
                <label className="form-label text-white">Analysis Name (Optional)</label>
                <input
                  type="text"
                  className="form-control form-control-cyber"
                  placeholder="e.g. Morning Commute Sept 2025"
                  value={uploadName}
                  onChange={(e) => setUploadName(e.target.value)}
                />
              </div>
              <div className="col-md-6 mb-3">
                <label className="form-label text-white">Gaze Calibration (Optional)</label>
                <div className="d-flex gap-2 align-items-center">
                  <select
                    className="form-select form-control-cyber flex-grow-1"
                    value={selectedCalId}
                    onChange={(e) => setSelectedCalId(e.target.value)}
                  >
                    <option value="">-- Use Default Model --</option>
                    {calibrations.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  {selectedCalId && (
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      title="Rename calibration"
                      onClick={async () => {
                        const cal = calibrations.find(c => c.id === selectedCalId);
                        const newName = window.prompt('Rename calibration:', cal?.name || '');
                        if (!newName || !newName.trim()) return;
                        try {
                          await renameCalibration(selectedCalId, newName.trim());
                          const updated = (await listCalibrations()).filter(c => c.is_trained);
                          setCalibrations(updated);
                        } catch {
                          setLocalError('Failed to rename calibration.');
                        }
                      }}
                    >
                      <i className="bi bi-pencil"></i>
                    </button>
                  )}
                </div>
                {calibrations.length === 0 && (
                  <div className="form-text text-muted small" style={{ fontSize: '0.7rem' }}>
                    No trained calibrations found. <a href="/calibrate" className="text-info">Calibrate here</a> to improve results.
                  </div>
                )}
              </div>
              <div className="col-md-6">
                <FileDropZone
                  label="Road Video (Front Facing)"
                  files={roadFiles}
                  setFiles={setRoadFiles}
                  accept="video/*"
                  helperText="Supported formats: MP4, AVI, MOV. Select multiple files to splice."
                  multiple={true}
                />
              </div>
              <div className="col-md-6">
                <FileDropZone
                  label="Driver Video (Face Facing)"
                  files={faceFiles}
                  setFiles={setFaceFiles}
                  accept="video/*"
                  helperText="Ideally aligned with road video. Select multiple files to splice."
                  multiple={true}
                />
              </div>
            </div>

            <div className="form-check mb-3">
              <input
                className="form-check-input"
                type="checkbox"
                id="keepVideosCheck"
                checked={keepVideos}
                onChange={(e) => setKeepVideos(e.target.checked)}
              />
              <label className="form-check-label text-white" htmlFor="keepVideosCheck">
                Keep videos on server after analysis (Uncheck to delete after processing)
              </label>
            </div>

            <div className="form-check mb-4">
              <input
                className="form-check-input"
                type="checkbox"
                id="alreadySyncedCheck"
                checked={alreadySynced}
                onChange={(e) => setAlreadySynced(e.target.checked)}
              />
              <label className="form-check-label text-white" htmlFor="alreadySyncedCheck">
                Videos are already synchronised (e.g., recorded by the same device or hardware-synced)
              </label>
            </div>

            {/* Progress indicators */}
            {isSyncAnalyzing && syncUploadProgress > 0 && syncUploadProgress < 100 && (
              <div className="progress mb-2">
                <div
                  className="progress-bar progress-bar-striped progress-bar-animated"
                  role="progressbar"
                  style={{ width: `${syncUploadProgress}%` }}
                  aria-valuenow={syncUploadProgress}
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  Uploading {syncUploadProgress}%
                </div>
              </div>
            )}
            {isSyncAnalyzing && (
              <div className="d-flex align-items-center text-muted small mb-3">
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                Analysing audio for synchronisation…
              </div>
            )}
            {isUploading && progress > 0 && progress < 100 && (
              <div className="progress mb-3">
                <div
                  className="progress-bar progress-bar-striped progress-bar-animated"
                  role="progressbar"
                  style={{ width: `${progress}%` }}
                  aria-valuenow={progress}
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  Uploading {progress}%
                </div>
              </div>
            )}

            <button
              className="btn btn-cyber-primary w-100 mb-4"
              onClick={handleUpload}
              disabled={isBusy}
            >
              {isBusy ? (
                <span>
                  <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                  {isSyncAnalyzing ? 'Analysing…' : 'Processing…'}
                </span>
              ) : 'START NEW ANALYSIS'}
            </button>

            <hr className="my-4 border-secondary" />
          </div>
        </>
      ) : (
        <div className="card-header text-center py-4">
          <h4 className="mb-2">Explore Driver Safety</h4>
          <p className="text-muted mb-0">Select a demo video below to see the analysis in action. <a href="/login" className="text-cyber-blue">Login</a> to upload your own.</p>
        </div>
      )}

      <div className="card-body pt-0">
        <h5 className="mb-3 text-muted">Load Previous Analysis</h5>

        {user ? (
          <div className="mb-3">
            <h6 className="text-cyber-blue mb-3 fw-bold"><i className="bi bi-person-video me-2"></i>My Private Analyses</h6>
            <div className="analysis-list border-0 bg-transparent">
              {myAnalysesGroups.map(group => (
                <div key={group[0].id} className="mb-3">
                  <AnalysisListItem
                    analysis={group[0]}
                    onClick={() => handleView(group[0])}
                    onView={() => handleView(group[0])}
                    onRename={() => handleRenameItem(group[0])}
                    onDelete={() => handleDeleteItem(group[0])}
                    etaMs={getEtaMs(group[0].id, group[0].progress || 0)}
                  />
                  {group.length > 1 && (
                    <div className="accordion mt-2" id={`accordion-uploader-${group[0].id}`}>
                      <div className="accordion-item" style={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)' }}>
                        <h2 className="accordion-header">
                          <button className="accordion-button collapsed py-2 px-3 text-muted" type="button" data-bs-toggle="collapse" data-bs-target={`#collapse-uploader-${group[0].id}`} style={{ backgroundColor: 'transparent', boxShadow: 'none', fontSize: '0.85rem' }}>
                            Show {group.length - 1} other re-analyses
                          </button>
                        </h2>
                        <div id={`collapse-uploader-${group[0].id}`} className="accordion-collapse collapse" data-bs-parent={`#accordion-uploader-${group[0].id}`}>
                          <div className="accordion-body p-2 bg-dark">
                            {group.slice(1).map(analysis => (
                              <AnalysisListItem
                                key={analysis.id}
                                analysis={analysis}
                                onClick={() => handleView(analysis)}
                                onView={() => handleView(analysis)}
                                onRename={() => handleRenameItem(analysis)}
                                onDelete={() => handleDeleteItem(analysis)}
                                etaMs={getEtaMs(analysis.id, analysis.progress || 0)}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {myAnalysesGroups.length === 0 && (
                <div className="p-4 text-center text-muted border border-secondary border-dashed rounded bg-panel-lighter">
                  <i className="bi bi-cloud-plus fs-2 mb-2 d-block opacity-50"></i>
                  No personal analyses found.<br />Upload your first video above.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="alert alert-cyber-info mb-3">
            <p className="mb-0">You are viewing the uploader as a <strong>Guest</strong>. <a href="/login" className="text-cyber-blue fw-bold">Login</a> to start your own analysis or view your previous results.</p>
          </div>
        )}

      </div>
    </div>
  )
}

export default Uploader
