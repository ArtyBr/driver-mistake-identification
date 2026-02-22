"""
Sync routes — experimental audio cross-correlation endpoint.

POST /sync/analyze
  Accepts two video files, computes the temporal offset via FFT cross-correlation,
  and returns waveform data + backend-served video URLs for the browser.
  No authentication required (prototype endpoint).

Temp files are kept so the frontend can stream them via /static/.
Old sync_temp directories (>30 min) are cleaned up at the start of each request.
"""

import uuid
import shutil
import logging
import time
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException

from ..core.config import UPLOAD_DIR
from ..services import sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])

SYNC_TEMP_DIR = UPLOAD_DIR / "sync_temp"
MAX_AGE_SECONDS = 30 * 60  # 30 minutes


def _cleanup_old_sessions():
    """Remove sync_temp subdirectories older than MAX_AGE_SECONDS."""
    if not SYNC_TEMP_DIR.exists():
        return
    now = time.time()
    for session_dir in SYNC_TEMP_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        try:
            age = now - session_dir.stat().st_mtime
            if age > MAX_AGE_SECONDS:
                shutil.rmtree(session_dir, ignore_errors=True)
                logger.info("Cleaned up old sync session: %s", session_dir.name)
        except OSError:
            pass


@router.post("/analyze")
async def analyze_sync(
    road_video: UploadFile = File(...),
    face_video: UploadFile = File(...),
):
    """
    Compute the audio-based temporal offset between two videos.

    Returns offset_seconds, per-video durations, downsampled waveforms,
    a correlation confidence score, and backend URLs to stream the videos.
    """
    _cleanup_old_sessions()

    session_id = str(uuid.uuid4())
    temp_dir = SYNC_TEMP_DIR / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    road_path = temp_dir / "road.mp4"
    face_path = temp_dir / "face.mp4"

    try:
        road_path.write_bytes(await road_video.read())
        face_path.write_bytes(await face_video.read())

        result = sync_service.analyze_sync(road_path, face_path)

        # Return backend-served URLs instead of relying on blob: (blocked by CSP in production)
        result["road_video_url"] = f"/static/sync_temp/{session_id}/road.mp4"
        result["face_video_url"] = f"/static/sync_temp/{session_id}/face.mp4"
        return result

    except ValueError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.warning("Sync analysis failed (bad input): %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.exception("Unexpected error during sync analysis: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during synchronisation analysis.",
        )
