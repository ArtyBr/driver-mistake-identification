import React, { useEffect, useRef, useState } from 'react';
import './VideoDisplay.css';
import { VIDEO_DIMENSIONS } from '../../../constants/videoConstants';

const VideoDisplay = ({
  roadUrl,
  faceUrl,
  roadVideoRef,
  faceVideoRef,
  canvasRef,
  faceCanvasRef,
  onTimeUpdate,
  onEnded,
  onLoadedMetadata,
  roadAspectRatio,
  faceAspectRatio,
  isBuffering,
  currentEvent
}) => {
  const roadWrapperRef = useRef(null);
  const [roadHeight, setRoadHeight] = useState(null);

  // Force video reload when src changes (important for local blobs)
  useEffect(() => {
    if (roadVideoRef.current) roadVideoRef.current.load();
  }, [roadUrl, roadVideoRef]);

  useEffect(() => {
    if (faceVideoRef.current) faceVideoRef.current.load();
  }, [faceUrl, faceVideoRef]);

  // Track road wrapper height so the face cam can match it exactly
  useEffect(() => {
    const el = roadWrapperRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const h = entries[0].contentRect.height;
      setRoadHeight(h > 0 ? h : null);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const containerClass = `video-container ${currentEvent ? `event-active ${currentEvent.severity.toLowerCase()}` : ''}`;

  // When road height is known, constrain face wrapper to the same height.
  // flex: '0 0 auto' + explicit width prevents flex from resizing it.
  const faceWrapperStyle = roadHeight
    ? { height: `${roadHeight}px`, width: `${roadHeight * faceAspectRatio}px`, flex: '0 0 auto', minWidth: 0 }
    : { aspectRatio: faceAspectRatio };

  // When face wrapper has an explicit height, fill it by height rather than width.
  const faceVideoStyle = roadHeight ? { height: '100%', width: 'auto' } : undefined;

  return (
    <div className={containerClass}>
      {isBuffering && (
        <div className="video-buffering-overlay">
          <div className="spinner"></div>
          <span>Loading video...</span>
        </div>
      )}
      <div ref={roadWrapperRef} className="video-wrapper road" style={{ aspectRatio: roadAspectRatio }}>
        <video
          ref={roadVideoRef}
          src={roadUrl}
          onTimeUpdate={onTimeUpdate}
          onLoadedMetadata={onLoadedMetadata}
          onEnded={onEnded}
          muted
        />
        <canvas
          ref={canvasRef}
          width={VIDEO_DIMENSIONS.ROAD.width}
          height={VIDEO_DIMENSIONS.ROAD.height}
          className="overlay-canvas"
        />
      </div>
      <div className="video-wrapper face" style={faceWrapperStyle}>
        <video
          ref={faceVideoRef}
          src={faceUrl}
          style={faceVideoStyle}
          muted
        />
        <canvas
          ref={faceCanvasRef}
          width={VIDEO_DIMENSIONS.FACE.width}
          height={VIDEO_DIMENSIONS.FACE.height}
          className="overlay-canvas"
        />
      </div>
    </div>
  );
};

export default VideoDisplay;
