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

  const updateBuffering = useCallback(() => {
    const roadVid = roadVideoRef.current;
    const faceVid = faceVideoRef.current;
    if (!roadVid || !faceVid) return;

    const roadReady = roadVid.readyState >= 3; // HAVE_FUTURE_DATA
    const faceReady = faceVid.readyState >= 3;
    
    const isActuallyBuffering = roadWaitingRef.current || faceWaitingRef.current || 
                               isSeekingRef.current || !roadReady || !faceReady;
    
    setIsBuffering(isActuallyBuffering);
  }, [roadVideoRef, faceVideoRef]);

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
    updateBuffering(); // Immediately show loading state

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
    
    // Safety timeout to clear isSeeking if no event fires (e.g. video fails to seek)
    seekTimeoutRef.current = setTimeout(() => { 
        if (isSeekingRef.current) {
            console.warn("Seek timed out, force clearing seeking state");
            isSeekingRef.current = false; 
            updateBuffering();
        }
    }, 5000); // Increased to 5s to allow for buffering
  };

  // Handle Play/Pause
  const togglePlay = () => {
    const roadVid = roadVideoRef.current;
    const faceVid = faceVideoRef.current;
    if (!roadVid || !faceVid) return;

    const isLastPart = currentPartIndex === (roadUrls.length - 1);
    const isEnded = roadVid.ended || (roadVid.duration > 0 && Math.abs(roadVid.currentTime - roadVid.duration) < 0.2);

    if (isLastPart && isEnded) {
      handleSeek(0);
      setIsPlaying(true);
      return;
    }

    if (isPlaying) {
      roadVid.pause();
      faceVid.pause();
      setIsPlaying(false);
    } else {
      // Check if we can actually play (both not waiting)
      if (!roadWaitingRef.current && !faceWaitingRef.current) {
          roadVid.play().catch(e => console.error("Play error:", e));
          faceVid.play().catch(e => console.error("Play error:", e));
      }
      setIsPlaying(true);
    }
  };

  // Handle Part Switching and Metadata loading
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
              if (isPlaying && roadVid.readyState >= 3 && faceVid.readyState >= 3) {
                  roadVid.play().catch(() => {});
                  faceVid.play().catch(() => {});
              }
          }
          updateBuffering();
      };

      const onWaiting = (e) => {
          if (e.target === roadVid) roadWaitingRef.current = true;
          if (e.target === faceVid) faceWaitingRef.current = true;
          
          updateBuffering();

          // If one waits, pause both to sync
          roadVid.pause();
          faceVid.pause();
      };

      const onCanPlay = (e) => {
          if (e.target === roadVid) roadWaitingRef.current = false;
          if (e.target === faceVid) faceWaitingRef.current = false;
          
          updateBuffering();

          // Resume ONLY if both are ready, we are "playing", and NOT seeking
          if (isPlaying && !roadWaitingRef.current && !faceWaitingRef.current && !isSeekingRef.current) {
              const roadReady = roadVid.readyState >= 3;
              const faceReady = faceVid.readyState >= 3;
              if (roadReady && faceReady) {
                  roadVid.play().catch(() => {});
                  faceVid.play().catch(() => {});
              }
          }
      };

      const onSeeking = () => {
          isSeekingRef.current = true;
          updateBuffering();
      };

      const onSeeked = () => {
          // Both videos must finish seeking
          const isRoadSeeking = roadVid.seeking;
          const isFaceSeeking = (faceVid.readyState >= 1) ? faceVid.seeking : false;

          if (!isRoadSeeking && !isFaceSeeking) {
            
            // Check if we actually reached the target time
            // We only check roadVid for simplicity as faceVid syncs to it
            // Calculate local target time based on currentPart
            let offset = 0;
            for(let i=0; i<currentPartIndex; i++) offset += partDurations[i] || 0;
            
            // If we have a specific target time set by handleSeek
            if (targetSeekTimeRef.current !== null) {
                const localTarget = Math.max(0, targetSeekTimeRef.current - offset);
                const diff = Math.abs(roadVid.currentTime - localTarget);
                
                // If we are far off (> 0.5s), it means the seek "completed" but didn't reach the target
                // (likely clamped to buffered range). We should stay in "seeking" state.
                if (diff > 0.5) {
                   // Do not clear isSeekingRef
                   // Ensure we are paused while we wait
                   roadVid.pause();
                   faceVid.pause();
                   return; 
                }
            }
            
            isSeekingRef.current = false;
            targetSeekTimeRef.current = null; // Reset target
            
            if (seekTimeoutRef.current) {
                clearTimeout(seekTimeoutRef.current);
                seekTimeoutRef.current = null;
            }
            updateBuffering();
            
            if (isPlaying && !roadWaitingRef.current && !faceWaitingRef.current) {
                roadVid.play().catch(() => {});
                faceVid.play().catch(() => {});
            }
          }
      };
      
      // Monitor buffering progress to re-trigger seek if needed
      const onProgress = () => {
          const roadVid = roadVideoRef.current;
          if (!roadVid) return;

          // Update buffered ranges state
          let offset = 0;
          for(let i=0; i<currentPartIndex; i++) offset += partDurations[i] || 0;

          const ranges = [];
          const buffered = roadVid.buffered;
          for (let i = 0; i < buffered.length; i++) {
              ranges.push({
                  start: buffered.start(i) + offset,
                  end: buffered.end(i) + offset
              });
          }
          setBufferedRanges(ranges);

          if (isSeekingRef.current && targetSeekTimeRef.current !== null) {
              const localTarget = Math.max(0, targetSeekTimeRef.current - offset);
              
              // Check if the buffered ranges now include our target
              for(let i=0; i<buffered.length; i++) {
                  if (buffered.start(i) <= localTarget && buffered.end(i) >= localTarget) {
                      // We have data! Retry the seek if we aren't there yet
                      if (Math.abs(roadVid.currentTime - localTarget) > 0.5) {
                          console.log("Buffered range covers target, re-seeking...");
                          roadVid.currentTime = localTarget;
                          if(faceVid.readyState >= 1) faceVid.currentTime = localTarget;
                      }
                      break;
                  }
              }
          }
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
      }
  }, [currentPartIndex, activePartIndex, isPlaying, pendingSeek, roadVideoRef, faceVideoRef, updateBuffering, partDurations]);

  const onTimeUpdate = () => {
    const roadVid = roadVideoRef.current;
    const faceVid = faceVideoRef.current;
    if (!roadVid || isSeekingRef.current || pendingSeek !== null || roadWaitingRef.current || faceWaitingRef.current) return;
    
    // Sync face video if it drifts significantly, but ONLY if it's not already doing something
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
