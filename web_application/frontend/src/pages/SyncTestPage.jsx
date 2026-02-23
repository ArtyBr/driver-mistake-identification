/**
 * SyncTestPage — experimental audio synchronisation test page.
 *
 * Upload two video files → backend computes cross-correlation offset →
 * display waveforms + interactive offset controls + synchronised video player.
 *
 * Videos are served from the backend (/static/sync_temp/...) to avoid
 * blob: URLs, which are blocked by the production nginx CSP.
 */
import { useState, useCallback, useEffect } from 'react';
import api, { getFileUrl } from '../services/api';
import FileDropZone from '../components/common/FileDropZone';
import AudioWaveform from '../components/features/AudioWaveform';
import { useVideoSync } from '../hooks/useVideoSync';

export default function SyncTestPage() {
  const [roadFiles, setRoadFiles] = useState([]);
  const [faceFiles, setFaceFiles] = useState([]);

  const [syncData,       setSyncData]       = useState(null);
  const [manualOffset,   setManualOffset]   = useState(0);
  const [isAnalyzing,    setIsAnalyzing]    = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error,          setError]          = useState(null);
  // 'none' | 'road' | 'face'
  const [audioSource,    setAudioSource]    = useState('none');

  // ------------------------------------------------------------------
  // Video sync hook
  // ------------------------------------------------------------------
  const {
    roadVideoRef,
    faceVideoRef,
    isPlaying,
    currentTime,
    togglePlay,
    onRoadTimeUpdate,
    onRoadEnded,
    setRoadDuration,
    setFaceDuration,
  } = useVideoSync(manualOffset);

  // React's `muted` prop doesn't update the DOM property after initial render,
  // so we drive it imperatively whenever audioSource changes.
  useEffect(() => {
    if (roadVideoRef.current) roadVideoRef.current.muted = audioSource !== 'road';
    if (faceVideoRef.current) faceVideoRef.current.muted = audioSource !== 'face';
  }, [audioSource, roadVideoRef, faceVideoRef]);

  // ------------------------------------------------------------------
  // Analyze handler
  // ------------------------------------------------------------------
  const handleAnalyze = useCallback(async () => {
    if (!roadFiles.length || !faceFiles.length) return;

    setSyncData(null);
    setError(null);
    setIsAnalyzing(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('road_video', roadFiles[0]);
    formData.append('face_video', faceFiles[0]);

    try {
      const response = await api.post('/sync/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (evt) => {
          if (evt.total) {
            setUploadProgress(Math.round((evt.loaded / evt.total) * 100));
          }
        },
      });
      setSyncData(response.data);
      setManualOffset(response.data.offset_seconds);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Analysis failed.';
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  }, [roadFiles, faceFiles]);

  // ------------------------------------------------------------------
  // Derived values
  // ------------------------------------------------------------------
  const confidencePct = syncData ? Math.round(syncData.correlation_score * 100) : 0;
  const confidenceVariant =
    confidencePct >= 70 ? 'success' :
    confidencePct >= 40 ? 'warning' : 'danger';

  const offsetSign = manualOffset >= 0 ? '+' : '';
  const offsetDisplay = `${offsetSign}${manualOffset.toFixed(3)}s`;
  const maxRange = syncData
    ? Math.max(syncData.road_duration, syncData.face_duration)
    : 60;

  // Backend-served video URLs (avoid blob: which is blocked by prod CSP)
  const roadVideoUrl = syncData?.road_video_url ? getFileUrl(syncData.road_video_url) : null;
  const faceVideoUrl = syncData?.face_video_url ? getFileUrl(syncData.face_video_url) : null;

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div>
      {/* Experimental banner */}
      <div className="alert alert-warning d-flex align-items-center gap-2 mb-3" role="alert">
        <strong>Experimental:</strong> This page is a prototype for testing video synchronisation. It is not yet integrated into the analysis pipeline.
      </div>

      <div className="d-flex align-items-center gap-2 mb-4">
        <h2 className="mb-0">Sync Test</h2>
        <span className="badge bg-warning text-dark" style={{ fontSize: '0.7rem' }}>beta</span>
      </div>

      {/* ── Upload Card ─────────────────────────────────────────── */}
      <div className="card card-cyber mb-4">
        <div className="card-header">
          <h5 className="mb-0">Upload Videos</h5>
        </div>
        <div className="card-body">
          <div className="row">
            <div className="col-md-6">
              <FileDropZone
                label="Road Video (Dashcam)"
                files={roadFiles}
                setFiles={setRoadFiles}
                accept="video/*"
                helperText="MP4 recommended. Must contain audio."
              />
            </div>
            <div className="col-md-6">
              <FileDropZone
                label="Face Video (Phone)"
                files={faceFiles}
                setFiles={setFaceFiles}
                accept="video/*"
                helperText="MP4 recommended. Must contain audio."
              />
            </div>
          </div>

          {/* Upload progress */}
          {isAnalyzing && uploadProgress < 100 && (
            <div className="mb-3">
              <div className="d-flex justify-content-between small text-muted mb-1">
                <span>Uploading…</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="progress" style={{ height: '6px' }}>
                <div
                  className="progress-bar bg-info"
                  style={{ width: `${uploadProgress}%`, transition: 'width 0.2s' }}
                />
              </div>
            </div>
          )}

          {/* Computing spinner */}
          {isAnalyzing && uploadProgress >= 100 && (
            <div className="d-flex align-items-center gap-2 text-info mb-3">
              <div className="spinner-border spinner-border-sm" role="status" />
              <span>Computing cross-correlation…</span>
            </div>
          )}

          {error && (
            <div className="alert alert-danger py-2">{error}</div>
          )}

          <button
            className="btn btn-cyber"
            onClick={handleAnalyze}
            disabled={!roadFiles.length || !faceFiles.length || isAnalyzing}
          >
            {isAnalyzing ? 'Analyzing…' : 'Analyze Sync'}
          </button>
        </div>
      </div>

      {/* ── Results ─────────────────────────────────────────────── */}
      {syncData && (
        <div className="card card-cyber mb-4">
          <div className="card-header">
            <h5 className="mb-0">Synchronisation Results</h5>
          </div>
          <div className="card-body">

            {/* Confidence alert */}
            <div className={`alert alert-${confidenceVariant} py-2 mb-3`}>
              <strong>Confidence: {confidencePct}%</strong>
              {' — '}Auto-detected offset: <code>{`${syncData.offset_seconds >= 0 ? '+' : ''}${syncData.offset_seconds.toFixed(3)}s`}</code>
              {confidencePct < 40 && (
                <div className="small mt-1">
                  Low confidence — the videos may have very different audio environments. Manual adjustment is recommended.
                </div>
              )}
            </div>

            {/* Waveform */}
            <div className="mb-3">
              <div className="d-flex justify-content-between small text-muted mb-1">
                <span>
                  <span style={{ color: 'rgba(0,210,223,0.9)' }}>■</span> Road (dashcam)
                  {'  '}
                  <span style={{ color: 'rgba(255,193,7,0.9)' }}>■</span> Face (phone)
                </span>
                <span>Drag to adjust offset</span>
              </div>
              <AudioWaveform
                roadWaveform={syncData.road_waveform}
                faceWaveform={syncData.face_waveform}
                roadDuration={syncData.road_duration}
                faceDuration={syncData.face_duration}
                offset={manualOffset}
                onOffsetChange={setManualOffset}
                currentTime={currentTime}
              />
            </div>

            {/* Offset controls */}
            <div className="mb-4">
              <div className="d-flex align-items-center gap-3 mb-2">
                <label className="form-label mb-0 fw-bold">Offset</label>
                <code style={{ fontSize: '1rem', minWidth: '80px' }}>{offsetDisplay}</code>
                <div className="d-flex gap-1 ms-auto">
                  {[-0.1, -0.01, 0.01, 0.1].map(step => (
                    <button
                      key={step}
                      className="btn btn-outline-secondary btn-sm"
                      onClick={() => setManualOffset(prev => parseFloat((prev + step).toFixed(3)))}
                    >
                      {step > 0 ? `+${step}s` : `${step}s`}
                    </button>
                  ))}
                  <button
                    className="btn btn-outline-info btn-sm ms-2"
                    onClick={() => setManualOffset(syncData.offset_seconds)}
                  >
                    Reset
                  </button>
                </div>
              </div>
              <input
                type="range"
                className="form-range"
                min={-maxRange}
                max={maxRange}
                step={0.01}
                value={manualOffset}
                onChange={e => setManualOffset(parseFloat(e.target.value))}
              />
              <div className="d-flex justify-content-between small text-muted">
                <span>{`-${maxRange.toFixed(0)}s`}</span>
                <span>0s</span>
                <span>{`+${maxRange.toFixed(0)}s`}</span>
              </div>
            </div>

            {/* Dual video player */}
            {roadVideoUrl && faceVideoUrl && (
              <div>
                <h6 className="mb-3">Synchronised Preview</h6>
                <div className="row g-3 mb-3">
                  <div className="col-md-6">
                    <div className="small text-muted mb-1">Road (Dashcam)</div>
                    <video
                      ref={roadVideoRef}
                      src={roadVideoUrl}
                      className="w-100 rounded"
                      style={{ background: '#000', maxHeight: '280px' }}
                      onTimeUpdate={onRoadTimeUpdate}
                      onEnded={onRoadEnded}
                      onLoadedMetadata={e => setRoadDuration(e.target.duration)}
                      muted
                    />
                  </div>
                  <div className="col-md-6">
                    <div className="small text-muted mb-1">
                      Face (Phone)
                      {manualOffset !== 0 && (
                        <span className="ms-2 text-warning">
                          offset: {offsetDisplay}
                        </span>
                      )}
                    </div>
                    <video
                      ref={faceVideoRef}
                      src={faceVideoUrl}
                      className="w-100 rounded"
                      style={{ background: '#000', maxHeight: '280px' }}
                      onLoadedMetadata={e => setFaceDuration(e.target.duration)}
                      muted
                    />
                  </div>
                </div>

                <div className="d-flex align-items-center gap-3 flex-wrap">
                  <button className="btn btn-cyber" onClick={togglePlay}>
                    {isPlaying ? 'Pause' : 'Play'}
                  </button>
                  <span className="text-muted small font-monospace">
                    {currentTime.toFixed(2)}s
                  </span>
                  <div className="d-flex align-items-center gap-2 ms-auto">
                    <span className="small text-muted">Audio:</span>
                    <div className="btn-group btn-group-sm">
                      <button
                        className={`btn ${audioSource === 'road' ? 'btn-info' : 'btn-outline-secondary'}`}
                        onClick={() => setAudioSource(prev => prev === 'road' ? 'none' : 'road')}
                      >
                        Road
                      </button>
                      <button
                        className={`btn ${audioSource === 'face' ? 'btn-warning' : 'btn-outline-secondary'}`}
                        onClick={() => setAudioSource(prev => prev === 'face' ? 'none' : 'face')}
                      >
                        Face
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
