import React, { useRef, useEffect } from 'react';
import './LogViewer.css';

const LogViewer = ({
  history,
  events,
  activeLogIndex,
  hoveredEventIndex,
  setHoveredEventIndex,
  hoveredLogIndex,
  setHoveredLogIndex,
  hoveredFaceSegmentIndex,
  currentTime,
  onSeek,
  getColorForState,
  getLogIndexForSegment,
  faceSegments,
  iconMap
}) => {
  const itemRefs = useRef([]);
  const eventItemRefs = useRef([]);
  const logListRef = useRef(null);
  const eventListRef = useRef(null);

  const lastScrolledLogIndex = useRef(-1);
  const lastScrolledEventIndex = useRef(-1);

  // Helper to scroll container to item
  const scrollToItem = (container, item, block = 'center') => {
    if (!container || !item) return;
    
    const relativeTop = item.offsetTop;
    
    let targetScroll = 0;
    if (block === 'center') {
      targetScroll = relativeTop - (container.clientHeight / 2) + (item.clientHeight / 2);
    } else {
      // nearest logic
      const scrollTop = container.scrollTop;
      const scrollBottom = scrollTop + container.clientHeight;
      if (relativeTop < scrollTop) {
        targetScroll = relativeTop;
      } else if (relativeTop + item.clientHeight > scrollBottom) {
        targetScroll = relativeTop - container.clientHeight + item.clientHeight;
      } else {
        return; // Already in view
      }
    }

    // Only scroll if target is significantly different from current
    if (Math.abs(container.scrollTop - targetScroll) > 2) {
      container.scrollTo({
        top: targetScroll,
        behavior: 'smooth'
      });
    }
  };

  // Auto-scroll log list on playback
  useEffect(() => {
    if (activeLogIndex !== -1 && itemRefs.current[activeLogIndex] && 
        hoveredLogIndex === null && hoveredFaceSegmentIndex === null &&
        activeLogIndex !== lastScrolledLogIndex.current) {
      scrollToItem(logListRef.current, itemRefs.current[activeLogIndex], 'center');
      lastScrolledLogIndex.current = activeLogIndex;
    }
  }, [activeLogIndex, hoveredLogIndex, hoveredFaceSegmentIndex]);

  // Scroll to active log item when hovering face segment
  useEffect(() => {
    if (hoveredFaceSegmentIndex !== null) {
      const segment = faceSegments[hoveredFaceSegmentIndex]
      const logIndex = getLogIndexForSegment(segment)
      
      if (logIndex !== -1 && itemRefs.current[logIndex]) {
        scrollToItem(logListRef.current, itemRefs.current[logIndex], 'center');
        lastScrolledLogIndex.current = logIndex;
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

    if (activeEventIndex !== -1 && eventItemRefs.current[activeEventIndex] && 
        activeEventIndex !== lastScrolledEventIndex.current) {
      const block = hoveredEventIndex !== null ? 'nearest' : 'center';
      scrollToItem(eventListRef.current, eventItemRefs.current[activeEventIndex], block);
      lastScrolledEventIndex.current = activeEventIndex;
    }
  }, [hoveredEventIndex, currentTime, events]);

  return (
    <div className="logs-row">
      <div className="face-log">
        <h3>Face Direction Log (Transitions)</h3>
        <div className="log-list" ref={logListRef}>
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
        <div className="event-list" ref={eventListRef}>
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
