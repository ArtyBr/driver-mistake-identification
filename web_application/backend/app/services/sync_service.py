"""
Audio synchronisation service.

Extracts audio from two video files via FFmpeg, computes the temporal offset
using FFT cross-correlation (scipy), and returns downsampled waveforms for
display in the browser.

Sign convention (matches audio_sync.py):
  offset > 0  →  face video starts *later* than road (face lags)
  offset < 0  →  face video starts *earlier* than road (face leads)
"""

import logging
import subprocess
import numpy as np
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# Audio extraction parameters
SAMPLE_RATE = 4000   # Hz — low enough for fast FFT, high enough for speech transients
MAX_DURATION = 120   # seconds to analyse (first 2 minutes)
WAVEFORM_POINTS = 2000  # down-sampled points sent to the browser


def extract_audio_pcm(video_path: Path) -> np.ndarray:
    """
    Extract mono PCM audio from *video_path* via FFmpeg.

    Returns a float32 numpy array sampled at SAMPLE_RATE Hz, capped at
    MAX_DURATION seconds.  Raises ValueError if no audio stream is found.
    """
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vn",                       # no video
        "-ac", "1",                  # mono
        "-ar", str(SAMPLE_RATE),     # sample rate
        "-t", str(MAX_DURATION),     # cap duration
        "-f", "f32le",               # raw float32 little-endian
        "pipe:1",                    # write to stdout
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0 and len(result.stdout) == 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        logger.error("FFmpeg failed for %s:\n%s", video_path, stderr_text)
        raise ValueError(
            f"No audio track found in {video_path.name}. "
            "Ensure the video file contains an audio stream."
        )
    pcm = np.frombuffer(result.stdout, dtype=np.float32).copy()
    if pcm.size == 0:
        raise ValueError(
            f"No audio data extracted from {video_path.name}. "
            "The file may have no audio or be corrupt."
        )
    return pcm


def compute_offset(
    road_pcm: np.ndarray, face_pcm: np.ndarray
) -> Tuple[float, float]:
    """
    Compute the temporal offset between two PCM signals via FFT cross-correlation.

    Returns (offset_seconds, correlation_score).
      offset > 0 → face lags road
      offset < 0 → face leads road
    """
    from scipy.signal import fftconvolve  # imported here so import errors are localised

    # Normalise: zero-mean, unit-variance (removes DC offset / volume differences)
    def _normalise(x: np.ndarray) -> np.ndarray:
        x = x - x.mean()
        std = x.std()
        if std > 1e-9:
            x = x / std
        return x

    road_norm = _normalise(road_pcm)
    face_norm = _normalise(face_pcm)

    # Full cross-correlation via FFT convolution
    correlation = fftconvolve(road_norm, face_norm[::-1], mode="full")

    # Peak lag
    peak_idx = int(np.argmax(np.abs(correlation)))
    lag = peak_idx - (len(face_norm) - 1)
    offset_seconds = float(lag / SAMPLE_RATE)

    # Normalised confidence score (clamped to [0, 1])
    peak_value = float(np.abs(correlation[peak_idx]))
    score = peak_value / np.sqrt(len(road_norm) * len(face_norm))
    score = float(np.clip(score, 0.0, 1.0))

    return offset_seconds, score


def downsample_waveform(pcm: np.ndarray, n_points: int = WAVEFORM_POINTS) -> list:
    """
    Down-sample *pcm* to *n_points* via linear interpolation, normalise by
    peak amplitude, and clip to [-1, 1].
    """
    src_indices = np.linspace(0, len(pcm) - 1, n_points)
    resampled = np.interp(src_indices, np.arange(len(pcm)), pcm)
    peak = np.abs(resampled).max()
    if peak > 1e-9:
        resampled = resampled / peak
    resampled = np.clip(resampled, -1.0, 1.0)
    return resampled.tolist()


def get_video_duration(video_path: Path) -> float:
    """Return duration of *video_path* in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        return float(result.stdout.decode().strip())
    except (ValueError, AttributeError):
        return 0.0


def analyze_sync(road_path: Path, face_path: Path) -> dict:
    """
    Full synchronisation analysis pipeline.

    Returns a dict with keys:
      offset_seconds, road_duration, face_duration,
      road_waveform, face_waveform, correlation_score
    """
    logger.info("Extracting audio from road video: %s", road_path.name)
    road_pcm = extract_audio_pcm(road_path)

    logger.info("Extracting audio from face video: %s", face_path.name)
    face_pcm = extract_audio_pcm(face_path)

    logger.info(
        "Computing cross-correlation (road=%d samples, face=%d samples)",
        len(road_pcm), len(face_pcm),
    )
    offset_seconds, correlation_score = compute_offset(road_pcm, face_pcm)

    road_duration = get_video_duration(road_path)
    face_duration = get_video_duration(face_path)

    road_waveform = downsample_waveform(road_pcm)
    face_waveform = downsample_waveform(face_pcm)

    logger.info(
        "Sync result: offset=%.3fs, score=%.3f", offset_seconds, correlation_score
    )

    return {
        "offset_seconds": offset_seconds,
        "road_duration": road_duration,
        "face_duration": face_duration,
        "road_waveform": road_waveform,
        "face_waveform": face_waveform,
        "correlation_score": correlation_score,
    }
