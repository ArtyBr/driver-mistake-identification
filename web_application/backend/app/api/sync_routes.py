"""
Sync routes — audio cross-correlation for video synchronisation.

POST /sync/analyze
  Accepts two video files (each may be multi-part; parts are spliced server-side),
  computes the temporal offset via FFT cross-correlation, and returns waveform data,
  a session_id, and backend-served video URLs for the browser.
  No authentication required (session is short-lived temp storage).

POST /sync/submit
  Accepts a session_id + confirmed offset, trims both videos to their temporal
  intersection, creates a Job DB record, and submits to the SLURM pipeline.
  Requires authentication.

Temp files are kept so the frontend can stream them via /static/.
Old sync_temp directories (>30 min) are cleaned up at the start of each request.
"""

import uuid
import json
import shutil
import logging
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from ..core.config import UPLOAD_DIR
from ..db.database import get_session
from ..models.job import Job
from ..models.user import User
from ..services import sync_service
from ..services.analysis_service import run_analysis_process
from ..services.auth_service import get_current_user
from ..services.job_service import JobService
from ..services.file_service import FileService
from ..services.video_utils import get_video_duration, splice_videos, trim_video

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])

SYNC_TEMP_DIR = UPLOAD_DIR / "sync_temp"
MAX_AGE_SECONDS = 30 * 60  # 30 minutes
MIN_OVERLAP_SECONDS = 2.0


def get_job_service(session: Session = Depends(get_session)) -> JobService:
    return JobService(session)


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


def _do_analyze_background(
    session_id: str, road_parts: List[Path], face_parts: List[Path], temp_dir: Path
) -> None:
    """Splice videos and compute sync offset; write result or error JSON to session dir."""
    road_path   = temp_dir / "road.mp4"
    face_path   = temp_dir / "face.mp4"
    result_path = temp_dir / "sync_result.json"
    error_path  = temp_dir / "sync_error.json"
    try:
        if not splice_videos(road_parts, road_path):
            raise ValueError("Failed to splice road video parts.")
        if not splice_videos(face_parts, face_path):
            raise ValueError("Failed to splice face video parts.")

        result = sync_service.analyze_sync(road_path, face_path)
        result["session_id"]     = session_id
        result["road_video_url"] = f"/static/sync_temp/{session_id}/road.mp4"
        result["face_video_url"] = f"/static/sync_temp/{session_id}/face.mp4"
        result_path.write_text(json.dumps(result))
    except Exception as exc:
        logger.exception("Background sync analysis failed for session %s: %s", session_id, exc)
        try:
            error_path.write_text(json.dumps({"detail": str(exc)}))
        except Exception:
            pass


@router.post("/init")
async def init_sync():
    """Initializes a new sync analysis session."""
    _cleanup_old_sessions()
    session_id = str(uuid.uuid4())
    temp_dir = SYNC_TEMP_DIR / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    return {"session_id": session_id}

@router.post("/{session_id}/file/{video_type}")
async def upload_sync_file(
    session_id: str,
    video_type: str,
    file: UploadFile = File(...),
):
    """Uploads a single file part to a sync session."""
    if video_type not in ["road", "face"]:
        raise HTTPException(status_code=400, detail="Invalid video_type.")
        
    temp_dir = SYNC_TEMP_DIR / session_id
    if not temp_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")
        
    try:
        FileService.save_single_upload(temp_dir, file, video_type)
        return {"message": "File uploaded"}
    except Exception as exc:
        logger.error("Failed to save sync file part: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save file part")

@router.post("/{session_id}/finalize")
async def finalize_sync_analysis(
    session_id: str,
    background_tasks: BackgroundTasks,
):
    """Splicing and start background sync analysis."""
    temp_dir = SYNC_TEMP_DIR / session_id
    if not temp_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")
        
    road_parts = sorted(list(temp_dir.glob("road_part_*.mp4")))
    face_parts = sorted(list(temp_dir.glob("face_part_*.mp4")))
    
    if not road_parts or not face_parts:
        raise HTTPException(status_code=400, detail="Both road and face parts are required")
        
    background_tasks.add_task(_do_analyze_background, session_id, road_parts, face_parts, temp_dir)
    return {"session_id": session_id, "status": "processing"}

@router.post("/analyze")
async def analyze_sync(
    background_tasks: BackgroundTasks,
    road_video: List[UploadFile] = File(...),
    face_video: List[UploadFile] = File(...),
):
    """
    Save uploaded video parts and kick off audio cross-correlation in the background.

    Returns immediately with {session_id, status: "processing"}.
    Poll GET /sync/status/{session_id} for the result.
    """
    _cleanup_old_sessions()

    session_id = str(uuid.uuid4())
    temp_dir = SYNC_TEMP_DIR / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        road_parts: List[Path] = []
        for i, part in enumerate(road_video):
            p = temp_dir / f"road_part_{i}.mp4"
            with open(p, "wb") as buf:
                shutil.copyfileobj(part.file, buf)
            road_parts.append(p)

        face_parts: List[Path] = []
        for i, part in enumerate(face_video):
            p = temp_dir / f"face_part_{i}.mp4"
            with open(p, "wb") as buf:
                shutil.copyfileobj(part.file, buf)
            face_parts.append(p)
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error("Failed to save uploaded files for session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail="Failed to save uploaded files.")

    background_tasks.add_task(_do_analyze_background, session_id, road_parts, face_parts, temp_dir)
    return {"session_id": session_id, "status": "processing"}


@router.get("/status/{session_id}")
async def get_sync_status(session_id: str):
    """
    Poll the status of a sync analysis session started by POST /sync/analyze.

    Returns {status: "processing"} while running,
    {status: "done", ...result_fields} on success, or
    {status: "error", detail: "..."} on failure.
    """
    temp_dir = SYNC_TEMP_DIR / session_id
    if not temp_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    result_path = temp_dir / "sync_result.json"
    error_path  = temp_dir / "sync_error.json"

    if result_path.exists():
        return {"status": "done", **json.loads(result_path.read_text())}
    if error_path.exists():
        error_data = json.loads(error_path.read_text())
        return {"status": "error", "detail": error_data.get("detail", "Unknown error")}
    return {"status": "processing"}


class SyncSubmitRequest(BaseModel):
    session_id: str
    offset: float
    name: Optional[str] = None
    keep_videos: bool = False
    calibration_id: Optional[str] = None


@router.post("/submit")
async def submit_sync(
    body: SyncSubmitRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
):
    """
    Trim both synced videos to their temporal intersection and submit for analysis.

    offset = face_start − road_start  (same sign convention as sync_service)
      offset > 0  → road started earlier; skip first `offset` seconds of road
      offset < 0  → face started earlier; skip first `|offset|` seconds of face
    """
    session_dir = SYNC_TEMP_DIR / body.session_id
    road_src = session_dir / "road.mp4"
    face_src = session_dir / "face.mp4"

    if not road_src.exists() or not face_src.exists():
        raise HTTPException(
            status_code=404,
            detail="Session expired or not found — please re-run sync analysis.",
        )

    # Measure durations
    road_dur = get_video_duration(road_src)
    face_dur = get_video_duration(face_src)

    # Trim geometry
    skip_road = max(0.0, body.offset)
    skip_face = max(0.0, -body.offset)
    overlap = min(road_dur - skip_road, face_dur - skip_face)

    if overlap < MIN_OVERLAP_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"Offset leaves less than {MIN_OVERLAP_SECONDS}s of overlapping content "
                   f"(overlap = {overlap:.2f}s). Adjust the offset and try again.",
        )

    # Generate a unique job_id
    base = "sync"
    job_id = f"{base}_{uuid.uuid4().hex[:8]}"
    while (UPLOAD_DIR / job_id).exists():
        job_id = f"{base}_{uuid.uuid4().hex[:8]}"

    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    road_out = job_dir / "road.mp4"
    face_out = job_dir / "face.mp4"

    try:
        if not trim_video(road_src, road_out, skip_road, overlap):
            raise RuntimeError("FFmpeg failed to trim road video.")
        if not trim_video(face_src, face_out, skip_face, overlap):
            raise RuntimeError("FFmpeg failed to trim face video.")
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.error("Trim failed for session %s: %s", body.session_id, exc)
        raise HTTPException(status_code=500, detail=f"Video trimming failed: {exc}")

    # Build metadata (mirrors job_service.create_job pattern)
    road_meta = json.dumps({
        "filenames": ["road.mp4"],
        "count": 1,
        "sizes": [road_out.stat().st_size],
        "duration": overlap,
    })
    face_meta = json.dumps({
        "filenames": ["face.mp4"],
        "count": 1,
        "sizes": [face_out.stat().st_size],
        "duration": overlap,
    })

    # Persist Job record
    job = Job(
        id=job_id,
        name=body.name or job_id,
        status="PENDING",
        owner_id=current_user.id,
        calibration_id=body.calibration_id,
        road_path=f"REMOTE:{job_id}/road.mp4",
        face_path=f"REMOTE:{job_id}/face.mp4",
        road_metadata=road_meta,
        face_metadata=face_meta,
    )
    service.session.add(job)
    service.session.commit()
    service.session.refresh(job)

    # Check per-user calibration
    models_dir = None
    from ..services import calibration_service as cal_svc
    if body.calibration_id and cal_svc.has_trained_model(current_user.id, body.calibration_id):
        models_dir = str(cal_svc.get_user_model_dir(current_user.id, body.calibration_id))

    # Submit to SLURM pipeline
    background_tasks.add_task(
        run_analysis_process,
        job_id,
        str(road_out),
        str(face_out),
        body.keep_videos,
        json.loads(road_meta),
        json.loads(face_meta),
        models_dir,
    )

    # Clean up sync temp session
    shutil.rmtree(session_dir, ignore_errors=True)

    return {"job_id": job_id}
