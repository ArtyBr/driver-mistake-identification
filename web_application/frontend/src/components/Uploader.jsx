import { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

function Uploader({ onUploadSuccess }) {
  const [roadFile, setRoadFile] = useState(null)
  const [faceFile, setFaceFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [analyses, setAnalyses] = useState([])
  const [selectedAnalysis, setSelectedAnalysis] = useState("")

  useEffect(() => {
    // Fetch available analyses
    axios.get(`${API_BASE}/list_analyses`)
      .then(res => {
        if (res.data.analyses) {
          setAnalyses(res.data.analyses)
        }
      })
      .catch(err => console.error("Failed to fetch analyses:", err))
  }, [])

  const handleUpload = async () => {
    if (!roadFile || !faceFile) {
      setError("Please select both road and face videos.")
      return
    }

    setUploading(true)
    setError(null)

    const formData = new FormData()
    formData.append('video_road', roadFile)
    formData.append('video_face', faceFile)

    console.log("Starting upload...", { roadFile: roadFile.name, faceFile: faceFile.name })

    try {
      const res = await axios.post(`${API_BASE}/upload`, formData)
      console.log("Upload response:", res.data)

      // The status endpoint returns the URLs
      const statusRes = await axios.get(`${API_BASE}/status/${res.data.job_id}`)
      console.log("Initial status response:", statusRes.data)
      
      onUploadSuccess(res.data.job_id, statusRes.data)
    } catch (err) {
      console.error(err)
      setError("Upload failed. Make sure the backend is running.")
    } finally {
      setUploading(false)
    }
  }

  const handleLoadAnalysis = async () => {
    setUploading(true)
    setError(null)
    try {
      const url = selectedAnalysis 
        ? `${API_BASE}/run_test?analysis_id=${selectedAnalysis}`
        : `${API_BASE}/run_test`
        
      const res = await axios.post(url)
      
      if (res.data.error) {
         setError(res.data.error)
         setUploading(false)
         return
      }

      const statusRes = await axios.get(`${API_BASE}/status/${res.data.job_id}`)
      onUploadSuccess(res.data.job_id, statusRes.data)
    } catch (err) {
      console.error(err)
      setError("Failed to load analysis.")
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
        
        <button 
          className="btn btn-primary w-100 mb-4" 
          onClick={handleUpload} 
          disabled={uploading}
        >
          {uploading ? (
            <span><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Uploading...</span>
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
