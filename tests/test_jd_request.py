import pytest
from pydantic import ValidationError

from app.models.jd_request import JDAnalysisRequest


def test_valid_job_description_can_be_created() -> None:
    request = JDAnalysisRequest(job_description="Build backend services with Python.")

    assert request.job_description == "Build backend services with Python."


def test_empty_job_description_is_rejected() -> None:
    with pytest.raises(ValidationError):
        JDAnalysisRequest(job_description="")


def test_whitespace_only_job_description_is_rejected() -> None:
    with pytest.raises(ValidationError):
        JDAnalysisRequest(job_description=" \n\t ")
