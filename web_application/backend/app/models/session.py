from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
import json

class DrivingSession(SQLModel, table=True):
    __tablename__ = "driving_sessions"
    
    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # File Paths (Stored locally on the server)
    phone_video_path: Optional[str] = None
    dashcam_video_path: Optional[str] = None
    
    # Synchronization Status
    is_synced: bool = False
    sync_offset_ms: int = 0
    synced_video_path_phone: Optional[str] = None # Path to the trimmed/synced version
    synced_video_path_dashcam: Optional[str] = None # Path to the trimmed/synced version
    
    # Calibration Data (Stored as JSON string)
    calibration_data: Optional[str] = None 
    
    # Link to the main analysis Job
    job_id: Optional[str] = Field(default=None, foreign_key="jobs.id")
    
    # Session Status
    status: str = Field(default="CREATED") # CREATED, RECORDED, UPLOADING, READY_FOR_SYNC, SYNCING, SYNCED, ANALYZING, COMPLETED, FAILED

    def set_calibration_data(self, data: dict):
        self.calibration_data = json.dumps(data)

    def get_calibration_data(self) -> dict:
        if self.calibration_data:
            return json.loads(self.calibration_data)
        return {}
