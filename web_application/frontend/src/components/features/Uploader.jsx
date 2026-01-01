import { useState, useEffect } from 'react'
import { listAnalyses } from '../../services/api'
import FileDropZone from '../common/FileDropZone'
import { useJobUpload } from '../../hooks/useJob'

function Uploader({ onUploadSuccess }) {
  const [roadFiles, setRoadFiles] = useState([])
  const [faceFiles, setFaceFiles] = useState([])
  const [keepVideos, setKeepVideos] = useState(false)
  const [analyses, setAnalyses] = useState([])
  const [selectedAnalysis, setSelectedAnalysis] = useState("")
  
  const { upload, loadAnalysis, progress, isUploading, error: uploadError } = useJobUpload();
  const [localError, setLocalError] = useState(null);

  useEffect(() => {
    // Fetch available analyses
    listAnalyses()
      .then(data => setAnalyses(data))
      .catch(err => console.error("Failed to fetch analyses:", err))
  }, [])

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

    // Validate all files
    for (const file of roadFiles) {
      const err = validateFile(file);
      if (err) {
        setLocalError(`Road Video Error: ${err}`);
        return;
      }
    }
    for (const file of faceFiles) {
      const err = validateFile(file);
      if (err) {
        setLocalError(`Driver Video Error: ${err}`);
        return;
      }
    }

    try {
        const jobId = await upload(roadFiles, faceFiles, keepVideos);
        onUploadSuccess(jobId, {}, { roadFiles, faceFiles });
    } catch (e) {
        // Error is handled in hook
    }
  }

  const handleLoadAnalysis = async () => {
    setLocalError(null);
    try {
      const jobId = await loadAnalysis(selectedAnalysis);
      onUploadSuccess(jobId, {});
    } catch (e) {
      // Error handled in hook
    }
  }
  
  const displayError = localError || uploadError;

  return (
    <div className="card-cyber shadow-sm">
      <div className="card-header">
        <h4 className="mb-0">Upload New Analysis</h4>
      </div>
      <div className="card-body">
        {displayError && <div className="alert alert-danger">{displayError}</div>}
        
        <div className="row">
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

        <div className="form-check mb-4">
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
          disabled={isUploading}
        >
          {isUploading ? (
            <span><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...</span>
          ) : 'START NEW ANALYSIS'}
        </button>
        
        <hr className="my-4 border-secondary" />
        
        <h5 className="mb-3 text-muted">Or Load Previous Analysis</h5>
        <div className="row g-2 align-items-end">
          <div className="col-md-8">
            <label className="form-label small text-muted">Select Analysis:</label>
            <select 
              className="form-select form-control-cyber"
              value={selectedAnalysis} 
              onChange={(e) => setSelectedAnalysis(e.target.value)}
            >
              <option value="">-- Test Data (Default) --</option>
              {analyses.map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>
          <div className="col-md-4">
            <button 
              className="btn btn-cyber w-100" 
              onClick={handleLoadAnalysis} 
              disabled={isUploading}
            >
              LOAD ANALYSIS
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Uploader