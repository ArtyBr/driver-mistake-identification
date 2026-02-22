import uuid
import re
import json
import logging
import subprocess
from typing import List, Optional
from pathlib import Path
from datetime import datetime
from fastapi import UploadFile, BackgroundTasks
from sqlmodel import Session, select

from ..models.job import Job
from ..models.schemas import AnalysisItem
from ..core.config import UPLOAD_DIR
from .file_service import FileService
from .video_utils import get_video_duration
from .analysis_service import run_analysis_process
from .batch_service import BatchService

logger = logging.getLogger(__name__)

class JobService:
    def __init__(self, session: Session):
        self.session = session

    def create_job(
        self, 
        video_road: List[UploadFile], 
        video_face: List[UploadFile], 
        background_tasks: BackgroundTasks, 
        keep_videos: bool = False,
        owner_id: Optional[str] = None
    ) -> Job:
        
        # Generate ID
        base_name = Path(video_road[0].filename).stem
        safe_name = re.sub(r'[^\w\-]', '_', base_name)
        job_id = safe_name
        
        # Handle duplicates (check DB)
        counter = 1
        while self.session.get(Job, job_id):
             job_id = f"{safe_name}_{counter}"
             counter += 1
             
        # Create directory
        job_dir = FileService.create_job_directory(job_id)
        
        try:
            # Process files
            road_path, road_filenames, road_sizes, road_duration = FileService.process_uploads(job_dir, video_road, "road")
            face_path, face_filenames, face_sizes, face_duration = FileService.process_uploads(job_dir, video_face, "face")
            
            # Prepare metadata
            road_meta = json.dumps({
                "filenames": road_filenames, 
                "count": len(road_filenames), 
                "sizes": road_sizes,
                "duration": road_duration
            })
            face_meta = json.dumps({
                "filenames": face_filenames, 
                "count": len(face_filenames), 
                "sizes": face_sizes,
                "duration": face_duration
            })
            
            # Create DB Record
            job = Job(
                id=job_id,
                name=job_id, # Default name is the ID
                status="PENDING",
                owner_id=owner_id,
                road_path=f"REMOTE:{job_id}/road.mp4",
                face_path=f"REMOTE:{job_id}/face.mp4",
                road_metadata=road_meta,
                face_metadata=face_meta
            )
            self.session.add(job)
            self.session.commit()
            self.session.refresh(job)
            
            # Trigger Background Task
            # We pass strings because Job object might be detached or updated
            # Look up owner's calibration model dir (if trained)
            models_dir = None
            if owner_id:
                from . import calibration_service as cal_svc
                if cal_svc.has_trained_model(owner_id):
                    models_dir = str(cal_svc.get_user_model_dir(owner_id))

            background_tasks.add_task(
                run_analysis_process,
                job_id,
                str(road_path),
                str(face_path),
                keep_videos=keep_videos,
                road_metadata=json.loads(road_meta),
                face_metadata=json.loads(face_meta),
                models_dir=models_dir
            )
            
            return job

        except Exception as e:
            logger.error(f"Error creating job: {e}")
            FileService.delete_job_directory(job_id)
            raise e

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.session.get(Job, job_id)

    def check_job_status(self, job_id: str, force_refresh: bool = False) -> Optional[Job]:
        """
        Checks and updates the status of a job using passive filesystem monitoring.
        Avoids SSH calls (squeue/sacct) to prevent timeouts and respect cluster constraints.
        """
        job = self.get_job(job_id)
        if not job:
            return None

        # Allow re-checking if forced OR if not COMPLETED
        if not force_refresh and job.status == "COMPLETED":
            return job

        # Rate limit filesystem checks to once every 2 seconds
        now = datetime.utcnow()
        if not force_refresh and job.last_status_check:
            elapsed = (now - job.last_status_check).total_seconds()
            if elapsed < 2:
                return job

        job.last_status_check = now
        
        try:
            local_job_dir = str(UPLOAD_DIR / job_id)
            batch_service = BatchService()

            # 1. ALWAYS Check for Results (Completion) - This is the definitive success marker
            result_path = UPLOAD_DIR / job_id / "results.json"
            if result_path.exists():
                return self.finalize_job(job_id)

            # Only proceed with log checks if NOT already COMPLETED or if we are actively tracking
            if job.status in ["SUBMITTED", "RUNNING", "PENDING", "FAILED"]:
                # 2. Check for Log File (Running or Failed)
                log_file = batch_service._get_latest_slurm_log_local(local_job_dir)
                if log_file:
                    # If log exists, it's at least RUNNING
                    if job.status != "RUNNING" and job.status != "FAILED":
                        job.status = "RUNNING"
                    
                    # Update progress from log
                    progress = batch_service.get_job_progress(job_id, local_job_dir)
                    if progress is not None and progress > job.progress:
                        job.progress = progress
                    
                    # Detect Failure from log content (passive check)
                    error_msg = batch_service.get_job_error(job_id, local_job_dir)
                    if "Traceback" in error_msg or "Error:" in error_msg or "failed" in error_msg.lower():
                        # Preliminary failure detection
                        if "it/s]" not in error_msg.splitlines()[-1]:
                             job.status = "FAILED"
                             job.error = error_msg
                    
                    self.session.add(job)
                    self.session.commit()
                    self.session.refresh(job)
            
            # If no log file and status is SUBMITTED, we just wait (Pending in queue)
            # We explicitly AVOID SSH check_status here to prevent timeouts.

        except Exception as e:
            logger.error(f"Error in passive status check for {job_id}: {e}")
        
        return job

    def finalize_job(self, job_id: str) -> Optional[Job]:
        """
        Finalizes the job using local file access. 
        Note: We no longer store the full JSON result in the database to save space.
        """
        job = self.get_job(job_id)
        if not job:
            return None

        result_path = UPLOAD_DIR / job_id / "results.json"
        
        # Check if result file exists (either locally or in large storage)
        if not result_path.exists():
            # Check fallback large storage path if local doesn't have it
            local_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
            result_path = local_base / job_id / "results.json"

        if result_path.exists():
            job.status = "COMPLETED"
            job.progress = 100
            job.error = None
            # job.result = None  # We keep it as is in case it was already set, but don't update it from file
            self.session.add(job)
            self.session.commit()
            self.session.refresh(job)
            logger.info(f"Job {job_id} finalized successfully.")
        else:
            # Result file not found but job finished? Check logs for error.
            batch_service = BatchService()
            if job.batch_job_id:
                try:
                    local_job_dir = str(UPLOAD_DIR / job_id)
                    error_msg = batch_service.get_job_error(job_id, local_job_dir)
                    job.status = "FAILED"
                    job.error = str(error_msg) if error_msg else "Results file not found after job completion."
                    self.session.add(job)
                    self.session.commit()
                    self.session.refresh(job)
                except Exception as e:
                    logger.error(f"Error fetching error logs for {job_id}: {e}")
            else:
                job.status = "FAILED"
                job.error = "Results file not found."
                self.session.add(job)
                self.session.commit()
                self.session.refresh(job)
        
        return job

    def delete_job(self, job_id: str) -> None:
        """Deletes a job's DB record and its upload directory from disk."""
        job = self.session.get(Job, job_id)
        if not job:
            return

        # Remove files from both possible storage locations
        large_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
        for base in [large_base, UPLOAD_DIR]:
            job_dir = base / job_id
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir, ignore_errors=True)
                logger.info(f"Deleted job directory: {job_dir}")

        self.session.delete(job)
        self.session.commit()
        logger.info(f"Deleted job {job_id} from DB")

    def update_job_name(self, job_id: str, name: str) -> Optional[Job]:
        job = self.session.get(Job, job_id)
        if job:
            job.name = name
            self.session.add(job)
            self.session.commit()
            self.session.refresh(job)
        return job

    def list_analyses(self, user_id: Optional[str] = None) -> List[AnalysisItem]:
        analyses = []
        found_ids = set()
        
        # 1. Get all jobs from DB to look up names/metadata
        try:
            if user_id:
                # Include both user's jobs and ALL demo jobs
                statement = select(Job).where((Job.owner_id == user_id) | (Job.is_demo == True))
            else:
                # Unauthenticated users only see demo jobs
                statement = select(Job).where(Job.is_demo == True)
                
            results = self.session.exec(statement).all()
            db_jobs = {job.id: job for job in results}
        except Exception as e:
            logger.error(f"Error fetching jobs from DB: {e}")
            db_jobs = {}

        # 1.5 Refresh status/progress for any active jobs by reading SLURM logs.
        # check_job_status is already rate-limited to once per 2s per job, so this is safe.
        for job_id, job in list(db_jobs.items()):
            if job.status in ('PENDING', 'SUBMITTED', 'RUNNING'):
                refreshed = self.check_job_status(job_id)
                if refreshed:
                    db_jobs[job_id] = refreshed

        # 2. Iterate through matched DB jobs to check filesystem
        for job_id, job in db_jobs.items():
            # Check filesystem existence (minimal check)
            # Both local and fallback storage
            local_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
            job_dir_large = local_base / job_id
            job_dir_local = UPLOAD_DIR / job_id
            
            if job_dir_large.exists() or job_dir_local.exists():
                found_ids.add(job_id)
                name = job.name or job_id
                count = 0
                duration = 0.0
                created_at = job.created_at or datetime.now()
                
                if job.road_metadata:
                    try:
                        meta = json.loads(job.road_metadata)
                        count = meta.get("count", 0)
                        duration = meta.get("duration", 0.0)
                    except:
                        pass
                
                analyses.append(AnalysisItem(
                    id=job_id,
                    name=name,
                    is_demo=job.is_demo,
                    status=job.status,
                    progress=job.progress,
                    video_count=count,
                    duration_seconds=duration,
                    created_at=created_at
                ))

        return sorted(analyses, key=lambda x: x.created_at, reverse=True)
        
    def load_results(self, job_id: str) -> Optional[dict]:
        """
        Loads results from the filesystem for a given job.
        Tries local upload directory first, then fallback large storage.
        """
        job = self.get_job(job_id)
        
        # Possible folder names: the job ID itself, or the original source name
        possible_folders = [job_id]
        if job and job.name and job.name != job_id:
            possible_folders.append(job.name)
            
        for folder in possible_folders:
            result_path = UPLOAD_DIR / folder / "results.json"
            
            # Check fallback if not in local UPLOAD_DIR
            if not result_path.exists():
                local_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
                result_path = local_base / folder / "results.json"

            if result_path.exists():
                try:
                    with open(result_path, "r") as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error reading results file for {job_id} in {folder}: {e}")
                    continue

        return None

    def create_test_job(self, analysis_id: Optional[str] = None, owner_id: Optional[str] = None) -> Job:
        source_job_id = analysis_id if analysis_id else "test_video"
        
        # Check source analysis in DB
        source_job = self.get_job(source_job_id)
        is_demo = source_job.is_demo if source_job else False
        if source_job_id == "test_video":
             is_demo = True
             
        # Determine filenames
        if source_job_id == "test_video":
            road_filename = "road_test.mp4"
            face_filename = "face_test.mp4"
        else:
            road_filename = "road.mp4"
            face_filename = "face.mp4"

        # Check if source analysis exists (verify filesystem)
        local_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
        result_path = local_base / source_job_id / "results.json"

        if not result_path.exists():
             # Try local UPLOAD_DIR too just in case
             result_path = UPLOAD_DIR / source_job_id / "results.json"

        if not result_path.exists():
            logger.error(f"Failed to load analysis: Results not found for {source_job_id}")
            raise FileNotFoundError(f"Could not load analysis for {source_job_id} (checked local and large storage)")

        # If the source job already has video paths in the DB, reuse them directly.
        # This handles re-analysis jobs whose videos live in the original source's directory.
        if source_job and source_job.road_path and source_job.face_path:
            road_path_val = source_job.road_path
            face_path_val = source_job.face_path
        else:
            # Fallback: construct REMOTE: paths from the job directory
            road_path_val = f"REMOTE:{source_job_id}/{road_filename}"
            face_path_val = f"REMOTE:{source_job_id}/{face_filename}"

        # 3. Create Job Record (NO 'result' column update)
        new_job_id = str(uuid.uuid4())
        
        job = Job(
            id=new_job_id,
            name=source_job_id,
            status="COMPLETED",
            progress=100,
            owner_id=owner_id,
            is_demo=is_demo,
            road_path=road_path_val,
            face_path=face_path_val
        )
        
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def create_reanalysis_job(self, source_job: Job, owner_id: str, models_dir: str) -> Job:
        """
        Creates a new analysis job from the same videos as source_job, using a
        custom models_dir (the user's personal calibration model).
        """
        results = self.load_results(source_job.id)
        if not results:
            raise FileNotFoundError(f"No results found for source job {source_job.id}")

        new_job_id = str(uuid.uuid4())
        job = Job(
            id=new_job_id,
            name=f"Re-analysis of {source_job.name or source_job.id}",
            status="PENDING",
            owner_id=owner_id,
            road_path=source_job.road_path,
            face_path=source_job.face_path,
            road_metadata=source_job.road_metadata,
            face_metadata=source_job.face_metadata,
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)

        # Resolve REMOTE: paths to actual filesystem paths
        large_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
        def resolve_remote(remote_str):
            if remote_str and remote_str.startswith("REMOTE:"):
                parts = remote_str.split(":")[1].split("/")
                job_dir_id, filename = parts[0], "/".join(parts[1:])
                for base in [large_base, UPLOAD_DIR]:
                    p = base / job_dir_id / filename
                    if p.exists():
                        return str(p)
            return remote_str

        road_actual = resolve_remote(source_job.road_path)
        face_actual = resolve_remote(source_job.face_path)
        road_meta = json.loads(source_job.road_metadata) if source_job.road_metadata else None
        face_meta = json.loads(source_job.face_metadata) if source_job.face_metadata else None

        import threading
        t = threading.Thread(
            target=run_analysis_process,
            args=(new_job_id, road_actual, face_actual),
            kwargs=dict(road_metadata=road_meta, face_metadata=face_meta, models_dir=models_dir),
            daemon=True,
        )
        t.start()

        return job
