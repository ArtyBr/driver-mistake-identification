"""
Admin API routes. All endpoints require is_admin=True on the authenticated user.
Prefix: /admin
"""
import json
import shutil
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from pydantic import BaseModel

from ..db.database import get_session
from ..models.user import User, UserResponse
from ..models.job import Job
from ..models.calibration import UserCalibration
from ..models.session import DrivingSession
from ..services.auth_service import get_current_user
from ..services.auth_service import get_password_hash
from ..services.event_stats import read_event_stats
from ..core.config import UPLOAD_DIR

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dependency: require admin
# ---------------------------------------------------------------------------

async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AdminUserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_verified: Optional[bool] = None

class AdminJobUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    is_demo: Optional[bool] = None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def admin_stats(
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    users = session.exec(select(func.count()).select_from(User)).one()
    jobs = session.exec(select(func.count()).select_from(Job)).one()
    sessions = session.exec(select(func.count()).select_from(DrivingSession)).one()
    calibrations = session.exec(select(func.count()).select_from(UserCalibration)).one()
    running_jobs = session.exec(
        select(func.count()).select_from(Job).where(Job.status.in_(["RUNNING", "SUBMITTED", "PENDING"]))
    ).one()
    return {
        "users": users,
        "jobs": jobs,
        "sessions": sessions,
        "calibrations": calibrations,
        "running_jobs": running_jobs,
    }


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users")
async def admin_list_users(
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    users = session.exec(select(User)).all()
    result = []
    for u in users:
        job_count = session.exec(
            select(func.count()).select_from(Job).where(Job.owner_id == u.id)
        ).one()
        cal = session.exec(
            select(UserCalibration).where(UserCalibration.user_id == u.id)
        ).first()
        result.append({
            "id": u.id,
            "email": u.email,
            "is_admin": u.is_admin,
            "is_verified": u.is_verified,
            "job_count": job_count,
            "has_calibration": cal is not None,
            "calibration_trained": cal.is_trained if cal else False,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return result


@router.get("/users/{user_id}/jobs")
async def admin_get_user_jobs(
    user_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    """Return all non-demo jobs for a user with event stats for completed ones."""
    large_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
    jobs = session.exec(
        select(Job)
        .where(Job.owner_id == user_id, Job.is_demo == False)
        .order_by(Job.created_at.desc())
    ).all()

    result = []
    for job in jobs:
        item = {
            "id": job.id,
            "name": job.name or job.id,
            "status": job.status,
            "progress": job.progress,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "events": None,
        }
        if job.status == "COMPLETED":
            for base in [large_base, UPLOAD_DIR]:
                p = base / job.id / "results.json"
                if p.exists():
                    item["events"] = read_event_stats(p)
                    break
        result.append(item)
    return result


@router.put("/users/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: str,
    data: AdminUserUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.email is not None:
        # Check uniqueness
        existing = session.exec(select(User).where(User.email == data.email)).first()
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email
    if data.password is not None:
        user.hashed_password = get_password_hash(data.password)
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    if data.is_verified is not None:
        user.is_verified = data.is_verified
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    delete_jobs: bool = Query(False),
    session: Session = Depends(get_session),
    current_admin: User = Depends(get_admin_user),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if delete_jobs:
        jobs = session.exec(select(Job).where(Job.owner_id == user_id)).all()
        large_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
        for job in jobs:
            # Delete associated driving sessions
            driving_sessions = session.exec(select(DrivingSession).where(DrivingSession.job_id == job.id)).all()
            for ds in driving_sessions:
                session.delete(ds)
                
            for base in [large_base, UPLOAD_DIR]:
                job_dir = base / job.id
                if job_dir.exists():
                    shutil.rmtree(job_dir, ignore_errors=True)
            session.delete(job)

    # Delete calibration
    cal = session.exec(
        select(UserCalibration).where(UserCalibration.user_id == user_id)
    ).first()
    if cal:
        cal_dir = UPLOAD_DIR / "calibrations" / user_id
        if cal_dir.exists():
            shutil.rmtree(cal_dir, ignore_errors=True)
        large_cal_dir = Path("/dcs/large/safedrive_cs310_2526/uploads/calibrations") / user_id
        if large_cal_dir.exists():
            shutil.rmtree(large_cal_dir, ignore_errors=True)
        session.delete(cal)

    session.delete(user)
    session.commit()
    return {"message": f"User {user_id} deleted"}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@router.get("/jobs")
async def admin_list_jobs(
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    is_demo: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    stmt = select(Job)
    if status:
        stmt = stmt.where(Job.status == status.upper())
    if user_id:
        stmt = stmt.where(Job.owner_id == user_id)
    if is_demo is not None:
        stmt = stmt.where(Job.is_demo == is_demo)
    stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
    jobs = session.exec(stmt).all()

    # Build user email lookup
    owner_ids = {j.owner_id for j in jobs if j.owner_id}
    users_map: dict = {}
    if owner_ids:
        owners = session.exec(select(User).where(User.id.in_(owner_ids))).all()
        users_map = {u.id: u.email for u in owners}

    result = []
    for j in jobs:
        result.append({
            "id": j.id,
            "name": j.name,
            "status": j.status,
            "progress": j.progress,
            "is_demo": j.is_demo,
            "owner_id": j.owner_id,
            "owner_email": users_map.get(j.owner_id) if j.owner_id else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "error": j.error,
        })
    return result


@router.put("/jobs/{job_id}")
async def admin_update_job(
    job_id: str,
    data: AdminJobUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if data.name is not None:
        job.name = data.name
    if data.status is not None:
        job.status = data.status.upper()
    if data.is_demo is not None:
        job.is_demo = data.is_demo
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"id": job.id, "name": job.name, "status": job.status, "is_demo": job.is_demo}


@router.delete("/jobs/{job_id}")
async def admin_delete_job(
    job_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete associated driving sessions
    driving_sessions = session.exec(select(DrivingSession).where(DrivingSession.job_id == job_id)).all()
    for ds in driving_sessions:
        session.delete(ds)

    large_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
    for base in [large_base, UPLOAD_DIR]:
        job_dir = base / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)

    session.delete(job)
    session.commit()
    return {"message": f"Job {job_id} deleted"}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.get("/sessions")
async def admin_list_sessions(
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    driving_sessions = session.exec(
        select(DrivingSession).order_by(DrivingSession.created_at.desc())
    ).all()
    result = []
    for s in driving_sessions:
        result.append({
            "id": s.id,
            "status": s.status,
            "sync_offset_ms": s.sync_offset_ms,
            "is_synced": s.is_synced,
            "has_phone": s.phone_video_path is not None,
            "has_dashcam": s.dashcam_video_path is not None,
            "job_id": s.job_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return result


@router.delete("/sessions/{session_id}")
async def admin_delete_session(
    session_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    ds = session.get(DrivingSession, session_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Session not found")
    session.delete(ds)
    session.commit()
    return {"message": f"Session {session_id} deleted"}


# ---------------------------------------------------------------------------
# Calibrations
# ---------------------------------------------------------------------------

@router.get("/calibrations")
async def admin_list_calibrations(
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    cals = session.exec(select(UserCalibration)).all()
    user_ids = {c.user_id for c in cals}
    users_map: dict = {}
    if user_ids:
        owners = session.exec(select(User).where(User.id.in_(user_ids))).all()
        users_map = {u.id: u.email for u in owners}

    result = []
    for c in cals:
        sample_count = 0
        label_counts: dict = {}
        if c.training_data:
            try:
                samples = json.loads(c.training_data)
                sample_count = len(samples)
                for s in samples:
                    lbl = s.get("label", "unknown")
                    label_counts[lbl] = label_counts.get(lbl, 0) + 1
            except Exception:
                pass
        result.append({
            "id": c.id,
            "user_id": c.user_id,
            "user_email": users_map.get(c.user_id, "Unknown"),
            "is_trained": c.is_trained,
            "sample_count": sample_count,
            "label_counts": label_counts,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        })
    return result


@router.delete("/calibrations/{user_id}")
async def admin_delete_calibration(
    user_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_admin_user),
):
    cal = session.exec(
        select(UserCalibration).where(UserCalibration.user_id == user_id)
    ).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration not found")

    # Remove model files
    for base in [UPLOAD_DIR, Path("/dcs/large/safedrive_cs310_2526/uploads/")]:
        cal_dir = base / "calibrations" / user_id
        if cal_dir.exists():
            shutil.rmtree(cal_dir, ignore_errors=True)

    session.delete(cal)
    session.commit()
    return {"message": f"Calibration for user {user_id} deleted"}
