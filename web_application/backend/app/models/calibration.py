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
    # Multiple calibrations per user allowed
    user_id: str = Field(index=True)
    name: str = Field(default="New Calibration")
    is_trained: bool = Field(default=False)
    # JSON string: list of {"yaw": int, "pitch": int, "roll": int, "label": str}
    training_data: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
