import React, { useRef, useEffect, useState } from 'react';
import Webcam from 'react-webcam';
import { Button, Alert, ProgressBar } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { faceAnalysisService } from '../../services/FaceAnalysisService';

const FaceRecorder = () => {
  const navigate = useNavigate();
  const webcamRef = useRef(null);
  const canvasRef = useRef(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [faces, setFaces] = useState([]);
  const [jobId, setJobId] = useState(null);
  
  // Face Selection
  const [confirmedFaceIndex, setConfirmedFaceIndex] = useState(null);
  
  // Recording
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const chunksRef = useRef([]); // Use ref for immediate access in onstop
  
  // Calibration
  const [calibrationData, setCalibrationData] = useState({});
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [currentStep, setCurrentStep] = useState(null);
  const [calibrationProgress, setCalibrationProgress] = useState(0); // 0 to 100
  const [stabilityCounter, setStabilityCounter] = useState(0);
  
  const [uploadStatus, setUploadStatus] = useState(null);
  const [currentGaze, setCurrentGaze] = useState('Wait...');

  const calibrationSteps = ['Ahead', 'Left Mirror', 'Right Mirror', 'Rear Mirror'];
  const HOLD_TIME_MS = 2500;
  const UPDATE_INTERVAL_MS = 100;
  const REQUIRED_STABILITY_COUNT = HOLD_TIME_MS / UPDATE_INTERVAL_MS;

  useEffect(() => {
    const load = async () => {
      try {
        await faceAnalysisService.loadModels();
        setIsLoaded(true);
        const res = await axios.post('/api/session/init');
        setJobId(res.data.job_id);
      } catch (err) {
        setError('Failed to initialize. ' + err);
      }
    };
    load();
  }, []);

  // Main Processing Loop
  useEffect(() => {
    if (!isLoaded) return;

    let isProcessing = false;
    const interval = setInterval(async () => {
      if (webcamRef.current && webcamRef.current.video.readyState === 4 && !isProcessing) {
        isProcessing = true;
        const result = await faceAnalysisService.analyze(webcamRef.current.video);
        if (result && result.faces.length > 0) {
          setFaces(result.faces);
          
          // Auto-select first face if only one exists and none confirmed
          if (confirmedFaceIndex === null && result.faces.length === 1) {
            setConfirmedFaceIndex(0);
          }

          const activeFace = result.faces[confirmedFaceIndex || 0];
          
          if (isCalibrating && confirmedFaceIndex !== null) {
            handleAutoCalibration(activeFace.pose);
          }

          // Real-time Gaze Prediction if calibrated
          if (Object.keys(calibrationData).length === calibrationSteps.length) {
            predictGaze(activeFace.pose);
          }

          drawOverlay(result.faces);
        }
        isProcessing = false;
      }
    }, UPDATE_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [isLoaded, isCalibrating, confirmedFaceIndex, currentStep, stabilityCounter, calibrationData]);

  const predictGaze = (pose) => {
    // Find nearest calibration point using Euclidean distance in Yaw/Pitch space
    let minDistance = Infinity;
    let prediction = 'Unknown';

    Object.entries(calibrationData).forEach(([label, calibPose]) => {
      const dYaw = pose.yaw - calibPose.yaw;
      const dPitch = pose.pitch - calibPose.pitch;
      const distance = Math.sqrt(dYaw * dYaw + dPitch * dPitch);
      
      if (distance < minDistance) {
        minDistance = distance;
        prediction = label;
      }
    });

    // If distance is too large, consider it "Away"
    if (minDistance > 30) {
      setCurrentGaze('Looking Away');
    } else {
      setCurrentGaze(prediction);
    }
  };

  const checkPoseMatch = (pose, step) => {
    // Thresholds for gaze zones
    switch (step) {
      case 'Ahead':
        return Math.abs(pose.yaw) < 15 && Math.abs(pose.pitch) < 15;
      case 'Left Mirror':
        return pose.yaw > 20; // Looking left (positive yaw in our heuristic)
      case 'Right Mirror':
        return pose.yaw < -20; // Looking right
      case 'Rear Mirror':
        return pose.pitch < -15; // Looking up/rear (pitch is inverted in view, check heuristic)
      default:
        return false;
    }
  };

  const handleAutoCalibration = (pose) => {
    const stepName = calibrationSteps[currentStep];
    const isMatching = checkPoseMatch(pose, stepName);

    if (isMatching) {
      const nextCount = stabilityCounter + 1;
      setStabilityCounter(nextCount);
      const progress = Math.min((nextCount / REQUIRED_STABILITY_COUNT) * 100, 100);
      setCalibrationProgress(progress);

      if (nextCount >= REQUIRED_STABILITY_COUNT) {
        // Target held for required time
        captureCalibration(pose);
      }
    } else {
      // Reset if user looks away
      setStabilityCounter(0);
      setCalibrationProgress(0);
    }
  };

  const captureCalibration = async (pose) => {
    const stepName = calibrationSteps[currentStep];
    const newCalib = {
      ...calibrationData,
      [stepName]: pose
    };
    setCalibrationData(newCalib);
    setStabilityCounter(0);
    setCalibrationProgress(0);
    
    if (currentStep < calibrationSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      // All steps done
      setIsCalibrating(false);
      setCurrentStep(null);
      setUploadStatus('Saving calibration...');
      try {
        await axios.post(`/api/session/${jobId}/calibration`, newCalib);
        setUploadStatus('Calibration saved automatically!');
      } catch (err) {
        setError('Failed to save calibration.');
      }
    }
  };

  const drawOverlay = (detectedFaces) => {
    const canvas = canvasRef.current;
    if (!canvas || !webcamRef.current) return;
    const ctx = canvas.getContext('2d');
    const video = webcamRef.current.video;
    
    if (canvas.width !== video.videoWidth) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    detectedFaces.forEach((face, index) => {
      const isConfirmed = confirmedFaceIndex === index;
      const [x1, y1, x2, y2] = face.bbox;
      
      // Draw Bounding Box
      ctx.strokeStyle = isConfirmed ? '#00ff00' : '#ffff00';
      ctx.lineWidth = isConfirmed ? 4 : 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Label
      ctx.fillStyle = isConfirmed ? '#00ff00' : '#ffff00';
      ctx.font = '16px Arial';
      ctx.fillText(isConfirmed ? 'DRIVER' : `Face ${index+1}`, x1, y1 > 20 ? y1 - 5 : y1 + 20);

      if (face.landmarks && face.landmarks.length >= 3) {
        const nose = face.landmarks[2];
        const length = 80;
        const yawRad = face.pose.yaw * Math.PI / 180;
        const pitchRad = face.pose.pitch * Math.PI / 180;
        
        const endX = nose.x + length * Math.sin(yawRad) * Math.cos(pitchRad);
        const endY = nose.y + length * Math.sin(pitchRad);

        ctx.beginPath();
        ctx.moveTo(nose.x, nose.y);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = isConfirmed ? '#ff0000' : '#cccccc';
        ctx.lineWidth = 3;
        ctx.stroke();
        
        ctx.fillStyle = isConfirmed ? '#ff0000' : '#cccccc';
        ctx.beginPath();
        ctx.arc(nose.x, nose.y, 4, 0, 2 * Math.PI);
        ctx.fill();
      }
    });
  };

  const startRecording = () => {
    chunksRef.current = [];
    const stream = webcamRef.current.stream;
    const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => handleUpload();
    recorder.start();
    setMediaRecorder(recorder);
    setIsRecording(true);
    
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    osc.frequency.setValueAtTime(440, audioCtx.currentTime);
    osc.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.3);
  };

  const stopRecording = () => {
    if (mediaRecorder) mediaRecorder.stop();
    setIsRecording(false);
  };

  const handleUpload = async () => {
    if (chunksRef.current.length === 0) return;
    setUploadStatus('Uploading face video...');
    const blob = new Blob(chunksRef.current, { type: 'video/webm' });
    const formData = new FormData();
    formData.append('video', blob, 'face.webm');

    try {
      await axios.post(`/api/session/${jobId}/upload_face`, formData);
      setUploadStatus('Upload complete! Redirecting...');
      setTimeout(() => {
        navigate(`/status/${jobId}`);
      }, 1500);
    } catch (err) {
      setError('Failed to upload video.');
      setUploadStatus(null);
    }
  };

  const startCalibration = () => {
    if (confirmedFaceIndex === null) {
      setError('Please confirm the driver face first.');
      return;
    }
    setIsCalibrating(true);
    setCurrentStep(0);
    setStabilityCounter(0);
    setCalibrationProgress(0);
  };

  return (
    <div className="face-recorder-container position-relative bg-dark p-3 rounded shadow">
      {error && <Alert variant="danger" onClose={() => setError(null)} dismissible>{error}</Alert>}
      {uploadStatus && <Alert variant="info">{uploadStatus}</Alert>}
      
      {!isLoaded && !error && (
        <div className="loading-overlay text-white text-center py-5">
          <ProgressBar animated now={100} label="Loading Neural Models..." />
          <p className="mt-2 text-muted">Initializing driver monitoring...</p>
        </div>
      )}

      <div className="webcam-wrapper position-relative rounded overflow-hidden mb-3 border border-secondary" style={{ width: '100%', aspectRatio: '4/3', display: isLoaded ? 'block' : 'none' }}>
        <Webcam
          audio={true}
          ref={webcamRef}
          className="w-100 h-100 object-fit-cover"
          mirrored={true}
          videoConstraints={{ facingMode: 'user' }}
        />
        <canvas
          ref={canvasRef}
          className="position-absolute top-0 start-0 w-100 h-100"
          style={{ pointerEvents: confirmedFaceIndex === null ? 'auto' : 'none', transform: 'scaleX(-1)' }}
          onClick={(e) => {
            if (confirmedFaceIndex !== null) return;
            // Basic hit detection for face selection
            const rect = canvasRef.current.getBoundingClientRect();
            const canvasWidth = canvasRef.current.width;
            const x = canvasWidth - ((e.clientX - rect.left) * (canvasWidth / rect.width));
            // Toggle selection if faces exist
            if (faces.length > 0) setConfirmedFaceIndex(0);
          }}
        />
        
        {isCalibrating && (
          <div className="position-absolute top-0 start-0 w-100 h-100 d-flex flex-column justify-content-center align-items-center" style={{ backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 10 }}>
            <h2 className="text-white mb-2 text-center px-3">Look at {calibrationSteps[currentStep]}</h2>
            <p className="text-light mb-4">Hold position for 2 seconds</p>
            <div style={{ width: '60%' }}>
              <ProgressBar now={calibrationProgress} variant="success" label={`${Math.round(calibrationProgress)}%`} />
            </div>
          </div>
        )}

        {confirmedFaceIndex === null && faces.length > 0 && (
          <div className="position-absolute bottom-0 start-0 w-100 bg-warning text-dark text-center py-2 fw-bold">
            TAP YOUR FACE TO CONFIRM DRIVER
          </div>
        )}
      </div>

      <div className="controls d-flex flex-column align-items-center gap-3">
        {Object.keys(calibrationData).length === calibrationSteps.length && (
          <div className="gaze-indicator w-100 text-center mb-2">
            <h4 className="text-white">
              Currently Looking: <span className="text-warning">{currentGaze.toUpperCase()}</span>
            </h4>
          </div>
        )}

        {confirmedFaceIndex !== null && faces[confirmedFaceIndex] && (
          <div className="pose-info text-white text-center">
            <span className="badge bg-success me-2">Driver Confirmed</span>
            <span className="badge bg-secondary me-2">Yaw: {faces[confirmedFaceIndex].pose.yaw.toFixed(1)}°</span>
            <span className="badge bg-secondary">Pitch: {faces[confirmedFaceIndex].pose.pitch.toFixed(1)}°</span>
            <Button variant="link" size="sm" className="text-warning ms-2" onClick={() => setConfirmedFaceIndex(null)}>Retake</Button>
          </div>
        )}

        <div className="button-group d-flex gap-2">
          {!isRecording ? (
            <Button variant="danger" size="lg" onClick={startRecording} disabled={isCalibrating || !jobId || !isLoaded || confirmedFaceIndex === null}>
              Record Drive
            </Button>
          ) : (
            <Button variant="warning" size="lg" onClick={stopRecording}>
              Stop Recording
            </Button>
          )}
          <Button variant="outline-info" onClick={startCalibration} disabled={isRecording || isCalibrating || !jobId || !isLoaded || confirmedFaceIndex === null}>
            Automated Calibration
          </Button>
        </div>

        {isRecording && <ProgressBar animated now={100} variant="danger" className="w-100 mt-2" label="LIVE RECORDING" />}
      </div>
    </div>
  );
};

export default FaceRecorder;
