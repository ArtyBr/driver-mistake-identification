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
from .batch_service import BatchService

logger = logging.getLogger(__name__)

def update_job(job_id: str, status: str = None, progress: int = None, error: str = None, result: dict = None, batch_job_id: str = None):
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
            if batch_job_id:
                job.batch_job_id = batch_job_id
            if result: 
                job.result = json.dumps(result)
                job.status = "COMPLETED"
                job.progress = 100
            session.add(job)
            session.commit()

def run_analysis_process(job_id: str, road_path: str, face_path: str, keep_videos: bool = False, road_metadata: dict = None, face_metadata: dict = None) -> None:

    """

    Submits the analysis job to the compute cluster via SLURM.

    """

    try:

        logger.info(f"Submitting Job {job_id} to batch cluster")

        update_job(job_id, status="SUBMITTED")

        

        output_json_path = UPLOAD_DIR / job_id / "results.json"

        

        batch_service = BatchService()

        

        road_meta_str = json.dumps(road_metadata) if road_metadata else None

        face_meta_str = json.dumps(face_metadata) if face_metadata else None

        

        sbatch_script = batch_service._generate_sbatch_script(

            job_name=f"safedrive_{job_id[:8]}",

            road_path=str(road_path),

            face_path=str(face_path),

            output_path=str(output_json_path),

            road_meta=road_meta_str,

            face_meta=face_meta_str

        )

        

        slurm_job_id = batch_service.submit_job(sbatch_script)

        

        logger.info(f"Job {job_id} submitted to SLURM with ID: {slurm_job_id}")

        update_job(job_id, status="SUBMITTED", batch_job_id=slurm_job_id)

        

    except Exception as e:

        logger.error(f"Failed to submit Job {job_id}: {e}")

        traceback.print_exc()

        update_job(job_id, status="FAILED", error=str(e))
