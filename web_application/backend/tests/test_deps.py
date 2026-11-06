def test_paramiko_installed():
    import paramiko
    assert paramiko.__version__ is not None
