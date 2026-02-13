import subprocess
import json
import re
import logging
import traceback
from pathlib import Path
from sqlmodel import Session
from ..core.config import PROJECT_ROOT, UPLOAD_DIR
from ..db.database import engine
from ..models.job import Job
from .sync_service import SyncService
from .training_service import TrainingService

logger = logging.getLogger(__name__)

def update_job(job_id: str, status: str = None, progress: int = None, error: str = None, result: dict = None, sync_offset: float = None):
    """Helper to update job in a fresh session."""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job:
            if status: 
                job.status = status
            if progress is not None: 
                job.progress = progress
            if error: 
                job.error = error
            if sync_offset is not None:
                job.sync_offset = sync_offset
            if result: 
                job.result = json.dumps(result)
                job.status = "COMPLETED"
                job.progress = 100
            session.add(job)
            session.commit()

def run_analysis_process(job_id: str, road_path: str, face_path: str, keep_videos: bool = False, road_metadata: dict = None, face_metadata: dict = None) -> None:
    """
    Executes the analysis script in a subprocess.
    Updates the database with status, progress, and results.
    """
    try:
        logger.info(f"Starting analysis for Job {job_id}")
        update_job(job_id, status="PROCESSING")

        # Step 1: Calculate Sync Offset
        logger.info(f"Calculating sync offset for Job {job_id}")
        sync_offset = SyncService.get_audio_offset(Path(road_path), Path(face_path))
        update_job(job_id, sync_offset=sync_offset)

        # Step 2: Train Custom SVM if calibration exists
        custom_svm_path = None
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if job and job.calibration_data:
                logger.info(f"Training custom SVM for Job {job_id}")
                custom_svm_path = TrainingService.train_gaze_model(job_id, job.calibration_data, Path(road_path).parent)
        
        output_json_path = UPLOAD_DIR / job_id / "results.json"
        script_path = PROJECT_ROOT / "combined_analysis/run_headless.py"
        
        cmd = [
            "python", "-u", str(script_path),
            "--road", str(road_path),
            "--face", str(face_path),
            "--output", str(output_json_path),
            "--offset", str(sync_offset)
        ]

        if custom_svm_path:
            cmd.extend(["--svm", str(custom_svm_path)])

        if road_metadata:
            cmd.extend(["--road_meta", json.dumps(road_metadata)])
        if face_metadata:
            cmd.extend(["--face_meta", json.dumps(face_metadata)])
        
        logger.debug(f"Command: {' '.join(cmd)}")
        
        # Run subprocess and stream output for progress tracking
        with subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            cwd=str(PROJECT_ROOT),
            bufsize=1,
            universal_newlines=True
        ) as process:
            for line in process.stdout:
                # Log only if necessary or debug
                # logger.debug(f"Job {job_id} output: {line.strip()}")
                
                # Extract progress percentage from standard output
                # Expecting format like "35%|" from tqdm or custom print
                match = re.search(r"(\d+)%\|", line)
                if match:
                    try:
                        progress = int(match.group(1))
                        update_job(job_id, status="PROCESSING", progress=progress)
                    except ValueError:
                        pass
        
        # Post-process validation
        if output_json_path.exists():
            logger.info(f"Job {job_id}: Output file found.")
            with open(output_json_path, 'r') as f:
                analysis_result = json.load(f)
            
            update_job(job_id, result=analysis_result)
            
            # Cleanup videos if not keeping them
            if not keep_videos:
                try:
                    r_p = Path(road_path)
                    f_p = Path(face_path)
                    if r_p.exists(): r_p.unlink()
                    if f_p.exists(): f_p.unlink()
                    logger.info(f"Job {job_id}: Deleted source videos.")
                except Exception as cleanup_err:
                    logger.warning(f"Job {job_id}: Failed to delete videos: {cleanup_err}")

            logger.info(f"Job {job_id} completed successfully.")
        else:
            if process.returncode != 0:
                error_msg = f"Subprocess failed with code {process.returncode}."
            else:
                error_msg = "Output JSON was not created by subprocess."
            
            logger.error(f"Job {job_id} failed: {error_msg}")
            update_job(job_id, status="FAILED", error=error_msg)
            
    except Exception as e:
        logger.error(f"Job {job_id} exception: {e}")
        traceback.print_exc()
        update_job(job_id, status="FAILED", error=str(e))