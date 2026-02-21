import logging
import json
import subprocess
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ..core.config import UPLOAD_DIR
from ..db.database import get_session
from ..services.job_service import JobService
from ..services.auth_service import get_current_user, get_optional_current_user
from ..models.schemas import JobCreateResponse, JobStatusResponse, AnalysisListResponse, JobUpdate
from ..models.job import Job
from ..models.user import User
from . import auth_routes

router = APIRouter()
logger = logging.getLogger(__name__)

# Include Auth Routes
router.include_router(auth_routes.router, tags=["auth"])

def get_job_service(session: Session = Depends(get_session)) -> JobService:
    return JobService(session)

@router.post("/upload", response_model=JobCreateResponse)
async def upload_videos(
    background_tasks: BackgroundTasks,
    video_road: List[UploadFile] = File(...),
    video_face: List[UploadFile] = File(...),
    keep_videos: bool = Form(False),
    name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service)
):
    """
    Uploads road and face videos and starts the analysis process in the background.
    Supports multiple files per category (will be spliced).
    """
    if not video_road or not video_face:
        raise HTTPException(status_code=400, detail="Both road and face videos are required")

    job = service.create_job(video_road, video_face, background_tasks, keep_videos, owner_id=current_user.id)
    
    # Update name if provided
    if name:
        service.update_job_name(job.id, name)
        
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
    analyses = service.list_analyses(user_id=current_user.id if current_user else None)
    return {"analyses": analyses}

@router.delete("/job/{job_id}")
async def delete_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
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
    
    # Check authorization
    is_owner = current_user and job.owner_id == current_user.id
    if not job.is_demo and not is_owner:
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

    return {
        "status": job.status,
        "name": job.name,
        "is_demo": job.is_demo,
        "progress": job.progress,
        "road_url": road_url,
        "face_url": face_url,
        "road_metadata": json.loads(job.road_metadata) if job.road_metadata else None,
        "face_metadata": json.loads(job.face_metadata) if job.face_metadata else None,
        "error": job.error
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
    
    # Check authorization
    is_owner = current_user and job.owner_id == current_user.id
    if not job.is_demo and not is_owner:
         raise HTTPException(status_code=403, detail="Not authorized to view these results")

    results = service.load_results(job_id)
    if results:
        return results

    # Handle status-based responses
    if job.status == "FAILED":
        return {"error": job.error or "Analysis failed without detailed error message."}
    else:
        return {"status": job.status}

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
    except Exception:
         pass

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
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }

    return StreamingResponse(
        iterfile(safe_path, start, content_length),
        status_code=206, # Partial Content
        headers=headers,
        media_type="video/mp4"
    )