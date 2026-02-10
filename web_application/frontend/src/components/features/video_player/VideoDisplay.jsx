import React, { useEffect } from 'react';
import './VideoDisplay.css';

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
}) => {  // Force video reload when src changes (important for local blobs)
  useEffect(() => {
    if (roadVideoRef.current) roadVideoRef.current.load();
  }, [roadUrl, roadVideoRef]);

  useEffect(() => {
    if (faceVideoRef.current) faceVideoRef.current.load();
  }, [faceUrl, faceVideoRef]);

  const containerClass = `video-container ${currentEvent ? `event-active ${currentEvent.severity.toLowerCase()}` : ''}`;

  return (
    <div className={containerClass}>
      {isBuffering && (
        <div className="video-buffering-overlay">
          <div className="spinner"></div>
          <span>Loading video...</span>
        </div>
      )}
      <div className="video-wrapper road" style={{ aspectRatio: roadAspectRatio }}>
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
          width={1280}
          height={720}
          className="overlay-canvas"
        />
      </div>
      <div className="video-wrapper face" style={{ aspectRatio: faceAspectRatio }}>
        <video
          ref={faceVideoRef}
          src={faceUrl}
          muted
        />
        <canvas
          ref={faceCanvasRef}
          width={640}
          height={480}
          className="overlay-canvas"
        />
      </div>
    </div>
  );
};

export default VideoDisplay;
