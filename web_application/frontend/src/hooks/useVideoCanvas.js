import { useEffect, useState } from 'react';
import { GAZE_STATES, getColorForState } from '../constants/videoConstants';

export function useVideoCanvas(
  results,
  roadVideoRef,
  faceVideoRef,
  canvasRef,
  faceCanvasRef,
  activePartIndex,
  partDurations,
  originalFaceDimsRef
) {
  const [currentFaceState, setCurrentFaceState] = useState("N/A");

  useEffect(() => {
    let animationFrameId;
    let videoCallbackId;
    let lastRenderedState = null;
    let lastIndex = 0;

    const draw = (now, metadata) => {
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
        const vidTime = (metadata && metadata.mediaTime !== undefined) ? metadata.mediaTime : roadVideo.currentTime;
        let offset = 0;
        for (let i = 0; i < activePartIndex; i++) {
            offset += partDurations[i] || 0;
        }
        const time = offset + vidTime;

        // Search for current frame data
        let frame = null;
        let foundLinear = false;

        // Optimization: Linear check from lastIndex for forward playback
        if (lastIndex < results.frame_data.length) {
          // Check current cached index
          const curr = results.frame_data[lastIndex];
          const next = results.frame_data[lastIndex + 1];

          if (curr && time >= curr.time && (!next || time < next.time)) {
            frame = curr;
            foundLinear = true;
          } 
          // Check next few frames (forward playback)
          else if (next && time >= next.time) {
             let steps = 0;
             for (let i = lastIndex + 1; i < results.frame_data.length; i++) {
                 const f = results.frame_data[i];
                 const n = results.frame_data[i+1];
                 if (time >= f.time && (!n || time < n.time)) {
                     frame = f;
                     lastIndex = i;
                     foundLinear = true;
                     break;
                 }
                 steps++;
                 if (steps > 10) break; // Fallback to binary search if not found quickly
             }
          }
        }

        if (!foundLinear) {
          // Binary search (fallback for seek or first render)
          let low = 0;
          let high = results.frame_data.length - 1;
          
          while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            const f = results.frame_data[mid];
            const next = results.frame_data[mid + 1];
            
            if (time >= f.time && (!next || time < next.time)) {
              frame = f;
              lastIndex = mid;
              break;
            } else if (time < f.time) {
              high = mid - 1;
            } else {
              low = mid + 1;
            }
          }
        }

        if (frame) {
          const noseLineColor = getColorForState(frame.current_state);

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
              // Use original (1080p) face video dimensions so the overlay stays
              // aligned when a lower-quality variant is playing.
              const vW = originalFaceDimsRef?.current?.w ?? faceVideo.videoWidth ?? 640;
              const vH = originalFaceDimsRef?.current?.h ?? faceVideo.videoHeight ?? 480;
              const scaleX = faceCanvasRef.current.width / vW;
              const scaleY = faceCanvasRef.current.height / vH;
              const startX = nose_2d[0] * scaleX;
              const startY = nose_2d[1] * scaleY;
              const endX = (nose_2d[0] + yaw * 10) * scaleX;
              const endY = (nose_2d[1] - pitch * 10) * scaleY;

              faceCtx.strokeStyle = noseLineColor;
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
    
    const currentRoadVideo = roadVideoRef.current;
    return () => {
      if (videoCallbackId && currentRoadVideo && currentRoadVideo.cancelVideoFrameCallback) {
        currentRoadVideo.cancelVideoFrameCallback(videoCallbackId);
      }
      cancelAnimationFrame(animationFrameId);
    }
  }, [results, activePartIndex, partDurations, roadVideoRef, faceVideoRef, canvasRef, faceCanvasRef, originalFaceDimsRef]);

  return { currentFaceState };
}
