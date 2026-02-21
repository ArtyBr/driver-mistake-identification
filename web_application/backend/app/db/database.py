from sqlmodel import SQLModel, create_engine, Session
from ..core.config import DB_PATH

# SQLite URL
sqlite_url = f"sqlite:///{DB_PATH}"

# Create Engine
# check_same_thread=False is needed for SQLite with FastAPI (multiple threads)
engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})

def init_db():
    """Initializes the database tables and seeds demo data."""
    from ..models.job import Job
    from ..models.calibration import UserCalibration  # ensures table is created
    from sqlmodel import select
    
    SQLModel.metadata.create_all(engine)
    
    # Seed test_video as a demo
    with Session(engine) as session:
        statement = select(Job).where(Job.id == "test_video")
        test_job = session.exec(statement).first()
        
        from pathlib import Path
        from ..core.config import UPLOAD_DIR
        large_base = Path("/dcs/large/safedrive_cs310_2526/uploads/")
        
        if (large_base / "test_video").exists() or (UPLOAD_DIR / "test_video").exists():
            if not test_job:
                test_job = Job(
                    id="test_video",
                    name="Pre-recorded Demo",
                    status="COMPLETED",
                    is_demo=True,
                    road_path="REMOTE:test_video/road_test.mp4",
                    face_path="REMOTE:test_video/face_test.mp4",
                    progress=100
                )
                session.add(test_job)
                print("Seeded new demo job: test_video")
            else:
                test_job.is_demo = True
                test_job.name = "Pre-recorded Demo"
                session.add(test_job)
                print("Updated existing job to demo: test_video")
            session.commit()
            
        # Seed gym video as a demo
        gym_id = "2025_0916_134624_007979F_cut_1"
        statement = select(Job).where(Job.id == gym_id)
        gym_job = session.exec(statement).first()
        if (large_base / gym_id).exists() or (UPLOAD_DIR / gym_id).exists():
            if not gym_job:
                gym_job = Job(
                    id=gym_id,
                    name="Me to gym turn cut 2",
                    status="COMPLETED",
                    is_demo=True,
                    road_path=f"REMOTE:{gym_id}/road.mp4",
                    face_path=f"REMOTE:{gym_id}/face.mp4",
                    progress=100
                )
                session.add(gym_job)
                print(f"Seeded new demo job: {gym_id}")
            else:
                gym_job.is_demo = True
                gym_job.name = "Me to gym turn cut 2"
                session.add(gym_job)
                print(f"Updated existing job to demo: {gym_id}")
            session.commit()

def get_session():
    """Dependency that provides a database session."""
    with Session(engine) as session:
        yield session