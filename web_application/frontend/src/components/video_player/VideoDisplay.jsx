import React from 'react';

const VideoDisplay = ({ 
  roadUrl, 
  faceUrl, 
  roadVideoRef, 
  faceVideoRef, 
  canvasRef, 
  faceCanvasRef,
  onTimeUpdate,
  onLoadedMetadata
}) => {
  return (
    <div className="video-container">
      <div className="video-wrapper road">
        <video
          ref={roadVideoRef}
          src={roadUrl}
          onTimeUpdate={onTimeUpdate}
          onLoadedMetadata={onLoadedMetadata}
          muted
        />
        <canvas
          ref={canvasRef}
          width={1280}
          height={720}
          className="overlay-canvas"
        />
      </div>
      <div className="video-wrapper face">
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
