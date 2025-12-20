import { useRef, useEffect, useState } from 'react'

function VideoPlayer({ results, roadUrl, faceUrl }) {
  const roadVideoRef = useRef(null)
  const faceVideoRef = useRef(null)
  const canvasRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  // Sync videos
  const togglePlay = () => {
    if (roadVideoRef.current.paused) {
      roadVideoRef.current.play()
      faceVideoRef.current.play()
      setIsPlaying(true)
    } else {
      roadVideoRef.current.pause()
      faceVideoRef.current.pause()
      setIsPlaying(false)
    }
  }

  const handleSeek = (e) => {
    const time = parseFloat(e.target.value)
    roadVideoRef.current.currentTime = time
    faceVideoRef.current.currentTime = time
    setCurrentTime(time)
  }

  const onTimeUpdate = () => {
    setCurrentTime(roadVideoRef.current.currentTime)
  }

  const onLoadedMetadata = () => {
    setDuration(roadVideoRef.current.duration)
  }

  // Draw loop
  useEffect(() => {
    let animationFrameId

    const draw = () => {
      const ctx = canvasRef.current.getContext('2d')
      const roadVideo = roadVideoRef.current
      if (!ctx || !roadVideo) return

      // Clear canvas
      ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)

      // Find frame data for current time
      const time = roadVideo.currentTime
      const frame = results.frame_data.find((f, i) => {
          const next = results.frame_data[i+1]
          return time >= f.time && (!next || time < next.time)
      })

      if (frame) {
        // Draw Lanes
        ctx.strokeStyle = '#00FF00'
        ctx.lineWidth = 3
        frame.lane_lines.forEach(lane => {
          ctx.beginPath()
          lane.forEach((pt, i) => {
            // Need to scale coordinates if canvas size != video size
            // For now assume they match or we scale here
            const x = (pt[0] / 1920) * canvasRef.current.width
            const y = (pt[1] / 1080) * canvasRef.current.height
            if (i === 0) ctx.moveTo(x, y)
            else ctx.lineTo(x, y)
          })
          ctx.stroke()
        })

        // Draw Face Info (Overlay on top left or in a box)
        if (frame.face_info && frame.face_info.bbox) {
            // Face info is from face video, but we might want to overlay some status on road video
            ctx.fillStyle = 'rgba(0, 0, 0, 0.5)'
            ctx.fillRect(10, 10, 250, 80)
            ctx.fillStyle = 'white'
            ctx.font = '16px Arial'
            ctx.fillText(`State: ${frame.current_state || 'N/A'}`, 20, 35)
            ctx.fillText(`Gaze: Y:${frame.face_info.yaw?.toFixed(1)} P:${frame.face_info.pitch?.toFixed(1)}`, 20, 65)
        }
      }

      animationFrameId = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(animationFrameId)
  }, [results])

  return (
    <div className="video-dashboard">
      <div className="video-container">
        <div className="video-wrapper road">
          <video 
            ref={roadVideoRef} 
            src={roadUrl} 
            onTimeUpdate={onTimeUpdate}
            onLoadedMetadata={onLoadedMetadata}
            muted
          />
          <canvas 
            ref={canvasRef} 
            width={1280} 
            height={720}
            className="overlay-canvas"
          />
        </div>
        <div className="video-wrapper face">
          <video 
            ref={faceVideoRef} 
            src={faceUrl} 
            muted
          />
        </div>
      </div>

      <div className="controls">
        <button onClick={togglePlay}>{isPlaying ? 'Pause' : 'Play'}</button>
        <input 
          type="range" 
          min="0" 
          max={duration} 
          step="0.01" 
          value={currentTime} 
          onChange={handleSeek} 
          className="timeline-slider"
        />
        <span>{currentTime.toFixed(2)} / {duration.toFixed(2)}s</span>
      </div>

      <div className="events-timeline">
        <h3>Detected Events</h3>
        <div className="event-list">
          {results.timeline_events.map((event, i) => (
            <div 
              key={i} 
              className={`event-item ${event.severity}`}
              onClick={() => {
                roadVideoRef.current.currentTime = Math.max(0, event.timestamp - 2)
                faceVideoRef.current.currentTime = Math.max(0, event.timestamp - 2)
              }}
            >
              <strong>{event.timestamp.toFixed(2)}s:</strong> {event.message}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default VideoPlayer
