import { useRef, useEffect, useState, useMemo } from 'react'

function VideoPlayer({ results, roadUrl, faceUrl }) {
  const roadVideoRef = useRef(null)
  const faceVideoRef = useRef(null)
  const canvasRef = useRef(null)
  const faceCanvasRef = useRef(null)
  const itemRefs = useRef([])
  const eventItemRefs = useRef([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [currentFaceState, setCurrentFaceState] = useState("N/A")
  const [activeLogIndex, setActiveLogIndex] = useState(-1)
  const [hoveredEventIndex, setHoveredEventIndex] = useState(null)
  const [hoveredFaceSegmentIndex, setHoveredFaceSegmentIndex] = useState(null)
  const [hoveredLogIndex, setHoveredLogIndex] = useState(null)

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
          if (lastState === null) {
             // Record initial state
             hist.push({
               from: "Start",
               to: state,
               time: frame.time
             })
             lastState = state
          } else if (state !== lastState) {
            lastState = state
          }
        }
      })
    }
    return hist
  }, [results])

  // Memoize face segments for timeline
  const faceSegments = useMemo(() => {
    const segments = []
    let currentSegment = null

    if (results && results.frame_data) {
      results.frame_data.forEach(frame => {
        const state = frame.current_state
        if (state && state !== "N/A" && state !== "Unknown") {
          if (!currentSegment) {
            currentSegment = { state, startTime: frame.time, endTime: frame.time }
          } else if (currentSegment.state !== state) {
            // Close current segment
            segments.push(currentSegment)
            // Start new one
            currentSegment = { state, startTime: frame.time, endTime: frame.time }
          } else {
            // Extend current
            currentSegment.endTime = frame.time
          }
        } else if (currentSegment) {
            // End segment on N/A or Unknown (gap)
            segments.push(currentSegment)
            currentSegment = null
        }
      })
      if (currentSegment) {
        segments.push(currentSegment)
      }
    }
    return segments
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
    const time = roadVideoRef.current.currentTime
    setCurrentTime(time)
    if (time >= duration) {
      setIsPlaying(false)
    }
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

  // Scroll to active event item (for hover or playback)
  useEffect(() => {
    // Find the currently active event index (either hovered or by time)
    const activeEventIndex = results.timeline_events.findIndex((event, i) => {
       const isTimeActive = currentTime >= (event.timestamp - 5) && currentTime <= event.timestamp
       const isHovered = i === hoveredEventIndex
       return isTimeActive || isHovered
    })

    if (activeEventIndex !== -1 && eventItemRefs.current[activeEventIndex]) {
      // Only scroll if it's the hovered one (user interaction) or maybe just always?
      // If we scroll on playback it might be annoying if user is scrolling manually.
      // Let's scroll primarily if it's hovered (user intention to see it).
      if (hoveredEventIndex !== null) {
          eventItemRefs.current[activeEventIndex].scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
          })
      }
    }
  }, [hoveredEventIndex, currentTime, results])

  // Scroll to active log item when hovering face segment
  useEffect(() => {
    if (hoveredFaceSegmentIndex !== null) {
      // Find the log item that corresponds to this face segment
      const segment = faceSegments[hoveredFaceSegmentIndex]
      if (segment) {
        // Find the history item where the transition TO matches the segment state
        // and the time is at or just before the segment start
        const logIndex = history.findIndex(item => 
          item.to === segment.state && Math.abs(item.time - segment.startTime) < 1.0
        )
        
        if (logIndex !== -1 && itemRefs.current[logIndex]) {
          itemRefs.current[logIndex].scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
          })
        }
      }
    }
  }, [hoveredFaceSegmentIndex, faceSegments, history])

  // Draw loop
  useEffect(() => {
    let animationFrameId
    let videoCallbackId
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
          frame.lane_lines.forEach(coeffs => {
            const [a, b, c] = coeffs
            
            ctx.beginPath()
            // Generate points from y=720 to 1080 (bottom third of 1080p)
            const startY = 720
            const endY = 1080
            const numSteps = 30
            const step = (endY - startY) / numSteps

            for (let i = 0; i <= numSteps; i++) {
              const y_1080 = startY + i * step
              const x_1920 = a * (y_1080 * y_1080) + b * y_1080 + c
              
              // Scale to canvas
              const x = (x_1920 / 1920) * canvasRef.current.width
              const y = (y_1080 / 1080) * canvasRef.current.height
              
              if (i === 0) ctx.moveTo(x, y)
              else ctx.lineTo(x, y)
            }
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

      if (roadVideoRef.current && roadVideoRef.current.requestVideoFrameCallback) {
        videoCallbackId = roadVideoRef.current.requestVideoFrameCallback(draw)
      } else {
        animationFrameId = requestAnimationFrame(draw)
      }
    }

    if (roadVideoRef.current && roadVideoRef.current.requestVideoFrameCallback) {
      videoCallbackId = roadVideoRef.current.requestVideoFrameCallback(draw)
    } else {
      draw()
    }
    
    return () => {
      if (videoCallbackId && roadVideoRef.current && roadVideoRef.current.cancelVideoFrameCallback) {
        roadVideoRef.current.cancelVideoFrameCallback(videoCallbackId)
      }
      cancelAnimationFrame(animationFrameId)
    }
  }, [results])

  const iconMap = {
    'Left Mirror': '[ < ]',
    'Right Mirror': '[ > ]',
    'Looking Ahead': '[ ^ ]',
    'N/A': '[ ? ]',
    'Unknown': '[ ? ]'
  }

  const getColorForState = (state) => {
    if (state === 'Looking Ahead') return '#2ecc71'
    if (state === 'Left Mirror') return '#e84393'
    if (state === 'Right Mirror') return '#00cec9'
    if (state === 'N/A' || state === 'Unknown') return '#aaa'
    return '#9b59b6' // Other
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
        <button onClick={togglePlay} className="play-button">
          {isPlaying ? "⏸️" : "▶️"}
        </button>
        
        <div className="timeline-wrapper">
          <div className="timeline-events-track">
            {duration > 0 && results.timeline_events.map((event, i) => {
              const startTime = Math.max(0, event.timestamp - 5)
              const endTime = event.timestamp
              const isTimeActive = currentTime >= startTime && currentTime <= endTime
              const isHovered = i === hoveredEventIndex
              
              const leftPct = (startTime / duration) * 100
              const widthPct = ((endTime - startTime) / duration) * 100
              
              let color = '#ccc'
              if (event.severity === 'CRITICAL') color = '#ff4d4d' // Red
              else if (event.severity === 'WARNING') color = '#ffa500' // Orange
              else if (event.severity === 'INFO') color = '#4caf50' // Green

              return (
                <div
                  key={i}
                  className={`timeline-event-bar ${isTimeActive ? 'playback-active' : ''} ${isHovered ? 'hover-active' : ''}`}
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    backgroundColor: color,
                    zIndex: isHovered ? 6 : (isTimeActive ? 5 : 1)
                  }}
                  onMouseEnter={() => setHoveredEventIndex(i)}
                  onMouseLeave={() => setHoveredEventIndex(null)}
                  onClick={() => {
                    const seekTime = Math.max(0, event.timestamp - 5)
                    roadVideoRef.current.currentTime = seekTime
                    faceVideoRef.current.currentTime = seekTime
                    setCurrentTime(seekTime)
                  }}
                  title={`${event.message} (${startTime.toFixed(1)}s - ${endTime.toFixed(1)}s)`}
                />
              )
            })}
            
            {/* Vertical Cursor on Event Track */}
            <div 
              className="timeline-cursor"
              style={{
                left: `${(currentTime / duration) * 100}%`
              }}
            />
          </div>

          <div className="timeline-face-track">
            {duration > 0 && faceSegments.map((seg, i) => {
              const widthPct = ((seg.endTime - seg.startTime) / duration) * 100
              const leftPct = (seg.startTime / duration) * 100
              
              const isTimeActive = currentTime >= seg.startTime && currentTime <= seg.endTime
              const isHovered = i === hoveredFaceSegmentIndex
              
              // Check if this segment corresponds to the hovered log item
              const isLogHovered = hoveredLogIndex !== null && (() => {
                const logItem = history[hoveredLogIndex]
                return logItem && logItem.to === seg.state && Math.abs(logItem.time - seg.startTime) < 1.0
              })()
              
              let color = '#9b59b6' // Purple for other states
              if (seg.state === 'Looking Ahead') color = '#2ecc71' // Green
              else if (seg.state === 'Left Mirror') color = '#e84393' // Pink
              else if (seg.state === 'Right Mirror') color = '#00cec9' // Teal/Cyan
              else if (seg.state === 'N/A') color = '#555'

              return (
                <div 
                  key={i}
                  className={`timeline-event-bar ${isTimeActive ? 'playback-active' : ''} ${isHovered || isLogHovered ? 'hover-active' : ''}`}
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    backgroundColor: color,
                    zIndex: (isHovered || isLogHovered) ? 6 : (isTimeActive ? 5 : 1)
                  }}
                  onMouseEnter={() => setHoveredFaceSegmentIndex(i)}
                  onMouseLeave={() => setHoveredFaceSegmentIndex(null)}
                  onClick={() => {
                     roadVideoRef.current.currentTime = seg.startTime
                     faceVideoRef.current.currentTime = seg.startTime
                     setCurrentTime(seg.startTime)
                  }}
                  title={`${seg.state} (${seg.startTime.toFixed(1)}s - ${seg.endTime.toFixed(1)}s)`}
                />
              )
            })}
             {/* Vertical Cursor on Face Track */}
             <div 
              className="timeline-cursor"
              style={{
                left: `${(currentTime / duration) * 100}%`
              }}
            />
          </div>

          <input
            type="range"
            min="0"
            max={duration}
            step="0.01"
            value={currentTime}
            onChange={handleSeek}
            className="timeline-slider"
          />
          
          <span className="track-label events-label">Events</span>
          <span className="track-label gaze-label">Gaze</span>
        </div>

        <span className="time-display">{currentTime.toFixed(2)} / {duration.toFixed(2)}s</span>
      </div>

      <div className="timeline-legend">
        <div className="legend-row">
          <span className="legend-title">Events:</span>
          {[
            { label: 'Critical', color: '#ff4d4d' },
            { label: 'Warning', color: '#ffa500' },
            { label: 'Info', color: '#4caf50' }
          ].map((item, i) => (
            <div key={i} className="legend-item">
              <span className="legend-swatch" style={{ backgroundColor: item.color }}></span>
              <span className="legend-label">{item.label}</span>
            </div>
          ))}
        </div>
        <div className="legend-row">
          <span className="legend-title">Gaze:</span>
          {[
            { label: 'Looking Ahead', color: '#2ecc71' },
            { label: 'Left Mirror', color: '#e84393' },
            { label: 'Right Mirror', color: '#00cec9' },
            { label: 'Other', color: '#9b59b6' },
            { label: 'N/A', color: '#555' }
          ].map((item, i) => (
            <div key={i} className="legend-item">
              <span className="legend-swatch" style={{ backgroundColor: item.color }}></span>
              <span className="legend-label">{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="logs-row">
        <div className="face-log">
          <hr />
          <h4>
            Current Face Direction: <span style={{ color: getColorForState(currentFaceState) }}>
              {iconMap[currentFaceState] || iconMap['N/A']} {currentFaceState || "N/A"}
            </span>
          </h4>
          <hr />
          <h3>Face Direction Log (Transitions)</h3>
          <div className="log-list">
            {history.map((item, i) => {
              const isCurrent = i === activeLogIndex
              const isHovered = i === hoveredLogIndex
              
              // Check if this log corresponds to the hovered face segment
              const isSegmentHovered = hoveredFaceSegmentIndex !== null && (() => {
                const segment = faceSegments[hoveredFaceSegmentIndex]
                return segment && item.to === segment.state && Math.abs(item.time - segment.startTime) < 1.0
              })()
              
              return (
                <div
                  key={i}
                  ref={el => itemRefs.current[i] = el}
                  className={`log-item ${isCurrent ? 'active' : ''} ${isHovered || isSegmentHovered ? 'hover-active' : ''}`}
                  onClick={() => {
                    roadVideoRef.current.currentTime = Math.max(0, item.time - 0.5)
                    faceVideoRef.current.currentTime = Math.max(0, item.time - 0.5)
                  }}
                  onMouseEnter={() => setHoveredLogIndex(i)}
                  onMouseLeave={() => setHoveredLogIndex(null)}
                >
                  <span className="log-time">{item.time.toFixed(1)}s</span>
                  <span className="log-state-container">
                    <span className="log-state-from">
                      {iconMap[item.from] || iconMap['N/A']} <strong style={{ color: getColorForState(item.from) }}>{item.from}</strong>
                    </span>
                    <span className="log-arrow">→</span>
                    <span className="log-state-to">
                      {iconMap[item.to] || iconMap['N/A']} <strong style={{ color: getColorForState(item.to) }}>{item.to}</strong>
                    </span>
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        <div className="events-timeline">
          <h3>Detected Events</h3>
          <div className="event-list">
            {results.timeline_events.map((event, i) => {
              const isTimeActive = currentTime >= (event.timestamp - 5) && currentTime <= event.timestamp
              const isHovered = i === hoveredEventIndex
              
              return (
                <div
                  key={i}
                  ref={el => eventItemRefs.current[i] = el}
                  className={`event-item ${event.severity} ${isTimeActive ? 'playback-active' : ''} ${isHovered ? 'hover-active' : ''}`}
                  onClick={() => {
                    roadVideoRef.current.currentTime = Math.max(0, event.timestamp - 5)
                    faceVideoRef.current.currentTime = Math.max(0, event.timestamp - 5)
                  }}
                  onMouseEnter={() => setHoveredEventIndex(i)}
                  onMouseLeave={() => setHoveredEventIndex(null)}
                >
                  <span className="event-time">{event.timestamp.toFixed(1)}s</span>
                  <span className="event-message">{event.message}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

export default VideoPlayer
