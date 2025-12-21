import { useState, useEffect } from 'react'
import axios from 'axios'
import VideoPlayer from './components/VideoPlayer'
import Uploader from './components/Uploader'
import './App.css'

const API_BASE = 'http://localhost:8000'

function App() {
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState(null)
  const [jobData, setJobData] = useState(null)

  const handleUploadSuccess = (id, data) => {
    setJobId(id)
    setJobData(data)
    setStatus('PENDING')
    setProgress(0)
  }

  useEffect(() => {
    let interval
    if (jobId && (status === 'PENDING' || status === 'PROCESSING')) {
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE}/status/${jobId}`)
          console.log(`Polling status for ${jobId}:`, res.data)
          
          setStatus(res.data.status)
          if (res.data.progress) {
            setProgress(res.data.progress)
          }
          if (res.data.status === 'COMPLETED') {
            console.log("Job completed. Fetching results...")
            const resultRes = await axios.get(`${API_BASE}/results/${jobId}`)
            console.log("Results received:", resultRes.data)
            
            setResults(resultRes.data)
            clearInterval(interval)
          } else if (res.data.status === 'FAILED') {
            console.error("Job failed:", res.data.error)
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
            {status === 'PROCESSING' && (
              <>
                <p>Analyzing video frames... This may take a few minutes.</p>
                <div className="progress-container">
                  <div className="progress-bar" style={{ width: `${progress}%` }}>
                    {progress}%
                  </div>
                </div>
              </>
            )}
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