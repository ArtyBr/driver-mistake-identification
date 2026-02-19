import uuid
import logging
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from fastapi import UploadFile, BackgroundTasks
from sqlmodel import Session, select

from ..models.session import DrivingSession
from ..models.job import Job
from ..core.config import UPLOAD_DIR
from .file_service import FileService
from .job_service import JobService

logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self, session: Session):
        self.session = session

    def create_session(self) -> DrivingSession:
        session_id = str(uuid.uuid4())
        
        # Create directory
        FileService.create_job_directory(session_id)
        
        db_session = DrivingSession(id=session_id)
        self.session.add(db_session)
        self.session.commit()
        self.session.refresh(db_session)
        return db_session

    def get_session(self, session_id: str) -> Optional[DrivingSession]:
        return self.session.get(DrivingSession, session_id)

    def upload_video(self, session_id: str, file: UploadFile, video_type: str) -> DrivingSession:
        """
        Handles uploading a video file for a session.
        video_type must be "phone" or "dashcam".
        """
        db_session = self.get_session(session_id)
        if not db_session:
            raise ValueError("Session not found")

        job_dir = UPLOAD_DIR / session_id
        
        # Use existing FileService to save/splice (even if it's just one file)
        # We wrap the single file in a list
        prefix = "face" if video_type == "phone" else "road"
        
        final_path, filenames, sizes, duration = FileService.process_uploads(job_dir, [file], prefix)
        
        # Update Session Record
        if video_type == "phone":
            db_session.phone_video_path = str(final_path)
        else:
            db_session.dashcam_video_path = str(final_path)
            
        # Check if we can proceed to sync
        self._check_sync_readiness(db_session)
        
        self.session.add(db_session)
        self.session.commit()
        self.session.refresh(db_session)
        
        return db_session

    def _check_sync_readiness(self, db_session: DrivingSession):
        if db_session.phone_video_path and db_session.dashcam_video_path:
            db_session.status = "READY_FOR_SYNC"

    def save_calibration(self, session_id: str, calibration_data: dict) -> DrivingSession:
        db_session = self.get_session(session_id)
        if not db_session:
            raise ValueError("Session not found")
            
        db_session.set_calibration_data(calibration_data)
        self.session.add(db_session)
        self.session.commit()
        self.session.refresh(db_session)
        return db_session

    def trigger_sync(self, session_id: str, background_tasks: BackgroundTasks):
        """
        Initiates the synchronization process.
        For now, this is a stub that marks it as SYNCED if both files exist.
        Later, this will call the actual audio analysis logic.
        """
        db_session = self.get_session(session_id)
        if not db_session:
            raise ValueError("Session not found")
            
        if db_session.status != "READY_FOR_SYNC":
            # If not ready, we can't sync. 
            # But if user forces it, we check again
            if not (db_session.phone_video_path and db_session.dashcam_video_path):
                 raise ValueError("Both videos are required for sync.")

        db_session.status = "SYNCING"
        self.session.add(db_session)
        self.session.commit()
        
        # Trigger Sync in Background
        background_tasks.add_task(self._finalize_sync, session_id)

    def _finalize_sync(self, session_id: str):
        from ..db.database import get_session
        from .audio_sync import AudioSyncService
        import traceback
        
        # New DB Session for background task
        session_gen = get_session()
        session = next(session_gen)
        
        try:
            db_session = session.get(DrivingSession, session_id)
            if not db_session:
                logger.error(f"Session {session_id} not found during sync.")
                return

            logger.info(f"Starting sync for session {session_id}")
            
            job_dir = UPLOAD_DIR / session_id
            phone_path = Path(db_session.phone_video_path)
            dashcam_path = Path(db_session.dashcam_video_path)
            
            try:
                synced_phone, synced_dashcam = AudioSyncService.sync_videos(
                    phone_path, dashcam_path, job_dir
                )
                
                db_session.status = "SYNCED"
                db_session.is_synced = True
                db_session.synced_video_path_phone = str(synced_phone)
                db_session.synced_video_path_dashcam = str(synced_dashcam)
                
                session.add(db_session)
                session.commit()
                session.refresh(db_session)
                
                logger.info(f"Session {session_id} synced successfully.")
                
                # Trigger Analysis
                self._trigger_analysis(session, db_session)
                
            except Exception as e:
                logger.error(f"Sync failed for session {session_id}: {e}")
                logger.error(traceback.format_exc())
                db_session.status = "FAILED"
                session.add(db_session)
                session.commit()
                
        finally:
            session.close()

    def _trigger_analysis(self, session: Session, db_session: DrivingSession):
        """
        Creates a standard Job from the Synced Session to reuse existing pipeline.
        """
        job_service = JobService(session)
        
        # We need to construct metadata manually since we didn't use JobService.create_job
        # Reading file info
        import os
        
        road_path = Path(db_session.synced_video_path_dashcam)
        face_path = Path(db_session.synced_video_path_phone)
        
        road_meta = json.dumps({
            "filenames": [road_path.name], "count": 1, 
            "sizes": [road_path.stat().st_size], "duration": 0 # TODO: Get duration
        })
        face_meta = json.dumps({
            "filenames": [face_path.name], "count": 1, 
            "sizes": [face_path.stat().st_size], "duration": 0
        })

        # Create Job
        job = Job(
            id=f"session_{db_session.id}",
            name=f"Session {db_session.id[:8]}",
            status="PENDING",
            road_path=str(road_path),
            face_path=str(face_path),
            road_metadata=road_meta,
            face_metadata=face_meta
        )
        
        session.add(job)
        session.commit()
        session.refresh(job)
        
        # Link back
        db_session.job_id = job.id
        db_session.status = "ANALYZING"
        session.add(db_session)
        session.commit()
        
        # We need to trigger the actual analysis process background task...
        # But we are inside a background task already. We can just call the function.
        from .analysis_service import run_analysis_process
        
        run_analysis_process(
            job.id,
            str(road_path),
            str(face_path),
            keep_videos=True,
            road_metadata=json.loads(road_meta),
            face_metadata=json.loads(face_meta)
        )
