import pytest
from unittest.mock import MagicMock, patch
from app.services.batch_service import BatchService

@pytest.fixture
def mock_ssh():
    with patch("app.services.batch_service.BatchService._get_ssh_client") as mock:
        yield mock

def test_get_job_progress_found(mock_ssh):
    """Test extracting progress from a valid log file."""
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client
    
    # 1. Mock ls command
    mock_ls_out = MagicMock(read=lambda: b"slurm_123.log\nslurm_124.log")
    mock_ls_out.channel.recv_exit_status.return_value = 0
    mock_ls = (MagicMock(), mock_ls_out, MagicMock())

    # 2. Mock cat command
    mock_cat_out = MagicMock(read=lambda: b"Processing...\n45%|####      | 450/1000 [00:10<00:12, 45.12it/s]\nINFO: Still running")
    mock_cat_out.channel.recv_exit_status.return_value = 0
    mock_cat = (MagicMock(), mock_cat_out, MagicMock())
    
    mock_client.exec_command.side_effect = [mock_ls, mock_cat]

    service = BatchService()
    progress = service.get_job_progress("job_123", "/path/to/job")
    
    assert progress == 45

def test_get_job_progress_no_log(mock_ssh):
    """Test behavior when no log file exists."""
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client
    
    # Mock ls command returning nothing
    mock_client.exec_command.return_value = (
        MagicMock(), 
        MagicMock(read=lambda: b""), 
        MagicMock()
    )
    mock_client.exec_command.return_value[1].channel.recv_exit_status.return_value = 0

    service = BatchService()
    progress = service.get_job_progress("job_123", "/path/to/job")
    
    assert progress is None

def test_get_job_error_found(mock_ssh):
    """Test extracting error message from log tail."""
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client
    
    # 1. Mock ls command
    mock_ls_out = MagicMock(read=lambda: b"slurm_123.log")
    mock_ls_out.channel.recv_exit_status.return_value = 0
    mock_ls = (MagicMock(), mock_ls_out, MagicMock())

    # 2. Mock tail command
    mock_tail_out = MagicMock(read=lambda: b"Traceback (most recent call last):\nValueError: Invalid video format")
    mock_tail_out.channel.recv_exit_status.return_value = 0
    mock_tail = (MagicMock(), mock_tail_out, MagicMock())

    mock_client.exec_command.side_effect = [mock_ls, mock_tail]

    service = BatchService()
    error = service.get_job_error("job_123", "/path/to/job")
    
    assert "ValueError: Invalid video format" in error

def test_read_remote_results_success(mock_ssh):
    """Test reading the results.json file."""
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client
    
    expected_json = '{"meta": {}, "timeline_events": []}'
    
    mock_client.exec_command.return_value = (
        MagicMock(), 
        MagicMock(read=lambda: expected_json.encode()), 
        MagicMock()
    )
    mock_client.exec_command.return_value[1].channel.recv_exit_status.return_value = 0

    service = BatchService()
    result = service.read_remote_results("/path/to/results.json")
    
    assert result == expected_json

def test_read_remote_results_not_found(mock_ssh):
    """Test handling of missing results file."""
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client
    
    mock_client.exec_command.return_value = (
        MagicMock(), 
        MagicMock(read=lambda: b""), 
        MagicMock()
    )
    # Simulate non-zero exit code (cat failed)
    mock_client.exec_command.return_value[1].channel.recv_exit_status.return_value = 1

    service = BatchService()
    result = service.read_remote_results("/path/to/results.json")
    
    assert result is None
