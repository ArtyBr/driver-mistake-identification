import logging
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ..core.config import UPLOAD_DIR
from ..db.database import get_session
from ..services.job_service import JobService
from ..services.auth_service import get_current_user, get_optional_current_user, get_verified_user
from ..services.file_service import FileService
from ..services.video_utils import trim_video
from ..models.schemas import JobCreateResponse, JobStatusResponse, AnalysisListResponse, JobUpdate
from ..models.job import Job
from ..models.user import User
from ..models.report import Report, ReportCreate
from . import auth_routes

router = APIRouter()
logger = logging.getLogger(__name__)

# Include Auth Routes
router.include_router(auth_routes.router, tags=["auth"])

# Quality file definitions: (label, road_filename, face_filename)
_QUALITY_FILES = [
    ("1080p", "road.mp4", "face.mp4"),
    ("720p", "road_720p.mp4", "face_720p.mp4"),
    ("480p", "road_480p.mp4", "face_480p.mp4"),
]

_LARGE_BASE = Path("/dcs/large/safedrive_cs310_2526/uploads")


def _build_quality_urls(job_id: str) -> dict:
    """Returns {"road": {quality: url, …}, "face": {quality: url, …}} for available files."""
    road_urls: dict = {}
    face_urls: dict = {}

    # Determine which base directory holds this job's files
    job_dir = None
    for base in [_LARGE_BASE, UPLOAD_DIR]:
        candidate = base / job_id
        if candidate.is_dir():
            job_dir = candidate
            break

    if job_dir is None:
        return {"road": road_urls, "face": face_urls}

    for label, road_file, face_file in _QUALITY_FILES:
        road_path = job_dir / road_file
        face_path = job_dir / face_file
        if road_path.exists():
            road_urls[label] = f"/video/remote/{job_id}/{road_file}"
        if face_path.exists():
            face_urls[label] = f"/video/remote/{job_id}/{face_file}"

    return {"road": road_urls, "face": face_urls}

def _resolve_video_path(job_id: str, filename: str) -> Optional[Path]:
    """Resolve a video file from job storage directories."""
    for base in [_LARGE_BASE, UPLOAD_DIR]:
        p = base / job_id / filename
        if p.exists():
            return p
    return None


def get_job_service(session: Session = Depends(get_session)) -> JobService:
    return JobService(session)

@router.post("/upload/init", response_model=JobCreateResponse)
async def init_upload(
    name: Optional[str] = Form(None),
    calibration_id: Optional[str] = Form(None),
    keep_videos: bool = Form(False),
    current_user: User = Depends(get_verified_user),
    service: JobService = Depends(get_job_service)
):
    """Initializes a new multi-step upload."""
    job = service.init_job(name=name, calibration_id=calibration_id, keep_videos=keep_videos, owner_id=current_user.id)
    return {"job_id": job.id}

@router.post("/upload/{job_id}/file/{video_type}")
async def upload_job_file(
    job_id: str,
    video_type: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_verified_user),
    service: JobService = Depends(get_job_service)
):
    """Uploads a single file part to an existing job."""
    if video_type not in ["road", "face"]:
        raise HTTPException(status_code=400, detail="Invalid video_type. Must be 'road' or 'face'.")
        
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        service.add_file_to_job(job_id, video_type, file)
        return {"message": "File uploaded"}
    except Exception as e:
        logger.error(f"Sequential upload part failed for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/{job_id}/finalize", response_model=JobCreateResponse)
async def finalize_upload(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_verified_user),
    service: JobService = Depends(get_job_service)
):
    """Finalizes a multi-step upload and starts analysis."""
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        service.finalize_upload(job_id, background_tasks)
        return {"job_id": job_id}
    except Exception as e:
        logger.error(f"Finalize upload failed for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload", response_model=JobCreateResponse)
async def upload_videos(
    background_tasks: BackgroundTasks,
    video_road: List[UploadFile] = File(...),
    video_face: List[UploadFile] = File(...),
    keep_videos: bool = Form(False),
    name: Optional[str] = Form(None),
    calibration_id: Optional[str] = Form(None),
    current_user: User = Depends(get_verified_user),
    service: JobService = Depends(get_job_service)
):
    """
    Uploads road and face videos and starts the analysis process in the background.
    Supports multiple files per category (will be spliced).
    """
    if not video_road or not video_face:
        raise HTTPException(status_code=400, detail="Both road and face videos are required")

    job = service.create_job(video_road, video_face, background_tasks, keep_videos, owner_id=current_user.id, calibration_id=calibration_id)

    # Update name if provided
    if name:
        service.update_job_name(job.id, name)

    # Kick off background transcoding for quality variants (ROAD only)
    # FACE transcoding is now handled by the analysis process after blurring
    road_path = UPLOAD_DIR / job.id / "road.mp4"
    background_tasks.add_task(FileService.transcode_job_videos_road_only, job.id, road_path)

    return {"job_id": job.id}

@router.get("/list_analyses", response_model=AnalysisListResponse)
async def list_analyses(
    current_user: Optional[User] = Depends(get_optional_current_user),
    service: JobService = Depends(get_job_service)
):
    """
    Lists available completed analyses. 
    Authenticated users see their own + demos.
    Unauthenticated users see only demos.
    """
    # If user is logged in but not verified, they should only see demos
    effective_user_id = None
    if current_user and current_user.is_verified:
        effective_user_id = current_user.id
        
    analyses = service.list_analyses(user_id=effective_user_id)
    return {"analyses": analyses}

@router.delete("/job/{job_id}")
async def delete_job(
    job_id: str,
    current_user: User = Depends(get_verified_user),
    service: JobService = Depends(get_job_service),
):
    """Deletes a job and its files from disk. Only the owner can delete their jobs."""
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_demo or job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this job")
    service.delete_job(job_id)
    return {"message": "Job deleted"}


@router.put("/job/{job_id}/name", response_model=JobStatusResponse)
async def update_job_name(job_id: str, update: JobUpdate, service: JobService = Depends(get_job_service)):
    """
    Updates the name of an existing job.
    """
    job = service.update_job_name(job_id, update.name)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Return basic status structure
    return {
        "status": job.status,
        "name": job.name,
        "progress": job.progress,
        "error": job.error
    }

@router.post("/run_test", response_model=JobCreateResponse)
async def run_test(
    analysis_id: Optional[str] = None, 
    current_user: Optional[User] = Depends(get_optional_current_user),
    service: JobService = Depends(get_job_service)
):
    """
    Simulates running an analysis by loading an existing result.
    If analysis_id is not provided, tries to load 'test_video'.
    Returns a new job ID that points to the existing data.
    """
    try:
        job = service.create_test_job(analysis_id, owner_id=current_user.id if current_user else None)
        return {"job_id": job.id}
    except FileNotFoundError as e:
         raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
         logger.error(f"Error in run_test: {e}")
         raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(
    job_id: str, 
    force_refresh: bool = False, 
    current_user: Optional[User] = Depends(get_optional_current_user),
    service: JobService = Depends(get_job_service)
):
    """
    Retrieves the status of a job.
    Only accessible by the owner or if the job is marked as a demo.
    """
    job = service.check_job_status(job_id, force_refresh=force_refresh)
    if not job:
        return {"status": "NOT_FOUND"}
    
    # Check authorization: owner, admin, or demo
    is_owner = current_user and job.owner_id == current_user.id
    is_admin = current_user and current_user.is_admin
    if not job.is_demo and not is_owner and not is_admin:
         raise HTTPException(status_code=403, detail="Not authorized to view this job")

    # Calculate relative URLs for static serving
    road_url = ""
    face_url = ""

    # Check for REMOTE prefix first
    if job.road_path and job.road_path.startswith("REMOTE:"):
        # Format: REMOTE:job_id/filename
        parts = job.road_path.split(":")
        if len(parts) > 1:
            remote_part = parts[1] # e.g., "test_video/road_test.mp4"
            r_job, r_file = remote_part.split("/")
            road_url = f"/video/remote/{r_job}/{r_file}"

    # Fallback to local file logic
    elif job.road_path:
        try:
             path_obj = Path(job.road_path)
             # Use resolve to handle absolute/relative mismatches if files exist
             if path_obj.exists() and path_obj.is_absolute():
                 try:
                    rel = path_obj.relative_to(UPLOAD_DIR)
                    road_url = f"/static/{rel}"
                 except ValueError:
                    # Path is not under UPLOAD_DIR
                    pass
        except Exception:
             pass

    # Check for REMOTE prefix first
    if job.face_path and job.face_path.startswith("REMOTE:"):
        parts = job.face_path.split(":")
        if len(parts) > 1:
            remote_part = parts[1]
            r_job, r_file = remote_part.split("/")
            face_url = f"/video/remote/{r_job}/{r_file}"
            
    elif job.face_path:
        try:
             path_obj = Path(job.face_path)
             if path_obj.exists() and path_obj.is_absolute():
                 try:
                    rel = path_obj.relative_to(UPLOAD_DIR)
                    face_url = f"/static/{rel}"
                 except ValueError:
                    pass
        except Exception:
             pass

    # Get calibration name if present
    calibration_name = None
    if job.calibration_id:
        from ..services import calibration_service as cal_svc
        cal = cal_svc.get_calibration_by_id(job.calibration_id, service.session)
        if cal:
            calibration_name = cal.name

    # Build quality URL map for REMOTE jobs
    video_qualities = None
    if job.road_path and job.road_path.startswith("REMOTE:"):
        qmap = _build_quality_urls(job_id)
        if qmap["road"] or qmap["face"]:
            video_qualities = qmap

    return {
        "status": job.status,
        "name": job.name,
        "is_demo": job.is_demo,
        "progress": job.progress,
        "road_url": road_url,
        "face_url": face_url,
        "road_metadata": json.loads(job.road_metadata) if job.road_metadata else None,
        "face_metadata": json.loads(job.face_metadata) if job.face_metadata else None,
        "error": job.error,
        "calibration_id": job.calibration_id,
        "calibration_name": calibration_name,
        "video_qualities": video_qualities,
    }

@router.get("/results/{job_id}")
async def get_results(
    job_id: str, 
    current_user: Optional[User] = Depends(get_optional_current_user),
    service: JobService = Depends(get_job_service)
):
    """
    Retrieves the detailed analysis results for a completed job.
    Only accessible by the owner or if the job is marked as a demo.
    """
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check authorization: owner, admin, or demo
    is_owner = current_user and job.owner_id == current_user.id
    is_admin = current_user and current_user.is_admin
    if not job.is_demo and not is_owner and not is_admin:
         raise HTTPException(status_code=403, detail="Not authorized to view these results")

    results = service.load_results(job_id)
    if results:
        return results

    # Handle status-based responses
    if job.status == "FAILED":
        return {"error": job.error or "Analysis failed without detailed error message."}
    else:
        return {"status": job.status}

@router.get("/job/{job_id}/events")
async def get_job_events(
    job_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    service: JobService = Depends(get_job_service),
):
    """Returns lightweight event stats for a completed job (same auth rules as /results)."""
    from ..services.event_stats import read_event_stats
    job = service.get_job(job_id)
    if not job or job.status != "COMPLETED":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    is_owner = current_user and job.owner_id == current_user.id
    is_admin = current_user and current_user.is_admin
    if not job.is_demo and not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    large_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
    for base in [large_base, UPLOAD_DIR]:
        p = base / job_id / "results.json"
        if p.exists():
            stats = read_event_stats(p)
            if stats is not None:
                return stats
    raise HTTPException(status_code=404, detail="Results not found")


@router.get("/job/{job_id}/clip")
async def download_clip(
    job_id: str,
    timestamp: float,
    service: JobService = Depends(get_job_service),
    _admin: User = Depends(get_current_user),
):
    """
    Admin-only: download a 15-second clip (road + face) centered on `timestamp`.
    Returns a ZIP containing road_clip.mp4 and face_clip.mp4.
    """
    if not _admin.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    road_path = _resolve_video_path(job_id, "road.mp4")
    face_path = _resolve_video_path(job_id, "face.mp4")
    if not road_path or not face_path:
        raise HTTPException(status_code=404, detail="Video files not found")

    start = max(0.0, timestamp - 7.5)
    duration = 15.0

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        road_clip = tmp_dir / "road_clip.mp4"
        face_clip = tmp_dir / "face_clip.mp4"

        if not trim_video(road_path, road_clip, start, duration):
            raise HTTPException(status_code=500, detail="Failed to trim road video")
        if not trim_video(face_path, face_clip, start, duration):
            raise HTTPException(status_code=500, detail="Failed to trim face video")

        zip_path = tmp_dir / "clip.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(road_clip, "road_clip.mp4")
            zf.write(face_clip, "face_clip.mp4")

        def iterfile():
            try:
                with open(zip_path, "rb") as f:
                    while chunk := f.read(1024 * 1024):
                        yield chunk
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return StreamingResponse(
            iterfile(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=clip_{job_id}_{timestamp:.1f}s.zip"},
        )
    except HTTPException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Clip generation failed")


@router.get("/video/remote/{job_id}/{filename}")
async def stream_remote_video(
    job_id: str, 
    filename: str, 
    request: Request,
    range: str = Header(None)
):
    """
    Streams a video file directly from the large storage directory.
    Supports HTTP Range requests for seeking and robust playback.
    """
    base_path = Path("/dcs/large/safedrive_cs310_2526/uploads")
    # precise construction to prevent traversal
    safe_path = base_path / job_id / filename
    
    # Ensure the path is actually within the intended directory (security check)
    try:
        resolved_path = safe_path.resolve()
        resolved_base = base_path.resolve()
        if not resolved_path.is_relative_to(resolved_base):
            raise HTTPException(status_code=403, detail="Access denied")
    except (OSError, ValueError):
        # resolve() failed (e.g. permissions); treat as not found
        raise HTTPException(status_code=404, detail="Video file not found")

    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
        
    file_size = safe_path.stat().st_size
    start = 0
    end = file_size - 1
    chunk_size = 1024 * 1024 # Default 1MB chunks

    # Handle Range Header
    if range:
        try:
            # Parse "bytes=0-", "bytes=100-200", or "bytes=-500"
            range_str = range.replace("bytes=", "")
            range_parts = range_str.split("-")
            
            if range_parts[0] == "":
                # Suffix range: bytes=-500 (last 500 bytes)
                suffix = int(range_parts[1])
                start = max(0, file_size - suffix)
                end = file_size - 1
            elif len(range_parts) > 1 and range_parts[1] == "":
                 # Prefix range: bytes=500- (from 500 to end)
                 start = int(range_parts[0])
                 end = file_size - 1
            else:
                 # Standard range: bytes=0-500
                 start = int(range_parts[0])
                 end = int(range_parts[1])
            
            # Ensure valid range
            if start >= file_size:
                # 416 Range Not Satisfiable
                raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")
                
            # Correct end if it exceeds file size
            end = min(end, file_size - 1)
        except ValueError:
             # Malformed range header, ignore and send full file
             pass

    # Calculate content length for this response
    content_length = (end - start) + 1

    def iterfile(path, start_byte, length):
        with open(path, "rb") as f:
            f.seek(start_byte)
            remaining = length
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }

    if range:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        status_code = 206
    else:
        status_code = 200

    return StreamingResponse(
        iterfile(safe_path, start, content_length),
        status_code=status_code,
        headers=headers,
        media_type="video/mp4"
    )

@router.post("/jobs/{job_id}/report")
async def create_report(
    job_id: str,
    report_data: ReportCreate,
    current_user: User = Depends(get_verified_user),
    service: JobService = Depends(get_job_service)
):
    """Submits an error report for a specific job."""
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    report = Report(
        job_id=job_id,
        user_id=current_user.id,
        timestamp=report_data.timestamp,
        event_type=report_data.event_type,
        report_type=report_data.report_type,
        description=report_data.description
    )
    service.session.add(report)
    service.session.commit()
    service.session.refresh(report)
    return {"message": "Report submitted successfully", "id": report.id}