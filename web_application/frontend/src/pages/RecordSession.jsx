import React, { useEffect, useRef, useState } from 'react';
import { useVideoRecorder } from '../hooks/useVideoRecorder';
import { createSession, uploadSessionVideo, saveCalibration } from '../services/api';
import { saveVideo, deleteVideo } from '../services/storage';
import { useNavigate } from 'react-router-dom';
import FaceOverlay from '../components/features/FaceOverlay';

export default function RecordSession() {
  const videoRef = useRef(null);
  const { 
    stream, 
    startCamera, 
    stopCamera, 
    startRecording, 
    stopRecording, 
    recordedBlob,
    clearRecording
  } = useVideoRecorder();
  
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [status, setStatus] = useState('idle'); // idle, calibrating, recording, review, uploading, done
  
  // Calibration State
  const [calibStep, setCalibStep] = useState(0);
  const [calibData, setCalibData] = useState({});
  const calibSteps = ['center', 'left_mirror', 'right_mirror', 'rear_mirror'];
  const [calibMessage, setCalibMessage] = useState("");
  
  const navigate = useNavigate();

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, [startCamera, stopCamera]);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  const handleFaceDetected = () => {
      // data contains matrix and landmarks
      // For real calibration, we would check if yaw/pitch matches target
      // For now, we just let the user manually confirm
  };

  // Calibration Logic
  const startCalibration = () => {
      setStatus('calibrating');
      setCalibStep(0);
      setCalibData({});
      setCalibMessage(`Please look at the ${calibSteps[0].replace('_', ' ')}`);
  };

  const nextCalibStep = () => {
      const currentLabel = calibSteps[calibStep];
      const timestamp = Date.now(); // We would record range if we were recording video during this
      
      setCalibData(prev => ({
          ...prev,
          [currentLabel]: { timestamp }
      }));

      if (calibStep < calibSteps.length - 1) {
          const next = calibStep + 1;
          setCalibStep(next);
          setCalibMessage(`Great! Now look at the ${calibSteps[next].replace('_', ' ')}`);
      } else {
          setStatus('idle');
          setCalibMessage("Calibration Complete! You can now start recording.");
          // Ideally we save this locally or send it with the session later
      }
  };

  const handleStart = () => {
    if (Object.keys(calibData).length === 0) {
        if (!confirm("You haven't calibrated yet. Continue anyway?")) return;
    }
    startRecording();
    setStatus('recording');
  };

  const handleStop = () => {
    stopRecording();
    setStatus('review');
  };

  const handleDiscard = () => {
    clearRecording();
    setStatus('idle');
  };

  const handleUpload = async () => {
    if (!recordedBlob) return;
    
    try {
      setIsUploading(true);
      setStatus('uploading');
      
      // 1. Create Session
      const session = await createSession();
      console.log("Created session:", session.id);
      
      // 2. Upload Calibration if exists
      if (Object.keys(calibData).length > 0) {
          await saveCalibration(session.id, calibData);
      }
      
      // 3. Save locally just in case (optional, good for resilience)
      await saveVideo(session.id, recordedBlob);
      
      // 4. Upload Video
      await uploadSessionVideo(session.id, 'phone', recordedBlob, (percent) => {
        setUploadProgress(percent);
      });
      
      // 5. Cleanup local
      await deleteVideo(session.id);
      
      setStatus('done');
      alert(`Session ${session.id} created! You can now upload the dashcam footage.`);
      navigate('/');
      
    } catch (e) {
      console.error(e);
      alert("Upload failed. Video is saved locally.");
      setStatus('review');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="container mt-4">
      <h2>Record Session</h2>
      
      {calibMessage && <div className="alert alert-info">{calibMessage}</div>}

      <div className="position-relative bg-black rounded overflow-hidden" style={{ aspectRatio: '16/9', maxHeight: '60vh', transform: 'scaleX(-1)' }}>
        {status === 'review' && recordedBlob ? (
          <video 
            src={URL.createObjectURL(recordedBlob)} 
            controls 
            className="w-100 h-100 object-fit-contain" 
            style={{ transform: 'scaleX(1)' }} 
          />
        ) : (
          <>
            <video 
                ref={videoRef} 
                autoPlay 
                muted 
                playsInline 
                className="w-100 h-100 object-fit-cover" 
            />
            <FaceOverlay 
                videoRef={videoRef} 
                isEnabled={status === 'idle' || status === 'recording' || status === 'calibrating'} 
                onFaceDetected={handleFaceDetected}
            />
          </>
        )}
      </div>

      <div className="mt-3 d-flex justify-content-center gap-3" style={{ transform: 'none' }}>
        
        {status === 'idle' && (
          <>
            <button className="btn btn-info btn-lg" onClick={startCalibration}>
                Calibrate
            </button>
            <button className="btn btn-danger btn-lg rounded-circle p-4" onClick={handleStart}>
                Start Rec
            </button>
          </>
        )}

        {status === 'calibrating' && (
            <button className="btn btn-success btn-lg" onClick={nextCalibStep}>
                Capture & Next
            </button>
        )}
        
        {status === 'recording' && (
          <button className="btn btn-secondary btn-lg" onClick={handleStop}>
            Stop Recording
          </button>
        )}
        
        {status === 'review' && (
          <>
            <button className="btn btn-outline-danger" onClick={handleDiscard} disabled={isUploading}>
              Discard
            </button>
            <button className="btn btn-primary" onClick={handleUpload} disabled={isUploading}>
              {isUploading ? `Uploading ${uploadProgress}%` : 'Save & Upload'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
