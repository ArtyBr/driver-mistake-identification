#!/usr/bin/env python3
"""
Transcodes existing job videos to 720p/480p quality variants.
Run once (idempotent) to backfill quality options for existing uploads.

Usage (from web_application/backend/):
    python -m scripts.transcode_existing_jobs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import UPLOAD_DIR
from app.services.file_service import FileService

_LARGE_BASE = Path("/dcs/large/safedrive_cs310_2526/uploads")


def main():
    bases = [b for b in [_LARGE_BASE, UPLOAD_DIR] if b.exists()]
    if not bases:
        print("No upload directories found.")
        return

    for base in bases:
        job_dirs = [d for d in base.iterdir() if d.is_dir()]
        print(f"Found {len(job_dirs)} job directories in {base}")
        for job_dir in job_dirs:
            road = job_dir / "road.mp4"
            face = job_dir / "face.mp4"
            if road.exists() or face.exists():
                print(f"  Transcoding {job_dir.name}…")
                FileService.transcode_job_videos(job_dir.name, road, face)
                print(f"  Done: {job_dir.name}")
            else:
                print(f"  Skipping {job_dir.name} (no road.mp4 or face.mp4)")


if __name__ == "__main__":
    main()
