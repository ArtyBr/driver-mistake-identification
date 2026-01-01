
from sqlmodel import SQLModel, create_engine, Session, select
from web_application.backend.app.models.job import Job
import json
import sys

# Add the project root to sys.path to ensure imports work
sys.path.append("/home/arty/projects/driver_mistake_identification")

sqlite_url = "sqlite:///web_application/backend/jobs.db"
engine = create_engine(sqlite_url)

def inspect_jobs():
    with Session(engine) as session:
        statement = select(Job)
        results = session.exec(statement).all()
        
        print(f"Found {len(results)} jobs.")
        for job in results:
            print(f"Job ID: {job.id}")
            print(f"  Road Path: {job.road_path}")
            print(f"  Road Metadata: {job.road_metadata}")
            
            if job.road_metadata:
                try:
                    meta = json.loads(job.road_metadata)
                    print(f"  Parsed Duration: {meta.get('duration')}")
                except Exception as e:
                    print(f"  Error parsing metadata: {e}")
            print("-" * 20)

if __name__ == "__main__":
    inspect_jobs()
