/**
 * AudioWaveform — canvas-based dual waveform display with drag-to-adjust offset.
 *
 * Props:
 *   roadWaveform   — float[] (2000 pts, -1..1) for the road (dashcam) video
 *   faceWaveform   — float[] (2000 pts, -1..1) for the face (phone) video
 *   roadDuration   — number (seconds)
 *   faceDuration   — number (seconds)
 *   offset         — number (seconds); positive → face lags road
 *   onOffsetChange — (newOffset: number) => void
 *   currentTime    — number (seconds); road video playback position for playhead
 */
import { useRef, useEffect, useCallback } from 'react';

const ROAD_COLOR     = 'rgba(0, 210, 223, 0.8)';   // cyan
const FACE_COLOR     = 'rgba(255, 193, 7, 0.75)';  // amber
const BG_COLOR       = '#0d1117';
const ZERO_COLOR     = 'rgba(255,255,255,0.15)';
const BOUND_COLOR    = 'rgba(255,255,255,0.6)';
const PLAYHEAD_COLOR = 'rgba(255, 255, 255, 0.95)';

export default function AudioWaveform({
  roadWaveform,
  faceWaveform,
  roadDuration,
  faceDuration,
  offset,
  onOffsetChange,
  currentTime = 0,
}) {
  const canvasRef  = useRef(null);
  const dragRef    = useRef(null); // { startX, startOffset }

  // ------------------------------------------------------------------
  // Draw
  // ------------------------------------------------------------------
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    const midY = H / 2;

    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, W, H);

    // Zero line
    ctx.strokeStyle = ZERO_COLOR;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(W, midY);
    ctx.stroke();

    if (!roadWaveform || !faceWaveform || !roadDuration) return;

    const shiftPx = (offset / roadDuration) * W;

    // Helper: draw one waveform
    const drawWave = (waveform, color, xOrigin, xScale) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      const n = waveform.length;
      for (let i = 0; i < n; i++) {
        const x = xOrigin + (i / (n - 1)) * W * xScale;
        const y = midY - waveform[i] * (midY * 0.85);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };

    // Road waveform — spans full canvas width
    drawWave(roadWaveform, ROAD_COLOR, 0, 1);

    // Face waveform — shifted right by shiftPx, scaled by duration ratio
    const faceScale = faceDuration > 0 ? faceDuration / roadDuration : 1;
    drawWave(faceWaveform, FACE_COLOR, shiftPx, faceScale);

    // Sync boundary line
    if (shiftPx > 0 && shiftPx < W) {
      ctx.strokeStyle = BOUND_COLOR;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(shiftPx, 0);
      ctx.lineTo(shiftPx, H);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Playhead — solid white line at current road video time
    if (currentTime > 0 && roadDuration > 0) {
      const playheadX = (currentTime / roadDuration) * W;
      ctx.strokeStyle = PLAYHEAD_COLOR;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(playheadX, 0);
      ctx.lineTo(playheadX, H);
      ctx.stroke();

      // Small triangle marker at the top
      ctx.fillStyle = PLAYHEAD_COLOR;
      ctx.beginPath();
      ctx.moveTo(playheadX - 5, 0);
      ctx.lineTo(playheadX + 5, 0);
      ctx.lineTo(playheadX, 8);
      ctx.closePath();
      ctx.fill();
    }
  }, [roadWaveform, faceWaveform, roadDuration, faceDuration, offset, currentTime]);

  // ------------------------------------------------------------------
  // Resize observer — keep canvas pixel dimensions in sync with CSS size
  // ------------------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        canvas.width  = entry.contentRect.width;
        canvas.height = entry.contentRect.height;
        draw();
      }
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [draw]);

  // Redraw when data / offset changes
  useEffect(() => { draw(); }, [draw]);

  // ------------------------------------------------------------------
  // Drag-to-adjust offset
  // ------------------------------------------------------------------
  const pxToSeconds = useCallback((dx) => {
    const canvas = canvasRef.current;
    if (!canvas || !roadDuration) return 0;
    return (dx / canvas.clientWidth) * roadDuration;
  }, [roadDuration]);

  const onMouseDown = useCallback((e) => {
    dragRef.current = { startX: e.clientX, startOffset: offset };
  }, [offset]);

  const onMouseMove = useCallback((e) => {
    if (!dragRef.current) return;
    const { startX, startOffset } = dragRef.current;
    const delta = pxToSeconds(e.clientX - startX);
    onOffsetChange(startOffset + delta);
  }, [pxToSeconds, onOffsetChange]);

  const onMouseUp = useCallback(() => { dragRef.current = null; }, []);

  const onTouchStart = useCallback((e) => {
    dragRef.current = { startX: e.touches[0].clientX, startOffset: offset };
  }, [offset]);

  const onTouchMove = useCallback((e) => {
    if (!dragRef.current) return;
    const { startX, startOffset } = dragRef.current;
    const delta = pxToSeconds(e.touches[0].clientX - startX);
    onOffsetChange(startOffset + delta);
  }, [pxToSeconds, onOffsetChange]);

  const onTouchEnd = useCallback(() => { dragRef.current = null; }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '160px', cursor: 'ew-resize', display: 'block', borderRadius: '4px' }}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    />
  );
}
