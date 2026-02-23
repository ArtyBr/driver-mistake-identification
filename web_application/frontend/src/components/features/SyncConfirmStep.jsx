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
 */
import { useState, useCallback } from 'react';
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
}) {
  const [previewOpen, setPreviewOpen] = useState(false);

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
      <div className="card-header d-flex align-items-center justify-content-between">
        <h4 className="mb-0">Confirm Synchronisation</h4>
        <span className={`badge bg-${confVariant} ms-2`}>
          {confLabel} ({(confidence * 100).toFixed(0)}%)
        </span>
      </div>

      <div className="card-body">

        {/* Waveform */}
        <div className="mb-3">
          <label className="form-label text-white small mb-1">
            Audio waveform — drag to adjust offset
          </label>
          <AudioWaveform
            roadWaveform={syncData?.road_waveform}
            faceWaveform={syncData?.face_waveform}
            roadDuration={syncData?.road_duration}
            faceDuration={syncData?.face_duration}
            offset={manualOffset}
            onOffsetChange={setManualOffset}
            currentTime={currentTime}
          />
          <div className="d-flex gap-3 mt-1 small text-muted">
            <span><span style={{ color: 'rgba(0,210,223,0.8)' }}>■</span> Road (dashcam)</span>
            <span><span style={{ color: 'rgba(255,193,7,0.75)' }}>■</span> Driver (phone)</span>
          </div>
        </div>

        {/* Offset controls */}
        <div className="mb-3">
          <label className="form-label text-white small mb-1">Offset (seconds)</label>
          <div className="d-flex align-items-center gap-2 mb-2">
            <code className="fs-5 text-cyber-blue" style={{ minWidth: '7ch', fontFamily: 'monospace' }}>
              {manualOffset >= 0 ? '+' : ''}{manualOffset.toFixed(3)}s
            </code>
            <button className="btn btn-outline-secondary btn-sm" onClick={() => nudge(-0.1)}>−0.1</button>
            <button className="btn btn-outline-secondary btn-sm" onClick={() => nudge(-0.01)}>−0.01</button>
            <button className="btn btn-outline-secondary btn-sm" onClick={() => nudge(+0.01)}>+0.01</button>
            <button className="btn btn-outline-secondary btn-sm" onClick={() => nudge(+0.1)}>+0.1</button>
            <button
              className="btn btn-outline-secondary btn-sm ms-1"
              onClick={() => setManualOffset(syncData?.offset_seconds ?? 0)}
              title="Reset to auto-detected value"
            >
              Reset
            </button>
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

        {/* Trim info */}
        <div className="card bg-panel-lighter border-secondary mb-3">
          <div className="card-body py-2 px-3 small">
            <div className="d-flex justify-content-between mb-1">
              <span className="text-muted">Road: skip from start</span>
              <code className="text-white">{skipRoad.toFixed(2)}s</code>
            </div>
            <div className="d-flex justify-content-between mb-2">
              <span className="text-muted">Driver: skip from start</span>
              <code className="text-white">{skipFace.toFixed(2)}s</code>
            </div>
            <hr className="my-1 border-secondary" />
            <div className="d-flex justify-content-between align-items-center">
              <span className="text-white fw-bold">Final duration</span>
              <span className="text-white fw-bold">
                {formatDuration(overlap)}&nbsp;
                <span className="text-muted fw-normal">({overlap.toFixed(1)}s)</span>
              </span>
            </div>
            {overlap < WARN_OVERLAP && overlap >= MIN_OVERLAP && (
              <div className="alert alert-warning py-1 px-2 mt-2 mb-0 small">
                Short overlap — consider adjusting the offset for more shared footage.
              </div>
            )}
            {overlap < MIN_OVERLAP && (
              <div className="alert alert-danger py-1 px-2 mt-2 mb-0 small">
                Overlap is less than {MIN_OVERLAP}s — cannot submit. Adjust the offset.
              </div>
            )}
          </div>
        </div>

        {/* Collapsible preview */}
        <div className="mb-4">
          <button
            className="btn btn-outline-secondary btn-sm w-100"
            onClick={() => setPreviewOpen(o => !o)}
          >
            {previewOpen ? '▲ Hide Preview' : '▼ Show Video Preview'}
          </button>

          {previewOpen && (
            <div className="mt-3">
              <div className="row g-2">
                <div className="col-md-6">
                  <label className="form-label text-white small mb-1">Road (dashcam)</label>
                  {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
                  <video
                    ref={roadVideoRef}
                    src={getFileUrl(syncData?.road_video_url)}
                    className="w-100 rounded"
                    style={{ maxHeight: '220px', background: '#000', objectFit: 'contain' }}
                    onLoadedMetadata={e => setRoadDuration(e.target.duration)}
                    onTimeUpdate={onRoadTimeUpdate}
                    onEnded={onRoadEnded}
                    playsInline
                  />
                </div>
                <div className="col-md-6">
                  <label className="form-label text-white small mb-1">Driver (phone)</label>
                  {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
                  <video
                    ref={faceVideoRef}
                    src={getFileUrl(syncData?.face_video_url)}
                    className="w-100 rounded"
                    style={{ maxHeight: '220px', background: '#000', objectFit: 'contain' }}
                    onLoadedMetadata={e => setFaceDuration(e.target.duration)}
                    playsInline
                  />
                </div>
              </div>
              <div className="text-center mt-2">
                <button
                  className="btn btn-outline-light btn-sm px-4"
                  onClick={togglePlay}
                >
                  {isPlaying ? '⏸ Pause' : '▶ Play'}
                </button>
              </div>
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
