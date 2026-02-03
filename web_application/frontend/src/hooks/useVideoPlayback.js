import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';

export function useVideoPlayback(roadUrls, faceUrls, roadVideoRef, faceVideoRef) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [roadAspectRatio, setRoadAspectRatio] = useState(16/9);
  const [faceAspectRatio, setFaceAspectRatio] = useState(4/3);
  
  // Multi-part support
  const [partDurations, setPartDurations] = useState([]);
  const [currentPartIndex, setCurrentPartIndex] = useState(0);
  const [activePartIndex, setActivePartIndex] = useState(0);
  const [pendingSeek, setPendingSeek] = useState(null);
  const [isBuffering, setIsBuffering] = useState(false);
  const [bufferedRanges, setBufferedRanges] = useState([]); // Array of {start, end} in global time
  
  // Internal state to track what the video element is actually playing
  const isSeekingRef = useRef(false);
  const targetSeekTimeRef = useRef(null); // The global time we WANT to be at
  const seekTimeoutRef = useRef(null);
  const roadWaitingRef = useRef(false);
  const faceWaitingRef = useRef(false);

  // Load durations and dimensions for all parts
  useLayoutEffect(() => {
    if (!roadUrls || roadUrls.length === 0) {
      setTimeout(() => {
        setPartDurations([]);
        setDuration(0);
        setCurrentPartIndex(0);
        setActivePartIndex(0);
        setCurrentTime(0);
      }, 0);
      return;
    }

    const loadMetadata = async () => {
      const container = document.createElement('div');
      container.style.display = 'none';
      document.body.appendChild(container);

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
      
      if (container.parentNode) document.body.removeChild(container);
      
      // Update durations after they are all fetched
      setPartDurations(roadDurs);
      const total = roadDurs.reduce((a, b) => a + b, 0);
      setDuration(total > 0 ? total : 0);
    };
    
    loadMetadata();
    // Use setTimeout to avoid synchronous setState in effect body
    setTimeout(() => {
        setCurrentPartIndex(0);
        setActivePartIndex(0);
        setCurrentTime(0);
    }, 0);
  }, [roadUrls, faceUrls]);

  // Helper to convert local time of current part to global time
  const getGlobalTime = useCallback((localTime, partIdx) => {
    let offset = 0;
    for (let i = 0; i < partIdx; i++) {
        offset += partDurations[i] || 0;
    }
    return offset + localTime;
  }, [partDurations]);

  // Helper to check if a video has enough buffer
  const checkBuffer = useCallback((vid) => {
    if (!vid) return false;
    if (vid.error) return false;
    // If ended, we definitely have enough
    if (vid.ended) return true;
    // If the browser says we have enough data to play through, trust it.
    if (vid.readyState === 4) return true;
    
    const ct = vid.currentTime;
    const dur = vid.duration;
    // If close to end, we have enough
    if (dur > 0 && dur - ct < 1.0) return true; 

    const buffered = vid.buffered;
    // Dynamic threshold: 2 seconds or remaining time, whichever is smaller
    const requiredBuffer = Math.min(2.0, dur - ct);

    for (let i = 0; i < buffered.length; i++) {
        if (buffered.start(i) <= ct + 0.5 && buffered.end(i) >= ct) {
             const ahead = buffered.end(i) - ct;
             if (ahead >= requiredBuffer) return true;
        }
    }
    return false;
  }, []);

  const updateBuffering = useCallback(() => {
    const roadVid = roadVideoRef.current;
    const faceVid = faceVideoRef.current;
    if (!roadVid || !faceVid) return;

    const roadWaiting = roadWaitingRef.current;
    const faceWaiting = faceWaitingRef.current;
    const isSeeking = isSeekingRef.current;
    
    const roadReady = roadVid.readyState >= 3; // HAVE_FUTURE_DATA
    const faceReady = faceVid.readyState >= 3;
    
    // ENTER buffering if forced to wait/seek or not ready
    if (roadWaiting || faceWaiting || isSeeking || !roadReady || !faceReady) {
        setIsBuffering(true);
    } else {
        // EXIT buffering only if we have enough buffer (hysteresis)
        setIsBuffering(wasBuffering => {
            if (wasBuffering) {
                const rEnough = checkBuffer(roadVid);
                const fEnough = checkBuffer(faceVid);
                return !(rEnough && fEnough); // Keep buffering if not enough
            }
            return false; // Not buffering
        });
    }
  }, [roadVideoRef, faceVideoRef, checkBuffer]);

  // Handle Seeking
  const handleSeek = (globalTime) => {
    isSeekingRef.current = true;
    targetSeekTimeRef.current = globalTime;
    if (seekTimeoutRef.current) clearTimeout(seekTimeoutRef.current);

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
    
    if (targetIndex === -1) {
         if (partDurations.length > 0) {
             targetIndex = Math.max(0, partDurations.length - 1);
             localTime = partDurations[targetIndex]; 
             if (localTime > 0.1) localTime -= 0.1;
         } else {
             targetIndex = 0;
             localTime = 0;
         }
    }
    
    setCurrentTime(globalTime);
    updateBuffering(); // Will set isBuffering=true immediately

    if (targetIndex !== currentPartIndex) {
        setPendingSeek(localTime);
        setCurrentPartIndex(targetIndex);
    } else {
        if (roadVideoRef.current) {
            roadVideoRef.current.currentTime = localTime;
        }
        if (faceVideoRef.current) {
            faceVideoRef.current.currentTime = localTime;
        }
    }
    
    seekTimeoutRef.current = setTimeout(() => { 
        if (isSeekingRef.current) {
            console.warn("Seek timed out, force clearing seeking state");
            isSeekingRef.current = false; 
            updateBuffering();
        }
    }, 5000); 
  };

  // Handle Play/Pause
  const togglePlay = () => {
    const roadVid = roadVideoRef.current;
    if (!roadVid) return;

    const isLastPart = currentPartIndex === (roadUrls.length - 1);
    const isEnded = roadVid.ended || (roadVid.duration > 0 && Math.abs(roadVid.currentTime - roadVid.duration) < 0.2);

    if (isLastPart && isEnded) {
      handleSeek(0);
      setIsPlaying(true);
      return;
    }

    setIsPlaying(p => !p);
  };

  // Centralized Playback Control Effect
  useEffect(() => {
      const roadVid = roadVideoRef.current;
      const faceVid = faceVideoRef.current;
      if (!roadVid || !faceVid) return;

      if (isPlaying && !isBuffering) {
          // Both should play
          if (roadVid.paused && roadVid.readyState >= 2) {
              roadVid.play().catch(e => {
                  // Ignore abort errors which happen on rapid pause/play
                  if (e.name !== 'AbortError') console.error("Road play error:", e);
              });
          }
          if (faceVid.paused && faceVid.readyState >= 2) {
              faceVid.play().catch(e => {
                  if (e.name !== 'AbortError') console.error("Face play error:", e);
              });
          }
      } else {
          // Should pause
          if (!roadVid.paused) roadVid.pause();
          if (!faceVid.paused) faceVid.pause();
      }
  }, [isPlaying, isBuffering, roadVideoRef, faceVideoRef]);


  // Handle Part Switching and Events
  useEffect(() => {
      const roadVid = roadVideoRef.current;
      const faceVid = faceVideoRef.current;
      if (!roadVid || !faceVid) return;

      const onLoadedMetadata = () => {
          // Only proceed if road is loaded; face will sync once it's ready
          if (roadVid.readyState >= 1) {
              setActivePartIndex(currentPartIndex);
              if (pendingSeek !== null) {
                  const targetTime = pendingSeek;
                  setPendingSeek(null); 
                  roadVid.currentTime = targetTime;
                  if (faceVid.readyState >= 1) faceVid.currentTime = targetTime;
              }
          }
          updateBuffering();
      };

      const onWaiting = (e) => {
          if (e.target === roadVid) roadWaitingRef.current = true;
          if (e.target === faceVid) faceWaitingRef.current = true;
          updateBuffering();
      };

      const onCanPlay = (e) => {
          if (e.target === roadVid) roadWaitingRef.current = false;
          if (e.target === faceVid) faceWaitingRef.current = false;
          updateBuffering();
      };

      const onSeeking = () => {
          isSeekingRef.current = true;
          updateBuffering();
      };

      const onSeeked = () => {
          const isRoadSeeking = roadVid.seeking;
          const isFaceSeeking = (faceVid.readyState >= 1) ? faceVid.seeking : false;

          if (!isRoadSeeking && !isFaceSeeking) {
            // Check if we actually reached the target time
            let offset = 0;
            for(let i=0; i<currentPartIndex; i++) offset += partDurations[i] || 0;
            
            if (targetSeekTimeRef.current !== null) {
                const localTarget = Math.max(0, targetSeekTimeRef.current - offset);
                const diff = Math.abs(roadVid.currentTime - localTarget);
                
                if (diff > 0.5) {
                   // Ensure we are paused while we wait
                   roadVid.pause();
                   faceVid.pause();
                   return; 
                }
            }
            
            isSeekingRef.current = false;
            targetSeekTimeRef.current = null;
            
            if (seekTimeoutRef.current) {
                clearTimeout(seekTimeoutRef.current);
                seekTimeoutRef.current = null;
            }
            updateBuffering();
          }
      };
      
      const onProgress = () => {
          const roadVid = roadVideoRef.current;
          if (!roadVid) return;

          // Update buffered ranges state (only for road video for now)
          let offset = 0;
          for(let i=0; i<currentPartIndex; i++) offset += partDurations[i] || 0;

          const ranges = [];
          const buffered = roadVid.buffered;
          for (let i = 0; i < buffered.length; i++) {
              const start = buffered.start(i) + offset;
              const end = buffered.end(i) + offset;

              // Merge overlapping or adjacent ranges (tolerance 0.5s)
              if (ranges.length > 0) {
                  const last = ranges[ranges.length - 1];
                  if (start - last.end < 0.5) {
                      last.end = Math.max(last.end, end);
                  } else {
                      ranges.push({ start, end });
                  }
              } else {
                  ranges.push({ start, end });
              }
          }
          setBufferedRanges(ranges);

          // Seek retry logic
          if (isSeekingRef.current && targetSeekTimeRef.current !== null) {
              const localTarget = Math.max(0, targetSeekTimeRef.current - offset);
              for(let i=0; i<buffered.length; i++) {
                  if (buffered.start(i) <= localTarget && buffered.end(i) >= localTarget) {
                      if (Math.abs(roadVid.currentTime - localTarget) > 0.5) {
                          roadVid.currentTime = localTarget;
                          if(faceVid.readyState >= 1) faceVid.currentTime = localTarget;
                      }
                      break;
                  }
              }
          }
          
          updateBuffering(); // Check if we have enough buffer now
      };
      
      const onFaceProgress = () => {
          updateBuffering();
      };

      roadVid.addEventListener('loadedmetadata', onLoadedMetadata);
      roadVid.addEventListener('waiting', onWaiting);
      roadVid.addEventListener('playing', onCanPlay);
      roadVid.addEventListener('canplay', onCanPlay);
      roadVid.addEventListener('seeking', onSeeking);
      roadVid.addEventListener('seeked', onSeeked);
      roadVid.addEventListener('progress', onProgress);

      faceVid.addEventListener('loadedmetadata', onLoadedMetadata);
      faceVid.addEventListener('waiting', onWaiting);
      faceVid.addEventListener('playing', onCanPlay);
      faceVid.addEventListener('canplay', onCanPlay);
      faceVid.addEventListener('seeking', onSeeking);
      faceVid.addEventListener('seeked', onSeeked);
      faceVid.addEventListener('progress', onFaceProgress);
      
      if (roadVid.readyState >= 1 && activePartIndex === currentPartIndex) {
          if (pendingSeek !== null) {
              const targetTime = pendingSeek;
              setTimeout(() => setPendingSeek(null), 0);
              roadVid.currentTime = targetTime;
              faceVid.currentTime = targetTime;
          }
      }

      return () => {
          roadVid.removeEventListener('loadedmetadata', onLoadedMetadata);
          roadVid.removeEventListener('waiting', onWaiting);
          roadVid.removeEventListener('playing', onCanPlay);
          roadVid.removeEventListener('canplay', onCanPlay);
          roadVid.removeEventListener('seeking', onSeeking);
          roadVid.removeEventListener('seeked', onSeeked);
          roadVid.removeEventListener('progress', onProgress);

          faceVid.removeEventListener('waiting', onWaiting);
          faceVid.removeEventListener('playing', onCanPlay);
          faceVid.removeEventListener('canplay', onCanPlay);
          faceVid.removeEventListener('seeking', onSeeking);
          faceVid.removeEventListener('seeked', onSeeked);
          faceVid.removeEventListener('progress', onFaceProgress);
      }
  }, [currentPartIndex, activePartIndex, pendingSeek, roadVideoRef, faceVideoRef, updateBuffering, partDurations]); // Removed isPlaying from dep as it is handled in separate effect

  const onTimeUpdate = () => {
    const roadVid = roadVideoRef.current;
    const faceVid = faceVideoRef.current;
    if (!roadVid || isSeekingRef.current || pendingSeek !== null || roadWaitingRef.current || faceWaitingRef.current) return;
    
    // Sync face video if it drifts significantly
    if (faceVid && !faceVid.seeking && !faceWaitingRef.current && Math.abs(roadVid.currentTime - faceVid.currentTime) > 0.3) {
        faceVid.currentTime = roadVid.currentTime;
    }

    const vidTime = roadVid.currentTime;
    const globalT = getGlobalTime(vidTime, activePartIndex);
    
    // Sanity check
    let offset = 0;
    for (let i = 0; i < activePartIndex; i++) offset += partDurations[i] || 0;
    const partEnd = offset + (partDurations[activePartIndex] || 0);
    
    if (globalT >= offset - 1.0 && globalT <= partEnd + 1.0) {
        setCurrentTime(globalT);
    }
  };

  const onPartEnded = () => {
      if (currentPartIndex < roadUrls.length - 1) {
          setPendingSeek(0);
          setCurrentPartIndex(prev => prev + 1);
      } else {
          setIsPlaying(false);
      }
  };

  return {
    isPlaying,
    isBuffering,
    currentTime,
    duration,
    currentPartIndex,
    activePartIndex,
    partDurations,
    roadAspectRatio,
    faceAspectRatio,
    handleSeek,
    togglePlay,
    onTimeUpdate,
    onPartEnded,
    bufferedRanges
  };
}