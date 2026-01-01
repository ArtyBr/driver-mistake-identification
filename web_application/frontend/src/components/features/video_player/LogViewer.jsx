import React, { useRef, useEffect } from 'react';

const LogViewer = ({
  history,
  events,
  activeLogIndex,
  hoveredEventIndex,
  setHoveredEventIndex,
  hoveredLogIndex,
  setHoveredLogIndex,
  hoveredFaceSegmentIndex,
  currentFaceState,
  currentTime,
  onSeek,
  getColorForState,
  getLogIndexForSegment,
  faceSegments,
  iconMap
}) => {
  const itemRefs = useRef([]);
  const eventItemRefs = useRef([]);

  // Auto-scroll log list on playback
  useEffect(() => {
    if (activeLogIndex !== -1 && itemRefs.current[activeLogIndex] && hoveredLogIndex === null && hoveredFaceSegmentIndex === null) {
      itemRefs.current[activeLogIndex].scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      })
    }
  }, [activeLogIndex, hoveredLogIndex, hoveredFaceSegmentIndex]);

  // Scroll to active log item when hovering face segment
  useEffect(() => {
    if (hoveredFaceSegmentIndex !== null) {
      const segment = faceSegments[hoveredFaceSegmentIndex]
      const logIndex = getLogIndexForSegment(segment)
      
      if (logIndex !== -1 && itemRefs.current[logIndex]) {
        itemRefs.current[logIndex].scrollIntoView({
          behavior: 'smooth',
          block: 'center'
        })
      }
    }
  }, [hoveredFaceSegmentIndex, faceSegments, history, getLogIndexForSegment]);

  // Scroll to active event item (for hover or playback)
  useEffect(() => {
    const activeEventIndex = events.findIndex((event, i) => {
       const isTimeActive = currentTime >= (event.timestamp - 5) && currentTime <= event.timestamp
       const isHovered = i === hoveredEventIndex
       return isTimeActive || isHovered
    })

    if (activeEventIndex !== -1 && eventItemRefs.current[activeEventIndex]) {
      if (hoveredEventIndex !== null) {
          eventItemRefs.current[activeEventIndex].scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
          })
      }
    }
  }, [hoveredEventIndex, currentTime, events]);

  return (
    <div className="logs-row">
      <div className="face-log">
        <h3>Face Direction Log (Transitions)</h3>
        <div className="log-list">
          {history.map((item, i) => {
            const isCurrent = i === activeLogIndex
            const isHovered = i === hoveredLogIndex
            
            // Check if this log corresponds to the hovered face segment
            const isSegmentHovered = hoveredFaceSegmentIndex !== null && 
                                   getLogIndexForSegment(faceSegments[hoveredFaceSegmentIndex]) === i
            
            return (
              <div
                key={i}
                ref={el => itemRefs.current[i] = el}
                className={`log-item ${isCurrent ? 'active' : ''} ${isHovered || isSegmentHovered ? 'hover-active' : ''}`}
                onClick={() => onSeek(Math.max(0, item.time - 0.5))}
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
          {events.map((event, i) => {
            const isTimeActive = currentTime >= (event.timestamp - 5) && currentTime <= event.timestamp
            const isHovered = i === hoveredEventIndex
            
            return (
              <div
                key={i}
                ref={el => eventItemRefs.current[i] = el}
                className={`event-item ${event.severity} ${isTimeActive ? 'playback-active' : ''} ${isHovered ? 'hover-active' : ''}`}
                onClick={() => onSeek(Math.max(0, event.timestamp - 5))}
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
  );
};

export default LogViewer;
