import shutil
import uuid
import re
import json
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from ..core.config import UPLOAD_DIR
from ..db import database
from ..services.analysis_service import run_analysis_process
from ..models.schemas import JobCreateResponse, JobStatusResponse, AnalysisListResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=JobCreateResponse)
async def upload_videos(
    background_tasks: BackgroundTasks,
    video_road: UploadFile = File(...),
    video_face: UploadFile = File(...)
):
    """
    Uploads road and face videos and starts the analysis process in the background.
    """
    # Generate a safe job ID from the filename
    base_name = Path(video_road.filename).stem
    safe_name = re.sub(r'[^\w\-]', '_', base_name)
    
    job_id = safe_name
    job_dir = UPLOAD_DIR / job_id
    
    # Handle duplicates
    counter = 1
    while job_dir.exists():
        job_id = f"{safe_name}_{counter}"
        job_dir = UPLOAD_DIR / job_id
        counter += 1
    
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Save files
    road_path = job_dir / "road.mp4"
    face_path = job_dir / "face.mp4"
    
    with open(road_path, "wb") as buffer:
        shutil.copyfileobj(video_road.file, buffer)
        
    with open(face_path, "wb") as buffer:
        shutil.copyfileobj(video_face.file, buffer)
        
    # Create DB entry
    database.create_job(job_id, str(road_path), str(face_path))
    
    # Trigger background task
    background_tasks.add_task(run_analysis_process, job_id, str(road_path), str(face_path))
    
    return {"job_id": job_id}

@router.get("/list_analyses", response_model=AnalysisListResponse)
async def list_analyses():
    """
    Lists all available completed analyses (folders with results.json).
    Useful for loading previous results.
    """
    analyses = []
    if UPLOAD_DIR.exists():
        for path in UPLOAD_DIR.iterdir():
            if path.is_dir() and (path / "results.json").exists():
                analyses.append(path.name)
    return {"analyses": sorted(analyses)}

@router.post("/run_test", response_model=JobCreateResponse)
async def run_test(analysis_id: str = None):
    """
    Simulates running an analysis by loading an existing result.
    If analysis_id is not provided, tries to load 'test_video'.
    Returns a new job ID that points to the existing data.
    """
    source_job_id = analysis_id if analysis_id else "test_video"
    source_dir = UPLOAD_DIR / source_job_id
    results_path = source_dir / "results.json"

    if not results_path.exists():
        raise HTTPException(status_code=404, detail=f"Analysis '{source_job_id}' not found or incomplete.")

    with open(results_path, 'r') as f:
        result_data = json.load(f)

    # Find video files
    if (source_dir / "road.mp4").exists():
        road_filename = "road.mp4"
    else:
        road_file = next(source_dir.glob("road_*.mp4"), None)
        road_filename = road_file.name if road_file else "road_test.mp4"

    if (source_dir / "face.mp4").exists():
        face_filename = "face.mp4"
    else:
        face_file = next(source_dir.glob("face_*.mp4"), None)
        face_filename = face_file.name if face_file else "face_test.mp4"

    # Create a new job record that points to the existing files
    new_job_id = str(uuid.uuid4())
    
    database.create_job(new_job_id, str(source_dir / road_filename), str(source_dir / face_filename))
    database.update_job_result(new_job_id, result_data)
    
    return {"job_id": new_job_id}

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str):
    """
    Retrieves the status of a job.
    """
    job = database.get_job(job_id)
    if not job:
        return {"status": "NOT_FOUND"}
    
    # Calculate relative URLs for static serving
    road_path = Path(job["road_path"])
    face_path = Path(job["face_path"])
    
    try:
        # Use relative_to to find path segment under uploads/
        # Since UPLOAD_DIR is absolute, and stored paths are absolute.
        # However, run_test creates paths that might point to other job folders.
        # This is fine as long as they are under UPLOAD_DIR.
        
        # Note: If paths are somehow not under UPLOAD_DIR (e.g. absolute paths elsewhere), this fails.
        # But our logic ensures they are.
        road_rel = road_path.relative_to(UPLOAD_DIR)
        face_rel = face_path.relative_to(UPLOAD_DIR)
        road_url = f"/static/{road_rel}"
        face_url = f"/static/{face_rel}"
    except ValueError:
        road_url = ""
        face_url = ""

    return {
        "status": job["status"],
        "progress": job["progress"],
        "road_url": road_url,
        "face_url": face_url,
        "error": job["error"]
    }

@router.get("/results/{job_id}")
async def get_results(job_id: str):
    """
    Retrieves the detailed analysis results for a completed job.
    """
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] == "COMPLETED":
        return job["result"]
    elif job["status"] == "FAILED":
        return {"error": job["error"]}
    else:
        return {"status": job["status"]}
