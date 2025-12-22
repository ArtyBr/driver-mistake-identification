import subprocess
import json
import re
import logging
import traceback
from pathlib import Path
from ..core.config import PROJECT_ROOT, UPLOAD_DIR
from ..db import database

logger = logging.getLogger(__name__)

def run_analysis_process(job_id: str, road_path: str, face_path: str) -> None:
    """
    Executes the analysis script in a subprocess.
    Updates the database with status, progress, and results.
    """
    try:
        logger.info(f"Starting analysis for Job {job_id}")
        database.update_job_status(job_id, "PROCESSING")
        
        output_json_path = UPLOAD_DIR / job_id / "results.json"
        script_path = PROJECT_ROOT / "combined_analysis/run_headless.py"
        
        cmd = [
            "python", "-u", str(script_path),
            "--road", str(road_path),
            "--face", str(face_path),
            "--output", str(output_json_path)
        ]
        
        logger.debug(f"Command: {' '.join(cmd)}")
        
        # Run subprocess and stream output for progress tracking
        with subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            cwd=str(PROJECT_ROOT),
            bufsize=1,
            universal_newlines=True
        ) as process:
            for line in process.stdout:
                # Log only if necessary or debug
                # logger.debug(f"Job {job_id} output: {line.strip()}")
                
                # Extract progress percentage from standard output
                # Expecting format like "35%|" from tqdm or custom print
                match = re.search(r"(\d+)%\|", line)
                if match:
                    try:
                        progress = int(match.group(1))
                        database.update_job_status(job_id, "PROCESSING", progress=progress)
                    except ValueError:
                        pass
        
        # Post-process validation
        if output_json_path.exists():
            logger.info(f"Job {job_id}: Output file found.")
            with open(output_json_path, 'r') as f:
                analysis_result = json.load(f)
            
            database.update_job_result(job_id, analysis_result)
            logger.info(f"Job {job_id} completed successfully.")
        else:
            if process.returncode != 0:
                error_msg = f"Subprocess failed with code {process.returncode}."
            else:
                error_msg = "Output JSON was not created by subprocess."
            
            logger.error(f"Job {job_id} failed: {error_msg}")
            database.update_job_status(job_id, "FAILED", error=error_msg)
            
    except Exception as e:
        logger.error(f"Job {job_id} exception: {e}")
        traceback.print_exc()
        database.update_job_status(job_id, "FAILED", error=str(e))
