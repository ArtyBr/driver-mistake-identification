import logging
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from ..db.database import get_session
from ..models.user import User
from ..models.job import Job
from ..services.auth_service import get_current_user
from ..services import calibration_service
from ..core.config import UPLOAD_DIR

router = APIRouter(prefix="/calibration", tags=["calibration"])
logger = logging.getLogger(__name__)


# ─── Request Schemas ─────────────────────────────────────────────────────────

class RawSampleInput(BaseModel):
    yaw: float
    pitch: float
    roll: float
    label: str  # Must be one of CLASS_NAMES values


class AddRawSamplesRequest(BaseModel):
    cal_id: str
    samples: List[RawSampleInput]


class CorrectionRequest(BaseModel):
    job_id: str
    start_time: float
    end_time: float
    correct_label: str
    cal_id: Optional[str] = None


class RenameRequest(BaseModel):
    name: str


class CreateRequest(BaseModel):
    name: Optional[str] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_authorized_job(job_id: str, user: User, session: Session) -> Job:
    """Fetches a job and checks the user is the owner or it's a demo."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_demo and job.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    return job


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/list")
async def list_calibrations(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Returns all calibrations for the current user."""
    return calibration_service.list_calibrations(current_user.id, session)


@router.post("/create")
async def create_calibration(
    request: CreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Creates a new calibration."""
    return calibration_service.create_calibration(current_user.id, session, name=request.name)


@router.patch("/{cal_id}/rename")
async def rename_calibration(
    cal_id: str,
    request: RenameRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Renames a calibration."""
    cal = calibration_service.rename_calibration(cal_id, current_user.id, request.name, session)
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration not found")
    return cal


@router.delete("/{cal_id}")
async def delete_calibration(
    cal_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Deletes a calibration."""
    success = calibration_service.delete_calibration(cal_id, current_user.id, session)
    if not success:
        raise HTTPException(status_code=404, detail="Calibration not found")
    return {"message": "Calibration deleted"}


@router.get("/status")
async def get_calibration_status(
    cal_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Returns calibration status. If cal_id is provided, returns per-class counts for it.
    If not, returns whether the user has ANY trained calibration."""
    if cal_id:
        status = calibration_service.get_status(cal_id, current_user.id, session)
        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])
        return status
    
    cals = calibration_service.list_calibrations(current_user.id, session)
    return {
        "has_any_calibration": len(cals) > 0,
        "is_trained": any(c.is_trained for c in cals),
        "total_calibrations": len(cals)
    }


@router.post("/samples")
async def add_calibration_samples(
    request: AddRawSamplesRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Accepts pre-computed {yaw, pitch, roll, label} samples and stores them.
    """
    new_samples = [s.model_dump() for s in request.samples]

    if not new_samples:
        raise HTTPException(status_code=400, detail="No samples provided.")

    unknown_labels = [s["label"] for s in new_samples if s["label"] not in calibration_service.LABEL_TO_IDX]
    if unknown_labels:
        raise HTTPException(status_code=400, detail=f"Unknown label(s): {list(set(unknown_labels))}")

    # Replace (not accumulate) for this specific calibration session submission
    calibration_service.reset_samples(request.cal_id, current_user.id, session)
    updated_status = calibration_service.add_samples(request.cal_id, current_user.id, new_samples, session)
    
    if "error" in updated_status:
        raise HTTPException(status_code=404, detail=updated_status["error"])
        
    return {"added": len(new_samples), "status": updated_status}


@router.get("/samples")
async def get_calibration_samples(
    cal_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Returns all stored raw training samples for a calibration."""
    samples = calibration_service.get_samples(cal_id, current_user.id, session)
    return {"samples": samples}


@router.delete("/samples")
async def reset_calibration_samples(
    cal_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Clears all training samples for a calibration."""
    calibration_service.reset_samples(cal_id, current_user.id, session)
    return {"message": "Training data cleared."}


@router.post("/train")
async def train_calibration_model(
    cal_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Trains a specific calibration model."""
    result = calibration_service.train_user_model(cal_id, current_user.id, session)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/plots")
async def get_calibration_plots(
    cal_id: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Returns diagnostic plots for a specific calibration."""
    plots = calibration_service.get_saved_plots_b64(cal_id, current_user.id)
    if not plots:
        raise HTTPException(status_code=404, detail="No plots found. Train the model first.")
    return {"plots": plots}


@router.post("/correct")
async def submit_correction(
    request: CorrectionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Adds a gaze correction and retrains the specified (or first) calibration.
    """
    _get_authorized_job(request.job_id, current_user, session)
    
    cal_id = request.cal_id
    if not cal_id:
        # Fallback to the first available calibration or create one
        cals = calibration_service.list_calibrations(current_user.id, session)
        if not cals:
            cal = calibration_service.create_calibration(current_user.id, session)
            cal_id = cal.id
        else:
            cal_id = cals[0].id

    segments = [{
        "start_time": request.start_time,
        "end_time": request.end_time,
        "label": request.correct_label,
    }]
    try:
        new_samples = calibration_service.extract_pose_from_job(
            request.job_id, segments, session
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not new_samples:
        raise HTTPException(
            status_code=400,
            detail="No face data found in the given time range.",
        )

    calibration_service.add_samples(cal_id, current_user.id, new_samples, session)
    result = calibration_service.train_user_model(cal_id, current_user.id, session)
    return {
        "added": len(new_samples),
        "retrained": result["success"],
        "message": result["message"],
        "cal_id": cal_id
    }


@router.post("/reanalyze/{job_id}")
async def reanalyze_with_user_model(
    job_id: str,
    background_tasks: BackgroundTasks,
    cal_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Re-analyzes a job with a specific calibration model.
    """
    if not calibration_service.has_trained_model(current_user.id, cal_id):
        raise HTTPException(
            status_code=400,
            detail="Calibration model not found or not trained.",
        )

    job = _get_authorized_job(job_id, current_user, session)
    models_dir = str(calibration_service.get_user_model_dir(current_user.id, cal_id))

    # Resolve source results.json
    source_results = None
    for base in [UPLOAD_DIR, Path("/dcs/large/safedrive_cs310_2526/uploads")]:
        p = base / job_id / "results.json"
        if p.exists():
            source_results = p
            break
    if not source_results:
        raise HTTPException(status_code=404, detail="No results found for this job.")

    # Create lightweight new job record
    new_job_id = str(uuid.uuid4())
    new_job = Job(
        id=new_job_id,
        name=f"Re-analysis of {job.name or job_id}",
        status="PENDING",
        owner_id=current_user.id,
        calibration_id=cal_id,
        road_path=job.road_path,
        face_path=job.face_path,
        road_metadata=job.road_metadata,
        face_metadata=job.face_metadata,
    )
    session.add(new_job)
    session.commit()

    from ..services.analysis_service import run_recalibrate_process
    background_tasks.add_task(run_recalibrate_process, new_job_id, str(source_results), models_dir)

    return {"job_id": new_job_id}
