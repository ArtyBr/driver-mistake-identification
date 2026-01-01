import sys
from pathlib import Path
from sqlmodel import Session, create_engine
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Add backend to sys.path
backend_path = Path("web_application/backend").resolve()
sys.path.append(str(backend_path))

from app.services.job_service import JobService
from app.core.config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}")

with Session(engine) as session:
    service = JobService(session)
    analyses = service.list_analyses()
    for a in analyses:
        print(f"ID: {a.id}, Name: {a.name}, Duration: {a.duration_seconds}")
