import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db.database import get_session
from app.models.job import Job
from app.services.batch_service import BatchService

# Setup in-memory SQLite for testing
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session
    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_status_polling_updates_db(client, session, monkeypatch):
    """Test that GET /status/{id} triggers a DB update from BatchService."""
    
    # 1. Create a job in SUBMITTED state
    job_id = "test_polling_job"
    job = Job(
        id=job_id,
        name=job_id,
        status="SUBMITTED",
        batch_job_id="slurm_999",
        road_path="road.mp4",
        face_path="face.mp4"
    )
    session.add(job)
    session.commit()
    
    # 2. Mock BatchService
    mock_batch = MagicMock(spec=BatchService)
    # First poll: Running, 45%
    mock_batch.check_status.return_value = "RUNNING"
    mock_batch.get_job_progress.return_value = 45
    
    with patch("app.services.job_service.BatchService", return_value=mock_batch):
        response = client.get(f"/status/{job_id}?force_refresh=true")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "RUNNING"
        assert data["progress"] == 45
        
        # Verify DB was updated
        session.refresh(job)
        assert job.status == "RUNNING"
        assert job.progress == 45

    # Second poll: Completed
    mock_batch.check_status.return_value = "COMPLETED"
    mock_batch.read_results_local.return_value = json.dumps({
        "meta": {"duration": 10},
        "timeline_events": [],
        "frame_data": []
    })
    
    with patch("app.services.job_service.BatchService", return_value=mock_batch):
        response = client.get(f"/status/{job_id}?force_refresh=true")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["progress"] == 100
        
        # Verify DB was updated
        session.refresh(job)
        assert job.status == "COMPLETED"
        assert job.result is not None

def test_status_polling_handles_failure(client, session, monkeypatch):
    """Test that GET /status/{id} handles batch job failure."""
    
    job_id = "test_fail_job"
    job = Job(
        id=job_id,
        status="RUNNING",
        batch_job_id="slurm_fail",
        road_path="road.mp4",
        face_path="face.mp4"
    )
    session.add(job)
    session.commit()
    
    mock_batch = MagicMock(spec=BatchService)
    mock_batch.check_status.return_value = "FAILED"
    mock_batch.get_job_error.return_value = "Python error: File not found"
    
    with patch("app.services.job_service.BatchService", return_value=mock_batch):
        response = client.get(f"/status/{job_id}?force_refresh=true")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "FAILED"
        assert "Python error" in data["error"]
        
        session.refresh(job)
        assert job.status == "FAILED"
        assert "Python error" in job.error
