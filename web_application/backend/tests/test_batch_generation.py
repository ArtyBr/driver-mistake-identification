import pytest
from app.services.batch_service import BatchService

def test_generate_sbatch_script():
    service = BatchService()
    
    job_name = "analysis_job_123"
    road_path = "/dcs/large/safedrive/road.mp4"
    face_path = "/dcs/large/safedrive/face.mp4"
    output_path = "/dcs/large/safedrive/results.json"
    
    script = service._generate_sbatch_script(job_name, road_path, face_path, output_path)
    
    assert "#!/bin/bash" in script
    assert f"#SBATCH --job-name={job_name}" in script
    assert "#SBATCH --partition=gpus" in script  # Assuming GPU partition
    assert "#SBATCH --gres=gpu:1" in script      # Request 1 GPU
    assert "source /dcs/project/safedrive/driver-mistake-identification/lane_detection/lanedet/environment.yaml" in script or "conda activate" in script or "source" in script
    # We expect the command to run the headless script
    assert "python combined_analysis/run_headless.py" in script
    assert f"--road {road_path}" in script
    assert f"--face {face_path}" in script
    assert f"--output {output_path}" in script
