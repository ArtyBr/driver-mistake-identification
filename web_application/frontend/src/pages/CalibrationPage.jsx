import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { listAnalyses, getJobStatus, getFileUrl, getJobResults } from '../services/api';
import {
  listCalibrations,
  createCalibration,
  renameCalibration,
  deleteCalibration,
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
const MIN_SAMPLES = 3; 
const ZOOM_PRESETS = [1, 5, 15, 30, 60, 120, 300, 600];

function CalibrationPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [step, setStep] = useState(0);

  // Step 0: Manage Calibrations
  const [calibrations, setCalibrations] = useState([]);
  const [selectedCalId, setSelectedCalId] = useState('');
  const [loadingCals, setLoadingCals] = useState(false);

  // Step 1: Select Job
  const [analyses, setAnalyses] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [jobStatus, setJobStatus] = useState(null);
  const [loadingJob, setLoadingJob] = useState(false);

  // Step 2+: Video and Labeling
  const faceVideoRef = useRef(null);
  const [videoDuration, setVideoDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [rangeStart, setRangeStart] = useState(0);
  const [rangeEnd, setRangeEnd] = useState(10);
  const [gazeSegments, setGazeSegments] = useState([]);
  const [viewStart, setViewStart] = useState(0);
  const [viewEnd, setViewEnd] = useState(0);
  const minimapRef = useRef(null);
  const minimapDragRef = useRef(null); // null | { offsetSecs }
  const minimapMarkerDragRef = useRef(null); // null | 'start' | 'end'
  const viewRef = useRef({ viewStart: 0, viewEnd: 0, duration: 0 });
  const rangeRef = useRef({ rangeStart: 0, rangeEnd: 10 });
  const frameTimesRef = useRef([]);
  const frameDataRef = useRef([]);
  const canvasRef = useRef(null);
  const [currentFrameInfo, setCurrentFrameInfo] = useState(null);
  const [capturedSegments, setCapturedSegments] = useState([]);
  const [hoveredSegmentIndex, setHoveredSegmentIndex] = useState(null);
  const [submittingSamples, setSubmittingSamples] = useState(false);
  const [sampleError, setSampleError] = useState(null);
  const [calStatus, setCalStatus] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState(null);
  const [trainPlots, setTrainPlots] = useState(null);

  useEffect(() => {
    viewRef.current = { viewStart, viewEnd, duration: videoDuration };
  }, [viewStart, viewEnd, videoDuration]);

  useEffect(() => {
    rangeRef.current = { rangeStart, rangeEnd };
  }, [rangeStart, rangeEnd]);

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

  const snapToFrame = useCallback((t) => {
    const times = frameTimesRef.current;
    if (!times.length) return parseFloat(t.toFixed(3));
    let lo = 0, hi = times.length - 1;
    while (lo < hi - 1) {
      const mid = (lo + hi) >> 1;
      if (times[mid] <= t) lo = mid; else hi = mid;
    }
    return Math.abs(t - times[lo]) <= Math.abs(t - times[hi]) ? times[lo] : times[hi];
  }, []);

  const handleRangeChange = useCallback((s, e) => { setRangeStart(snapToFrame(s)); setRangeEnd(snapToFrame(e)); }, [snapToFrame]);
  const handleSeek = useCallback((t) => { if (faceVideoRef.current) faceVideoRef.current.currentTime = t; }, []);

  // Minimap drag — pans the zoom window
  useEffect(() => {
    const handleMove = (e) => {
      const rect = minimapRef.current?.getBoundingClientRect();
      if (!rect) return;
      const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const { duration: d } = viewRef.current;
      const t = frac * d;

      if (minimapDragRef.current) {
        const { viewStart: vs, viewEnd: ve } = viewRef.current;
        const w = ve - vs;
        const ns = Math.max(0, Math.min(d - w, t - minimapDragRef.current.offsetSecs));
        setViewStart(ns);
        setViewEnd(Math.min(d, ns + w));
      } else if (minimapMarkerDragRef.current) {
        const { rangeStart: rs, rangeEnd: re } = rangeRef.current;
        if (minimapMarkerDragRef.current === 'start') {
          const ns = Math.max(0, Math.min(t, re - 0.1));
          handleRangeChange(ns, re);
          handleSeek(ns);
        } else {
          const ne = Math.min(d, Math.max(t, rs + 0.1));
          handleRangeChange(rs, ne);
          handleSeek(ne);
        }
      }
    };
    const handleUp = () => { 
      minimapDragRef.current = null; 
      minimapMarkerDragRef.current = null;
    };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [handleRangeChange, handleSeek]);

  const refreshCalibrations = useCallback(async () => {
    setLoadingCals(true);
    try {
      const data = await listCalibrations();
      setCalibrations(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to load calibrations", err);
      setCalibrations([]);
    } finally {
      setLoadingCals(false);
    }
  }, []);

  useEffect(() => {
    refreshCalibrations();
    listAnalyses()
      .then(data => setAnalyses(Array.isArray(data) ? data.filter(a => !a.is_demo) : []))
      .catch(() => {});
  }, [refreshCalibrations]);

  // Handle incoming navigation from ResultPage
  useEffect(() => {
    const handleAutoRedirect = async () => {
      if (location.state?.jobId) {
        setSelectedJobId(location.state.jobId);
        
        let calId = location.state.calibrationId;
        
        if (!calId) {
          try {
            const existing = await listCalibrations();
            if (Array.isArray(existing) && existing.length > 0) {
              calId = existing[0].id; 
            } else {
              const newCal = await createCalibration("Calibration 1");
              calId = newCal.id;
            }
          } catch (err) {
            console.error("Auto-calibration setup failed", err);
          }
        }
        
        if (calId) {
          setSelectedCalId(calId);
          setStep(2); 
        }
      }
    };
    
    handleAutoRedirect();
  }, [location.state]);

  useEffect(() => {
    if (!selectedJobId) return;
    setLoadingJob(true);
    getJobStatus(selectedJobId)
      .then(setJobStatus)
      .catch(() => setJobStatus(null))
      .finally(() => setLoadingJob(false));

    getJobResults(selectedJobId)
      .then(results => {
        const frames = (results?.frame_data || []).filter(f => typeof f.time === 'number');
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
        frameDataRef.current = frames;
        frameTimesRef.current = frames.map(f => f.time);
      })
      .catch(() => { setGazeSegments([]); frameTimesRef.current = []; frameDataRef.current = []; });
  }, [selectedJobId]);

  useEffect(() => {
    if (selectedCalId) {
      getCalibrationStatus(selectedCalId).then(setCalStatus).catch(() => {});
    }
  }, [selectedCalId]);

  const handleCreateCal = async () => {
    const name = prompt("Enter a name for the new calibration:", "Calibration " + (calibrations.length + 1));
    if (name) {
      try {
        const newCal = await createCalibration(name);
        await refreshCalibrations();
        setSelectedCalId(newCal.id);
      } catch (err) { console.error("Create failed", err); }
    }
  };

  const handleRenameCal = async (id, oldName) => {
    const newName = prompt("Enter new name:", oldName);
    if (newName && newName !== oldName) {
      try {
        await renameCalibration(id, newName);
        await refreshCalibrations();
      } catch (err) { console.error("Rename failed", err); }
    }
  };

  const handleDeleteCal = async (id, name) => {
    if (window.confirm("Delete calibration \"" + name + "\"? This cannot be undone.")) {
      try {
        await deleteCalibration(id);
        if (selectedCalId === id) setSelectedCalId('');
        await refreshCalibrations();
      } catch (err) { console.error("Delete failed", err); }
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    const video  = faceVideoRef.current;
    if (!canvas || !video) return;
    const w = canvas.offsetWidth, h = canvas.offsetHeight;
    if (!w || !h) return;
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, w, h);
    const fi = currentFrameInfo?.face_info;
    if (!fi?.nose_2d) return;
    const vW = video.videoWidth || 640, vH = video.videoHeight || 480;
    drawGazeLine(ctx, fi.nose_2d, fi.yaw ?? 0, fi.pitch ?? 0, vW, vH, w, h, GAZE_STATES[fi.label]?.color || '#00d9ff');
  }, [currentFrameInfo]);

  const currentSessionPoints = useMemo(() => {
    const points = [];
    for (const seg of capturedSegments) {
      const matched = frameDataRef.current.filter(f => f.time >= seg.startTime && f.time <= seg.endTime && f.face_info?.yaw != null);
      matched.forEach(f => points.push({ yaw: f.face_info.yaw, pitch: f.face_info.pitch, roll: f.face_info.roll ?? 0, label: seg.label }));
    }
    return points;
  }, [capturedSegments]);

  const handleZoom = (factor) => {
    const { viewStart: vs, viewEnd: ve, duration: d } = viewRef.current;
    if (!d) return;
    const w = ve - vs, mid = (vs + ve) / 2;
    let newW;
    if (factor < 1) {
      const smaller = ZOOM_PRESETS.filter(l => l < w - 0.5);
      newW = smaller.length ? smaller[smaller.length - 1] : Math.max(1, d * 0.02);
    } else {
      const larger = ZOOM_PRESETS.filter(l => l > w + 0.5 && l <= d);
      newW = larger.length ? larger[0] : d;
    }
    const ns = Math.max(0, mid - newW / 2), ne = Math.min(d, ns + newW);
    setViewStart(ns); setViewEnd(ne);
  };

  const handleAddSegment = (label) => {
    const s = parseFloat(rangeStart.toFixed(3)), e = parseFloat(rangeEnd.toFixed(3));
    if (e - s < 0.1) return;
    setCapturedSegments(prev => [...prev, { startTime: s, endTime: e, label }]);
  };

  const handleDeleteSegment = (index) => {
    setCapturedSegments(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmitSamples = async () => {
    setSubmittingSamples(true); setSampleError(null);
    try {
      await submitSamples(selectedCalId, currentSessionPoints);
      setCalStatus(await getCalibrationStatus(selectedCalId));
      setCapturedSegments([]); setStep(3);
    } catch (e) { setSampleError(e.response?.data?.detail || 'Submission failed.'); }
    finally { setSubmittingSamples(false); }
  };

  const handleResetSamples = async () => {
    setResetting(true);
    try { 
      await resetSamples(selectedCalId); 
      setCalStatus(await getCalibrationStatus(selectedCalId)); 
    } catch (err) {
      console.error("Reset failed", err);
    } finally { setResetting(false); }
  };

  const handleTrain = async () => {
    setTraining(true); setStep(4);
    try {
      const res = await trainModel(selectedCalId);
      setTrainResult(res); setTrainPlots(res.plots);
      setCalStatus(await getCalibrationStatus(selectedCalId));
    } catch (e) { setTrainResult({ success: false, message: e.response?.data?.detail || 'Training failed.' }); }
    finally { setTraining(false); }
  };

  const handleReanalyze = async () => {
    try {
      const { job_id } = await requestReanalysis(selectedJobId, selectedCalId);
      navigate('/job/' + job_id);
    } catch (e) { alert(e.response?.data?.detail || 'Re-analysis failed.'); }
  };

  const secondsByClass = Object.fromEntries(GAZE_CLASS_NAMES.map(cls => [cls, capturedSegments.filter(s => s.label === cls).reduce((sum, s) => sum + (s.endTime - s.startTime), 0)]));
  const allClassesReady = MANDATORY_CLASS_NAMES.every(cls => (secondsByClass[cls] || 0) >= MIN_SECONDS_PER_CLASS);
  const hasCurrentPoints = currentSessionPoints.length > 0;
  const sampleCounts = calStatus?.sample_counts || {};
  const allClassesMeetMinimum = MANDATORY_CLASS_NAMES.every(cls => (sampleCounts[cls] || 0) >= MIN_SAMPLES);
  const faceVideoUrl = jobStatus?.face_url ? getFileUrl(jobStatus.face_url) : null;

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <div className="d-flex justify-content-between align-items-center mb-1">
        <h2 className="page-title mb-0">Personal Gaze Calibration</h2>
        <Link to="/analyze" className="btn btn-sm btn-cyber">Back to Analyze</Link>
      </div>
      <p className="text-muted mb-4" style={{ fontSize: '0.95rem' }}>
        Fine-tune the AI to your specific camera angle and head pose.
      </p>

      <StepIndicator current={step} onStepClick={setStep} />

      {/* ── Step 0: Manage Calibrations ──────────────────────────────────── */}
      {step === 0 && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header d-flex justify-content-between align-items-center">
            <h4 className="mb-0">Step 1: Select or Create Calibration</h4>
            <button className="btn btn-cyber-primary btn-sm" onClick={handleCreateCal}>＋ NEW CALIBRATION</button>
          </div>
          <div className="card-body">
            <div className="guiding-section p-3 mb-4 rounded border border-secondary bg-panel-lighter">
              <h6 className="text-cyber-blue fw-bold mb-2">Why Calibrate?</h6>
              <p className="small text-muted mb-2">
                "Think of it like teaching a new driver where your mirrors are in your car."
              </p>
              <p className="small text-muted mb-0">
                AI models can be slightly off because every camera is at a different angle. 
                Calibration "teaches" the system what <strong>your</strong> head looks like when you check your mirrors.
              </p>
            </div>

            {loadingCals ? <div className="text-center py-4"><div className="spinner-border" /></div> : (
              <div className="list-group list-group-flush mb-4">
                {calibrations.length === 0 ? <p className="text-center text-muted py-3">No calibrations yet. Create one above!</p> : 
                  calibrations.map(c => (
                    <div key={c.id} 
                      className={"list-group-item bg-transparent border-secondary d-flex justify-content-between align-items-center p-3 mb-2 rounded border cursor-pointer " + (selectedCalId === c.id ? 'border-primary' : '')}
                      onClick={() => setSelectedCalId(c.id)}
                      style={{ transition: 'all 0.2s', backgroundColor: selectedCalId === c.id ? 'rgba(0, 217, 255, 0.05)' : 'transparent' }}
                    >
                      <div>
                        <div className="fw-bold text-white">{c.name}</div>
                        <div className="small text-muted">
                          {c.is_trained ? <span className="text-success">✓ Trained</span> : <span className="text-warning">⚠ Not Trained</span>}
                          <span className="mx-2">•</span>
                          Created {new Date(c.created_at).toLocaleDateString()}
                        </div>
                      </div>
                      <div className="d-flex gap-2">
                        <button className="btn btn-sm btn-outline-cyber" onClick={(e) => { e.stopPropagation(); handleRenameCal(c.id, c.name); }}>Rename</button>
                        <button className="btn btn-sm btn-outline-cyber border-danger text-danger" onClick={(e) => { e.stopPropagation(); handleDeleteCal(c.id, c.name); }}>Delete</button>
                      </div>
                    </div>
                  ))
                }
              </div>
            )}
            <button 
              className="btn btn-cyber-primary w-100 fw-bold" 
              disabled={!selectedCalId} 
              onClick={() => setStep(selectedJobId ? 2 : 1)}
            >
              {selectedJobId ? 'NEXT: LABEL CLIPS' : 'NEXT: SELECT VIDEO'}
            </button>
          </div>
        </div>
      )}

      {/* ── Step 1: Select Job ────────────────────────────────────────────── */}
      {step === 1 && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header">
            <h4>Step 2: Choose a Video to Reference</h4>
            <p className="small text-muted mb-0">Pick an analysis where you clearly check your mirrors. We'll use this to "map" your gaze.</p>
          </div>
          <div className="card-body">
            <select className="form-select mb-4" value={selectedJobId} onChange={e => setSelectedJobId(e.target.value)}>
              <option value="">-- Select an analysis --</option>
              {analyses.map(a => <option key={a.id} value={a.id}>{a.name || a.id}</option>)}
            </select>
            {loadingJob && <p className="text-muted small">Loading job info…</p>}
            {selectedJobId && jobStatus && !jobStatus.face_url && <div className="alert alert-cyber-danger py-2">No face video available for this job.</div>}
            
            <div className="d-flex gap-2">
              <button className="btn btn-cyber" onClick={() => setStep(0)}>BACK</button>
              <button className="btn btn-cyber-primary fw-bold ms-auto" disabled={!selectedJobId || !faceVideoUrl} onClick={() => setStep(2)}>NEXT: LABEL CLIPS</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Step 2: Label segments ────────────────────────────────────────── */}
      {step === 2 && faceVideoUrl && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header">
            <h4>Step 3: Label Gaze Clips</h4>
            <p className="small text-muted mb-0">Find moments where you are looking at a mirror, select the range, and click the label.</p>
          </div>
          <div className="card-body">
            <div className="guiding-section p-3 mb-3 rounded bg-panel-lighter border border-secondary">
              <h6 className="text-white small fw-bold mb-2">How to Label:</h6>
              <ol className="small text-muted ps-3 mb-0">
                <li className="mb-2">
                  <strong>Use the Minimap:</strong> The thin top bar shows the full video. The <strong>white bracket</strong> below it indicates the section visible in the main labeling timeline.
                </li>
                <li className="mb-2">
                  <strong>Zoom for Precision:</strong> Use the ＋ and － buttons to narrow or widen the visible section. Zooming in lets you find the exact frame where you check a mirror.
                </li>
                <li className="mb-2">
                  <strong>Select & Tag:</strong> Use the blue handles on the large timeline to highlight a steady moment. Click a mirror button (e.g. "Left Mirror") to "tag" that clip.
                </li>
                <li>
                  <strong>Check the Graph:</strong> Try to capture a wide variety of head positions for each mirror to build a robust model.
                </li>
              </ol>
            </div>

            <div className="bg-panel-darker p-3 mb-3 rounded border border-secondary text-center">
              <div style={{ position: 'relative', maxWidth: 480, margin: '0 auto' }}>
                <video ref={faceVideoRef} src={faceVideoUrl} controls className="w-100 rounded border border-secondary"
                  onLoadedMetadata={e => { setVideoDuration(e.target.duration); setViewEnd(e.target.duration); }}
                  onTimeUpdate={e => { setCurrentTime(e.target.currentTime); setCurrentFrameInfo(findCurrentFrame(e.target.currentTime)); }} />
                <canvas ref={canvasRef} style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }} />
              </div>
              {currentFrameInfo?.face_info && (
                <div className="d-flex justify-content-center gap-2 mt-2 small text-muted font-monospace">
                  <span>YAW: {Math.round(currentFrameInfo.face_info.yaw)}°</span>
                  <span>PITCH: {Math.round(currentFrameInfo.face_info.pitch)}°</span>
                  <span className="text-white fw-bold">LABEL: {currentFrameInfo.face_info.label}</span>
                </div>
              )}
            </div>

            {/* Existing gaze reference bar — acts as minimap for panning the zoom window */}
            {gazeSegments.length > 0 && videoDuration > 0 && (
              <div className="mb-3">
                <p className="text-muted small mb-1" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.72rem' }}>
                  Existing gaze analysis — click to jump or drag bracket to pan
                </p>
                <div
                  ref={minimapRef}
                  style={{ position: 'relative', height: 24, borderRadius: 4, background: 'var(--bg-panel-lighter)', border: '1px solid var(--border-color)', overflow: 'hidden', marginBottom: 2, cursor: 'pointer' }}
                  onClick={(e) => {
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
                  {/* Existing Gaze color segments (Top half) */}
                  {gazeSegments.map((seg, i) => (
                    <div
                      key={"gaze-" + i}
                      title={seg.label + " (" + (seg.startTime || 0).toFixed(1) + "s – " + (seg.endTime || 0).toFixed(1) + "s)"}
                      style={{
                        position: 'absolute',
                        top: 0, height: '60%',
                        left: ((seg.startTime || 0) / videoDuration) * 100 + "%",
                        width: Math.max(0, (((seg.endTime || 0) - (seg.startTime || 0)) / videoDuration) * 100) + "%",
                        background: GAZE_STATES[seg.label]?.color || '#888',
                        opacity: 0.5,
                        pointerEvents: 'none',
                      }}
                    />
                  ))}

                  {/* Captured Segments (Bottom half) */}
                  {capturedSegments.map((seg, i) => {
                    const isHovered = hoveredSegmentIndex === i;
                    const color = GAZE_STATES[seg.label]?.color || '#888';
                    return (
                      <div
                        key={"cap-" + i}
                        onMouseEnter={() => setHoveredSegmentIndex(i)}
                        onMouseLeave={() => setHoveredSegmentIndex(null)}
                        style={{
                          position: 'absolute',
                          bottom: 0, height: '40%',
                          left: ((seg.startTime || 0) / videoDuration) * 100 + "%",
                          width: Math.max(0, (((seg.endTime || 0) - (seg.startTime || 0)) / videoDuration) * 100) + "%",
                          background: color,
                          opacity: isHovered ? 1 : 0.8,
                          boxShadow: isHovered ? "0 0 10px " + color : 'none',
                          zIndex: isHovered ? 10 : 1
                        }}
                      />
                    );
                  })}

                  {/* Range start marker */}
                  <div style={{ position: 'absolute', top: 0, bottom: 0, left: ((rangeStart || 0) / videoDuration) * 100 + "%", width: 2, background: '#00d9ff', pointerEvents: 'none', zIndex: 11 }} />
                  {/* Range end marker */}
                  <div style={{ position: 'absolute', top: 0, bottom: 0, left: ((rangeEnd || 0) / videoDuration) * 100 + "%", width: 2, background: '#00d9ff', pointerEvents: 'none', zIndex: 11 }} />
                </div>

                {/* Zoom-window bracket — white line with vertical bars */}
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
                    <div style={{ position: 'absolute', left: (viewStart / videoDuration) * 100 + "%", top: 0, width: 2, height: '100%', background: 'rgba(255,255,255,0.85)', borderRadius: 1 }} />
                    <div style={{ position: 'absolute', left: (viewStart / videoDuration) * 100 + "%", width: ((viewEnd - viewStart) / videoDuration) * 100 + "%", top: '50%', height: 2, background: 'rgba(255,255,255,0.85)', transform: 'translateY(-50%)' }} />
                    <div style={{ position: 'absolute', left: (viewEnd / videoDuration) * 100 + "%", top: 0, width: 2, height: '100%', background: 'rgba(255,255,255,0.85)', borderRadius: 1 }} />
                  </div>
                )}

                {/* Triangle markers — show rangeStart / rangeEnd positions on the full timeline */}
                <div style={{ position: 'relative', height: 10, marginBottom: 4 }}>
                  <div 
                    title={"Selection start: " + (rangeStart || 0).toFixed(2) + "s (Drag to move)"} 
                    style={{ position: 'absolute', left: ((rangeStart || 0) / videoDuration) * 100 + "%", transform: 'translateX(-50%)', top: 0, width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderBottom: '8px solid var(--accent-primary)', cursor: 'ew-resize', zIndex: 10 }} 
                    onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); minimapMarkerDragRef.current = 'start'; }}
                  />
                  <div 
                    title={"Selection end: " + (rangeEnd || 0).toFixed(2) + "s (Drag to move)"} 
                    style={{ position: 'absolute', left: ((rangeEnd || 0) / videoDuration) * 100 + "%", transform: 'translateX(-50%)', top: 0, width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderBottom: '8px solid var(--accent-primary)', cursor: 'ew-resize', zIndex: 10 }} 
                    onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); minimapMarkerDragRef.current = 'end'; }}
                  />
                </div>

                <div className="d-flex flex-wrap gap-2 mt-1 justify-content-center" style={{ fontSize: '0.65rem' }}>
                  {GAZE_CLASS_NAMES.filter(cls => gazeSegments.some(s => s.label === cls)).map(cls => (
                    <span key={cls} style={{ color: GAZE_STATES[cls]?.color }}>
                      {GAZE_STATES[cls]?.icon} {cls}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="d-flex gap-2 mb-2 align-items-center">
              <span className="small text-muted">Zoom:</span>
              <button 
                className="btn btn-sm btn-cyber" 
                style={{ width: 24, height: 24, padding: 0, fontSize: '0.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }} 
                onClick={() => handleZoom(0.5)}
              >＋</button>
              <button 
                className="btn btn-sm btn-cyber" 
                style={{ width: 24, height: 24, padding: 0, fontSize: '0.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }} 
                onClick={() => handleZoom(2)}
              >－</button>
              <button 
                className="btn btn-sm btn-cyber" 
                style={{ padding: '0 8px', height: 24, fontSize: '0.7rem' }} 
                onClick={() => { setViewStart(0); setViewEnd(videoDuration); }}
              >RESET</button>
            </div>

            <CalibrationTimeline duration={videoDuration} segments={capturedSegments} rangeStart={rangeStart} rangeEnd={rangeEnd}
              onRangeChange={handleRangeChange} onSeek={handleSeek} currentTime={currentTime}
              viewStart={viewEnd > 0 ? viewStart : undefined} viewEnd={viewEnd > 0 ? viewEnd : undefined}
              hoveredIndex={hoveredSegmentIndex} onHover={setHoveredSegmentIndex} onLeave={() => setHoveredSegmentIndex(null)} />

            <div className="text-center mb-4">
              <div className="d-flex flex-wrap gap-2 justify-content-center mt-3">
                {GAZE_CLASS_NAMES.map(cls => (
                  <button key={cls} className="btn btn-cyber" style={{ borderColor: GAZE_STATES[cls]?.color, color: GAZE_STATES[cls]?.color, minWidth: 120 }} onClick={() => handleAddSegment(cls)}>
                    {GAZE_STATES[cls]?.icon} {cls}
                  </button>
                ))}
              </div>
            </div>

            <div className="row g-2 mb-4">
              {MANDATORY_CLASS_NAMES.map(cls => {
                const s = secondsByClass[cls] || 0;
                const ok = s >= MIN_SECONDS_PER_CLASS;
                return (
                  <div key={cls} className="col-4">
                    <div className={"p-2 rounded text-center border " + (ok ? 'border-success' : 'border-secondary')} style={{ backgroundColor: 'var(--bg-panel-lighter)' }}>
                      <div className="small text-muted">{cls}</div>
                      <div className={"fw-bold " + (ok ? 'text-success' : 'text-white')}>{(s || 0).toFixed(1) + "s / " + MIN_SECONDS_PER_CLASS + "s"}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Live scatter plot of current session samples */}
            {(() => {
              const points = currentSessionPoints;
              if (points.length === 0) return null;
              const xMin = -60, xMax = 60, yMin = -40, yMax = 40;
              const w = 300, h = 200;
              const toX = (v) => ((v - xMin) / (xMax - xMin)) * w;
              const toY = (v) => h - ((v - yMin) / (yMax - yMin)) * h;
              return (
                <div className="mb-4 text-center">
                  <p className="text-muted small mb-2" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.72rem' }}>
                    Live Distribution (Yaw vs Pitch) — Try to get a wide spread of dots
                  </p>
                  <svg width="100%" viewBox={"0 0 " + w + " " + h} className="rounded border border-secondary bg-panel-darker" style={{ maxWidth: 400 }}>
                    {/* Grid lines */}
                    <line x1={0} y1={h/2} x2={w} y2={h/2} stroke="#374151" strokeWidth={1} strokeDasharray="4 4" />
                    <line x1={w/2} y1={0} x2={w/2} y2={h} stroke="#374151" strokeWidth={1} strokeDasharray="4 4" />
                    {/* Data points */}
                    {points.map((p, i) => (
                      <circle
                        key={i}
                        cx={toX(p.yaw)}
                        cy={toY(p.pitch)}
                        r={2.5}
                        fill={GAZE_STATES[p.label]?.color || '#888'}
                        opacity={0.8}
                      />
                    ))}
                    {/* Labels */}
                    <text x={w/2} y={h - 5} fill="#9ca3af" fontSize={8} textAnchor="middle">Yaw (Horizontal)</text>
                    <text x={5} y={h/2} fill="#9ca3af" fontSize={8} textAnchor="start" transform={"rotate(-90, 5, " + (h/2) + ")"}>Pitch (Vertical)</text>
                  </svg>
                </div>
              );
            })()}

            {/* List of currently tagged clips in this session */}
            {capturedSegments.length > 0 && (
              <div className="mb-4">
                <p className="text-muted small mb-2" style={{ textTransform: 'uppercase', letterSpacing: '0.5px', fontSize: '0.72rem' }}>
                  Tagged Clips ({capturedSegments.length}) — Remove any incorrect ones
                </p>
                <div style={{ maxHeight: 150, overflowY: 'auto' }} className="bg-panel-darker rounded border border-secondary">
                  <div className="list-group list-group-flush">
                    {capturedSegments.map((seg, i) => {
                      const isHovered = hoveredSegmentIndex === i;
                      const color = GAZE_STATES[seg.label]?.color || '#888';
                      return (
                        <div 
                          key={i} 
                          className={"list-group-item d-flex justify-content-between align-items-center py-2 px-3 " + (isHovered ? 'hover-active' : 'bg-transparent')}
                          onMouseEnter={() => setHoveredSegmentIndex(i)}
                          onMouseLeave={() => setHoveredSegmentIndex(null)}
                          style={{ 
                            transition: 'all 0.2s',
                            borderLeft: '3px solid ' + (isHovered ? color : 'transparent'),
                            backgroundColor: isHovered ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                            borderBottom: '1px solid var(--border-color)'
                          }}
                        >
                          <div className="small">
                            <span style={{ color: color, fontWeight: 600 }} className="me-2">
                              {GAZE_STATES[seg.label]?.icon} {seg.label}
                            </span>
                            <span className="text-muted">
                              {(seg.startTime || 0).toFixed(1)}s – {(seg.endTime || 0).toFixed(1)}s
                            </span>
                          </div>
                          <button 
                            className="btn btn-sm btn-outline-danger border-0 py-0 px-2" 
                            style={{ fontSize: '0.65rem', fontWeight: 700 }}
                            onClick={(e) => { e.stopPropagation(); handleDeleteSegment(i); }}
                            title="Remove clip"
                          >
                            REMOVE
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {sampleError && (
              <div className="alert alert-cyber-danger py-2 mb-3">{sampleError}</div>
            )}

            <div className="d-flex gap-2">
              <button className="btn btn-cyber" onClick={() => setStep(1)}>BACK</button>
              <button className="btn btn-cyber-primary fw-bold ms-auto" disabled={!allClassesReady || !hasCurrentPoints || submittingSamples} onClick={handleSubmitSamples}>
                {submittingSamples ? 'SUBMITTING…' : 'SUBMIT SAMPLES'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Step 3: Review ───────────────────────────────────────────────── */}
      {step === 3 && calStatus && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header"><h4>Step 4: Review Samples</h4></div>
          <div className="card-body">
            <p className="text-muted small mb-4">{"We've collected " + calStatus.total_samples + " data points for \"" + calStatus.name + "\"."}</p>
            <div className="list-group mb-4">
              {GAZE_CLASS_NAMES.map(cls => {
                const count = sampleCounts[cls] || 0;
                const ok = count >= MIN_SAMPLES;
                return (
                  <div key={cls} className="list-group-item bg-transparent border-secondary text-white d-flex justify-content-between">
                    <span>{GAZE_STATES[cls].icon + " " + cls}</span>
                    <span className={ok ? 'text-success' : 'text-warning'}>{count + " samples " + (ok ? '✓' : "(Need 3)")}</span>
                  </div>
                );
              })}
            </div>
            <div className="d-flex gap-2">
              <button className="btn btn-cyber" onClick={() => setStep(2)}>CAPTURE MORE</button>
              <button className="btn btn-cyber text-danger border-danger" disabled={resetting} onClick={handleResetSamples}>CLEAR ALL</button>
              <button className="btn btn-cyber-primary fw-bold ms-auto" disabled={!allClassesMeetMinimum} onClick={handleTrain}>TRAIN MODEL</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Step 4: Training ─────────────────────────────────────────────── */}
      {step === 4 && (
        <div className="card card-cyber shadow-lg">
          <div className="card-header"><h4>{training ? 'Training…' : 'Result'}</h4></div>
          <div className="card-body text-center">
            {training ? <div className="py-5"><div className="spinner-border text-primary mb-3" /><p>Building your personal gaze map…</p></div> : (
              <>
                <div className={"alert " + (trainResult?.success ? 'alert-success' : 'alert-danger')}>{trainResult?.message}</div>
                {trainPlots && (
                  <div className="row g-2 mb-4">
                    <div className="col-6"><img src={trainPlots.head_pose} className="img-fluid rounded border border-secondary" alt="Head Pose" /></div>
                    <div className="col-6"><img src={trainPlots.pca} className="img-fluid rounded border border-secondary" alt="PCA" /></div>
                    <div className="col-12 mt-2"><img src={trainPlots.decision_boundary} className="img-fluid rounded border border-secondary" alt="Boundary" /></div>
                  </div>
                )}
                <div className="d-flex gap-2 justify-content-center">
                  <button className="btn btn-cyber" onClick={() => setStep(0)}>FINISH</button>
                  {trainResult?.success && <button className="btn btn-cyber-primary fw-bold" onClick={handleReanalyze}>APPLY TO VIDEO</button>}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

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

function StepIndicator({ current, onStepClick }) {
  const labels = ['Manage', 'Video', 'Label', 'Review', 'Train'];
  return (
    <div className="d-flex align-items-center gap-0 mb-4 overflow-auto pb-2">
      {labels.map((label, i) => {
        const isDone = i < current;
        const isActive = i === current;
        const clickable = isDone && onStepClick;
        return (
          <React.Fragment key={i}>
            <div className="d-flex flex-column align-items-center" style={{ minWidth: 70 }}>
              <div
                onClick={clickable ? () => onStepClick(i) : undefined}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 700,
                  fontSize: '0.75rem',
                  background: isDone ? 'var(--accent-success)' : isActive ? 'var(--accent-primary)' : 'var(--bg-panel-lighter)',
                  border: '2px solid ' + (isDone ? 'var(--accent-success)' : isActive ? 'var(--accent-primary)' : 'var(--border-color)'),
                  color: isDone || isActive ? '#fff' : 'var(--text-muted)',
                  cursor: clickable ? 'pointer' : 'default',
                }}
              >
                {isDone ? '✓' : i + 1}
              </div>
              <span style={{ fontSize: '0.65rem', marginTop: 4, color: isActive ? 'var(--text-main)' : 'var(--text-muted)', fontWeight: isActive ? 600 : 400 }}>
                {label}
              </span>
            </div>
            {i < labels.length - 1 && (
              <div style={{ flex: 1, height: 2, minWidth: 20, background: isDone ? 'var(--accent-success)' : 'var(--border-color)', marginBottom: 18 }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function CalibrationTimeline({
  duration, segments, rangeStart, rangeEnd,
  onRangeChange, onSeek, currentTime,
  viewStart: vsProp, viewEnd: veProp,
  hoveredIndex, onHover, onLeave
}) {
  const trackRef = useRef(null);
  const draggingRef = useRef(null);
  const dragOffsetRef = useRef(0);
  const vs = vsProp ?? 0;
  const ve = veProp ?? duration;
  const vDur = ve - vs;
  const stateRef = useRef({ rangeStart, rangeEnd, duration, vs, ve, vDur });
  useEffect(() => { stateRef.current = { rangeStart, rangeEnd, duration, vs, ve, vDur }; }, [rangeStart, rangeEnd, duration, vs, ve, vDur]);
  
  const getTimeFromEvent = (e) => {
    if (!trackRef.current || !stateRef.current.vDur) return 0;
    const rect = trackRef.current.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    return stateRef.current.vs + frac * stateRef.current.vDur;
  };

  const handleTrackMouseDown = (e) => {
    if (e.target !== trackRef.current) return;
    e.preventDefault();
    const t = getTimeFromEvent(e);
    const { rangeStart: rs, rangeEnd: re } = stateRef.current;
    draggingRef.current = Math.abs(t - rs) <= Math.abs(t - re) ? 'start' : 'end';
  };
  const handleRangeZoneMouseDown = (e) => {
    e.preventDefault(); e.stopPropagation();
    dragOffsetRef.current = getTimeFromEvent(e) - stateRef.current.rangeStart;
    draggingRef.current = 'range';
  };
  const handleStartHandleMouseDown = (e) => { e.preventDefault(); e.stopPropagation(); draggingRef.current = 'start'; };
  const handleEndHandleMouseDown   = (e) => { e.preventDefault(); e.stopPropagation(); draggingRef.current = 'end';   };
  
  useEffect(() => {
    const handleMove = (e) => {
      if (!draggingRef.current) return;
      const t = getTimeFromEvent(e);
      const { rangeStart: rs, rangeEnd: re, duration: d } = stateRef.current;
      if (draggingRef.current === 'start') {
        const ns = Math.max(0, Math.min(t, re - 0.2));
        onRangeChange(ns, re); onSeek?.(ns);
      } else if (draggingRef.current === 'end') {
        const ne = Math.max(rs + 0.2, Math.min(t, d));
        onRangeChange(rs, ne); onSeek?.(ne);
      } else {
        const w = re - rs;
        let s = Math.max(0, Math.min(d - w, t - dragOffsetRef.current));
        onRangeChange(s, s + w); onSeek?.(s);
      }
    };
    const handleUp = () => { draggingRef.current = null; };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => { window.removeEventListener('mousemove', handleMove); window.removeEventListener('mouseup', handleUp); };
  }, [onRangeChange, onSeek]);

  if (!duration) return null;
  const toLeftPct  = (t) => Math.max(0, Math.min(100, ((t - vs) / vDur) * 100));
  const toWidthPct = (s, e) => {
    const cs = Math.max(s, vs), ce = Math.min(e, ve);
    return ce > cs ? ((ce - cs) / vDur) * 100 : 0;
  };
  const startPct = toLeftPct(rangeStart);
  const endPct   = toLeftPct(rangeEnd);
  const selStart = Math.max(rangeStart, vs);
  const selEnd   = Math.min(rangeEnd, ve);
  return (
    <div style={{ position: 'relative', paddingBottom: 22, marginBottom: '0.5rem', userSelect: 'none' }}>
      <div ref={trackRef} style={{ position: 'relative', height: 24, background: 'var(--bg-panel-lighter)', borderRadius: 4, border: '1px solid var(--border-color)', cursor: 'pointer', overflow: 'hidden' }} onMouseDown={handleTrackMouseDown}>
        {segments.map((seg, i) => {
          if (seg.endTime < vs || seg.startTime > ve) return null;
          const isHovered = hoveredIndex === i;
          const color = GAZE_STATES[seg.label]?.color || '#888';
          return (
            <div 
              key={i} 
              onMouseEnter={() => onHover?.(i)}
              onMouseLeave={() => onLeave?.()}
              style={{ 
                position: 'absolute', 
                top: 0, bottom: 0, 
                left: toLeftPct(Math.max(seg.startTime, vs)) + '%', 
                width: toWidthPct(seg.startTime, seg.endTime) + '%', 
                background: color, 
                opacity: isHovered ? 1 : 0.55, 
                boxShadow: isHovered ? ('0 0 12px ' + color) : 'none',
                border: isHovered ? ('1px solid ' + color) : 'none',
                boxSizing: 'border-box',
                borderRadius: 2,
                zIndex: isHovered ? 5 : 1
              }} 
            />
          );
        })}
        {selEnd > selStart && <div style={{ position: 'absolute', top: 0, bottom: 0, left: ((selStart - vs) / vDur) * 100 + '%', width: ((selEnd - selStart) / vDur) * 100 + '%', background: 'rgba(255,255,255,0.15)', borderLeft: rangeStart >= vs ? '2px solid rgba(255,255,255,0.75)' : 'none', borderRight: rangeEnd <= ve ? '2px solid rgba(255,255,255,0.75)' : 'none', boxSizing: 'border-box', cursor: 'move', zIndex: 2 }} onMouseDown={handleRangeZoneMouseDown} />}
        {currentTime >= vs && currentTime <= ve && <div style={{ position: 'absolute', top: -3, bottom: -3, left: toLeftPct(currentTime) + '%', width: 2, background: 'rgba(255,255,255,0.85)', borderRadius: 1, pointerEvents: 'none', zIndex: 10 }} />}
      </div>
      {startPct >= 0 && startPct <= 100 && <div style={{ position: 'absolute', top: -6, left: startPct + '%', transform: 'translateX(-50%)', width: 8, height: 36, background: 'var(--accent-primary)', borderRadius: 2, cursor: 'ew-resize', zIndex: 11 }} onMouseDown={handleStartHandleMouseDown} />}
      {endPct >= 0 && endPct <= 100 && <div style={{ position: 'absolute', top: -6, left: endPct + '%', transform: 'translateX(-50%)', width: 8, height: 36, background: 'var(--accent-primary)', borderRadius: 2, cursor: 'ew-resize', zIndex: 11 }} onMouseDown={handleEndHandleMouseDown} />}
    </div>
  );
}

export default CalibrationPage;
