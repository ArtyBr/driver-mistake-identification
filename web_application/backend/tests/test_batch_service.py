import pytest
from app.services.batch_service import BatchService

def test_batch_service_init():
    service = BatchService()
    assert service.target_host == "kudu-taught.dcs.warwick.ac.uk"
    assert service.username == "u2204449"