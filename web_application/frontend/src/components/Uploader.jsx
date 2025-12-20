import { useState } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

function Uploader({ onUploadSuccess }) {
  const [roadFile, setRoadFile] = useState(null)
  const [faceFile, setFaceFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

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

    try {
      const res = await axios.post(`${API_BASE}/upload`, formData)
      // The status endpoint returns the URLs
      const statusRes = await axios.get(`${API_BASE}/status/${res.data.job_id}`)
      onUploadSuccess(res.data.job_id, statusRes.data)
    } catch (err) {
      console.error(err)
      setError("Upload failed. Make sure the backend is running.")
    } finally {
      setUploading(false)
    }
  }

  const handleRunTest = async () => {
    setUploading(true)
    setError(null)
    try {
      const res = await axios.post(`${API_BASE}/run_test`)
      const statusRes = await axios.get(`${API_BASE}/status/${res.data.job_id}`)
      onUploadSuccess(res.data.job_id, statusRes.data)
    } catch (err) {
      console.error(err)
      setError("Test run failed.")
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
      <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
        <button onClick={handleUpload} disabled={uploading}>
          {uploading ? 'Uploading...' : 'Start Analysis'}
        </button>
        <button onClick={handleRunTest} disabled={uploading} style={{ backgroundColor: '#444' }}>
          Run Test Analysis (Local Data)
        </button>
      </div>
    </div>
  )
}

export default Uploader
