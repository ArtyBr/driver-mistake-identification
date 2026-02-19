import { useState, useRef, useCallback } from 'react';

export const useVideoRecorder = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [stream, setStream] = useState(null);
  const [recordedBlob, setRecordedBlob] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  const startCamera = useCallback(async () => {
    try {
      const userStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: true
      });
      setStream(userStream);
      return userStream;
    } catch (err) {
      console.error("Error accessing camera:", err);
      throw err;
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
  }, [stream]);

  const startRecording = useCallback(() => {
    if (!stream) return;

    chunksRef.current = [];
    // Prefer mp4, fallback to webm
    const mimeTypes = [
      'video/mp4', 
      'video/webm;codecs=vp9', 
      'video/webm'
    ];
    
    let selectedType = mimeTypes.find(type => MediaRecorder.isTypeSupported(type));
    
    if (!selectedType) {
        console.warn("No supported mime type found, letting browser decide");
        selectedType = ''; // Let browser pick default
    }

    try {
        const recorder = new MediaRecorder(stream, { mimeType: selectedType });
        
        recorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
            chunksRef.current.push(event.data);
          }
        };

        recorder.onstop = () => {
          const blob = new Blob(chunksRef.current, { type: selectedType || 'video/webm' });
          setRecordedBlob(blob);
          setIsRecording(false);
        };

        recorder.start(1000); // Collect chunks every second
        mediaRecorderRef.current = recorder;
        setIsRecording(true);
    } catch (e) {
        console.error("MediaRecorder init failed", e);
    }
  }, [stream]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
  }, [isRecording]);

  return {
    stream,
    isRecording,
    recordedBlob,
    startCamera,
    stopCamera,
    startRecording,
    stopRecording,
    clearRecording: () => setRecordedBlob(null)
  };
};
