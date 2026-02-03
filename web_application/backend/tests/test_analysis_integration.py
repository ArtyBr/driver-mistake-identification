import pytest
from unittest.mock import MagicMock, patch
from app.services.analysis_service import run_analysis_process

@patch('app.services.analysis_service.BatchService')
@patch('app.services.analysis_service.update_job')
def test_run_analysis_process_calls_batch(mock_update, mock_batch_class):
    mock_batch_service = mock_batch_class.return_value
    mock_batch_service.submit_job.return_value = "job_999"
    mock_batch_service._generate_sbatch_script.return_value = "#!/bin/bash\necho test"
    
    job_id = "test_job"
    road_path = "/path/to/road.mp4"
    face_path = "/path/to/face.mp4"
    
    run_analysis_process(job_id, road_path, face_path)
    
    # Verify BatchService was used
    assert mock_batch_service.submit_job.called
    assert mock_batch_service._generate_sbatch_script.called
    
    # Verify update_job was called to set status and batch_job_id
    mock_update.assert_any_call(job_id, status="SUBMITTED")
    mock_update.assert_any_call(job_id, status="SUBMITTED", batch_job_id="job_999")
