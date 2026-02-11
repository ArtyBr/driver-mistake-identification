import { useRef, useState } from 'react'
import VideoDisplay from './video_player/VideoDisplay'
import Timeline from './video_player/Timeline'
import LogViewer from './video_player/LogViewer'
import Legend from './video_player/Legend'
import { useVideoPlayback } from '../../hooks/useVideoPlayback'
import { useVideoAnalysisData } from '../../hooks/useVideoAnalysisData'
import { useVideoCanvas } from '../../hooks/useVideoCanvas'

// Icon Components
const PlayIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="5 3 19 12 5 21 5 3"></polygon>
  </svg>
);

const PauseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="6" y="4" width="4" height="16"></rect>
    <rect x="14" y="4" width="4" height="16"></rect>
  </svg>
);

function VideoPlayer({ results, roadUrls, faceUrls }) {
  // DOM Refs
  const roadVideoRef = useRef(null)
  const faceVideoRef = useRef(null)
  const canvasRef = useRef(null)
  const faceCanvasRef = useRef(null)

  // Custom Hooks for logic separation
  const {
    isPlaying,
    isBuffering,
    currentTime,
    duration,
    currentPartIndex,
    activePartIndex,
    partDurations,
    roadAspectRatio,
    faceAspectRatio,
    handleSeek,
    togglePlay,
    onTimeUpdate,
    onPartEnded,
    bufferedRanges
  } = useVideoPlayback(roadUrls, faceUrls, roadVideoRef, faceVideoRef)

  const { history, faceSegments } = useVideoAnalysisData(results)

  const { currentFaceState } = useVideoCanvas(
    results,
    roadVideoRef,
    faceVideoRef,
    canvasRef,
    faceCanvasRef,
    activePartIndex,
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
    'Left Mirror': '[ < ]', 'Right Mirror': '[ > ]', 'Rear Mirror': '[ | ]', 'Looking Ahead': '[ ^ ]', 'N/A': '[ ? ]', 'Unknown': '[ ? ]'
  }

  const getColorForState = (state) => {
    if (state === 'Looking Ahead') return '#20c997'
    if (state === 'Left Mirror') return '#6f42c1'
    if (state === 'Right Mirror') return '#0ffc10'
    if (state === 'Rear Mirror') return '#ffc107'
    return '#ffc107'
  }

  // Find active safety event for visual feedback
  // Following timeline logic: event occurs 5s prior to the timestamp
  const currentEvent = results.timeline_events ? [...results.timeline_events].reverse().find(e => 
    currentTime >= Math.max(0, e.timestamp - 5) && currentTime <= e.timestamp
  ) : null;

  return (
    <div className="video-dashboard">
      <div className="event-banner-container">
        {currentEvent && (
          <div className={`event-banner ${currentEvent.severity.toLowerCase()}`}>
            <strong>{currentEvent.severity}:</strong> {currentEvent.message}
          </div>
        )}
      </div>

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
        isBuffering={isBuffering}
        currentEvent={currentEvent}
      />

      <div className="controls">
        <button onClick={togglePlay} className="play-button" aria-label={isPlaying ? "Pause" : "Play"}>
          {isPlaying ? <PauseIcon /> : <PlayIcon />}
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
          bufferedRanges={bufferedRanges}
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
