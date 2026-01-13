import React, { useMemo } from 'react';

const Timeline = ({
  currentTime,
  duration,
  events,
  faceSegments,
  history,
  hoveredEventIndex,
  setHoveredEventIndex,
  hoveredFaceSegmentIndex,
  setHoveredFaceSegmentIndex,
  hoveredLogIndex,
  onSeek,
  getColorForState
}) => {

  const eventBars = useMemo(() => {
    return duration > 0 && events.map((event, i) => {
      const startTime = Math.max(0, event.timestamp - 5)
      const endTime = event.timestamp
      const isHovered = i === hoveredEventIndex
      
      const leftPct = (startTime / duration) * 100
      const widthPct = ((endTime - startTime) / duration) * 100
      
      let color = '#ccc'
      if (event.severity === 'CRITICAL') color = '#dc3545' // Danger Red
      else if (event.severity === 'WARNING') color = '#ffc107' // Warning Amber
      else if (event.severity === 'INFO') color = '#20c997' // Subtle Green

      return (
        <div
          key={i}
          className={`timeline-event-bar ${isHovered ? 'hover-active' : ''}`}
          style={{
            left: `${leftPct}%`,
            width: `${widthPct}%`,
            backgroundColor: color,
            zIndex: isHovered ? 6 : 1
          }}
          onMouseEnter={() => setHoveredEventIndex(i)}
          onMouseLeave={() => setHoveredEventIndex(null)}
          onClick={() => onSeek(Math.max(0, event.timestamp - 5))}
          title={`${event.message} (${startTime.toFixed(1)}s - ${endTime.toFixed(1)}s)`}
        />
      )
    });
  }, [duration, events, hoveredEventIndex, setHoveredEventIndex, onSeek]);

  const faceBars = useMemo(() => {
    return duration > 0 && faceSegments.map((seg, i) => {
      const widthPct = ((seg.endTime - seg.startTime) / duration) * 100
      const leftPct = (seg.startTime / duration) * 100
      
      const isHovered = i === hoveredFaceSegmentIndex
      
      // Check if this segment corresponds to the hovered log item
      const isLogHovered = hoveredLogIndex !== null && (() => {
        const logItem = history[hoveredLogIndex]
        return logItem && logItem.to === seg.state && Math.abs(logItem.time - seg.startTime) < 1.0
      })()
      
      let color = getColorForState(seg.state)

      return (
        <div 
          key={i}
          className={`timeline-event-bar ${isHovered || isLogHovered ? 'hover-active' : ''}`}
          style={{
            left: `${leftPct}%`,
            width: `${widthPct}%`,
            backgroundColor: color,
            zIndex: (isHovered || isLogHovered) ? 6 : 1
          }}
          onMouseEnter={() => setHoveredFaceSegmentIndex(i)}
          onMouseLeave={() => setHoveredFaceSegmentIndex(null)}
          onClick={() => onSeek(seg.startTime)}
          title={`${seg.state} (${seg.startTime.toFixed(1)}s - ${seg.endTime.toFixed(1)}s)`}
        />
      )
    });
  }, [duration, faceSegments, hoveredFaceSegmentIndex, hoveredLogIndex, history, setHoveredFaceSegmentIndex, onSeek, getColorForState]);

  return (
    <div className="timeline-wrapper">
      <div className="timeline-events-track">
        {eventBars}
        
        {/* Vertical Cursor on Event Track */}
        <div 
          className="timeline-cursor"
          style={{
            left: `${(currentTime / duration) * 100}%`
          }}
        />
      </div>

      <div className="timeline-face-track">
        {faceBars}
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
        onChange={(e) => onSeek(parseFloat(e.target.value))}
        className="timeline-slider"
      />
      
      <span className="track-label events-label">Events</span>
      <span className="track-label gaze-label">Gaze</span>
    </div>
  );
};

export default Timeline;
