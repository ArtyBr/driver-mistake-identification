import { useState, useEffect } from 'react'
import { uploadVideos, listAnalyses, runTestAnalysis, getJobStatus } from '../services/api'

function Uploader({ onUploadSuccess }) {
  const [roadFile, setRoadFile] = useState(null)
  const [faceFile, setFaceFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const [analyses, setAnalyses] = useState([])
  const [selectedAnalysis, setSelectedAnalysis] = useState("")

  useEffect(() => {
    // Fetch available analyses
    listAnalyses()
      .then(data => setAnalyses(data))
      .catch(err => console.error("Failed to fetch analyses:", err))
  }, [])

  const validateFile = (file) => {
    const validTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo'];

    if (!validTypes.includes(file.type) && !file.name.match(/\.(mp4|avi|mov)$/i)) {
      return "Invalid file type. Please upload MP4, AVI, or MOV.";
    }
    return null;
  }

  const handleUpload = async () => {
    setError(null)
    setUploadProgress(0)

    if (!roadFile || !faceFile) {
      setError("Please select both road and face videos.")
      return
    }

    const roadError = validateFile(roadFile);
    if (roadError) {
      setError(`Road Video: ${roadError}`);
      return;
    }

    const faceError = validateFile(faceFile);
    if (faceError) {
      setError(`Driver Video: ${faceError}`);
      return;
    }

    setUploading(true)

    const formData = new FormData()
    formData.append('video_road', roadFile)
    formData.append('video_face', faceFile)

    try {
      const data = await uploadVideos(formData, setUploadProgress)
      const statusData = await getJobStatus(data.job_id)
      onUploadSuccess(data.job_id, statusData)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || "Upload failed. Check your connection or file size.")
    } finally {
      setUploading(false)
    }
  }

  const handleLoadAnalysis = async () => {
    setUploading(true)
    setError(null)
    try {
      const data = await runTestAnalysis(selectedAnalysis)
      const statusData = await getJobStatus(data.job_id)
      onUploadSuccess(data.job_id, statusData)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || "Failed to load analysis.")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="card shadow-sm">
      <div className="card-header bg-primary text-white">
        <h4 className="mb-0">Upload New Analysis</h4>
      </div>
      <div className="card-body">
        {error && <div className="alert alert-danger">{error}</div>}
        
        <div className="mb-4">
          <label className="form-label fw-bold">Road Video (Front Facing):</label>
          <input 
            className="form-control" 
            type="file" 
            accept="video/*" 
            onChange={(e) => setRoadFile(e.target.files[0])} 
          />
          <div className="form-text">Supported formats: MP4, AVI, MOV.</div>
        </div>
        
        <div className="mb-4">
          <label className="form-label fw-bold">Driver Video (Face Facing):</label>
          <input 
            className="form-control" 
            type="file" 
            accept="video/*" 
            onChange={(e) => setFaceFile(e.target.files[0])} 
          />
        </div>
        
        {uploading && uploadProgress > 0 && uploadProgress < 100 && (
          <div className="progress mb-3">
            <div 
              className="progress-bar progress-bar-striped progress-bar-animated" 
              role="progressbar" 
              style={{ width: `${uploadProgress}%` }} 
              aria-valuenow={uploadProgress} 
              aria-valuemin="0" 
              aria-valuemax="100"
            >
              Uploading {uploadProgress}%
            </div>
          </div>
        )}

        <button 
          className="btn btn-primary w-100 mb-4" 
          onClick={handleUpload} 
          disabled={uploading}
        >
          {uploading ? (
            <span><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...</span>
          ) : 'Start New Analysis'}
        </button>
        
        <hr className="my-4" />
        
        <h5 className="mb-3 text-secondary">Or Load Previous Analysis</h5>
        <div className="row g-2 align-items-end">
          <div className="col-md-8">
            <label className="form-label small text-muted">Select Analysis:</label>
            <select 
              className="form-select"
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
              className="btn btn-outline-secondary w-100" 
              onClick={handleLoadAnalysis} 
              disabled={uploading}
            >
              Load Analysis
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Uploader
