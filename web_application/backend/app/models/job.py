from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    id: str = Field(primary_key=True)
    status: str
    road_path: Optional[str] = None
    face_path: Optional[str] = None
    # Storing JSON as strings for SQLite simplicity
    road_metadata: Optional[str] = None 
    face_metadata: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    progress: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
