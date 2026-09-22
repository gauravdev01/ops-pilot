import pytest
from pydantic import ValidationError

from app.models.resume_analysis import (
    ResumeAnalysis,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
)


def test_resume_analysis_can_be_created_with_all_fields() -> None:
    analysis = ResumeAnalysis(
        name="Alex Morgan",
        current_role="Senior Software Engineer",
        years_of_experience=6.5,
        skills=["Python", "AWS"],
        experience=[
            ResumeExperience(
                company="Acme Corp",
                role="Software Engineer",
                highlights=["Built backend services"],
            )
        ],
        projects=[
            ResumeProject(
                name="Resume Parser",
                description="A tool for extracting resume data.",
                technologies=["Python", "FastAPI"],
            )
        ],
        education=[
            ResumeEducation(
                institution="State University",
                degree="BSc Computer Science",
                graduation_year=2020,
            )
        ],
        keywords=["backend", "cloud"],
    )

    assert analysis.name == "Alex Morgan"
    assert analysis.experience[0].company == "Acme Corp"
    assert analysis.projects[0].name == "Resume Parser"
    assert analysis.education[0].graduation_year == 2020


def test_resume_analysis_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        ResumeAnalysis(
            name="",
            skills=[],
            experience=[],
            projects=[],
            education=[],
            keywords=[],
        )


def test_resume_experience_rejects_empty_company() -> None:
    with pytest.raises(ValidationError):
        ResumeExperience(company="", role="Engineer", highlights=[])


def test_resume_experience_rejects_empty_role() -> None:
    with pytest.raises(ValidationError):
        ResumeExperience(company="Acme Corp", role="", highlights=[])


def test_resume_project_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        ResumeProject(name="", technologies=[])


def test_resume_education_rejects_empty_institution() -> None:
    with pytest.raises(ValidationError):
        ResumeEducation(institution="", degree=None, graduation_year=None)


def test_resume_analysis_rejects_negative_years_of_experience() -> None:
    with pytest.raises(ValidationError):
        ResumeAnalysis(
            name="Alex Morgan",
            years_of_experience=-1,
            skills=[],
            experience=[],
            projects=[],
            education=[],
            keywords=[],
        )


def test_resume_education_rejects_graduation_year_before_1900() -> None:
    with pytest.raises(ValidationError):
        ResumeEducation(
            institution="State University",
            degree=None,
            graduation_year=1899,
        )


def test_resume_optional_fields_can_be_none() -> None:
    analysis = ResumeAnalysis(
        name="Alex Morgan",
        current_role=None,
        years_of_experience=None,
        skills=[],
        experience=[],
        projects=[ResumeProject(name="Portfolio", description=None, technologies=[])],
        education=[
            ResumeEducation(
                institution="State University",
                degree=None,
                graduation_year=None,
            )
        ],
        keywords=[],
    )

    assert analysis.current_role is None
    assert analysis.years_of_experience is None
    assert analysis.projects[0].description is None
    assert analysis.education[0].degree is None
    assert analysis.education[0].graduation_year is None
