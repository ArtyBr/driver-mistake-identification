import logging
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form, Depends
from sqlmodel import Session

from ..core.config import UPLOAD_DIR
from ..db.database import get_session
from ..services.job_service import JobService
from ..models.schemas import JobCreateResponse, JobStatusResponse, AnalysisListResponse
from ..models.job import Job

router = APIRouter()
logger = logging.getLogger(__name__)

def get_job_service(session: Session = Depends(get_session)) -> JobService:
    return JobService(session)

@router.post("/upload", response_model=JobCreateResponse)
async def upload_videos(
    background_tasks: BackgroundTasks,
    video_road: List[UploadFile] = File(...),
    video_face: List[UploadFile] = File(...),
    keep_videos: bool = Form(False),
    service: JobService = Depends(get_job_service)
):
    """
    Uploads road and face videos and starts the analysis process in the background.
    Supports multiple files per category (will be spliced).
    """
    if not video_road or not video_face:
        raise HTTPException(status_code=400, detail="Both road and face videos are required")

    job = service.create_job(video_road, video_face, background_tasks, keep_videos)
    return {"job_id": job.id}

@router.get("/list_analyses", response_model=AnalysisListResponse)
async def list_analyses(service: JobService = Depends(get_job_service)):
    """
    Lists all available completed analyses (folders with results.json).
    Useful for loading previous results.
    """
    analyses = service.list_analyses()
    return {"analyses": analyses}

@router.post("/run_test", response_model=JobCreateResponse)
async def run_test(analysis_id: Optional[str] = None, service: JobService = Depends(get_job_service)):
    """
    Simulates running an analysis by loading an existing result.
    If analysis_id is not provided, tries to load 'test_video'.
    Returns a new job ID that points to the existing data.
    """
    try:
        job = service.create_test_job(analysis_id)
        return {"job_id": job.id}
    except FileNotFoundError as e:
         raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
         logger.error(f"Error in run_test: {e}")
         raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str, service: JobService = Depends(get_job_service)):
    """
    Retrieves the status of a job.
    """
    job = service.get_job(job_id)
    if not job:
        return {"status": "NOT_FOUND"}
    
    # Calculate relative URLs for static serving
    road_url = ""
    face_url = ""
    
    # Logic to resolve path relative to uploads if possible
    # UPLOAD_DIR = backend/../uploads
    if job.road_path:
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

    if job.face_path:
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
        "progress": job.progress,
        "road_url": road_url,
        "face_url": face_url,
        "road_metadata": json.loads(job.road_metadata) if job.road_metadata else None,
        "face_metadata": json.loads(job.face_metadata) if job.face_metadata else None,
        "error": job.error
    }

@router.get("/results/{job_id}")
async def get_results(job_id: str, service: JobService = Depends(get_job_service)):
    """
    Retrieves the detailed analysis results for a completed job.
    """
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status == "COMPLETED" and job.result:
        return json.loads(job.result)
    elif job.status == "FAILED":
        return {"error": job.error}
    else:
        return {"status": job.status}