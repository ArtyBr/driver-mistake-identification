import { useState, useEffect } from 'react'
import axios from 'axios'
import VideoPlayer from './components/VideoPlayer'
import Uploader from './components/Uploader'
import './App.css'

const API_BASE = 'http://localhost:8000'

function App() {
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [results, setResults] = useState(null)
  const [jobData, setJobData] = useState(null)

  const handleUploadSuccess = (id, data) => {
    setJobId(id)
    setJobData(data)
    setStatus('PENDING')
  }

  useEffect(() => {
    let interval
    if (jobId && (status === 'PENDING' || status === 'PROCESSING')) {
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE}/status/${jobId}`)
          setStatus(res.data.status)
          if (res.data.status === 'COMPLETED') {
            const resultRes = await axios.get(`${API_BASE}/results/${jobId}`)
            setResults(resultRes.data)
            clearInterval(interval)
          } else if (res.data.status === 'FAILED') {
            clearInterval(interval)
          }
        } catch (err) {
          console.error("Error polling status:", err)
        }
      }, 2000)
    }
    return () => clearInterval(interval)
  }, [jobId, status])

  return (
    <div className="app-container">
      <header>
        <h1>Driver Mistake Identification System</h1>
      </header>

      <main>
        {!jobId && <Uploader onUploadSuccess={handleUploadSuccess} />}

        {jobId && status !== 'COMPLETED' && (
          <div className="status-panel">
            <h2>Status: {status}</h2>
            {status === 'PROCESSING' && <p>Analyzing video frames... This may take a few minutes.</p>}
          </div>
        )}

        {status === 'COMPLETED' && results && jobData && (
          <VideoPlayer 
            results={results} 
            roadUrl={`${API_BASE}${jobData.road_url}`}
            faceUrl={`${API_BASE}${jobData.face_url}`}
          />
        )}
      </main>
    </div>
  )
}

export default App