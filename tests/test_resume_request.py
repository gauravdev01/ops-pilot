import pytest
from pydantic import ValidationError

from app.models.resume_request import ResumeAnalysisRequest


def test_valid_resume_is_accepted_and_preserved() -> None:
    resume = "Alex Morgan\nSoftware Engineer"

    request = ResumeAnalysisRequest(resume=resume)

    assert request.resume == resume


def test_empty_resume_is_rejected() -> None:
    with pytest.raises(ValidationError, match="resume cannot be empty"):
        ResumeAnalysisRequest(resume="")


def test_whitespace_only_resume_is_rejected() -> None:
    with pytest.raises(ValidationError, match="resume cannot be empty"):
        ResumeAnalysisRequest(resume=" \n\t ")
