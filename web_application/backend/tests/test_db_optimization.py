import sys
import json
from pathlib import Path

# Add the app directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from sqlmodel import Session, create_engine, select
from app.models.job import Job
from app.services.job_service import JobService
from app.core.config import DB_PATH

# Use the existing database engine for testing
sqlite_url = f"sqlite:///{DB_PATH}"
engine = create_engine(sqlite_url)

def test_db_optimization():
    print("Starting DB optimization verification test...")
    
    with Session(engine) as session:
        service = JobService(session)
        
        # 1. Create a test job using the refactored method
        # This uses the existing "test_video" in large storage
        print("Creating test job...")
        try:
            job = service.create_test_job("test_video")
            job_id = job.id
            print(f"Test job created with ID: {job_id}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False

        # 2. Verify the job record in DB has NO result data
        session.expire_all()
        db_job = session.exec(select(Job).where(Job.id == job_id)).one()
        
        print(f"Checking DB record for job {job_id}...")
        if db_job.result is not None:
            print(f"FAILED: Job record in DB still contains result data! (Length: {len(db_job.result)})")
            return False
        else:
            print("SUCCESS: Job record in DB has no result data.")

        # 3. Verify load_results correctly fetches from filesystem
        print("Testing load_results...")
        results = service.load_results(job_id)
        if results and isinstance(results, dict):
            print("SUCCESS: load_results correctly fetched results from filesystem.")
            print(f"Result keys found: {list(results.keys())}")
        else:
            print("FAILED: load_results failed to fetch results from filesystem.")
            return False

        # 4. Test finalize_job refactor
        # We'll use "test_video" as an existing job_id in DB to test finalize
        print("Testing finalize_job (using test_video as target)...")
        # Ensure test_video job exists or create it
        test_job = session.get(Job, "test_video")
        if not test_job:
            test_job = Job(id="test_video", status="PENDING", road_metadata="{}", face_metadata="{}")
            session.add(test_job)
            session.commit()
        else:
            test_job.status = "PENDING"
            test_job.result = None
            session.add(test_job)
            session.commit()

        finalized_job = service.finalize_job("test_video")
        if finalized_job:
            print(f"Finalize job status: {finalized_job.status}")
            if finalized_job.result is None:
                 print("SUCCESS: finalize_job did not populate the result column.")
            else:
                 print(f"WARNING: finalize_job result column value not None: {len(finalized_job.result)}")
        
        print("\nAll DB optimization tests completed!")
        return True

if __name__ == "__main__":
    success = test_db_optimization()
    sys.exit(0 if success else 1)
