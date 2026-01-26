import { useState, useEffect, useLayoutEffect } from 'react';

export function useVideoPlayback(roadUrls, faceUrls, roadVideoRef, faceVideoRef) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [roadAspectRatio, setRoadAspectRatio] = useState(16/9);
  const [faceAspectRatio, setFaceAspectRatio] = useState(4/3);
  
  // Multi-part support
  const [partDurations, setPartDurations] = useState([]);
  const [currentPartIndex, setCurrentPartIndex] = useState(0);
  const [pendingSeek, setPendingSeek] = useState(null);

  // Load durations and dimensions for all parts
  useLayoutEffect(() => {
    if (!roadUrls || roadUrls.length === 0) return;

    const loadMetadata = async () => {
      // Use a hidden container to ensure browser loads the video
      const container = document.createElement('div');
      container.style.display = 'none';
      document.body.appendChild(container);

      // Load road durations and the first part's aspect ratio
      const roadDurs = await Promise.all(roadUrls.map((url, i) => {
        return new Promise((resolve) => {
          const v = document.createElement('video');
          v.preload = 'metadata';
          v.onloadedmetadata = () => {
              if (i === 0 && v.videoHeight > 0) {
                  setRoadAspectRatio(v.videoWidth / v.videoHeight);
              }
              resolve(v.duration);
          };
          v.onerror = () => {
              console.warn("Failed to load metadata for road", url);
              resolve(0);
          };
          v.src = url;
          container.appendChild(v);
        })
      }));

      // Load face first part aspect ratio (assuming faceUrls corresponds to roadUrls)
      if (faceUrls && faceUrls.length > 0) {
          const v = document.createElement('video');
          v.preload = 'metadata';
          v.onloadedmetadata = () => {
              if (v.videoHeight > 0) {
                  setFaceAspectRatio(v.videoWidth / v.videoHeight);
              }
          };
          v.src = faceUrls[0];
          container.appendChild(v);
      }
      
      document.body.removeChild(container);
      setPartDurations(roadDurs);
      const total = roadDurs.reduce((a, b) => a + b, 0);
      setDuration(total > 0 ? total : 0);
    };
    
    loadMetadata();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCurrentPartIndex(0);
    setCurrentTime(0);
  }, [roadUrls, faceUrls]);

  // Helper to convert local time of current part to global time
  const getGlobalTime = (localTime) => {
    let offset = 0;
    for (let i = 0; i < currentPartIndex; i++) {
        offset += partDurations[i] || 0;
    }
    return offset + localTime;
  };

  // Handle Seeking
  const handleSeek = (globalTime) => {
    let offset = 0;
    let targetIndex = -1;
    let localTime = globalTime;
    
    for (let i = 0; i < partDurations.length; i++) {
        const dur = partDurations[i];
        if (globalTime < offset + dur) {
            targetIndex = i;
            localTime = globalTime - offset;
            break;
        }
        offset += dur;
    }
    
    // Clamp to end if not found in loop (e.g. globalTime >= total duration)
    if (targetIndex === -1) {
         if (partDurations.length > 0) {
             targetIndex = partDurations.length - 1;
             localTime = partDurations[targetIndex]; 
             if (localTime > 0.1) localTime -= 0.1;
         } else {
             targetIndex = 0;
             localTime = 0;
         }
    }
    
    if (targetIndex !== currentPartIndex) {
        setPendingSeek(localTime);
        setCurrentPartIndex(targetIndex);
    } else {
        if (roadVideoRef.current) roadVideoRef.current.currentTime = localTime;
        if (faceVideoRef.current) faceVideoRef.current.currentTime = localTime;
        setCurrentTime(globalTime);
    }
  };

  // Handle Play/Pause
  const togglePlay = () => {
    const roadVid = roadVideoRef.current;
    const faceVid = faceVideoRef.current;
    
    if (!roadVid || !faceVid) return;

    // Check if we are at the end of the last part
    const isLastPart = currentPartIndex === (roadUrls.length - 1);
    const isEnded = roadVid.ended || (roadVid.duration > 0 && Math.abs(roadVid.currentTime - roadVid.duration) < 0.1);

    if (isLastPart && isEnded) {
      setCurrentPartIndex(0);
      setPendingSeek(0);
      setIsPlaying(true);
      return;
    }

    if (roadVid.paused) {
      roadVid.play();
      faceVid.play();
      setIsPlaying(true);
    } else {
      roadVid.pause();
      faceVid.pause();
      setIsPlaying(false);
    }
  };

  // Handle Part Switching and Pending Seeks
  useEffect(() => {
      const roadVid = roadVideoRef.current;
      const faceVid = faceVideoRef.current;
      if (!roadVid || !faceVid) return;

      const performSeek = () => {
           if (pendingSeek !== null) {
              roadVid.currentTime = pendingSeek;
              faceVid.currentTime = pendingSeek;
              setPendingSeek(null);
          }
          if (isPlaying) {
              roadVid.play().catch(e => console.log("Play interrupted", e));
              faceVid.play().catch(e => console.log("Play interrupted", e));
          }
      }

      // Check if metadata is already loaded
      if (roadVid.readyState >= 1) {
          performSeek();
      } else {
          // If not, wait for it
          roadVid.addEventListener('loadedmetadata', performSeek, { once: true });
      }
      
      return () => {
          roadVid.removeEventListener('loadedmetadata', performSeek);
      }
  }, [currentPartIndex, roadUrls, isPlaying, pendingSeek, roadVideoRef, faceVideoRef]);

  const onTimeUpdate = () => {
    if (!roadVideoRef.current) return;
    const vidTime = roadVideoRef.current.currentTime;
    const globalT = getGlobalTime(vidTime);
    setCurrentTime(globalT);
  };

  const onPartEnded = () => {
      if (currentPartIndex < roadUrls.length - 1) {
          setCurrentPartIndex(prev => prev + 1);
          // pendingSeek is 0 by default for new part
          setPendingSeek(0);
      } else {
          setIsPlaying(false);
      }
  };

  return {
    isPlaying,
    currentTime,
    duration,
    currentPartIndex,
    partDurations,
    roadAspectRatio,
    faceAspectRatio,
    handleSeek,
    togglePlay,
    onTimeUpdate,
    onPartEnded
  };
}
