import React, { useEffect, useRef, useState } from 'react';
import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

export default function FaceOverlay({ videoRef, isEnabled = true, onFaceDetected }) {
  const canvasRef = useRef(null);
  const landmarkerRef = useRef(null);
  const requestRef = useRef(null);
  const [modelLoaded, setModelLoaded] = useState(false);

  // Initialize Landmarker
  useEffect(() => {
    const initLandmarker = async () => {
      try {
        const filesetResolver = await FilesetResolver.forVisionTasks(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm"
        );
        
        landmarkerRef.current = await FaceLandmarker.createFromOptions(filesetResolver, {
          baseOptions: {
            modelAssetPath: `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`,
            delegate: "GPU"
          },
          outputFaceBlendshapes: false,
          outputFacialTransformationMatrixes: true,
          runningMode: "VIDEO",
          numFaces: 1
        });
        
        setModelLoaded(true);
      } catch (e) {
        console.error("Failed to load FaceLandmarker", e);
      }
    };
    
    initLandmarker();
    
    return () => {
      if (landmarkerRef.current) {
        landmarkerRef.current.close();
      }
    };
  }, []);

  // Detection Loop
  useEffect(() => {
    if (!isEnabled || !modelLoaded || !videoRef.current) return;

    let lastVideoTime = -1;

    const renderLoop = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      
      if (video && video.readyState >= 2 && canvas && landmarkerRef.current) {
        // Resize canvas to match video
        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
        }

        const ctx = canvas.getContext('2d');
        const startTimeMs = performance.now();
        
        if (video.currentTime !== lastVideoTime) {
          lastVideoTime = video.currentTime;
          const result = landmarkerRef.current.detectForVideo(video, startTimeMs);
          
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          
          // Draw logic
          if (result.faceLandmarks && result.faceLandmarks.length > 0) {
             drawFace(ctx, result, canvas.width, canvas.height);
             
             // Notify parent
             if (onFaceDetected && result.facialTransformationMatrixes && result.facialTransformationMatrixes.length > 0) {
                 const matrix = result.facialTransformationMatrixes[0];
                 onFaceDetected({
                     matrix: matrix,
                     landmarks: result.faceLandmarks[0]
                 });
             }
          }
        }
      }
      requestRef.current = requestAnimationFrame(renderLoop);
    };

    const drawFace = (ctx, result, width, height) => {
        const landmarks = result.faceLandmarks[0];
        const matrix = result.facialTransformationMatrixes ? result.facialTransformationMatrixes[0] : null;

        // Draw Bounding Box (Approximate from landmarks)
        // Landmarks are normalized [0,1]
        let minX = 1, minY = 1, maxX = 0, maxY = 0;
        landmarks.forEach(pt => {
            if (pt.x < minX) minX = pt.x;
            if (pt.x > maxX) maxX = pt.x;
            if (pt.y < minY) minY = pt.y;
            if (pt.y > maxY) maxY = pt.y;
        });
        
        const x = minX * width;
        const y = minY * height;
        const w = (maxX - minX) * width;
        const h = (maxY - minY) * height;

        ctx.strokeStyle = '#00FF00';
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
        
        // Draw Nose Vector if Matrix exists
        if (matrix) {
            // Nose tip is index 1
            const nose = landmarks[1];
            const noseX = nose.x * width;
            const noseY = nose.y * height;
            
            // Calculate Rotation from Matrix
            const m = matrix; 
            const sy = Math.sqrt(m[0] * m[0] + m[4] * m[4]);
            
            let pitch, yaw;
            if (sy > 1e-6) {
                pitch = Math.atan2(m[9], m[10]);
                yaw = Math.atan2(-m[8], sy);
            } else {
                pitch = Math.atan2(-m[6], m[5]);
                yaw = Math.atan2(-m[8], sy);
            }
            
            // Draw Vector
            const len = 100;
            const endX = noseX + len * Math.sin(yaw);
            const endY = noseY - len * Math.sin(pitch); // Minus because Y is down
            
            ctx.beginPath();
            ctx.moveTo(noseX, noseY);
            ctx.lineTo(endX, endY);
            ctx.strokeStyle = '#FF0000';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // Draw Text
            ctx.save();
            ctx.fillStyle = "white";
            ctx.font = "16px Arial";
            ctx.fillText(`Y: ${(yaw * 180 / Math.PI).toFixed(1)}`, x, y - 10);
            ctx.restore();
        }
    };

    renderLoop();

    return () => cancelAnimationFrame(requestRef.current);
  }, [isEnabled, modelLoaded, videoRef, onFaceDetected]);

  return (

    <canvas 
      ref={canvasRef} 
      className="position-absolute top-0 start-0 w-100 h-100"
      style={{ pointerEvents: 'none' }}
    />
  );
}
