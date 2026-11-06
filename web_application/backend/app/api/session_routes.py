import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlmodel import Session

from ..db.database import get_session
from ..services.session_service import SessionService
from ..models.session import DrivingSession

router = APIRouter()
logger = logging.getLogger(__name__)

def get_session_service(session: Session = Depends(get_session)) -> SessionService:
    return SessionService(session)

@router.post("/sessions", response_model=DrivingSession)
async def create_session(service: SessionService = Depends(get_session_service)):
    """
    Creates a new empty driving session.
    """
    return service.create_session()

@router.get("/sessions/{session_id}", response_model=DrivingSession)
async def get_session_status(session_id: str, service: SessionService = Depends(get_session_service)):
    """
    Retrieves the status of a session.
    """
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/sessions/{session_id}/upload/{video_type}", response_model=DrivingSession)
async def upload_session_video(
    session_id: str,
    video_type: str,
    file: UploadFile = File(...),
    service: SessionService = Depends(get_session_service)
):
    """
    Uploads a video file for the session.
    video_type must be 'phone' or 'dashcam'.
    """
    if video_type not in ["phone", "dashcam"]:
        raise HTTPException(status_code=400, detail="Invalid video_type. Must be 'phone' or 'dashcam'.")
        
    try:
        return service.upload_video(session_id, file, video_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

@router.post("/sessions/{session_id}/calibrate", response_model=DrivingSession)
async def save_calibration(
    session_id: str,
    calibration_data: dict,
    service: SessionService = Depends(get_session_service)
):
    """
    Saves calibration metadata (timestamps, labels) for the session.
    """
    try:
        return service.save_calibration(session_id, calibration_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/sessions/{session_id}/sync", response_model=DrivingSession)
async def trigger_sync(
    session_id: str,
    background_tasks: BackgroundTasks,
    service: SessionService = Depends(get_session_service)
):
    """
    Triggers the synchronization process if both videos are present.
    """
    try:
        service.trigger_sync(session_id, background_tasks)
        return service.get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
