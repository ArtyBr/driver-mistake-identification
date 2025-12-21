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
    <div className="uploader-box">
      <h2>Upload New Analysis</h2>
      <div className="input-group">
        <label>Road Video (Front Facing):</label>
        <input type="file" accept="video/*" onChange={(e) => setRoadFile(e.target.files[0])} />
      </div>
      <div className="input-group">
        <label>Driver Video (Face Facing):</label>
        <input type="file" accept="video/*" onChange={(e) => setFaceFile(e.target.files[0])} />
      </div>
      {error && <p className="error">{error}</p>}
      
      <div className="actions-row" style={{ display: 'flex', gap: '20px', marginTop: '20px', alignItems: 'flex-end' }}>
        <button onClick={handleUpload} disabled={uploading}>
          {uploading ? 'Uploading...' : 'Start New Analysis'}
        </button>
        
        <div className="separator" style={{ width: '1px', background: '#444', height: '40px' }}></div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <label style={{ fontSize: '0.9em', color: '#888' }}>Load Previous Analysis:</label>
          <div style={{ display: 'flex', gap: '10px' }}>
            <select 
              value={selectedAnalysis} 
              onChange={(e) => setSelectedAnalysis(e.target.value)}
              style={{ padding: '8px', borderRadius: '4px', background: '#333', color: 'white', border: '1px solid #555' }}
            >
              <option value="">-- Test Data (Default) --</option>
              {analyses.map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
            <button onClick={handleLoadAnalysis} disabled={uploading} style={{ backgroundColor: '#444' }}>
              Load Analysis
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Uploader
