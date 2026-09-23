import pytest
from pydantic import ValidationError

from app.models.jd_analysis import JDAnalysis
from app.models.job_match_request import JobMatchRequest
from app.models.resume_analysis import ResumeAnalysis


def test_job_match_request_accepts_valid_nested_models() -> None:
    job = JDAnalysis(
        title="Backend Engineer",
        seniority="Senior",
        required_skills=["Python"],
        preferred_skills=["AWS"],
        responsibilities=["Build services"],
        experience_min_years=5,
        experience_max_years=8,
        keywords=["backend"],
    )
    resume = ResumeAnalysis(
        name="Alex Morgan",
        current_role="Senior",
        years_of_experience=6,
        skills=["Python"],
        experience=[],
        projects=[],
        education=[],
        keywords=["backend"],
    )

    request = JobMatchRequest(job=job, resume=resume)

    assert request.job is job
    assert request.resume is resume


def test_job_match_request_rejects_invalid_job_payload() -> None:
    resume = ResumeAnalysis(
        name="Alex Morgan",
        skills=[],
        experience=[],
        projects=[],
        education=[],
        keywords=[],
    )

    with pytest.raises(ValidationError):
        JobMatchRequest.model_validate(
            {
                "job": {
                    "title": "",
                    "required_skills": [],
                    "preferred_skills": [],
                    "responsibilities": [],
                    "keywords": [],
                },
                "resume": resume.model_dump(),
            }
        )
