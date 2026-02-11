from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    id: str = Field(primary_key=True)
    status: str
    name: Optional[str] = None
    road_path: Optional[str] = None
    face_path: Optional[str] = None
    # Storing JSON as strings for SQLite simplicity
    road_metadata: Optional[str] = None 
    face_metadata: Optional[str] = None
    # result: Deprecated - Storing full JSON in DB is avoided for new jobs. 
    # Use JobService.load_results() to fetch from disk instead.
    result: Optional[str] = None
    error: Optional[str] = None
    batch_job_id: Optional[str] = None
    progress: int = Field(default=0)
    last_status_check: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
