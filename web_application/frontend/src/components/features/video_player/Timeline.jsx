import React from 'react';
import './Timeline.css';

const Timeline = ({
  currentTime,
  duration,
  onSeek,
  events,
  faceSegments,
  history,
  hoveredEventIndex,
  setHoveredEventIndex,
  hoveredFaceSegmentIndex,
  setHoveredFaceSegmentIndex,
  hoveredLogIndex,
  getColorForState,
  bufferedRanges = []
}) => {
  return (
    <div className="timeline-wrapper">
      <input
        type="range"
        min="0"
        max={duration}
        step="0.01"
        value={currentTime}
        onChange={(e) => onSeek(parseFloat(e.target.value))}
        className="timeline-slider"
      />

      <div className="timeline-events-track">
        {/* Buffered Ranges Layer */}
        {duration > 0 && bufferedRanges.map((range, i) => {
           const startPct = (range.start / duration) * 100;
           const widthPct = ((range.end - range.start) / duration) * 100;
           return (
             <div 
               key={`buf-${i}`}
               style={{
                 position: 'absolute',
                 left: `${startPct}%`,
                 width: `${widthPct}%`,
                 height: '100%',
                 backgroundColor: 'rgba(255, 255, 255, 0.2)',
                 zIndex: 0
               }}
             />
           );
        })}

        {duration > 0 && events && events.map((event, i) => {
          const startTime = Math.max(0, event.timestamp - 5)
          const endTime = event.timestamp
          const isTimeActive = currentTime >= startTime && currentTime <= endTime
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
              className={`timeline-event-bar ${isTimeActive ? 'playback-active' : ''} ${isHovered ? 'hover-active' : ''}`}
              style={{
                left: `${leftPct}%`,
                width: `${widthPct}%`,
                backgroundColor: color,
                zIndex: isHovered ? 6 : (isTimeActive ? 5 : 1)
              }}
              onMouseEnter={() => setHoveredEventIndex(i)}
              onMouseLeave={() => setHoveredEventIndex(null)}
              onClick={() => onSeek(Math.max(0, event.timestamp - 5))}
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

        {/* Custom Handle (Synced with Cursor) */}
        <div 
          className="timeline-handle"
          style={{
            left: `${(currentTime / duration) * 100}%`
          }}
        />
      </div>

      <div className="timeline-face-track">
        {duration > 0 && faceSegments && faceSegments.map((seg, i) => {
          const widthPct = ((seg.endTime - seg.startTime) / duration) * 100
          const leftPct = (seg.startTime / duration) * 100
          
          const isTimeActive = currentTime >= seg.startTime && currentTime <= seg.endTime
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
              className={`timeline-event-bar ${isTimeActive ? 'playback-active' : ''} ${isHovered || isLogHovered ? 'hover-active' : ''}`}
              style={{
                left: `${leftPct}%`,
                width: `${widthPct}%`,
                backgroundColor: color,
                zIndex: (isHovered || isLogHovered) ? 6 : (isTimeActive ? 5 : 1)
              }}
              onMouseEnter={() => setHoveredFaceSegmentIndex(i)}
              onMouseLeave={() => setHoveredFaceSegmentIndex(null)}
              onClick={() => onSeek(seg.startTime)}
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

      <span className="track-label events-label">Events</span>
      <span className="track-label gaze-label">Gaze</span>
    </div>
  );
};

export default Timeline;
