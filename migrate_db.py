import sqlite3
from pathlib import Path

db_path = Path("/dcs/project/safedrive/driver-mistake-identification/web_application/backend/jobs.db")

def migrate():
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Adding last_status_check column...")
        cursor.execute("ALTER TABLE jobs ADD COLUMN last_status_check DATETIME")
        conn.commit()
    except sqlite3.OperationalError:
        print("last_status_check already exists.")

    try:
        print("Adding is_checking column...")
        cursor.execute("ALTER TABLE jobs ADD COLUMN is_checking BOOLEAN DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        print("is_checking already exists.")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
