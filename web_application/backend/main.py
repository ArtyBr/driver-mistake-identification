import sys
import os
import shutil
import uuid
import re
import json
import threading
import logging
import traceback
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add paths
current_dir = Path(__file__).resolve().parent
web_app_dir = current_dir.parent
project_root = web_app_dir.parent

# Paths required for imports to work
sys.path.extend([
    str(project_root),
    str(project_root / "combined_analysis"),
    str(project_root / "combined_analysis" / "src"),
    str(project_root / "lane_detection"), 
    str(project_root / "lane_detection" / "lanedet"),
])

logger.info(f"Sys Path: {sys.path}")

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOAD_DIR = web_app_dir / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

# Job Store (In-memory for prototype)
jobs: Dict[str, Dict] = {}

import subprocess

def process_video_task(job_id: str, road_path: str, face_path: str):
    try:
        jobs[job_id]["status"] = "PROCESSING"
        
        output_json_path = UPLOAD_DIR / job_id / "results.json"
        script_path = project_root / "combined_analysis/run_headless.py"
        
        cmd = [
            "python", "-u", str(script_path),
            "--road", str(road_path),
            "--face", str(face_path),
            "--output", str(output_json_path)
        ]
        
        print(f"Job {job_id}: Starting subprocess: {' '.join(cmd)}")
        
        # Run subprocess and stream output
        with subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            cwd=str(project_root),
            bufsize=1,
            universal_newlines=True
        ) as process:
            for line in process.stdout:
                print(f"Job {job_id}: {line.strip()}")
                
                # Extract progress
                match = re.search(r"(\d+)%\|", line)
                if match:
                    try:
                        progress = int(match.group(1))
                        jobs[job_id]["progress"] = progress
                    except ValueError:
                        pass
        
        # Check if output file exists regardless of return code
        if output_json_path.exists():
            print(f"Job {job_id}: Output file found. Assuming success despite potential exit codes.")
            with open(output_json_path, 'r') as f:
                analysis_result = json.load(f)
            
            jobs[job_id]["status"] = "COMPLETED"
            jobs[job_id]["result"] = analysis_result
            print(f"Job {job_id} completed successfully.")
        else:
            if process.returncode != 0:
                raise Exception(f"Subprocess failed with code {process.returncode} and no output file was created.")
            else:
                raise FileNotFoundError("Output JSON was not created by subprocess.")
        
    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        jobs[job_id]["status"] = "FAILED"
        jobs[job_id]["error"] = str(e)
        traceback.print_exc()

@app.post("/upload")
async def upload_videos(
    background_tasks: BackgroundTasks,
    video_road: UploadFile = File(...),
    video_face: UploadFile = File(...)
):
    # Generate a user-friendly job ID/folder name from the road video filename
    base_name = Path(video_road.filename).stem
    # Sanitize: replace non-alphanumeric with underscore
    safe_name = re.sub(r'[^\w\-]', '_', base_name)
    
    job_id = safe_name
    job_dir = UPLOAD_DIR / job_id
    
    # Handle duplicates by appending a counter
    counter = 1
    while job_dir.exists():
        job_id = f"{safe_name}_{counter}"
        job_dir = UPLOAD_DIR / job_id
        counter += 1
    
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Save as standard names
    road_path = job_dir / "road.mp4"
    face_path = job_dir / "face.mp4"
    
    with open(road_path, "wb") as buffer:
        shutil.copyfileobj(video_road.file, buffer)
        
    with open(face_path, "wb") as buffer:
        shutil.copyfileobj(video_face.file, buffer)
        
    jobs[job_id] = {
        "status": "PENDING",
        "road_url": f"/static/{job_id}/road.mp4",
        "face_url": f"/static/{job_id}/face.mp4"
    }
    
    background_tasks.add_task(process_video_task, job_id, str(road_path), str(face_path))
    
    return {"job_id": job_id}

@app.get("/list_analyses")
async def list_analyses():
    """List all available completed analyses (folders with results.json)"""
    analyses = []
    if UPLOAD_DIR.exists():
        for path in UPLOAD_DIR.iterdir():
            if path.is_dir() and (path / "results.json").exists():
                analyses.append(path.name)
    return {"analyses": sorted(analyses)}

@app.post("/run_test")
async def run_test(background_tasks: BackgroundTasks, analysis_id: str = None):
    # 1. Generate a new ID so the frontend has a handle to query (or reuse the analysis_id)
    # Actually, for viewing an existing result, we might not strictly need a new job ID 
    # if we just want to load it. But to keep the frontend flow consistent (polling etc),
    # we can just register the existing analysis as a "COMPLETED" job.
    
    source_job_id = analysis_id if analysis_id else "test_video"
    source_dir = UPLOAD_DIR / source_job_id
    results_path = source_dir / "results.json"

    if not results_path.exists():
        logger.error(f"Results not found at {results_path}")
        return {"error": f"Analysis '{source_job_id}' not found or incomplete."}

    # 3. Load the existing result JSON
    with open(results_path, 'r') as f:
        result_data = json.load(f)

    # 4. Find the video files - prefer standard names, fallback to glob
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

    # Use the source_job_id as the key so we don't spawn infinite new UUIDs for the same data
    # But if the frontend expects a unique handle every time (to reset state), we can use a new UUID.
    # The frontend uses the returned ID to poll status.
    
    # If we use a new UUID, we need to make sure the URLs point to the OLD directory.
    new_job_id = str(uuid.uuid4())

    jobs[new_job_id] = {
        "status": "COMPLETED",
        "road_url": f"/static/{source_job_id}/{road_filename}",
        "face_url": f"/static/{source_job_id}/{face_filename}",
        "result": result_data
    }

    return {"job_id": new_job_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    return jobs.get(job_id, {"status": "NOT_FOUND"})

@app.get("/results/{job_id}")
async def get_results(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    
    if job["status"] == "COMPLETED":
        return job["result"]
    elif job["status"] == "FAILED":
        return {"error": job.get("error")}
    else:
        return {"status": job["status"]}

# Serve uploaded files statically
app.mount("/static", StaticFiles(directory=str(UPLOAD_DIR)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)