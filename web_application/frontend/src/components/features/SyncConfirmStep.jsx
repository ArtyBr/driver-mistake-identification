/**
 * SyncConfirmStep — inline sync confirmation view shown between upload and submission.
 *
 * Props:
 *   syncData        — response from POST /sync/analyze
 *   manualOffset    — number (seconds), controlled by parent
 *   setManualOffset — (offset: number) => void
 *   onConfirm       — () => void — called when user clicks "Confirm & Analyse"
 *   onBack          — () => void — called when user clicks "← Back to Upload"
 *   isSubmitting    — boolean
 *   flipFace        — boolean — whether to mirror the face video horizontally
 *   setFlipFace     — (flip: boolean) => void
 */
import { useState, useCallback, useEffect } from 'react';
import AudioWaveform from './AudioWaveform';
import { useVideoSync } from '../../hooks/useVideoSync';
import { getFileUrl } from '../../services/api';

const MIN_OVERLAP = 2;     // seconds — below this, Confirm is disabled
const WARN_OVERLAP = 10;   // seconds — below this, show a warning

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '0s';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function SyncConfirmStep({
  syncData,
  manualOffset,
  setManualOffset,
  onConfirm,
  onBack,
  isSubmitting,
  flipFace,
  setFlipFace,
}) {
  const [previewOpen, setPreviewOpen] = useState(true);
  const [audioSource, setAudioSource] = useState('none');

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

  // Sync muted state
  useEffect(() => {
    if (roadVideoRef.current) roadVideoRef.current.muted = (audioSource !== 'road');
    if (faceVideoRef.current) faceVideoRef.current.muted = (audioSource !== 'face');
  }, [audioSource, roadVideoRef, faceVideoRef]);

  // Trim preview — live-updated from manualOffset
  const skipRoad = Math.max(0, manualOffset);
  const skipFace = Math.max(0, -manualOffset);
  const overlap  = Math.min(
    (syncData?.road_duration ?? 0) - skipRoad,
    (syncData?.face_duration ?? 0) - skipFace,
  );

  // Confidence badge (backend field is correlation_score)
  const confidence = syncData?.correlation_score ?? 0;
  const confVariant =
    confidence >= 0.7 ? 'success' :
    confidence >= 0.4 ? 'warning' : 'danger';
  const confLabel =
    confidence >= 0.7 ? 'High confidence' :
    confidence >= 0.4 ? 'Medium confidence' : 'Low confidence';

  const nudge = useCallback((delta) => {
    setManualOffset(prev => Math.round((prev + delta) * 1000) / 1000);
  }, [setManualOffset]);

  const maxSlider = Math.max(
    syncData?.road_duration ?? 60,
    syncData?.face_duration ?? 60,
  );

  const confirmDisabled = isSubmitting || overlap < MIN_OVERLAP;

  return (
    <div className="card-cyber shadow-sm">
      <div className="card-header">
        <h4 className="mb-0">Confirm Synchronisation</h4>
      </div>

      <div className="card-body">

        {/* Confidence alert */}
        <div className={`alert alert-${confVariant} py-2 mb-3`}>
          <div className="d-flex justify-content-between align-items-center">
            <span>
              <strong>{confLabel}</strong> ({(confidence * 100).toFixed(0)}%)
              {' — '}Auto-detected offset: <code>{syncData?.offset_seconds >= 0 ? '+' : ''}{(syncData?.offset_seconds ?? 0).toFixed(3)}s</code>
            </span>
          </div>
          {confidence < 0.4 && (
            <div className="small mt-1 text-danger">
              Low confidence — the videos may have very different audio environments. Manual adjustment is recommended.
            </div>
          )}
        </div>

        {/* Waveform */}
        <div className="mb-4">
          <div className="d-flex justify-content-between small text-muted mb-1">
            <span>
              <span style={{ color: 'rgba(0,210,223,0.9)' }}>■</span> Road (dashcam)
              {'  '}
              <span style={{ color: 'rgba(255,193,7,0.9)' }}>■</span> Driver (phone)
            </span>
            <span>Drag to adjust offset</span>
          </div>
          <AudioWaveform
            roadWaveform={syncData?.road_waveform}
            faceWaveform={syncData?.face_waveform}
            roadDuration={syncData?.road_duration}
            faceDuration={syncData?.face_duration}
            offset={manualOffset}
            onOffsetChange={setManualOffset}
            currentTime={currentTime}
          />
        </div>

        {/* Offset controls */}
        <div className="mb-4">
          <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
            <label className="form-label mb-0 fw-bold small text-white text-uppercase">Offset Control</label>
            <code className="fs-5 text-highlight-cyan" style={{ minWidth: '8ch', fontFamily: 'monospace' }}>
              {manualOffset >= 0 ? '+' : ''}{manualOffset.toFixed(3)}s
            </code>
            <div className="d-flex flex-wrap gap-1 ms-sm-auto">
              <button className="btn btn-outline-secondary btn-sm" onClick={() => nudge(-0.1)}>−0.1s</button>
              <button className="btn btn-outline-secondary btn-sm" onClick={() => nudge(-0.01)}>−0.01s</button>
              <button className="btn btn-outline-secondary btn-sm" onClick={() => nudge(+0.01)}>+0.01s</button>
              <button className="btn btn-outline-secondary btn-sm" onClick={() => nudge(+0.1)}>+0.1s</button>
              <button
                className="btn btn-outline-info btn-sm"
                onClick={() => setManualOffset(syncData?.offset_seconds ?? 0)}
                title="Reset to auto-detected value"
              >
                Reset
              </button>
            </div>
          </div>
          <input
            type="range"
            className="form-range"
            min={-maxSlider}
            max={maxSlider}
            step={0.01}
            value={manualOffset}
            onChange={e => setManualOffset(parseFloat(e.target.value))}
          />
        </div>

        {/* Video Preview */}
        <div className="mb-4">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <h6 className="mb-0 text-white small text-uppercase fw-bold">Synchronised Preview</h6>
            <button
              className="btn btn-link btn-sm text-muted p-0 text-decoration-none"
              onClick={() => setPreviewOpen(!previewOpen)}
            >
              {previewOpen ? 'Hide Videos' : 'Show Videos'}
            </button>
          </div>

          {previewOpen && (
            <div className="mt-3">
              <div className="row g-2">
                <div className="col-md-6">
                  <div className="small text-muted mb-1">Road (dashcam)</div>
                  <video
                    ref={roadVideoRef}
                    src={getFileUrl(syncData?.road_video_url)}
                    className="w-100 rounded"
                    style={{ maxHeight: '220px', background: '#000', objectFit: 'contain' }}
                    onLoadedMetadata={e => setRoadDuration(e.target.duration)}
                    onTimeUpdate={onRoadTimeUpdate}
                    onEnded={onRoadEnded}
                    playsInline
                    webkit-playsinline="true"
                    muted
                  />
                </div>
                <div className="col-md-6">
                  <div className="small text-muted mb-1">Driver (phone){flipFace ? ' — Mirrored' : ''}</div>
                  <video
                    ref={faceVideoRef}
                    src={getFileUrl(syncData?.face_video_url)}
                    className="w-100 rounded"
                    style={{ maxHeight: '220px', background: '#000', objectFit: 'contain', transform: flipFace ? 'scaleX(-1)' : 'none' }}
                    onLoadedMetadata={e => setFaceDuration(e.target.duration)}
                    playsInline
                    webkit-playsinline="true"
                    muted
                  />
                </div>
              </div>
              
              <div className="d-flex flex-wrap align-items-center gap-2 mt-3 p-2 bg-panel-lighter rounded border" style={{ borderColor: 'var(--border-color)' }}>
                <button
                  className="btn btn-cyber-primary px-4"
                  onClick={togglePlay}
                >
                  {isPlaying ? '⏸ Pause' : '▶ Play'}
                </button>
                
                <span className="text-muted small font-monospace">
                  {currentTime.toFixed(2)}s
                </span>

                <div className="ms-sm-auto d-flex align-items-center gap-2">
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
                      Driver
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Flip face video toggle */}
        <div className="alert alert-cyber-info py-3 mb-4">
          <div className="d-flex align-items-start gap-3">
            <div className="form-check form-switch mt-1">
              <input
                className="form-check-input"
                type="checkbox"
                role="switch"
                id="flipFaceCheck"
                checked={flipFace}
                onChange={e => setFlipFace(e.target.checked)}
              />
              <label className="form-check-label text-white fw-bold" htmlFor="flipFaceCheck">
                Mirror driver video
              </label>
            </div>
            <div className="small text-muted">
              Some phone cameras automatically mirror (flip) the video. Enable this if the driver's face
              appears on the <strong>right</strong> side in landscape, or if it looks like a mirror image.
              The driver's face should be on the <strong>left</strong> side in landscape, or the largest
              face in portrait.
            </div>
          </div>
        </div>

        {/* Trim info */}
        <div className="alert alert-cyber py-3 mb-4">
          <div className="row g-3 align-items-center">
            <div className="col-sm-4 border-end" style={{ borderColor: 'var(--border-color)' }}>
              <div className="small text-muted mb-1">Road Trim</div>
              <code className="text-highlight-cyan fs-6">{skipRoad.toFixed(2)}s from start</code>
            </div>
            <div className="col-sm-4 border-end" style={{ borderColor: 'var(--border-color)' }}>
              <div className="small text-muted mb-1">Driver Trim</div>
              <code className="text-highlight-cyan fs-6">{skipFace.toFixed(2)}s from start</code>
            </div>
            <div className="col-sm-4 text-center">
              <div className="small text-muted mb-1">Analysis Duration</div>
              <div className="fw-bold fs-5 text-white">{formatDuration(overlap)}</div>
              <div className="small text-muted">({overlap.toFixed(1)}s total)</div>
            </div>
          </div>
          
          {overlap < WARN_OVERLAP && overlap >= MIN_OVERLAP && (
            <div className="alert alert-warning py-1 px-2 mt-3 mb-0 small">
              <i className="bi bi-exclamation-triangle me-2"></i>
              Short overlap — consider adjusting the offset for more shared footage.
            </div>
          )}
          {overlap < MIN_OVERLAP && (
            <div className="alert alert-danger py-1 px-2 mt-3 mb-0 small">
              <i className="bi bi-x-circle me-2"></i>
              Overlap is less than {MIN_OVERLAP}s — cannot submit. Adjust the offset.
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="d-flex gap-2">
          <button
            className="btn btn-outline-secondary flex-shrink-0"
            onClick={onBack}
            disabled={isSubmitting}
          >
            ← Back to Upload
          </button>
          <button
            className="btn btn-cyber-primary flex-grow-1"
            onClick={onConfirm}
            disabled={confirmDisabled}
          >
            {isSubmitting ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                Submitting…
              </>
            ) : 'Confirm & Analyse →'}
          </button>
        </div>

      </div>
    </div>
  );
}
