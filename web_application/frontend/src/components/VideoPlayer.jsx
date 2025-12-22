import { useRef, useEffect, useState, useMemo } from 'react'
import VideoDisplay from './video_player/VideoDisplay'
import Timeline from './video_player/Timeline'
import LogViewer from './video_player/LogViewer'
import Legend from './video_player/Legend'

function VideoPlayer({ results, roadUrl, faceUrl }) {
  const roadVideoRef = useRef(null)
  const faceVideoRef = useRef(null)
  const canvasRef = useRef(null)
  const faceCanvasRef = useRef(null)
  // itemRefs and eventItemRefs are now inside LogViewer, so we don't need them here directly for scrolling, 
  // but wait - LogViewer needs to know which item to scroll to. 
  // Actually, LogViewer manages its own refs and receives the active index. 
  // So we can remove itemRefs and eventItemRefs from here.

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

  const handleSeek = (time) => {
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

  // Helper to find the specific log index for a given segment
  const getLogIndexForSegment = (segment) => {
    if (!segment) return -1
    let bestIndex = -1
    for (let i = 0; i < history.length; i++) {
      const item = history[i]
      if (item.time <= segment.startTime + 0.1) { 
         if (item.to === segment.state) {
           bestIndex = i
         }
      } else {
        break
      }
    }
    return bestIndex
  }

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
        ctx.strokeStyle = '#20c997' // Subtle Green
        ctx.lineWidth = 3
        if (frame.lane_lines) {
          frame.lane_lines.forEach(coeffs => {
            const [a, b, c] = coeffs
            
            ctx.beginPath()
            const startY = 720
            const endY = 1080
            const numSteps = 30
            const step = (endY - startY) / numSteps

            for (let i = 0; i <= numSteps; i++) {
              const y_1080 = startY + i * step
              const x_1920 = a * (y_1080 * y_1080) + b * y_1080 + c
              
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

          if (typeof nose_2d === 'string') {
            const match = nose_2d.match(/\((-?\d+),\s*(-?\d+)\)/);
            if (match) {
              nose_2d = [parseInt(match[1]), parseInt(match[2])];
            } else {
              console.warn("Failed to parse nose_2d:", nose_2d);
            }
          }

          if (Array.isArray(nose_2d) || (nose_2d.length === 2)) {
            const vW = faceVideo.videoWidth || 640
            const vH = faceVideo.videoHeight || 480

            const scaleX = faceCanvasRef.current.width / vW
            const scaleY = faceCanvasRef.current.height / vH

            const startX = nose_2d[0] * scaleX
            const startY = nose_2d[1] * scaleY

            const endX = (nose_2d[0] + yaw * 10) * scaleX
            const endY = (nose_2d[1] - pitch * 10) * scaleY

            faceCtx.strokeStyle = '#00d2df' // Subtle Cyan
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
    if (state === 'Looking Ahead') return '#20c997' // Subtle Green
    if (state === 'Left Mirror') return '#6f42c1' // Subtle Purple
    if (state === 'Right Mirror') return '#00d2df' // Subtle Cyan
    if (state === 'N/A' || state === 'Unknown') return '#6c757d'
    return '#ffc107' // Warning Amber (Other)
  }

  return (
    <div className="video-dashboard">
      <VideoDisplay 
        roadUrl={roadUrl}
        faceUrl={faceUrl}
        roadVideoRef={roadVideoRef}
        faceVideoRef={faceVideoRef}
        canvasRef={canvasRef}
        faceCanvasRef={faceCanvasRef}
        onTimeUpdate={onTimeUpdate}
        onLoadedMetadata={onLoadedMetadata}
      />

      <div className="controls">
        <button onClick={togglePlay} className="play-button">
          {isPlaying ? "⏸️" : "▶️"}
        </button>
        
        <Timeline 
          currentTime={currentTime}
          duration={duration}
          events={results.timeline_events}
          faceSegments={faceSegments}
          history={history}
          hoveredEventIndex={hoveredEventIndex}
          setHoveredEventIndex={setHoveredEventIndex}
          hoveredFaceSegmentIndex={hoveredFaceSegmentIndex}
          setHoveredFaceSegmentIndex={setHoveredFaceSegmentIndex}
          hoveredLogIndex={hoveredLogIndex}
          onSeek={handleSeek}
          getColorForState={getColorForState}
          getLogIndexForSegment={getLogIndexForSegment}
        />

        <span className="time-display">{currentTime.toFixed(2)} / {duration.toFixed(2)}s</span>
      </div>

      <Legend />

      <LogViewer 
        history={history}
        events={results.timeline_events}
        activeLogIndex={activeLogIndex}
        hoveredEventIndex={hoveredEventIndex}
        setHoveredEventIndex={setHoveredEventIndex}
        hoveredLogIndex={hoveredLogIndex}
        setHoveredLogIndex={setHoveredLogIndex}
        hoveredFaceSegmentIndex={hoveredFaceSegmentIndex}
        currentFaceState={currentFaceState}
        currentTime={currentTime}
        onSeek={handleSeek}
        getColorForState={getColorForState}
        getLogIndexForSegment={getLogIndexForSegment}
        faceSegments={faceSegments}
        iconMap={iconMap}
      />
    </div>
  )
}

export default VideoPlayer