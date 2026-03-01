from typing import Optional
from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field
from pydantic import BaseModel

class Report(SQLModel, table=True):
    __tablename__ = "reports"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", index=True)
    user_id: Optional[str] = Field(foreign_key="users.id", index=True, default=None)
    timestamp: float
    event_type: str
    report_type: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ReportCreate(BaseModel):
    timestamp: float
    event_type: str
    report_type: str
    description: Optional[str] = None
