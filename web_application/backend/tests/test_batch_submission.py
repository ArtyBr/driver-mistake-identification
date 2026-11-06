import pytest
from unittest.mock import MagicMock, patch
from app.services.batch_service import BatchService

@patch('paramiko.SSHClient')
def test_submit_job_success(mock_ssh):
    # We need to mock TWO SSHClient instances now
    mock_jump = MagicMock()
    mock_target = MagicMock()
    mock_ssh.side_effect = [mock_jump, mock_target]
    
    # Mock sbatch output on the target
    mock_stdin = MagicMock()
    mock_stdout = MagicMock()
    mock_stderr = MagicMock()
    
    mock_stdout.read.return_value = b"Submitted batch job 123456\n"
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stderr.read.return_value = b""
    
    mock_target.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
    
    # Mock transport for jump host
    mock_transport = MagicMock()
    mock_jump.get_transport.return_value = mock_transport
    mock_transport.open_channel.return_value = MagicMock()
    
    service = BatchService()
    service.jump_host = "remote-49"
    service.target_host = "kudu-taught"
    service.username = "safedrive"
    
    job_id = service.submit_job("echo test")
    
    assert job_id == "123456"
    assert mock_jump.connect.called
    assert mock_target.connect.called

@patch('paramiko.SSHClient')
def test_check_status_success(mock_ssh):
    mock_jump = MagicMock()
    mock_target = MagicMock()
    mock_ssh.side_effect = [mock_jump, mock_target]
    
    # Mock transport for jump host
    mock_jump.get_transport.return_value = MagicMock()
    
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b"RUNNING\n"
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_target.exec_command.return_value = (None, mock_stdout, MagicMock())
    
    service = BatchService()
    status = service.check_status("123456")
    
    assert status == "RUNNING"
    mock_target.exec_command.assert_called_with("squeue -j 123456 -h -o %T")

@patch('paramiko.SSHClient')
def test_submit_job_failure(mock_ssh):
    mock_jump = MagicMock()
    mock_target = MagicMock()
    mock_ssh.side_effect = [mock_jump, mock_target]
    mock_jump.get_transport.return_value = MagicMock()

    mock_stdout = MagicMock()
    mock_stderr = MagicMock()
    mock_stdout.channel.recv_exit_status.return_value = 1
    mock_stderr.read.return_value = b"Invalid partition\n"
    mock_target.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
    
    service = BatchService()
    with pytest.raises(Exception) as excinfo:
        service.submit_job("echo test")
    assert "Failed to submit job: Invalid partition" in str(excinfo.value)

@patch('paramiko.SSHClient')
def test_check_status_not_found(mock_ssh):
    mock_jump = MagicMock()
    mock_target = MagicMock()
    mock_ssh.side_effect = [mock_jump, mock_target]
    mock_jump.get_transport.return_value = MagicMock()

    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b"" # empty output
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_target.exec_command.return_value = (None, mock_stdout, MagicMock())
    
    service = BatchService()
    status = service.check_status("123456")
    assert status == "COMPLETED"

@patch('paramiko.SSHClient')
def test_check_status_error(mock_ssh):
    mock_jump = MagicMock()
    mock_target = MagicMock()
    mock_ssh.side_effect = [mock_jump, mock_target]
    mock_jump.get_transport.return_value = MagicMock()

    mock_stdout = MagicMock()
    mock_stdout.channel.recv_exit_status.return_value = 1
    mock_target.exec_command.return_value = (None, mock_stdout, MagicMock())
    
    service = BatchService()
    status = service.check_status("123456")
    assert status == "UNKNOWN"
