import { useEffect, useRef, useState } from 'react';

export function useVideoCanvas(
  results, 
  roadVideoRef, 
  faceVideoRef, 
  canvasRef, 
  faceCanvasRef, 
  currentPartIndex, 
  partDurations
) {
  const [currentFaceState, setCurrentFaceState] = useState("N/A");

  useEffect(() => {
    let animationFrameId;
    let videoCallbackId;
    let lastRenderedState = null;

    const draw = () => {
      const ctx = canvasRef.current?.getContext('2d');
      const faceCtx = faceCanvasRef.current?.getContext('2d');
      const roadVideo = roadVideoRef.current;
      const faceVideo = faceVideoRef.current;

      if (!roadVideo || !faceVideo) return;

      // Only draw if ready
      if (ctx && faceCtx && roadVideo.readyState >= 2) {
        ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
        faceCtx.clearRect(0, 0, faceCanvasRef.current.width, faceCanvasRef.current.height);

        // Calculate global time
        const vidTime = roadVideo.currentTime;
        let offset = 0;
        for (let i = 0; i < currentPartIndex; i++) {
            offset += partDurations[i] || 0;
        }
        const time = offset + vidTime;

        // Find current frame data
        const frame = results.frame_data.find((f, i) => {
          const next = results.frame_data[i + 1];
          return time >= f.time && (!next || time < next.time);
        });

        if (frame) {
          if (frame.current_state && frame.current_state !== lastRenderedState) {
            setCurrentFaceState(frame.current_state);
            lastRenderedState = frame.current_state;
          } else if (!frame.current_state && lastRenderedState !== "N/A") {
            setCurrentFaceState("N/A");
            lastRenderedState = "N/A";
          }

          // Draw Lane Lines
          ctx.strokeStyle = '#20c997';
          ctx.lineWidth = 3;
          if (frame.lane_lines) {
            frame.lane_lines.forEach(coeffs => {
              const [a, b, c] = coeffs;
              ctx.beginPath();
              const startY = 720; const endY = 1080; const numSteps = 30;
              const step = (endY - startY) / numSteps;
              for (let i = 0; i <= numSteps; i++) {
                const y_1080 = startY + i * step;
                const x_1920 = a * (y_1080 * y_1080) + b * y_1080 + c;
                const x = (x_1920 / 1920) * canvasRef.current.width;
                const y = (y_1080 / 1080) * canvasRef.current.height;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
              }
              ctx.stroke();
            });
          }

          // Draw Face/Head Pose
          if (frame.face_info && frame.face_info.nose_2d && frame.face_info.yaw !== undefined) {
            let { nose_2d, yaw, pitch } = frame.face_info;
            if (typeof nose_2d === 'string') {
              const match = nose_2d.match(/\((-?\d+),\s*(-?\d+)\)/);
              if (match) nose_2d = [parseInt(match[1]), parseInt(match[2])];
            }

            if (Array.isArray(nose_2d) || (nose_2d.length === 2)) {
              const vW = faceVideo.videoWidth || 640;
              const vH = faceVideo.videoHeight || 480;
              const scaleX = faceCanvasRef.current.width / vW;
              const scaleY = faceCanvasRef.current.height / vH;
              const startX = nose_2d[0] * scaleX;
              const startY = nose_2d[1] * scaleY;
              const endX = (nose_2d[0] + yaw * 10) * scaleX;
              const endY = (nose_2d[1] - pitch * 10) * scaleY;

              faceCtx.strokeStyle = '#00d2df';
              faceCtx.lineWidth = 3;
              faceCtx.beginPath();
              faceCtx.moveTo(startX, startY);
              faceCtx.lineTo(endX, endY);
              faceCtx.stroke();
            }
          }
        }
      }

      // Always re-schedule next frame to prevent loop death
      if (roadVideoRef.current && roadVideoRef.current.requestVideoFrameCallback) {
        videoCallbackId = roadVideoRef.current.requestVideoFrameCallback(draw);
      } else {
        animationFrameId = requestAnimationFrame(draw);
      }
    };

    // Kick off the loop
    if (roadVideoRef.current && roadVideoRef.current.requestVideoFrameCallback) {
      videoCallbackId = roadVideoRef.current.requestVideoFrameCallback(draw);
    } else {
      draw();
    }
    
    return () => {
      if (videoCallbackId && roadVideoRef.current && roadVideoRef.current.cancelVideoFrameCallback) {
        roadVideoRef.current.cancelVideoFrameCallback(videoCallbackId);
      }
      cancelAnimationFrame(animationFrameId);
    }
  }, [results, currentPartIndex, partDurations, roadVideoRef, faceVideoRef, canvasRef, faceCanvasRef]);

  return { currentFaceState };
}
