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
  const containerRef = useRef(null);
  const [contentWidth, setContentWidth] = useState(null);

  // Observe the container's content width (not any child) — no feedback loop possible
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      setContentWidth(entries[0].contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Force video reload when src changes (important for local blobs)
  useEffect(() => {
    if (roadVideoRef.current) roadVideoRef.current.load();
  }, [roadUrl, roadVideoRef]);

  useEffect(() => {
    if (faceVideoRef.current) faceVideoRef.current.load();
  }, [faceUrl, faceVideoRef]);

  // Compute a shared height so both videos are the same height and fill the container.
  // H = (containerContentWidth - gap) / (roadAR + faceAR)
  // On mobile (< 768px content width) fall back to CSS stacking layout,
  // UNLESS the face video is portrait — then keep side-by-side since the
  // narrow portrait video fits beside the road video without being too small.
  const GAP = 15; // matches CSS gap
  const isMobile = contentWidth !== null && contentWidth < 768;
  const faceIsPortrait = faceAspectRatio && faceAspectRatio < 1;
  const useSideBySide = contentWidth && roadAspectRatio && faceAspectRatio
    && (!isMobile || faceIsPortrait);
  const videoHeight = useSideBySide
    ? (contentWidth - GAP) / (roadAspectRatio + faceAspectRatio)
    : null;

  const roadWrapperStyle = videoHeight
    ? { height: `${videoHeight}px`, width: `${videoHeight * roadAspectRatio}px`, flex: '0 0 auto', minWidth: 0 }
    : {};
  const faceWrapperStyle = videoHeight
    ? { height: `${videoHeight}px`, width: `${videoHeight * faceAspectRatio}px`, flex: '0 0 auto', minWidth: 0 }
    : {};

  const sideBySideClass = isMobile && faceIsPortrait ? 'side-by-side' : '';
  const containerClass = `video-container ${sideBySideClass} ${currentEvent ? `event-active ${currentEvent.severity.toLowerCase()}` : ''}`;

  return (
    <div ref={containerRef} className={containerClass}>
      {isBuffering && (
        <div className="video-buffering-overlay">
          <div className="spinner"></div>
          <span>Loading video...</span>
        </div>
      )}
      <div className="video-wrapper road" style={roadWrapperStyle}>
        <video
          ref={roadVideoRef}
          src={roadUrl}
          onTimeUpdate={onTimeUpdate}
          onLoadedMetadata={onLoadedMetadata}
          onEnded={onEnded}
          muted
          playsInline
          webkit-playsinline="true"
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
          muted
          playsInline
          webkit-playsinline="true"
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
