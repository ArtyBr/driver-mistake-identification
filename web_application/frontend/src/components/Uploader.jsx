import { useState, useEffect } from 'react'
import { uploadVideos, listAnalyses, runTestAnalysis, getJobStatus } from '../services/api'
import FileDropZone from './FileDropZone'

function Uploader({ onUploadSuccess }) {
  const [roadFiles, setRoadFiles] = useState([])
  const [faceFiles, setFaceFiles] = useState([])
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
      return `Invalid file type: ${file.name}. Please upload MP4, AVI, or MOV.`;
    }
    return null;
  }

  const handleUpload = async () => {
    setError(null)
    setUploadProgress(0)

    if (!roadFiles || roadFiles.length === 0 || !faceFiles || faceFiles.length === 0) {
      setError("Please select both road and face videos.")
      return
    }

    // Validate all files
    for (const file of roadFiles) {
      const err = validateFile(file);
      if (err) {
        setError(`Road Video Error: ${err}`);
        return;
      }
    }
    for (const file of faceFiles) {
      const err = validateFile(file);
      if (err) {
        setError(`Driver Video Error: ${err}`);
        return;
      }
    }

    setUploading(true)

    const formData = new FormData()
    
    // Append all road files
    roadFiles.forEach(file => {
        formData.append('video_road', file)
    });

    // Append all face files
    faceFiles.forEach(file => {
        formData.append('video_face', file)
    });

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
    <div className="card-cyber shadow-sm">
      <div className="card-header">
        <h4 className="mb-0">Upload New Analysis</h4>
      </div>
      <div className="card-body">
        {error && <div className="alert alert-danger">{error}</div>}
        
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
          className="btn btn-cyber-primary w-100 mb-4" 
          onClick={handleUpload} 
          disabled={uploading}
        >
          {uploading ? (
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
              disabled={uploading}
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
