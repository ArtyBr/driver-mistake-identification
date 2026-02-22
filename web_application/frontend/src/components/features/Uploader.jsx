import { useState, useEffect } from 'react'
import './Uploader.css'
import api, { listAnalyses, updateJobName, deleteJob } from '../../services/api'
import FileDropZone from '../common/FileDropZone'
import SyncConfirmStep from './SyncConfirmStep'
import { useJobUpload } from '../../hooks/useJob'
import { useAuth } from '../../hooks/useAuth'

function Uploader({ onUploadSuccess }) {
  const { user } = useAuth();
  const [roadFiles, setRoadFiles] = useState([])
  const [faceFiles, setFaceFiles] = useState([])
  const [keepVideos, setKeepVideos] = useState(false)
  const [alreadySynced, setAlreadySynced] = useState(false)
  const [uploadName, setUploadName] = useState("")
  const [analyses, setAnalyses] = useState([])
  const [selectedAnalysis, setSelectedAnalysis] = useState("")

  // Sync flow state
  const [syncStep,           setSyncStep]           = useState('upload') // 'upload' | 'sync_confirm'
  const [syncData,           setSyncData]           = useState(null)
  const [manualOffset,       setManualOffset]       = useState(0)
  const [isSyncAnalyzing,    setIsSyncAnalyzing]    = useState(false)
  const [syncUploadProgress, setSyncUploadProgress] = useState(0)
  const [isSubmitting,       setIsSubmitting]       = useState(false)

  const { upload, loadAnalysis, progress, isUploading, error: uploadError } = useJobUpload();
  const [localError, setLocalError] = useState(null);

  useEffect(() => {
    listAnalyses()
      .then(data => setAnalyses(data))
      .catch(err => console.error("Failed to fetch analyses:", err))
  }, [user])

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
        const jobId = await upload(roadFiles, faceFiles, keepVideos, uploadName);
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
      const formData = new FormData();
      roadFiles.forEach(f => formData.append('road_video', f));
      faceFiles.forEach(f => formData.append('face_video', f));

      const res = await api.post('/sync/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (evt) => {
          if (evt.total) {
            setSyncUploadProgress(Math.round((evt.loaded * 100) / evt.total));
          }
        },
      });

      setSyncData(res.data);
      setManualOffset(res.data.offset_seconds ?? 0);
      setSyncStep('sync_confirm');
    } catch (err) {
      setLocalError(
        err.response?.data?.detail || 'Sync analysis failed. Check your videos and try again.'
      );
    } finally {
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
      });
      onUploadSuccess(res.data.job_id, {}, {});
    } catch (err) {
      setLocalError(err.response?.data?.detail || 'Submission failed.');
      setSyncStep('upload');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLoadAnalysis = async () => {
    setLocalError(null);
    try {
      const jobId = await loadAnalysis(selectedAnalysis);
      onUploadSuccess(jobId, {});
    } catch {
      // Error handled in hook
    }
  }

  const handleDelete = async () => {
    if (!selectedAnalysis) return;
    const current = analyses.find(a => a.id === selectedAnalysis);
    if (!window.confirm(`Delete "${current?.name || selectedAnalysis}" and all its files? This cannot be undone.`)) return;
    try {
      await deleteJob(selectedAnalysis);
      setSelectedAnalysis('');
      const data = await listAnalyses();
      setAnalyses(data);
    } catch (e) {
      setLocalError(e.response?.data?.detail || 'Failed to delete analysis.');
    }
  };

  const handleRename = async () => {
    if (!selectedAnalysis) return;
    const currentAnalysis = analyses.find(a => a.id === selectedAnalysis);
    const newName = prompt("Enter new name for this analysis:", currentAnalysis?.name || "");
    if (newName && newName.trim() !== "") {
      try {
        await updateJobName(selectedAnalysis, newName);
        const data = await listAnalyses();
        setAnalyses(data);
      } catch (e) {
        console.error("Failed to rename:", e);
        setLocalError("Failed to update name.");
      }
    }
  }

  const formatDuration = (seconds) => {
    if (!seconds) return "Unknown duration";
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  }

  const formatDate = (dateString) => {
    if (!dateString) return "Unknown date";
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

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
              <div className="col-md-12 mb-3">
                <label className="form-label text-white">Analysis Name (Optional)</label>
                <input
                  type="text"
                  className="form-control form-control-cyber"
                  placeholder="e.g. Morning Commute Sept 2025"
                  value={uploadName}
                  onChange={(e) => setUploadName(e.target.value)}
                />
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
              {Array.isArray(analyses) && analyses.filter(a => !a.is_demo).map(analysis => (
                <div
                  key={analysis.id}
                  className={`analysis-item-modern mb-2 p-3 rounded cursor-pointer ${selectedAnalysis === analysis.id ? "selected-analysis" : ""}`}
                  onClick={() => setSelectedAnalysis(analysis.id)}
                  style={{ cursor: 'pointer' }}
                >
                  <div className="d-flex justify-content-between align-items-start">
                    <div className="fw-bold text-white mb-1">{analysis.name}</div>
                    {selectedAnalysis === analysis.id && <i className="bi bi-check-circle-fill text-accent-primary"></i>}
                  </div>
                  <div className="small text-muted d-flex justify-content-between mt-1">
                    <span><i className="bi bi-files me-1"></i>{analysis.video_count} videos • {formatDuration(analysis.duration_seconds)}</span>
                    <span className="opacity-75">{formatDate(analysis.created_at)}</span>
                  </div>
                </div>
              ))}
              {(!analyses || !analyses.some(a => !a.is_demo)) && (
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

        <div className="row g-2">
          {user && (
            <>
              <div className="col-md-4">
                <button
                  className="btn btn-outline-cyber w-100"
                  onClick={handleRename}
                  disabled={!selectedAnalysis || analyses.find(a => a.id === selectedAnalysis)?.is_demo}
                  title="Rename Analysis"
                >
                  RENAME
                </button>
              </div>
              <div className="col-md-4">
                <button
                  className="btn btn-cyber w-100"
                  style={{ borderColor: 'var(--accent-danger)', color: 'var(--accent-danger)' }}
                  onClick={handleDelete}
                  disabled={!selectedAnalysis || analyses.find(a => a.id === selectedAnalysis)?.is_demo}
                  title="Delete Analysis and Files"
                >
                  DELETE
                </button>
              </div>
              <div className="col-md-4">
                <button
                  className="btn btn-cyber w-100"
                  onClick={handleLoadAnalysis}
                  disabled={isUploading || !selectedAnalysis}
                >
                  LOAD
                </button>
              </div>
            </>
          )}
          {!user && (
            <div className="col-md-12">
              <button
                className="btn btn-cyber w-100"
                onClick={handleLoadAnalysis}
                disabled={isUploading || !selectedAnalysis}
              >
                LOAD ANALYSIS
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Uploader
