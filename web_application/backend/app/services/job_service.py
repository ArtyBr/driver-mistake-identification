import uuid
import re
import json
import logging
from typing import List, Optional
from pathlib import Path
from fastapi import UploadFile, BackgroundTasks
from sqlmodel import Session

from ..models.job import Job
from .file_service import FileService
from ..core.config import UPLOAD_DIR
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
            road_path, road_filenames, road_sizes = FileService.process_uploads(job_dir, video_road, "road")
            face_path, face_filenames, face_sizes = FileService.process_uploads(job_dir, video_face, "face")
            
            # Prepare metadata
            road_meta = json.dumps({"filenames": road_filenames, "count": len(road_filenames), "sizes": road_sizes})
            face_meta = json.dumps({"filenames": face_filenames, "count": len(face_filenames), "sizes": face_sizes})
            
            # Create DB Record
            job = Job(
                id=job_id,
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
        
    def list_analyses(self) -> List[str]:
        analyses = []
        if UPLOAD_DIR.exists():
            for path in UPLOAD_DIR.iterdir():
                if path.is_dir() and (path / "results.json").exists():
                    analyses.append(path.name)
        return sorted(analyses)
        
    def create_test_job(self, analysis_id: Optional[str] = None) -> Job:
        source_job_id = analysis_id if analysis_id else "test_video"
        source_dir = UPLOAD_DIR / source_job_id
        results_path = source_dir / "results.json"

        if not results_path.exists():
            raise FileNotFoundError(f"Analysis '{source_job_id}' not found or incomplete.")

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

        new_job_id = str(uuid.uuid4())
        
        job = Job(
            id=new_job_id,
            status="COMPLETED",
            progress=100,
            road_path=str(source_dir / road_filename),
            face_path=str(source_dir / face_filename),
            result=json.dumps(result_data)
        )
        
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job
