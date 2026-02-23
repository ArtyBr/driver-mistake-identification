/**
 * useVideoSync — offset-aware dual-video playback hook.
 *
 * Manages two <video> ref elements with a fixed temporal offset.
 *
 * Sign convention (matches backend: offset = face_start − road_start):
 *   offset > 0  →  face started later than road (road leads)
 *                  → skip road forward: road.currentTime = offset, face.currentTime = 0
 *   offset < 0  →  face started earlier than road (face leads)
 *                  → skip face forward: face.currentTime = |offset|, road.currentTime = 0
 */
import { useRef, useState, useCallback, useEffect } from 'react';

const DRIFT_THRESHOLD = 0.3;   // seconds — resync if drift exceeds this
const DRIFT_INTERVAL  = 500;   // ms — how often to check for drift
const SEEK_SETTLE_MS  = 100;   // ms — wait after seek before calling play()

export function useVideoSync(offset) {
  const roadVideoRef = useRef(null);
  const faceVideoRef = useRef(null);

  const [isPlaying, setIsPlaying]       = useState(false);
  const [currentTime, setCurrentTime]   = useState(0);
  const [roadDuration, setRoadDuration] = useState(0);
  const [faceDuration, setFaceDuration] = useState(0);

  const driftTimerRef = useRef(null);

  // ------------------------------------------------------------------
  // Seek both videos to positions implied by the current offset
  // ------------------------------------------------------------------
  const applyOffset = useCallback(() => {
    const road = roadVideoRef.current;
    const face = faceVideoRef.current;
    if (!road || !face) return;

    if (offset >= 0) {
      // Face started later — skip road forward to where face starts
      road.currentTime = offset;
      face.currentTime = 0;
    } else {
      // Road started later — skip face forward to where road starts
      road.currentTime = 0;
      face.currentTime = Math.abs(offset);
    }
  }, [offset]);

  // ------------------------------------------------------------------
  // Drift correction — called every DRIFT_INTERVAL while playing
  // ------------------------------------------------------------------
  const startDriftCorrection = useCallback(() => {
    stopDriftCorrection();
    driftTimerRef.current = setInterval(() => {
      const road = roadVideoRef.current;
      const face = faceVideoRef.current;
      if (!road || !face || road.paused) return;

      // Expected face time = road time − offset
      // (road starts at `offset`, face starts at 0, so face_time = road_time − offset)
      const expectedFaceTime = road.currentTime - offset;
      const actualDrift = Math.abs(face.currentTime - expectedFaceTime);
      if (actualDrift > DRIFT_THRESHOLD) {
        face.currentTime = expectedFaceTime;
      }
    }, DRIFT_INTERVAL);
  }, [offset]);

  function stopDriftCorrection() {
    if (driftTimerRef.current) {
      clearInterval(driftTimerRef.current);
      driftTimerRef.current = null;
    }
  }

  // ------------------------------------------------------------------
  // Toggle play / pause
  // ------------------------------------------------------------------
  const togglePlay = useCallback(() => {
    const road = roadVideoRef.current;
    const face = faceVideoRef.current;
    if (!road || !face) return;

    if (isPlaying) {
      road.pause();
      face.pause();
      stopDriftCorrection();
      setIsPlaying(false);
    } else {
      applyOffset();
      setTimeout(() => {
        road.play().catch(() => {});
        face.play().catch(() => {});
        setIsPlaying(true);
        startDriftCorrection();
      }, SEEK_SETTLE_MS);
    }
  }, [isPlaying, applyOffset, startDriftCorrection]);

  // ------------------------------------------------------------------
  // Re-apply offset when it changes while paused
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!isPlaying) {
      applyOffset();
    }
  }, [offset, isPlaying, applyOffset]);

  // ------------------------------------------------------------------
  // Cleanup on unmount
  // ------------------------------------------------------------------
  useEffect(() => {
    return () => stopDriftCorrection();
  }, []);

  // ------------------------------------------------------------------
  // Event handlers forwarded to <video> elements
  // ------------------------------------------------------------------
  const onRoadTimeUpdate = useCallback(() => {
    const road = roadVideoRef.current;
    if (road) setCurrentTime(road.currentTime);
  }, []);

  const onRoadEnded = useCallback(() => {
    stopDriftCorrection();
    setIsPlaying(false);
  }, []);

  return {
    roadVideoRef,
    faceVideoRef,
    isPlaying,
    currentTime,
    roadDuration,
    faceDuration,
    togglePlay,
    onRoadTimeUpdate,
    onRoadEnded,
    setRoadDuration,
    setFaceDuration,
  };
}
