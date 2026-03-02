import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
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
    from ..models.user import User
    from ..models.report import Report
    from ..services.auth_service import get_password_hash
    from sqlmodel import select

    SQLModel.metadata.create_all(engine)

    # Migrate: add columns that may not exist in older DB schemas
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0",
            "ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0",
            "ALTER TABLE users ADD COLUMN created_at DATETIME",
            "ALTER TABLE user_calibrations ADD COLUMN name TEXT DEFAULT 'New Calibration'",
            "ALTER TABLE jobs ADD COLUMN calibration_id TEXT",
            "ALTER TABLE jobs ADD COLUMN is_demo BOOLEAN DEFAULT 0",
            "UPDATE jobs SET is_demo = 0 WHERE is_demo IS NULL",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except OperationalError:
                pass  # Column already exists

        # Migrate: replace unique index on user_calibrations.user_id with a non-unique one
        # (the original table was created with a unique constraint, but we now allow multiple calibrations per user)
        try:
            conn.execute(text("DROP INDEX IF EXISTS ix_user_calibrations_user_id"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_calibrations_user_id ON user_calibrations (user_id)"))
            conn.commit()
        except OperationalError:
            pass

        # Mark all existing users as verified if we just added the column
        # This only runs once effectively if is_verified was just added
        # Or we can just ensure all currently signed up users are verified as requested.
        try:
            conn.execute(text("UPDATE users SET is_verified = 1"))
            conn.commit()
        except Exception:
            pass

    # Seed admin account
    admin_email = "admin@admin.com"
    admin_password = os.environ.get("ADMIN_PASSWORD", "SafeDrive2026!")
    with Session(engine) as session:
        existing_admin = session.exec(select(User).where(User.email == admin_email)).first()
        if not existing_admin:
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
                is_admin=True,
            )
            session.add(admin_user)
            session.commit()
            print(f"Seeded admin user: {admin_email}")
    
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
                test_job.road_path = "REMOTE:test_video/road_test.mp4"
                test_job.face_path = "REMOTE:test_video/face_test.mp4"
                test_job.progress = 100
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
                gym_job.road_path = f"REMOTE:{gym_id}/road.mp4"
                gym_job.face_path = f"REMOTE:{gym_id}/face.mp4"
                gym_job.progress = 100
                session.add(gym_job)
                print(f"Updated existing job to demo: {gym_id}")
            session.commit()

def get_session():
    """Dependency that provides a database session."""
    with Session(engine) as session:
        yield session