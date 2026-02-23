from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class JobStatusResponse(BaseModel):
    status: str
    name: Optional[str] = None
    is_demo: bool = False
    progress: Optional[int] = 0
    road_url: Optional[str] = None
    face_url: Optional[str] = None
    road_metadata: Optional[Dict[str, Any]] = None
    face_metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class JobCreateResponse(BaseModel):
    job_id: str

class AnalysisItem(BaseModel):
    id: str
    name: str
    is_demo: bool = False
    status: Optional[str] = None
    progress: Optional[int] = 0
    video_count: Optional[int] = 0
    duration_seconds: Optional[float] = 0.0
    created_at: Optional[Any] = None

class AnalysisListResponse(BaseModel):
    analyses: List[AnalysisItem]

class JobUpdate(BaseModel):
    name: str
