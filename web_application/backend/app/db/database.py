import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from ..core.config import DB_PATH

def get_db_connection() -> sqlite3.Connection:
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initializes the database table if it doesn't exist."""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            road_path TEXT,
            face_path TEXT,
            road_metadata TEXT,
            face_metadata TEXT,
            result TEXT,
            error TEXT,
            progress INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def create_job(job_id: str, road_path: str, face_path: str, road_metadata: Dict = None, face_metadata: Dict = None) -> None:
    """Creates a new job record."""
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO jobs (id, status, road_path, face_path, road_metadata, face_metadata) VALUES (?, ?, ?, ?, ?, ?)',
        (job_id, 'PENDING', road_path, face_path, json.dumps(road_metadata) if road_metadata else None, json.dumps(face_metadata) if face_metadata else None)
    )
    conn.commit()
    conn.close()

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a job by its ID."""
    conn = get_db_connection()
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    conn.close()
    
    if job:
        job_dict = dict(job)
        # Parse JSON fields
        for field in ['result', 'road_metadata', 'face_metadata']:
            if job_dict.get(field):
                try:
                    job_dict[field] = json.loads(job_dict[field])
                except json.JSONDecodeError:
                    pass
        return job_dict
    return None

def update_job_status(job_id: str, status: str, progress: Optional[int] = None, error: Optional[str] = None) -> None:
    """Updates the status, progress, and error message of a job."""
    conn = get_db_connection()
    query = 'UPDATE jobs SET status = ?'
    params = [status]
    
    if progress is not None:
        query += ', progress = ?'
        params.append(progress)
        
    if error is not None:
        query += ', error = ?'
        params.append(error)
        
    query += ' WHERE id = ?'
    params.append(job_id)
    
    conn.execute(query, tuple(params))
    conn.commit()
    conn.close()

def update_job_result(job_id: str, result: Dict[str, Any]) -> None:
    """Marks a job as COMPLETED and saves the result."""
    conn = get_db_connection()
    conn.execute(
        'UPDATE jobs SET status = ?, result = ?, progress = ? WHERE id = ?',
        ('COMPLETED', json.dumps(result), 100, job_id)
    )
    conn.commit()
    conn.close()

def list_jobs() -> List[Dict[str, Any]]:
    """Lists all jobs ordered by creation date."""
    conn = get_db_connection()
    jobs = conn.execute('SELECT id, status, created_at FROM jobs ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(job) for job in jobs]
