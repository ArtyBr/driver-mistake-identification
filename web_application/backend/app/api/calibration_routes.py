import logging
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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
    samples: List[RawSampleInput]


class CorrectionRequest(BaseModel):
    job_id: str
    start_time: float
    end_time: float
    correct_label: str


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

@router.get("/status")
async def get_calibration_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Returns the user's calibration status and per-class sample counts."""
    return calibration_service.get_status(current_user.id, session)


@router.post("/samples")
async def add_calibration_samples(
    request: AddRawSamplesRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Accepts pre-computed {yaw, pitch, roll, label} samples from the frontend
    and stores them directly as training data.
    The frontend sends the exact data points it visualises in the scatter plot,
    guaranteeing that what the user sees == what gets trained.
    """
    new_samples = [s.model_dump() for s in request.samples]

    if not new_samples:
        raise HTTPException(status_code=400, detail="No samples provided.")

    unknown_labels = [s["label"] for s in new_samples if s["label"] not in calibration_service.LABEL_TO_IDX]
    if unknown_labels:
        raise HTTPException(status_code=400, detail=f"Unknown label(s): {list(set(unknown_labels))}")

    # Replace (not accumulate) — the user submits exactly what they labeled this session.
    calibration_service.reset_samples(current_user.id, session)
    updated_status = calibration_service.add_samples(current_user.id, new_samples, session)
    return {"added": len(new_samples), "status": updated_status}


@router.get("/samples")
async def get_calibration_samples(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Returns all stored raw training samples for the current user."""
    samples = calibration_service.get_samples(current_user.id, session)
    return {"samples": samples}


@router.delete("/samples")
async def reset_calibration_samples(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Clears all training samples and marks the model as untrained."""
    calibration_service.reset_samples(current_user.id, session)
    return {"message": "Training data cleared."}


@router.post("/train")
async def train_calibration_model(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Trains the user's personal PCA+SVM model from saved samples."""
    result = calibration_service.train_user_model(current_user.id, session)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/plots")
async def get_calibration_plots(
    current_user: User = Depends(get_current_user),
):
    """Returns base64-encoded diagnostic plot PNGs from the last training run."""
    plots = calibration_service.get_saved_plots_b64(current_user.id)
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
    Adds a gaze correction for a time segment and immediately retrains the model.
    Called from the ResultPage when the user spots a mislabelled segment.
    """
    _get_authorized_job(request.job_id, current_user, session)

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

    calibration_service.add_samples(current_user.id, new_samples, session)

    # Retrain immediately — sklearn SVM on small datasets completes in < 1s
    result = calibration_service.train_user_model(current_user.id, session)
    return {
        "added": len(new_samples),
        "retrained": result["success"],
        "message": result["message"],
    }


@router.post("/reanalyze/{job_id}")
async def reanalyze_with_user_model(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Creates a lightweight recalibration job: re-classifies stored head poses
    with the user's PCA+SVM model and replays safety logic. No GPU needed.
    Returns the new job_id immediately; frontend polls /status/{new_job_id}.
    """
    if not calibration_service.has_trained_model(current_user.id):
        raise HTTPException(
            status_code=400,
            detail="No trained calibration model found. Please train your model first.",
        )

    job = _get_authorized_job(job_id, current_user, session)
    models_dir = str(calibration_service.get_user_model_dir(current_user.id))

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
