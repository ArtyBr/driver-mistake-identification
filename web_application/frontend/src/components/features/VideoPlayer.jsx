import { useRef, useState, useEffect, useMemo } from 'react'
import VideoDisplay from './video_player/VideoDisplay'
import Timeline from './video_player/Timeline'
import LogViewer from './video_player/LogViewer'
import Legend from './video_player/Legend'
import ReportErrorForm from './ReportErrorForm'
import { useVideoPlayback } from '../../hooks/useVideoPlayback'
import { useVideoAnalysisData } from '../../hooks/useVideoAnalysisData'
import { useVideoCanvas } from '../../hooks/useVideoCanvas'
import { getColorForState } from '../../constants/videoConstants'
import { detectNetworkQuality } from '../../utils/networkQuality'

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

const PrevIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="19 20 9 12 19 4 19 20"></polygon>
    <line x1="5" y1="19" x2="5" y2="5"></line>
  </svg>
);

const NextIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="5 4 15 12 5 20 5 4"></polygon>
    <line x1="19" y1="5" x2="19" y2="19"></line>
  </svg>
);

function VideoPlayer({ results, roadUrls, faceUrls, jobId, roadQualityUrls = null, faceQualityUrls = null }) {
  // DOM Refs
  const roadVideoRef = useRef(null)
  const faceVideoRef = useRef(null)
  const canvasRef = useRef(null)
  const faceCanvasRef = useRef(null)

  // Report Form state
  const [showReportForm, setShowReportForm] = useState(false)

  // Quality selection state
  const [quality, setQuality] = useState('auto')
  const qualitySeekRef = useRef(null)
  // Stores the original (1080p) face video dimensions so the canvas overlay
  // scales nose_2d coordinates correctly even when a lower-quality variant is playing.
  const originalFaceDimsRef = useRef(null)

  // Available quality labels (ordered high → low)
  const availableQualities = useMemo(() => (
    roadQualityUrls
      ? ['1080p', '720p', '480p'].filter(q => roadQualityUrls[q])
      : []
  ), [roadQualityUrls])

  // Detect network quality from available options (derived, not stored in state)
  const detectedQuality = useMemo(() => (
    availableQualities.length ? detectNetworkQuality(availableQualities) : '1080p'
  ), [availableQualities])

  // Probe the original (1080p) face video once to get its native dimensions.
  // These are used by useVideoCanvas to scale nose_2d coordinates correctly
  // regardless of which quality variant is currently playing.
  useEffect(() => {
    const url = faceQualityUrls?.['1080p']?.[0]
    if (!url || originalFaceDimsRef.current) return
    const probe = document.createElement('video')
    probe.src = url
    probe.onloadedmetadata = () => {
      originalFaceDimsRef.current = { w: probe.videoWidth, h: probe.videoHeight }
      probe.src = ''
    }
    probe.load()
  }, [faceQualityUrls])

  const effectiveQuality = quality === 'auto' ? detectedQuality : quality

  const activeRoadUrls = useMemo(() => (
    roadQualityUrls?.[effectiveQuality] ?? roadUrls
  ), [roadQualityUrls, effectiveQuality, roadUrls])

  const activeFaceUrls = useMemo(() => (
    faceQualityUrls?.[effectiveQuality] ?? faceUrls
  ), [faceQualityUrls, effectiveQuality, faceUrls])

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
  } = useVideoPlayback(activeRoadUrls, activeFaceUrls, roadVideoRef, faceVideoRef)

  // After a quality switch, restore playback position
  useEffect(() => {
    if (qualitySeekRef.current !== null && duration > 0 && partDurations.length > 0) {
      handleSeek(qualitySeekRef.current)
      qualitySeekRef.current = null
    }
  }, [partDurations, duration, handleSeek])

  const handleQualityChange = (q) => {
    qualitySeekRef.current = currentTime
    setQuality(q)
  }

  const { history, faceSegments } = useVideoAnalysisData(results)

  const { currentFaceState } = useVideoCanvas(
    results,
    roadVideoRef,
    faceVideoRef,
    canvasRef,
    faceCanvasRef,
    activePartIndex,
    partDurations,
    originalFaceDimsRef
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

  // Find active safety event for visual feedback
  // Following timeline logic: event occurs 5s prior to the timestamp
  const currentEvent = results.timeline_events ? [...results.timeline_events].reverse().find(e => 
    currentTime >= Math.max(0, e.timestamp - 5) && currentTime <= e.timestamp
  ) : null;

  const jumpToEvent = (direction) => {
    if (!results.timeline_events || results.timeline_events.length === 0) return;
    
    const sortedEvents = [...results.timeline_events].sort((a, b) => a.timestamp - b.timestamp);
    
    if (direction === 'next') {
      // Find the first event whose WINDOW START is ahead of current time
      const next = sortedEvents.find(e => (e.timestamp - 5) > currentTime + 0.5);
      if (next) handleSeek(Math.max(0, next.timestamp - 5));
    } else {
      // Find the first event whose WINDOW START is behind current time
      // If we are currently in an event, this will jump to the start of the current event first
      const prev = [...sortedEvents].reverse().find(e => (e.timestamp - 5) < currentTime - 0.5);
      if (prev) handleSeek(Math.max(0, prev.timestamp - 5));
    }
  };

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
        roadUrl={activeRoadUrls ? activeRoadUrls[currentPartIndex] : ""}
        faceUrl={activeFaceUrls ? activeFaceUrls[currentPartIndex] : ""}
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

      <div className="controls d-flex align-items-center" style={{ gap: '20px' }}>
        <div className="d-flex flex-column gap-2" style={{ flexShrink: 0 }}>
          <div className="d-flex align-items-center gap-2">
            <button onClick={togglePlay} className="play-button" aria-label={isPlaying ? "Pause" : "Play"}>
              {isPlaying ? <PauseIcon /> : <PlayIcon />}
            </button>

            <div className="jump-controls d-flex gap-1">
              <button
                onClick={() => jumpToEvent('prev')}
                className="btn btn-cyber btn-sm"
                title="Previous Event"
                disabled={!results.timeline_events?.length}
              >
                <PrevIcon />
              </button>
              <button
                onClick={() => jumpToEvent('next')}
                className="btn btn-cyber btn-sm"
                title="Next Event"
                disabled={!results.timeline_events?.length}
              >
                <NextIcon />
              </button>
            </div>
          </div>
          <button 
            className="btn btn-outline-warning btn-sm d-flex align-items-center justify-content-center gap-2 shadow-sm w-100"
            style={{ fontSize: '0.75rem', padding: '4px 0' }}
            onClick={() => {
              if (!showReportForm && isPlaying) togglePlay();
              setShowReportForm(prev => !prev);
            }}
            title="Report an error in detection or classification"
          >
            <i className="bi bi-flag-fill"></i> <span className="d-none d-md-inline">{showReportForm ? 'Hide Report Form' : 'Report Model/Detection Error'}</span>
          </button>
        </div>

        <div className="d-flex align-items-center flex-grow-1 gap-3 h-100">
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
          <span className="time-display" style={{ flexShrink: 0 }}>{currentTime.toFixed(2)} / {duration.toFixed(2)}s</span>
        </div>
      </div>

      {showReportForm && (
        <ReportErrorForm
          jobId={jobId}
          currentTime={currentTime}
          onClose={() => setShowReportForm(false)}
          onSuccess={() => {
            setShowReportForm(false);
            alert("Report submitted successfully. Thank you!");
          }}
        />
      )}

      {availableQualities.length >= 1 && (
        <div className="d-flex align-items-center gap-2 px-3 py-2" style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderLeft: '3px solid var(--border-color)', borderRadius: '4px', marginTop: '6px' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>Quality</span>
          {['auto', ...availableQualities].map(q => (
            <button
              key={q}
              className={`btn btn-sm ${quality === q ? 'btn-cyber' : 'btn-outline-secondary'}`}
              onClick={() => handleQualityChange(q)}
              title={q === 'auto' ? 'Auto-select based on network speed' : q}
              style={{ fontSize: '0.75rem', padding: '2px 10px' }}
            >
              {q === 'auto' ? `Auto (${detectedQuality})` : q}
            </button>
          ))}
        </div>
      )}

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
        getLogIndexForSegment={getLogIndexForSegment}
        faceSegments={faceSegments}
      />
    </div>
  )
}

export default VideoPlayer
