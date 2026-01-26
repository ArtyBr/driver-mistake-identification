import { useRef, useState } from 'react'
import VideoDisplay from './video_player/VideoDisplay'
import Timeline from './video_player/Timeline'
import LogViewer from './video_player/LogViewer'
import Legend from './video_player/Legend'
import { useVideoPlayback } from '../../hooks/useVideoPlayback'
import { useVideoAnalysisData } from '../../hooks/useVideoAnalysisData'
import { useVideoCanvas } from '../../hooks/useVideoCanvas'

function VideoPlayer({ results, roadUrls, faceUrls }) {
  // DOM Refs
  const roadVideoRef = useRef(null)
  const faceVideoRef = useRef(null)
  const canvasRef = useRef(null)
  const faceCanvasRef = useRef(null)

  // Custom Hooks for logic separation
  const {
    isPlaying,
    currentTime,
    duration,
    currentPartIndex,
    partDurations,
    roadAspectRatio,
    faceAspectRatio,
    handleSeek,
    togglePlay,
    onTimeUpdate,
    onPartEnded
  } = useVideoPlayback(roadUrls, faceUrls, roadVideoRef, faceVideoRef)

  const { history, faceSegments } = useVideoAnalysisData(results)

  const { currentFaceState } = useVideoCanvas(
    results,
    roadVideoRef,
    faceVideoRef,
    canvasRef,
    faceCanvasRef,
    currentPartIndex,
    partDurations
  )

  // Derive active log index from current time during render
  const activeLogIndex = history.findIndex((item, i) => {
    const next = history[i + 1]
    return item.time <= currentTime && (!next || next.time > currentTime)
  })

  // Local UI State
  const [hoveredEventIndex, setHoveredEventIndex] = useState(null)
  const [hoveredFaceSegmentIndex, setHoveredFaceSegmentIndex] = useState(null)
  const [hoveredLogIndex, setHoveredLogIndex] = useState(null)

  const getLogIndexForSegment = (segment) => {
    if (!segment) return -1
    let bestIndex = -1
    for (let i = 0; i < history.length; i++) {
      const item = history[i]
      if (item.time <= segment.startTime + 0.1) { 
         if (item.to === segment.state) bestIndex = i
      } else {
        break
      }
    }
    return bestIndex
  }

  const iconMap = {
    'Left Mirror': '[ < ]', 'Right Mirror': '[ > ]', 'Looking Ahead': '[ ^ ]', 'N/A': '[ ? ]', 'Unknown': '[ ? ]'
  }

  const getColorForState = (state) => {
    if (state === 'Looking Ahead') return '#20c997'
    if (state === 'Left Mirror') return '#6f42c1'
    if (state === 'Right Mirror') return '#00d2df'
    if (state === 'N/A' || state === 'Unknown') return '#6c757d'
    return '#ffc107'
  }

  return (
    <div className="video-dashboard">
      <VideoDisplay 
        roadUrl={roadUrls ? roadUrls[currentPartIndex] : ""}
        faceUrl={faceUrls ? faceUrls[currentPartIndex] : ""}
        roadVideoRef={roadVideoRef}
        faceVideoRef={faceVideoRef}
        canvasRef={canvasRef}
        faceCanvasRef={faceCanvasRef}
        onTimeUpdate={onTimeUpdate}
        onEnded={onPartEnded}
        onLoadedMetadata={() => {}} // Handled by hook
        roadAspectRatio={roadAspectRatio}
        faceAspectRatio={faceAspectRatio}
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
