from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class JobStatusResponse(BaseModel):
    status: str
    progress: Optional[int] = 0
    road_url: Optional[str] = None
    face_url: Optional[str] = None
    error: Optional[str] = None

class JobCreateResponse(BaseModel):
    job_id: str

class AnalysisListResponse(BaseModel):
    analyses: List[str]
