import shutil
import logging
from pathlib import Path
from typing import List, Tuple
from fastapi import UploadFile
from ..core.config import UPLOAD_DIR
from .video_utils import splice_videos, get_video_duration, get_video_height, transcode_to_quality

logger = logging.getLogger(__name__)

class FileService:
    @staticmethod
    def create_job_directory(job_id: str) -> Path:
        job_dir = UPLOAD_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    @staticmethod
    def delete_job_directory(job_id: str):
        job_dir = UPLOAD_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)

    @staticmethod
    def process_uploads(job_dir: Path, files: List[UploadFile], prefix: str) -> Tuple[Path, List[str], List[int], float]:
        """
        Saves uploaded chunks, splices them, and returns (final_path, filenames, sizes, duration).
        """
        parts_paths = []
        filenames = []
        sizes = []
        
        for i, file_obj in enumerate(files):
            part_path = job_dir / f"{prefix}_part_{i:03d}.mp4"
            with open(part_path, "wb") as buffer:
                shutil.copyfileobj(file_obj.file, buffer)
            
            parts_paths.append(part_path)
            filenames.append(file_obj.filename)
            sizes.append(part_path.stat().st_size)
            
        final_path = job_dir / f"{prefix}.mp4"
        
        if not splice_videos(parts_paths, final_path):
            raise RuntimeError(f"Failed to splice {prefix} videos")
            
        # Cleanup parts if more than 1 (splice_videos handles moving if only 1)
        if len(parts_paths) > 1:
            for p in parts_paths:
                if p.exists():
                    p.unlink()
        
        duration = get_video_duration(final_path)
        return final_path, filenames, sizes, duration

    @staticmethod
    def transcode_job_videos(job_id: str, road_path: Path, face_path: Path):
        """
        Background-transcodes road and face videos to 720p and 480p quality variants.
        Skips upscaling and already-existing output files. Non-fatal on failure.
        """
        targets = [720, 480]
        pairs = [(road_path, "road"), (face_path, "face")]
        for path, prefix in pairs:
            if not path.exists():
                continue
            try:
                orig_height = get_video_height(path)
                if orig_height == 0:
                    logger.warning(f"Could not determine height for {path}, skipping transcoding")
                    continue
                for target in targets:
                    if orig_height <= target:
                        continue  # no upscaling
                    out_path = path.parent / f"{prefix}_{target}p.mp4"
                    if out_path.exists():
                        continue  # idempotent
                    logger.info(f"Transcoding {path.name} → {out_path.name} for job {job_id}")
                    success = transcode_to_quality(path, out_path, target)
                    if not success:
                        logger.error(f"Transcoding failed: {out_path.name} for job {job_id}")
            except Exception as e:
                logger.error(f"transcode_job_videos error for {prefix} ({job_id}): {e}")
