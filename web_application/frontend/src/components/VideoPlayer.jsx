import { useRef, useEffect, useState, useMemo } from 'react'

function VideoPlayer({ results, roadUrl, faceUrl }) {
  const roadVideoRef = useRef(null)
  const faceVideoRef = useRef(null)
  const canvasRef = useRef(null)
  const faceCanvasRef = useRef(null)
  const itemRefs = useRef([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [currentFaceState, setCurrentFaceState] = useState("N/A")
  const [activeLogIndex, setActiveLogIndex] = useState(-1)

  // Memoize history generation
  const history = useMemo(() => {
    const hist = []
    let lastState = null

    // Process frame data to find state changes
    if (results && results.frame_data) {
      results.frame_data.forEach(frame => {
        const state = frame.current_state
        if (state && state !== "N/A" && state !== "Unknown") {
          if (lastState !== null && state !== lastState) {
            hist.push({
              from: lastState,
              to: state,
              time: frame.time
            })
          }
          if (lastState === null || state !== lastState) {
            lastState = state
          }
        }
      })
    }
    return hist
  }, [results])

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

  // Update active log index based on time
  useEffect(() => {
    const index = history.findIndex((item, i) => {
      const next = history[i + 1]
      return item.time <= currentTime && (!next || next.time > currentTime)
    })
    if (index !== activeLogIndex) {
      setActiveLogIndex(index)
    }
  }, [currentTime, history, activeLogIndex])

  // Scroll to active item
  useEffect(() => {
    if (activeLogIndex !== -1 && itemRefs.current[activeLogIndex]) {
      itemRefs.current[activeLogIndex].scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      })
    }
  }, [activeLogIndex])

  // Draw loop
  useEffect(() => {
    let animationFrameId
    let lastRenderedState = null

    const draw = () => {
      const ctx = canvasRef.current.getContext('2d')
      const faceCtx = faceCanvasRef.current ? faceCanvasRef.current.getContext('2d') : null
      const roadVideo = roadVideoRef.current
      const faceVideo = faceVideoRef.current

      if (!ctx || !roadVideo || !faceCtx || !faceVideo) return

      // Clear canvases
      ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
      faceCtx.clearRect(0, 0, faceCanvasRef.current.width, faceCanvasRef.current.height)

      // Find frame data for current time
      const time = roadVideo.currentTime
      const frame = results.frame_data.find((f, i) => {
        const next = results.frame_data[i + 1]
        return time >= f.time && (!next || time < next.time)
      })

      if (frame) {
        // Update Current Face State UI (throttled check)
        if (frame.current_state && frame.current_state !== lastRenderedState) {
          setCurrentFaceState(frame.current_state)
          lastRenderedState = frame.current_state
        } else if (!frame.current_state && lastRenderedState !== "N/A") {
          setCurrentFaceState("N/A")
          lastRenderedState = "N/A"
        }

        // Draw Lanes (Road Canvas)
        ctx.strokeStyle = '#00FF00'
        ctx.lineWidth = 3
        if (frame.lane_lines) {
          frame.lane_lines.forEach(lane => {
            ctx.beginPath()
            lane.forEach((pt, i) => {
              const x = (pt[0] / 1920) * canvasRef.current.width
              const y = (pt[1] / 1080) * canvasRef.current.height
              if (i === 0) ctx.moveTo(x, y)
              else ctx.lineTo(x, y)
            })
            ctx.stroke()
          })
        }

        // Draw Face Arrow (Face Canvas)
        if (frame.face_info && frame.face_info.nose_2d && frame.face_info.yaw !== undefined) {
          let { nose_2d, yaw, pitch } = frame.face_info

          // Parse nose_2d if string (backend serialization quirk)
          if (typeof nose_2d === 'string') {
            const match = nose_2d.match(/\((-?\d+),\s*(-?\d+)\)/);
            if (match) {
              nose_2d = [parseInt(match[1]), parseInt(match[2])];
            } else {
              console.warn("Failed to parse nose_2d:", nose_2d);
            }
          }

          if (Array.isArray(nose_2d) || (nose_2d.length === 2)) {
            // Scale coordinates
            // Assuming nose_2d is in video native resolution. 
            // We need native resolution. If unavailable, default to 640x480 or similar?
            // faceVideo.videoWidth is available when loaded.
            const vW = faceVideo.videoWidth || 640
            const vH = faceVideo.videoHeight || 480

            const scaleX = faceCanvasRef.current.width / vW
            const scaleY = faceCanvasRef.current.height / vH

            const startX = nose_2d[0] * scaleX
            const startY = nose_2d[1] * scaleY

            const endX = (nose_2d[0] + yaw * 10) * scaleX
            const endY = (nose_2d[1] - pitch * 10) * scaleY

            faceCtx.strokeStyle = '#0000FF' // Blue in RGB
            faceCtx.lineWidth = 3
            faceCtx.beginPath()
            faceCtx.moveTo(startX, startY)
            faceCtx.lineTo(endX, endY)
            faceCtx.stroke()
          }
        }
      }

      animationFrameId = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(animationFrameId)
  }, [results])

  const iconMap = {
    'Left Mirror': '[ < ]',
    'Right Mirror': '[ > ]',
    'Looking Ahead': '[ ^ ]',
    'N/A': '[ ? ]',
    'Unknown': '[ ? ]'
  }

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
          <canvas
            ref={faceCanvasRef}
            width={640}
            height={480}
            className="overlay-canvas"
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

      <div className="face-log">
        <hr />
        <h4>
          Current Face Direction: {iconMap[currentFaceState] || iconMap['N/A']} {currentFaceState || "N/A"}
        </h4>
        <hr />
        <h3>Face Direction Log (Transitions)</h3>
        <div className="log-list">
          {history.map((item, i) => {
            const isCurrent = i === activeLogIndex
            
            return (
              <div
                key={i}
                ref={el => itemRefs.current[i] = el}
                className={`log-item ${isCurrent ? 'active' : ''}`}
                onClick={() => {
                  roadVideoRef.current.currentTime = Math.max(0, item.time - 0.5)
                  faceVideoRef.current.currentTime = Math.max(0, item.time - 0.5)
                }}
              >
                <span className="log-time">{item.time.toFixed(1)}s</span>
                <span className="log-state">
                  {iconMap[item.from] || iconMap['N/A']} <strong>{item.from}</strong> 
                  {' → '} 
                  {iconMap[item.to] || iconMap['N/A']} <strong>{item.to}</strong>
                </span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="events-timeline">
        <h3>Detected Events</h3>
        <div className="event-list">
          {results.timeline_events.map((event, i) => (
            <div
              key={i}
              className={`event-item ${event.severity}`}
              onClick={() => {
                roadVideoRef.current.currentTime = Math.max(0, event.timestamp - 5)
                faceVideoRef.current.currentTime = Math.max(0, event.timestamp - 5)
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
