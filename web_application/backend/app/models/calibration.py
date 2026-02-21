import uuid
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class UserCalibration(SQLModel, table=True):
    __tablename__ = "user_calibrations"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True
    )
    # One calibration row per user (unique constraint enforced in logic + DB)
    user_id: str = Field(unique=True, index=True)
    is_trained: bool = Field(default=False)
    # JSON string: list of {"yaw": int, "pitch": int, "roll": int, "label": str}
    training_data: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
