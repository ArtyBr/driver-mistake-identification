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
from .file_service import FileService
from .video_utils import get_video_duration
from .analysis_service import run_analysis_process

logger = logging.getLogger(__name__)

class JobService:
    def __init__(self, session: Session):
        self.session = session

    def create_job(
        self, 
        video_road: List[UploadFile], 
        video_face: List[UploadFile], 
        background_tasks: BackgroundTasks, 
        keep_videos: bool = False
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
                road_path=str(road_path),
                face_path=str(face_path),
                road_metadata=road_meta,
                face_metadata=face_meta
            )
            self.session.add(job)
            self.session.commit()
            self.session.refresh(job)
            
            # Trigger Background Task
            # We pass strings because Job object might be detached or updated
            background_tasks.add_task(
                run_analysis_process, 
                job_id, 
                str(road_path), 
                str(face_path), 
                keep_videos=keep_videos, 
                road_metadata=json.loads(road_meta), 
                face_metadata=json.loads(face_meta)
            )
            
            return job

        except Exception as e:
            logger.error(f"Error creating job: {e}")
            FileService.delete_job_directory(job_id)
            raise e

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.session.get(Job, job_id)
        
    def update_job_name(self, job_id: str, name: str) -> Optional[Job]:
        job = self.session.get(Job, job_id)
        if job:
            job.name = name
            self.session.add(job)
            self.session.commit()
            self.session.refresh(job)
        return job

    def list_analyses(self) -> List[AnalysisItem]:
        analyses = []
        found_ids = set()
        
        # 1. Get all jobs from DB to look up names/metadata
        try:
            statement = select(Job)
            results = self.session.exec(statement).all()
            db_jobs = {job.id: job for job in results}
        except Exception as e:
            logger.error(f"Error fetching jobs from DB: {e}")
            db_jobs = {}

        # 2. Fetch directory list from Remote Server
        remote_user = "u2204449"
        remote_host = "remote-49"
        remote_base = "~/cs310_data/uploads"
        
        try:
            # List directories on remote. Using ls -1 to get simple list.
            # We assume any folder there is a job. Checking for results.json via SSH loop is slow,
            # so we trust the folder presence or check DB match.
            cmd = ["ssh", f"{remote_user}@{remote_host}", f"ls -1 {remote_base}"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if process.returncode == 0:
                remote_folders = process.stdout.strip().split('\n')
                
                for job_id in remote_folders:
                    if not job_id.strip(): continue
                    job_id = job_id.strip()
                    found_ids.add(job_id)
                    
                    name = job_id
                    count = 0
                    duration = 0.0
                    created_at = datetime.now() # Fallback
                    
                    if job_id in db_jobs:
                        job = db_jobs[job_id]
                        name = job.name or job_id
                        if job.created_at:
                            created_at = job.created_at
                            
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
                        video_count=count,
                        duration_seconds=duration,
                        created_at=created_at
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch remote analysis list: {e}")

        return sorted(analyses, key=lambda x: x.created_at, reverse=True)
        
    def create_test_job(self, analysis_id: Optional[str] = None) -> Job:
        source_job_id = analysis_id if analysis_id else "test_video"
        
        # Determine filenames
        if source_job_id == "test_video":
            road_filename = "road_test.mp4"
            face_filename = "face_test.mp4"
        else:
            road_filename = "road.mp4"
            face_filename = "face.mp4"

        # Fetch Remote Results
        try:
            logger.info(f"Fetching remote results for {source_job_id}...")
            # Using specific user and host
            cmd = ["ssh", "u2204449@remote-49", f"cat ~/cs310_data/uploads/{source_job_id}/results.json"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if process.returncode != 0:
                raise FileNotFoundError(f"Remote results not found for {source_job_id}")
                
            result_data = json.loads(process.stdout)
            
            # If remote, we use the REMOTE: prefix logic
            road_path_val = f"REMOTE:{source_job_id}/{road_filename}"
            face_path_val = f"REMOTE:{source_job_id}/{face_filename}"
            
        except Exception as e:
            logger.error(f"Failed to load remote analysis: {e}")
            raise FileNotFoundError(f"Could not load analysis for {source_job_id} (checked remote only)")

        # 3. Create Job Record
        new_job_id = str(uuid.uuid4())
        
        job = Job(
            id=new_job_id,
            name=source_job_id,
            status="COMPLETED",
            progress=100,
            road_path=road_path_val,
            face_path=face_path_val,
            result=json.dumps(result_data)
        )
        
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job
