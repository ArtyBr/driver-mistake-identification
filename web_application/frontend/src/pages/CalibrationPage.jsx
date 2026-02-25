import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { listAnalyses, getJobStatus, getFileUrl, getJobResults } from '../services/api';
import {
  getCalibrationStatus,
  submitSamples,
  resetSamples,
  trainModel,
  requestReanalysis,
} from '../services/calibrationService';
import { GAZE_STATES } from '../constants/videoConstants';

const GAZE_CLASS_NAMES = ['Looking Ahead', 'Left Mirror', 'Right Mirror', 'Rear Mirror'];
const MANDATORY_CLASS_NAMES = ['Looking Ahead', 'Left Mirror', 'Right Mirror'];
const MIN_SECONDS_PER_CLASS = 0.5;
const MIN_SAMPLES = 3; // frame-level minimum for Step 3 train button
// Fixed zoom preset levels (seconds). Each step in/out snaps to the next preset.
const ZOOM_PRESETS = [1, 5, 15, 30, 60, 120, 300, 600];

/**
 * Draws a gaze-direction line from nose_2d — matches style used in useVideoCanvas.js
 * (plain line, no arrowhead; scaled by actual face video dimensions).
 */
function drawGazeLine(ctx, nose2d, yaw, pitch, videoW, videoH, canvasW, canvasH, color) {
  if (!nose2d || nose2d.length < 2) return;
  const scaleX = canvasW / videoW;
  const scaleY = canvasH / videoH;
  const startX = nose2d[0] * scaleX;
  const startY = nose2d[1] * scaleY;
  const endX = (nose2d[0] + yaw * 10) * scaleX;
  const endY = (nose2d[1] - pitch * 10) * scaleY;
  ctx.save();
  ctx.strokeStyle = color || '#00d9ff';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(startX, startY);
  ctx.lineTo(endX, endY);
  ctx.stroke();
  ctx.restore();
}

// ─── Step indicator ───────────────────────────────────────────────────────────

const StepIndicator = ({ current, onStepClick }) => {
  const labels = ['Select Job', 'Label Clips', 'Review', 'Train Model'];
  return (
    <div className="d-flex align-items-center gap-0 mb-4">
      {labels.map((label, i) => {
        const n = i + 1;
        const isDone = n < current;
        const isActive = n === current;
        const clickable = isDone && onStepClick;
        return (
          <React.Fragment key={i}>
            <div className="d-flex flex-column align-items-center" style={{ minWidth: 90 }}>
              <div
                onClick={clickable ? () => onStepClick(n) : undefined}
                title={clickable ? `Go back to ${label}` : undefined}
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 700,
                  fontSize: '0.85rem',
                  background: isDone ? 'var(--accent-success)' : isActive ? 'var(--accent-primary)' : 'var(--bg-panel-lighter)',
                  border: `2px solid ${isDone ? 'var(--accent-success)' : isActive ? 'var(--accent-primary)' : 'var(--border-color)'}`,
                  color: isDone || isActive ? '#fff' : 'var(--text-muted)',
                  cursor: clickable ? 'pointer' : 'default',
                }}
              >
                {isDone ? '✓' : n}
              </div>
              <span
                style={{
                  fontSize: '0.72rem',
                  marginTop: 4,
                  color: isActive ? 'var(--text-main)' : 'var(--text-muted)',
                  fontWeight: isActive ? 600 : 400,
                  textAlign: 'center',
                  letterSpacing: '0.3px',
                }}
              >
                {label}
              </span>
            </div>
            {i < labels.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  background: isDone ? 'var(--accent-success)' : 'var(--border-color)',
                  marginBottom: 20,
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

// ─── Calibration Timeline ─────────────────────────────────────────────────────

/**
 * Interactive dual-handle timeline with zoom support.
 * viewStart/viewEnd define the visible time window (defaults to full video).
 * Zoom is controlled externally via buttons; scroll-to-zoom is a secondary convenience.
 */
const CalibrationTimeline = ({
  duration, segments, rangeStart, rangeEnd,
  onRangeChange, onSeek, currentTime,
  viewStart: vsProp, viewEnd: veProp, onViewChange,
}) => {
  const trackRef = useRef(null);
  const draggingRef = useRef(null); // null | 'start' | 'end' | 'range'
  const dragOffsetRef = useRef(0);

  const vs = vsProp ?? 0;
  const ve = veProp ?? duration;
  const vDur = ve - vs;

  // Always-current snapshot — avoids stale closures in global event handlers
  const stateRef = useRef({ rangeStart, rangeEnd, duration, vs, ve, vDur });
  
  useEffect(() => {
    stateRef.current = { rangeStart, rangeEnd, duration, vs, ve, vDur };
  }, [rangeStart, rangeEnd, duration, vs, ve, vDur]);

  const getTimeFromEvent = useCallback((e) => {
    if (!trackRef.current || !stateRef.current.vDur) return 0;
    const rect = trackRef.current.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    return stateRef.current.vs + frac * stateRef.current.vDur;
  }, []);

  // Click bare track → snap nearest handle to clicked position
  const handleTrackMouseDown = (e) => {
    if (e.target !== trackRef.current) return;
    e.preventDefault();
    const t = getTimeFromEvent(e);
    const { rangeStart: rs, rangeEnd: re } = stateRef.current;
    draggingRef.current = Math.abs(t - rs) <= Math.abs(t - re) ? 'start' : 'end';
  };

  const handleRangeZoneMouseDown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragOffsetRef.current = getTimeFromEvent(e) - stateRef.current.rangeStart;
    draggingRef.current = 'range';
  };

  const handleStartHandleMouseDown = (e) => { e.preventDefault(); e.stopPropagation(); draggingRef.current = 'start'; };
  const handleEndHandleMouseDown   = (e) => { e.preventDefault(); e.stopPropagation(); draggingRef.current = 'end';   };

  // Global mouse-move / mouse-up for drag
  useEffect(() => {
    const handleMove = (e) => {
      if (!draggingRef.current) return;
      const t = getTimeFromEvent(e);
      const { rangeStart: rs, rangeEnd: re, duration: d } = stateRef.current;
      if (draggingRef.current === 'start') {
        const ns = Math.max(0, Math.min(t, re - 0.2));
        onRangeChange(ns, re); 
        onSeek?.(ns);
      } else if (draggingRef.current === 'end') {
        const ne = Math.max(rs + 0.2, Math.min(t, d));
        onRangeChange(rs, ne); 
        onSeek?.(ne);
      } else {
        const w = re - rs;
        let s = Math.max(0, Math.min(d - w, t - dragOffsetRef.current));
        onRangeChange(s, s + w); 
        onSeek?.(s);
      }
    };
    const handleUp = () => { draggingRef.current = null; };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => { window.removeEventListener('mousemove', handleMove); window.removeEventListener('mouseup', handleUp); };
  }, [onRangeChange, onSeek, getTimeFromEvent]);

  // Scroll-wheel zoom — centred on cursor (secondary to the zoom buttons)
  useEffect(() => {
    const el = trackRef.current;
    if (!el || !onViewChange) return;
    const onWheel = (e) => {
      e.preventDefault();
      const { vs: s, vDur: vd, duration: d } = stateRef.current;
      if (!vd || !d) return;
      const rect = el.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const anchor = s + frac * vd;
      const factor = e.deltaY > 0 ? 1.3 : 1 / 1.3;
      const minW = Math.max(1, d * 0.02);
      let newW = Math.max(minW, Math.min(d, vd * factor));
      let ns = anchor - frac * newW;
      let ne = ns + newW;
      if (ns < 0) { ne -= ns; ns = 0; }
      if (ne > d) { ns -= (ne - d); ne = d; }
      onViewChange(Math.max(0, ns), Math.min(d, ne));
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [onViewChange]);

  if (!duration) return null;

  // View-relative position helpers (clamped so elements don't escape the bar)
  const toLeftPct  = (t) => Math.max(0, Math.min(100, ((t - vs) / vDur) * 100));
  const toWidthPct = (s, e) => {
    const cs = Math.max(s, vs), ce = Math.min(e, ve);
    return ce > cs ? ((ce - cs) / vDur) * 100 : 0;
  };

  const startPct = toLeftPct(rangeStart);
  const endPct   = toLeftPct(rangeEnd);
  const startInView = rangeStart >= vs && rangeStart <= ve;
  const endInView   = rangeEnd   >= vs && rangeEnd   <= ve;
  const selStart = Math.max(rangeStart, vs);
  const selEnd   = Math.min(rangeEnd, ve);
  const isZoomed = vs > 0.01 || ve < duration - 0.01;

  return (
    <div style={{ position: 'relative', paddingBottom: 22, marginBottom: '0.5rem', userSelect: 'none' }}>
      {/* Track */}
      <div
        ref={trackRef}
        style={{ position: 'relative', height: 24, background: 'var(--bg-panel-lighter)', borderRadius: 4, border: '1px solid var(--border-color)', cursor: 'pointer', overflow: 'hidden' }}
        onMouseDown={handleTrackMouseDown}
      >
        {/* Labelled clips */}
        {segments.map((seg, i) => {
          if (seg.endTime < vs || seg.startTime > ve) return null;
          return (
            <div key={i} style={{ position: 'absolute', top: 0, bottom: 0, left: `${toLeftPct(Math.max(seg.startTime, vs))}%`, width: `${toWidthPct(seg.startTime, seg.endTime)}%`, background: GAZE_STATES[seg.label]?.color || '#888', opacity: 0.55, pointerEvents: 'none', borderRadius: 2 }} />
          );
        })}

        {/* Selection zone */}
        {selEnd > selStart && (
          <div
            style={{ position: 'absolute', top: 0, bottom: 0, left: `${((selStart - vs) / vDur) * 100}%`, width: `${((selEnd - selStart) / vDur) * 100}%`, background: 'rgba(255,255,255,0.15)', borderLeft: rangeStart >= vs ? '2px solid rgba(255,255,255,0.75)' : 'none', borderRight: rangeEnd <= ve ? '2px solid rgba(255,255,255,0.75)' : 'none', boxSizing: 'border-box', cursor: 'move' }}
            onMouseDown={handleRangeZoneMouseDown}
          />
        )}

        {/* Playhead */}
        {currentTime >= vs && currentTime <= ve && (
          <div style={{ position: 'absolute', top: -3, bottom: -3, left: `${toLeftPct(currentTime)}%`, width: 2, background: 'rgba(255,255,255,0.85)', borderRadius: 1, pointerEvents: 'none' }} />
        )}
      </div>

      {/* Start handle */}
      {startPct >= 0 && startPct <= 100 && (
        <div style={{ position: 'absolute', top: -6, left: `${startPct}%`, transform: 'translateX(-50%)', width: 8, height: 36, background: 'var(--accent-primary)', borderRadius: 2, cursor: 'ew-resize', zIndex: 3, boxShadow: '0 0 4px rgba(0,0,0,0.5)' }} onMouseDown={handleStartHandleMouseDown} />
      )}

      {/* End handle */}
      {endPct >= 0 && endPct <= 100 && (
        <div style={{ position: 'absolute', top: -6, left: `${endPct}%`, transform: 'translateX(-50%)', width: 8, height: 36, background: 'var(--accent-primary)', borderRadius: 2, cursor: 'ew-resize', zIndex: 3, boxShadow: '0 0 4px rgba(0,0,0,0.5)' }} onMouseDown={handleEndHandleMouseDown} />
      )}

      {/* Time labels */}
      {startInView && (
        <div style={{ position: 'absolute', bottom: 0, left: `${startPct}%`, transform: 'translateX(-50%)', fontSize: '0.7rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', pointerEvents: 'none' }}>
          {rangeStart.toFixed(2)}s
        </div>
      )}
      {endInView && Math.abs(endPct - startPct) > 6 && (
        <div style={{ position: 'absolute', bottom: 0, left: `${endPct}%`, transform: 'translateX(-50%)', fontSize: '0.7rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', pointerEvents: 'none' }}>
          {rangeEnd.toFixed(2)}s
        </div>
      )}

      {/* View-range edge labels */}
      {isZoomed && <div style={{ position: 'absolute', bottom: 0, left: 0, fontSize: '0.65rem', color: 'var(--border-color)', pointerEvents: 'none' }}>{vs.toFixed(1)}s</div>}
      <div style={{ position: 'absolute', bottom: 0, right: 0, fontSize: '0.65rem', color: 'var(--border-color)', pointerEvents: 'none' }}>
        {isZoomed ? ve.toFixed(1) : duration.toFixed(1)}s
      </div>
    </div>
  );
};

// ─── Main page ────────────────────────────────────────────────────────────────

const CalibrationPage = () => {
  const navigate = useNavigate();

  const [step, setStep] = useState(1);

  // Step 1
  const [analyses, setAnalyses] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [jobStatus, setJobStatus] = useState(null);
  const [loadingJob, setLoadingJob] = useState(false);

  // Step 2 — video
  const faceVideoRef = useRef(null);
  const [videoDuration, setVideoDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  // Step 2 — range selector
  const [rangeStart, setRangeStart] = useState(0);
  const [rangeEnd, setRangeEnd] = useState(10);

  // Step 2 — existing gaze segments (read-only reference bar)
  const [gazeSegments, setGazeSegments] = useState([]);

  // Step 2 — zoom window (viewStart/viewEnd define visible time range on timeline)
  const [viewStart, setViewStart] = useState(0);
  const [viewEnd, setViewEnd] = useState(0);

  // Minimap refs — for dragging the viewport indicator on the reference bar
  const minimapRef = useRef(null);
  const minimapDragRef = useRef(null); // null | { offsetSecs }
  const viewRef = useRef({ viewStart: 0, viewEnd: 0, duration: 0 });

  useEffect(() => {
    viewRef.current = { viewStart, viewEnd, duration: videoDuration };
  }, [viewStart, viewEnd, videoDuration]);

  // Frame times from results.json — used for snapping range handles to actual frames
  const frameTimesRef = useRef([]);
  // Full frame data — used for live yaw/pitch/roll card and scatter plot
  const frameDataRef = useRef([]);

  // Canvas overlay ref for nose arrow
  const canvasRef = useRef(null);

  // Current frame's face_info (updated on timeUpdate)
  const [currentFrameInfo, setCurrentFrameInfo] = useState(null);

  // Step 2 — captured segments (current session, not yet submitted)
  const [capturedSegments, setCapturedSegments] = useState([]);
  const [submittingSamples, setSubmittingSamples] = useState(false);
  const [sampleError, setSampleError] = useState(null);


  // Step 3
  const [calStatus, setCalStatus] = useState(null);
  const [resetting, setResetting] = useState(false);

  // Step 4
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState(null);
  const [trainPlots, setTrainPlots] = useState(null); // {head_pose, pca, decision_boundary} data URLs

  useEffect(() => {
    listAnalyses()
      .then(data => setAnalyses(data.filter(a => !a.is_demo)))
      .catch(() => {});
    getCalibrationStatus()
      .then(setCalStatus)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedJobId) { setJobStatus(null); setGazeSegments([]); frameTimesRef.current = []; frameDataRef.current = []; setCurrentFrameInfo(null); return; }
    setLoadingJob(true);
    getJobStatus(selectedJobId)
      .then(setJobStatus)
      .catch(() => setJobStatus(null))
      .finally(() => setLoadingJob(false));

    // Load existing gaze data for the reference bar
    getJobResults(selectedJobId)
      .then(results => {
        const frames = results?.frame_data || [];
        const segs = [];
        let cur = null;
        for (const frame of frames) {
          const label = frame.face_info?.label;
          if (!label || label === 'N/A' || label === 'Unknown') {
            if (cur) { segs.push(cur); cur = null; }
            continue;
          }
          if (!cur || cur.label !== label) {
            if (cur) segs.push(cur);
            cur = { label, startTime: frame.time, endTime: frame.time };
          } else {
            cur.endTime = frame.time;
          }
        }
        if (cur) segs.push(cur);
        setGazeSegments(segs);
        // Store full frame data for live card, nose arrow, and scatter plot
        frameDataRef.current = frames.filter(f => typeof f.time === 'number');
        // Store sorted timestamps for frame-snapping
        frameTimesRef.current = frameDataRef.current.map(f => f.time);
      })
      .catch(() => { setGazeSegments([]); frameTimesRef.current = []; frameDataRef.current = []; });
  }, [selectedJobId]);

  // Minimap drag — pans the zoom window. Uses refs to avoid stale closures.
  useEffect(() => {
    const handleMove = (e) => {
      if (!minimapDragRef.current) return;
      const rect = minimapRef.current?.getBoundingClientRect();
      if (!rect) return;
      const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const { viewStart: vs, viewEnd: ve, duration: d } = viewRef.current;
      const w = ve - vs;
      const t = frac * d;
      const ns = Math.max(0, Math.min(d - w, t - minimapDragRef.current.offsetSecs));
      setViewStart(ns);
      setViewEnd(Math.min(d, ns + w));
    };
    const handleUp = () => { minimapDragRef.current = null; };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, []);

  // ─── Step 2 helpers ──────────────────────────────────────────────────────

  // Navigate back to a previous step (step indicator click)
  const handleStepClick = useCallback((n) => setStep(n), []);

  // Binary-search frameDataRef for the frame closest to time t
  const findCurrentFrame = useCallback((t) => {
    const frames = frameDataRef.current;
    if (!frames.length) return null;
    let lo = 0, hi = frames.length - 1;
    while (lo < hi - 1) {
      const mid = (lo + hi) >> 1;
      if (frames[mid].time <= t) lo = mid;
      else hi = mid;
    }
    return Math.abs(t - frames[lo].time) <= Math.abs(t - frames[hi].time) ? frames[lo] : frames[hi];
  }, []);

  // Redraw nose line on canvas whenever current frame changes
  useEffect(() => {
    const canvas = canvasRef.current;
    const video  = faceVideoRef.current;
    if (!canvas || !video) return;
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    if (!w || !h) return;
    canvas.width  = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, w, h);
    const fi = currentFrameInfo?.face_info;
    if (!fi?.nose_2d) return;
    const vW = video.videoWidth  || 640;
    const vH = video.videoHeight || 480;
    const color = GAZE_STATES[fi.label]?.color || '#00d9ff';
    drawGazeLine(ctx, fi.nose_2d, fi.yaw ?? 0, fi.pitch ?? 0, vW, vH, w, h, color);
  }, [currentFrameInfo]);

  // Current-session data: exact yaw/pitch/roll points from frameDataRef for captured segments.
  // This is ALSO what gets submitted to the server — no re-extraction on the backend.
  const currentSessionPoints = useMemo(() => {
    const points = [];
    for (const seg of capturedSegments) {
      const matched = frameDataRef.current.filter(
        f => f.time >= seg.startTime && f.time <= seg.endTime && f.face_info?.yaw != null
      );
      for (const f of matched) {
        points.push({
          yaw: f.face_info.yaw,
          pitch: f.face_info.pitch,
          roll: f.face_info.roll ?? 0,
          label: seg.label,
        });
      }
    }
    return points;
  }, [capturedSegments]);

  // Snaps time t to the nearest frame timestamp from results.json.
  // Falls back to t unchanged if no frame data is available.
  const snapToFrame = useCallback((t) => {
    const times = frameTimesRef.current;
    if (!times.length) return parseFloat(t.toFixed(3));
    let lo = 0, hi = times.length - 1;
    while (lo < hi - 1) {
      const mid = (lo + hi) >> 1;
      if (times[mid] <= t) lo = mid;
      else hi = mid;
    }
    return Math.abs(t - times[lo]) <= Math.abs(t - times[hi]) ? times[lo] : times[hi];
  }, []);

  const handleRangeChange = useCallback((start, end) => {
    setRangeStart(snapToFrame(start));
    setRangeEnd(snapToFrame(end));
  }, [snapToFrame]);

  const handleSeek = useCallback((t) => {
    if (faceVideoRef.current) {
      faceVideoRef.current.currentTime = t;
    }
  }, []);

  const handleViewChange = useCallback((ns, ne) => {
    setViewStart(ns);
    setViewEnd(ne);
  }, []);

  const handleZoomIn = useCallback(() => {
    const { viewStart: vs, viewEnd: ve, duration: d } = viewRef.current;
    if (!d) return;
    const w = ve - vs;
    const mid = (vs + ve) / 2;
    // Find the largest preset that is strictly smaller than the current window
    const smaller = ZOOM_PRESETS.filter(l => l < w - 0.5);
    const newW = smaller.length ? smaller[smaller.length - 1] : Math.max(1, d * 0.02);
    const ns = Math.max(0, mid - newW / 2);
    const ne = Math.min(d, ns + newW);
    setViewStart(ns);
    setViewEnd(ne);
  }, []);

  const handleZoomOut = useCallback(() => {
    const { viewStart: vs, viewEnd: ve, duration: d } = viewRef.current;
    if (!d) return;
    const w = ve - vs;
    const mid = (vs + ve) / 2;
    // Find the smallest preset that is strictly larger than the current window and ≤ duration
    const larger = ZOOM_PRESETS.filter(l => l > w + 0.5 && l <= d);
    if (!larger.length) { setViewStart(0); setViewEnd(d); return; }
    const newW = larger[0];
    const ns = Math.max(0, mid - newW / 2);
    const ne = Math.min(d, ns + newW);
    setViewStart(ns);
    setViewEnd(ne);
  }, []);

  const handleZoomReset = useCallback(() => {
    const { duration: d } = viewRef.current;
    setViewStart(0);
    setViewEnd(d);
  }, []);

  const handleVideoLoaded = (e) => {
    const dur = e.target.duration;
    setVideoDuration(dur);
    // Default range: first 10 s (or full video if shorter)
    setRangeStart(0);
    setRangeEnd(Math.min(10, dur));
    // Default view: full video
    setViewStart(0);
    setViewEnd(dur);
  };

  const handleAddSegment = (label) => {
    const startTime = parseFloat(rangeStart.toFixed(3));
    const endTime = parseFloat(rangeEnd.toFixed(3));
    if (endTime - startTime < 0.1) return;
    setCapturedSegments(prev => [...prev, { startTime, endTime, label }]);
  };

  const handleDeleteSegment = (index) => {
    setCapturedSegments(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmitSamples = async () => {
    setSubmittingSamples(true);
    setSampleError(null);
    try {
      // Send the exact data points shown in the scatter — no backend re-extraction.
      await submitSamples(currentSessionPoints);
      const status = await getCalibrationStatus();
      setCalStatus(status);
      setCapturedSegments([]); // clear current session; data is now on the server
      setStep(3);
    } catch (e) {
      setSampleError(e.response?.data?.detail || 'Failed to submit samples. Please try again.');
    } finally {
      setSubmittingSamples(false);
    }
  };

  // ─── Step 3 helpers ──────────────────────────────────────────────────────

  const handleResetSamples = async () => {
    setResetting(true);
    try {
      await resetSamples();
      const status = await getCalibrationStatus();
      setCalStatus(status);
    } catch {
      // silently ignore
    } finally {
      setResetting(false);
    }
  };

  // ─── Step 4 helpers ──────────────────────────────────────────────────────

  const handleTrain = async () => {
    setTraining(true);
    setTrainPlots(null);
    setStep(4);
    try {
      const result = await trainModel();
      setTrainResult(result);
      setTrainPlots(result.plots || null);
      setCalStatus(await getCalibrationStatus());
    } catch (e) {
      setTrainResult({
        success: false,
        message: e.response?.data?.detail || 'Training failed. Please try again.',
      });
    } finally {
      setTraining(false);
    }
  };

  const handleReanalyze = async () => {
    try {
      const { job_id } = await requestReanalysis(selectedJobId);
      navigate(`/job/${job_id}`);
    } catch (e) {
      alert(e.response?.data?.detail || 'Re-analysis request failed.');
    }
  };

  // ─── Derived state ────────────────────────────────────────────────────────

  // Per-class total seconds from current capturedSegments
  const secondsByClass = Object.fromEntries(
    GAZE_CLASS_NAMES.map(cls => [
      cls,
      capturedSegments
        .filter(s => s.label === cls)
        .reduce((sum, s) => sum + (s.endTime - s.startTime), 0),
    ])
  );
  const allClassesReady = MANDATORY_CLASS_NAMES.every(
    cls => (secondsByClass[cls] || 0) >= MIN_SECONDS_PER_CLASS
  );
  // Must have actual data points computed (not just time; segments might span no analysed frames)
  const hasCurrentPoints = currentSessionPoints.length > 0;

  // Step 3 train button condition
  const sampleCounts = calStatus?.sample_counts || {};
  const allClassesMeetMinimum = MANDATORY_CLASS_NAMES.every(cls => (sampleCounts[cls] || 0) >= MIN_SAMPLES);

  const faceVideoUrl = jobStatus?.face_url ? getFileUrl(jobStatus.face_url) : null;

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <h2 className="page-title mb-1">Personal Gaze Calibration</h2>
      <p className="text-muted mb-4" style={{ fontSize: '0.95rem' }}>
        Train a gaze model tuned to your camera angle for more accurate results.
      </p>

      <StepIndicator current={step} onStepClick={handleStepClick} />

      {/* ── Step 1: Select a job ─────────────────────────────────────────── */}
      {step === 1 && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header">
            <h4>Step 1: Choose a Completed Analysis</h4>
            <p className="text-muted small mb-0">
              Pick one of your completed analyses. Pose data is already extracted — no reprocessing needed.
            </p>
          </div>
          <div className="card-body">
            {analyses.length === 0 ? (
              <div className="alert alert-cyber">
                No completed analyses found. Upload and analyse a video first, then return here to calibrate.
              </div>
            ) : (
              <div className="mb-3">
                <label className="form-label text-muted">Analysis job</label>
                <select
                  className="form-select"
                  value={selectedJobId}
                  onChange={e => setSelectedJobId(e.target.value)}
                >
                  <option value="">-- Select an analysis --</option>
                  {analyses.map(a => (
                    <option key={a.id} value={a.id}>{a.name || a.id}</option>
                  ))}
                </select>
              </div>
            )}

            {loadingJob && <p className="text-muted small mb-3">Loading job info…</p>}

            {selectedJobId && jobStatus && !jobStatus.face_url && (
              <div className="alert alert-cyber-danger py-2 mb-3">
                This job has no face video on the server. Please choose another analysis.
              </div>
            )}

            <button
              className="btn btn-cyber-primary fw-bold"
              disabled={!selectedJobId || !faceVideoUrl}
              onClick={() => setStep(2)}
            >
              NEXT: LABEL CLIPS
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Label segments ────────────────────────────────────────── */}
      {step === 2 && faceVideoUrl && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header">
            <h4>Step 2: Label Gaze Clips</h4>
            <p className="text-muted small mb-0">
              Drag the handles on the timeline bar to select a time range, then click the gaze label below.
              You need at least <strong className="text-white">{MIN_SECONDS_PER_CLASS}s</strong> per class —
              clips can be spread across different parts of the video.
            </p>
          </div>
          <div className="card-body">

            {/* Face video + canvas overlay */}
            <div style={{ maxWidth: 480, margin: '0 auto 0.75rem' }}>
              <div style={{ position: 'relative' }}>
                <video
                  ref={faceVideoRef}
                  src={faceVideoUrl}
                  controls
                  style={{ width: '100%', display: 'block', borderRadius: 4, background: '#000', border: '1px solid var(--border-color)' }}
                  onLoadedMetadata={handleVideoLoaded}
                  onTimeUpdate={e => {
                    const t = e.target.currentTime;
                    setCurrentTime(t);
                    setCurrentFrameInfo(findCurrentFrame(t));
                  }}
                  playsInline
                  webkit-playsinline="true"
                />
                {/* Nose-direction arrow overlay */}
                <canvas
                  ref={canvasRef}
                  style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', borderRadius: 4 }}
                />
              </div>
              {/* Yaw / Pitch / Roll live card */}
              {currentFrameInfo?.face_info && (() => {
                const fi = currentFrameInfo.face_info;
                return (
                  <div className="d-flex gap-2 mt-1" style={{ fontSize: '0.8rem' }}>
                    {[['YAW', fi.yaw], ['PITCH', fi.pitch], ['ROLL', fi.roll]].map(([name, val]) => (
                      <div key={name} className="analysis-item-modern flex-fill text-center py-1 px-2 rounded" style={{ fontFamily: 'monospace' }}>
                        <span className="text-muted" style={{ fontSize: '0.68rem', letterSpacing: '0.5px' }}>{name}</span>
                        <div style={{ fontWeight: 700, color: '#00d9ff' }}>
                          {val != null ? `${Math.round(val)}°` : '—'}
                        </div>
                      </div>
                    ))}
                    <div className="analysis-item-modern flex-fill text-center py-1 px-2 rounded" style={{ minWidth: 90 }}>
                      <span className="text-muted" style={{ fontSize: '0.68rem', letterSpacing: '0.5px' }}>LABEL</span>
                      <div style={{ fontWeight: 600, fontSize: '0.75rem', color: GAZE_STATES[fi.label]?.color || 'var(--text-muted)' }}>
                        {fi.label || '—'}
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Existing gaze reference bar — acts as minimap for panning the zoom window */}
            {gazeSegments.length > 0 && videoDuration > 0 && (
              <div className="mb-1">
                <div className="d-flex justify-content-between align-items-baseline mb-1">
                  <p className="text-muted small mb-0" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.72rem' }}>
                    Existing gaze analysis — drag highlight to pan timeline
                  </p>
                  {/* Legend inline */}
                  <div className="d-flex flex-wrap gap-2" style={{ fontSize: '0.7rem' }}>
                    {GAZE_CLASS_NAMES.filter(cls => gazeSegments.some(s => s.label === cls)).map(cls => (
                      <span key={cls} style={{ color: GAZE_STATES[cls]?.color }}>
                        {GAZE_STATES[cls]?.icon} {cls}
                      </span>
                    ))}
                  </div>
                </div>
                <div
                  ref={minimapRef}
                  style={{ position: 'relative', height: 20, borderRadius: 4, background: 'var(--bg-panel-lighter)', border: '1px solid var(--border-color)', overflow: 'hidden', marginBottom: 2, cursor: 'pointer' }}
                  onClick={(e) => {
                    // Clicking the minimap (outside the viewport indicator) centers the view there
                    if (minimapDragRef.current) return;
                    const rect = minimapRef.current.getBoundingClientRect();
                    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                    const t = frac * videoDuration;
                    const w = viewEnd - viewStart;
                    const ns = Math.max(0, Math.min(videoDuration - w, t - w / 2));
                    setViewStart(ns);
                    setViewEnd(Math.min(videoDuration, ns + w));
                  }}
                >
                  {/* Gaze color segments */}
                  {gazeSegments.map((seg, i) => (
                    <div
                      key={i}
                      title={`${seg.label} (${seg.startTime.toFixed(1)}s – ${seg.endTime.toFixed(1)}s)`}
                      style={{
                        position: 'absolute',
                        top: 0,
                        bottom: 0,
                        left: `${(seg.startTime / videoDuration) * 100}%`,
                        width: `${Math.max(0, ((seg.endTime - seg.startTime) / videoDuration) * 100)}%`,
                        background: GAZE_STATES[seg.label]?.color || '#888',
                        opacity: 0.7,
                        pointerEvents: 'none',
                      }}
                    />
                  ))}
                  {/* Range start marker */}
                  <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${(rangeStart / videoDuration) * 100}%`, width: 2, background: '#00d9ff', pointerEvents: 'none' }} />
                  {/* Range end marker */}
                  <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${(rangeEnd / videoDuration) * 100}%`, width: 2, background: '#00d9ff', pointerEvents: 'none' }} />
                </div>
                {/* Zoom-window bracket — white line with vertical bars, 2px below the bar */}
                {viewEnd > viewStart && viewEnd > 0 && (
                  <div
                    title="Drag to pan timeline"
                    style={{ position: 'relative', height: 8, marginBottom: 4, cursor: 'grab' }}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      const rect = minimapRef.current.getBoundingClientRect();
                      const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                      minimapDragRef.current = { offsetSecs: frac * videoDuration - viewStart };
                    }}
                  >
                    {/* Left vertical bar */}
                    <div style={{ position: 'absolute', left: `${(viewStart / videoDuration) * 100}%`, top: 0, width: 2, height: '100%', background: 'rgba(255,255,255,0.85)', borderRadius: 1 }} />
                    {/* Horizontal connecting line */}
                    <div style={{ position: 'absolute', left: `${(viewStart / videoDuration) * 100}%`, width: `${((viewEnd - viewStart) / videoDuration) * 100}%`, top: '50%', height: 2, background: 'rgba(255,255,255,0.85)', transform: 'translateY(-50%)' }} />
                    {/* Right vertical bar */}
                    <div style={{ position: 'absolute', left: `${(viewEnd / videoDuration) * 100}%`, top: 0, width: 2, height: '100%', background: 'rgba(255,255,255,0.85)', borderRadius: 1 }} />
                  </div>
                )}
                {/* Triangle markers — show rangeStart / rangeEnd positions on the full timeline */}
                <div style={{ position: 'relative', height: 10, marginBottom: 4 }}>
                  <div title={`Selection start: ${rangeStart.toFixed(2)}s`} style={{ position: 'absolute', left: `${(rangeStart / videoDuration) * 100}%`, transform: 'translateX(-50%)', top: 0, width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderBottom: '8px solid var(--accent-primary)', pointerEvents: 'none' }} />
                  <div title={`Selection end: ${rangeEnd.toFixed(2)}s`} style={{ position: 'absolute', left: `${(rangeEnd / videoDuration) * 100}%`, transform: 'translateX(-50%)', top: 0, width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderBottom: '8px solid var(--accent-primary)', pointerEvents: 'none' }} />
                </div>
              </div>
            )}

            {/* Zoom controls + timeline */}
            {videoDuration > 0 && (
              <div className="d-flex align-items-center gap-2 mb-2">
                <span className="text-muted" style={{ fontSize: '0.78rem' }}>Timeline zoom:</span>
                <button
                  className="btn btn-sm btn-cyber py-0 px-2"
                  style={{ fontSize: '1rem', lineHeight: 1.2, minWidth: 30 }}
                  onClick={handleZoomIn}
                  title="Zoom in (show less time, finer control)"
                >＋</button>
                <button
                  className="btn btn-sm btn-cyber py-0 px-2"
                  style={{ fontSize: '1rem', lineHeight: 1.2, minWidth: 30 }}
                  onClick={handleZoomOut}
                  title="Zoom out (show more time)"
                >－</button>
                <button
                  className="btn btn-sm btn-cyber py-0 px-2"
                  style={{ fontSize: '0.75rem' }}
                  onClick={handleZoomReset}
                  title="Show full video"
                >Reset</button>
                <span className="text-muted ms-1" style={{ fontSize: '0.75rem' }}>
                  {viewEnd > viewStart && viewEnd - viewStart < videoDuration - 0.5
                    ? `${Math.round(viewEnd - viewStart)}s window`
                    : 'full video'}
                </span>
              </div>
            )}

            {/* Range-selecting timeline */}
            <CalibrationTimeline
              duration={videoDuration}
              segments={capturedSegments}
              rangeStart={rangeStart}
              rangeEnd={rangeEnd}
              onRangeChange={handleRangeChange}
              onSeek={handleSeek}
              currentTime={currentTime}
              viewStart={viewEnd > 0 ? viewStart : undefined}
              viewEnd={viewEnd > 0 ? viewEnd : undefined}
              onViewChange={handleViewChange}
            />

            {/* Selection info */}
            <p className="text-muted small text-center mb-3" style={{ marginTop: '1.5rem' }}>
              Selected range:{' '}
              <strong className="text-white">{rangeStart.toFixed(1)}s – {rangeEnd.toFixed(1)}s</strong>
              <span className="ms-2 opacity-75">({(rangeEnd - rangeStart).toFixed(1)}s)</span>
            </p>

            {/* Gaze class label buttons */}
            <p className="text-muted small text-center mb-2" style={{ letterSpacing: '0.5px', textTransform: 'uppercase', fontSize: '0.75rem' }}>
              Label selected range as:
            </p>
            <div className="d-flex flex-wrap gap-2 justify-content-center mb-4">
              {GAZE_CLASS_NAMES.map(cls => (
                <button
                  key={cls}
                  className="btn btn-cyber"
                  style={{ borderColor: GAZE_STATES[cls]?.color, color: GAZE_STATES[cls]?.color, minWidth: 135 }}
                  onClick={() => handleAddSegment(cls)}
                >
                  {GAZE_STATES[cls]?.icon} {cls}
                </button>
              ))}
            </div>

            {/* Live Yaw vs Pitch scatter — current session only */}
            {currentSessionPoints.length > 0 && (() => {
              const yaws    = currentSessionPoints.map(p => p.yaw);
              const pitches = currentSessionPoints.map(p => p.pitch);
              const yMin = Math.min(...yaws)   - 8, yMax = Math.max(...yaws)   + 8;
              const pMin = Math.min(...pitches) - 8, pMax = Math.max(...pitches) + 8;
              const W = 340, H = 200, pad = 32;
              const toX = v => pad + ((v - yMin) / (yMax - yMin)) * (W - 2 * pad);
              const toY = v => H - pad - ((v - pMin) / (pMax - pMin)) * (H - 2 * pad);
              return (
                <div className="mb-3">
                  <p className="text-muted small mb-1" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.72rem' }}>
                    Labeled samples — Yaw vs Pitch ({currentSessionPoints.length} frames)
                  </p>
                  <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', background: 'var(--bg-panel-lighter)', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                    {/* Axes */}
                    <line x1={pad} y1={pad} x2={pad} y2={H-pad} stroke="#374151" strokeWidth={1}/>
                    <line x1={pad} y1={H-pad} x2={W-pad} y2={H-pad} stroke="#374151" strokeWidth={1}/>
                    {/* Zero lines if in range */}
                    {yMin < 0 && yMax > 0 && <line x1={toX(0)} y1={pad} x2={toX(0)} y2={H-pad} stroke="#4b5563" strokeWidth={1} strokeDasharray="4,3"/>}
                    {pMin < 0 && pMax > 0 && <line x1={pad} y1={toY(0)} x2={W-pad} y2={toY(0)} stroke="#4b5563" strokeWidth={1} strokeDasharray="4,3"/>}
                    {currentSessionPoints.map((p, i) => (
                      <circle key={i} cx={toX(p.yaw)} cy={toY(p.pitch)} r={2.5}
                        fill={GAZE_STATES[p.label]?.color || '#888'} opacity={0.8}/>
                    ))}
                    {/* Axis labels */}
                    <text x={W/2} y={H-4} fill="#6b7280" fontSize={9} textAnchor="middle">Yaw (°)</text>
                    <text x={8} y={H/2} fill="#6b7280" fontSize={9} textAnchor="middle" transform={`rotate(-90,8,${H/2})`}>Pitch (°)</text>
                    <text x={pad} y={H-4} fill="#4b5563" fontSize={8} textAnchor="middle">{Math.round(yMin)}</text>
                    <text x={W-pad} y={H-4} fill="#4b5563" fontSize={8} textAnchor="middle">{Math.round(yMax)}</text>
                  </svg>
                </div>
              );
            })()}

            {/* Per-class progress cards */}
            <div className="mb-4">
              <p className="text-muted small mb-2" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.75rem' }}>
                Progress per class ({MIN_SECONDS_PER_CLASS}s required each)
              </p>
              <div className="d-flex flex-wrap gap-2">
                {GAZE_CLASS_NAMES.map(cls => {
                  const secs = secondsByClass[cls] || 0;
                  const mandatory = MANDATORY_CLASS_NAMES.includes(cls);
                  const ok = secs >= MIN_SECONDS_PER_CLASS;
                  return (
                    <div
                      key={cls}
                      className="analysis-item-modern px-3 py-2 rounded"
                      style={{ flex: '1 0 calc(50% - 0.5rem)', minWidth: 140 }}
                    >
                      <div className="d-flex justify-content-between align-items-center mb-1">
                        <span style={{ color: GAZE_STATES[cls]?.color, fontSize: '0.82rem', fontWeight: 600 }}>
                          {GAZE_STATES[cls]?.icon} {cls}
                          {!mandatory && (
                            <span className="ms-1 text-muted fw-normal" style={{ fontSize: '0.7rem' }}>(optional)</span>
                          )}
                        </span>
                        <span
                          style={{
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            color: ok ? 'var(--accent-success)' : 'var(--text-muted)',
                          }}
                        >
                          {secs.toFixed(1)}s{mandatory ? ` / ${MIN_SECONDS_PER_CLASS}s` : ''}
                        </span>
                      </div>
                      {/* Mini progress bar */}
                      {mandatory && (
                        <div style={{ height: 4, background: 'var(--bg-panel-lighter)', borderRadius: 2 }}>
                          <div
                            style={{
                              height: '100%',
                              width: `${Math.min(100, (secs / MIN_SECONDS_PER_CLASS) * 100)}%`,
                              background: ok ? 'var(--accent-success)' : (GAZE_STATES[cls]?.color || 'var(--accent-primary)'),
                              borderRadius: 2,
                              transition: 'width 0.2s',
                            }}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Labelled clips list */}
            {capturedSegments.length > 0 && (
              <div className="mb-4">
                <p className="text-muted small mb-2" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.75rem' }}>
                  Labelled clips ({capturedSegments.length})
                </p>
                <div style={{ maxHeight: 180, overflowY: 'auto' }}>
                  {capturedSegments.map((seg, i) => (
                    <div
                      key={i}
                      className="analysis-item-modern d-flex justify-content-between align-items-center p-2 px-3 mb-1 rounded"
                    >
                      <span>
                        <span style={{ color: GAZE_STATES[seg.label]?.color, fontWeight: 600 }}>
                          {GAZE_STATES[seg.label]?.icon} {seg.label}
                        </span>
                        <span className="text-muted ms-2" style={{ fontSize: '0.85rem' }}>
                          {seg.startTime.toFixed(1)}s – {seg.endTime.toFixed(1)}s
                          <span className="ms-1 opacity-75">({(seg.endTime - seg.startTime).toFixed(1)}s)</span>
                        </span>
                      </span>
                      <button
                        className="btn btn-sm btn-cyber py-0 px-2"
                        style={{ fontSize: '0.78rem' }}
                        onClick={() => handleDeleteSegment(i)}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sampleError && (
              <div className="alert alert-cyber-danger py-2 mb-3">{sampleError}</div>
            )}

            <div className="d-flex gap-2">
              <button className="btn btn-cyber" onClick={() => setStep(1)}>
                BACK
              </button>
              <button
                className="btn btn-cyber-primary fw-bold"
                disabled={!allClassesReady || !hasCurrentPoints || submittingSamples}
                title={!allClassesReady ? `Select at least ${MIN_SECONDS_PER_CLASS}s each for: ${MANDATORY_CLASS_NAMES.join(', ')}` : (!hasCurrentPoints ? 'No analysed frames found in selected ranges' : '')}
                onClick={handleSubmitSamples}
              >
                {submittingSamples ? (
                  <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />SUBMITTING…</>
                ) : 'SUBMIT & REVIEW'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Step 3: Review ───────────────────────────────────────────────── */}
      {step === 3 && calStatus && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header">
            <h4>Step 3: Review Samples</h4>
            <p className="text-muted small mb-0">
              You need at least {MIN_SAMPLES} samples per gaze class to train the model.
            </p>
          </div>
          <div className="card-body">
            <table
              className="table table-sm mb-1"
              style={{
                '--bs-table-color': 'var(--text-main)',
                '--bs-table-bg': 'transparent',
                '--bs-table-border-color': 'var(--border-color)',
              }}
            >
              <thead>
                <tr>
                  <th className="text-muted fw-normal" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Gaze Class</th>
                  <th className="text-muted fw-normal" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Samples</th>
                  <th className="text-muted fw-normal" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {GAZE_CLASS_NAMES.map(cls => {
                  const count = sampleCounts[cls] || 0;
                  const mandatory = MANDATORY_CLASS_NAMES.includes(cls);
                  const ok = count >= MIN_SAMPLES;
                  return (
                    <tr key={cls}>
                      <td>
                        <span style={{ color: GAZE_STATES[cls]?.color, marginRight: 6 }}>
                          {GAZE_STATES[cls]?.icon}
                        </span>
                        {cls}
                        {!mandatory && <span className="text-muted ms-1" style={{ fontSize: '0.75rem' }}>(optional)</span>}
                      </td>
                      <td>{count}</td>
                      <td>
                        {ok
                          ? <span style={{ color: 'var(--accent-success)' }}>✓ Ready</span>
                          : mandatory
                            ? <span style={{ color: 'var(--accent-warning)' }}>Need {MIN_SAMPLES - count} more</span>
                            : <span className="text-muted">Optional</span>
                        }
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <p className="text-muted small mb-4">
              Total samples collected: <strong className="text-white">{calStatus.total_samples}</strong>
            </p>

            <div className="d-flex gap-2 flex-wrap">
              <button className="btn btn-cyber" onClick={() => setStep(2)}>
                BACK: CAPTURE MORE
              </button>
              <button
                className="btn btn-cyber"
                style={{ borderColor: 'var(--accent-danger)', color: 'var(--accent-danger)' }}
                disabled={resetting}
                onClick={handleResetSamples}
              >
                {resetting ? 'CLEARING…' : 'CLEAR ALL SAMPLES'}
              </button>
              <button
                className="btn btn-cyber-primary fw-bold ms-auto"
                disabled={!allClassesMeetMinimum}
                title={!allClassesMeetMinimum ? `Need at least ${MIN_SAMPLES} samples per class` : ''}
                onClick={handleTrain}
              >
                TRAIN MODEL
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Step 4: Training result ──────────────────────────────────────── */}
      {step === 4 && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header">
            <h4>{training ? 'Training Model…' : trainResult?.success ? 'Model Trained' : 'Training Failed'}</h4>
          </div>
          <div className="card-body">
            {training ? (
              <div className="text-center py-4">
                <div className="spinner-border mb-3" role="status" aria-hidden="true" />
                <p className="text-muted mb-0">Training your personal gaze model…</p>
              </div>
            ) : (
              <>
                <p className="text-muted mb-4">{trainResult?.message}</p>

                {trainResult?.success ? (
                  <>
                    {/* Diagnostic plots */}
                    {trainPlots && (
                      <div className="mb-4">
                        <p className="text-muted small mb-2" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.75rem' }}>
                          Training Diagnostics
                        </p>
                        <div className="row g-3 mb-2">
                          {[
                            { key: 'head_pose',         label: 'Yaw vs Pitch' },
                            { key: 'pca',               label: 'PCA Projection' },
                          ].map(({ key, label }) => trainPlots[key] && (
                            <div key={key} className="col-12 col-md-6">
                              <p className="text-muted mb-1" style={{ fontSize: '0.75rem', textAlign: 'center' }}>{label}</p>
                              <img src={trainPlots[key]} alt={label} style={{ width: '100%', borderRadius: 6, border: '1px solid var(--border-color)' }}/>
                            </div>
                          ))}
                        </div>
                        {trainPlots.decision_boundary && (
                          <div className="mb-2">
                            <p className="text-muted mb-1" style={{ fontSize: '0.75rem', textAlign: 'center' }}>SVM Decision Boundary</p>
                            <img src={trainPlots.decision_boundary} alt="SVM Decision Boundary" style={{ width: '100%', borderRadius: 6, border: '1px solid var(--border-color)' }}/>
                          </div>
                        )}
                        <p className="text-muted" style={{ fontSize: '0.78rem' }}>
                          If classes overlap heavily in the SVM boundary plot, add more varied samples from borderline positions and retrain.
                        </p>
                      </div>
                    )}
                    <div className="d-flex gap-2 flex-wrap">
                      <button className="btn btn-cyber" onClick={() => setStep(2)}>
                        ADD MORE SAMPLES
                      </button>
                      <button className="btn btn-cyber-primary fw-bold" onClick={handleReanalyze}>
                        RE-ANALYSE WITH NEW MODEL
                      </button>
                      <button className="btn btn-cyber" onClick={() => navigate('/analyze')}>
                        UPLOAD NEW VIDEO
                      </button>
                    </div>
                  </>
                ) : (
                  <button className="btn btn-cyber" onClick={() => setStep(3)}>
                    BACK TO REVIEW
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default CalibrationPage;
