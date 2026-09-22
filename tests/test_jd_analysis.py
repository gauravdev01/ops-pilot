import pytest
from pydantic import ValidationError

from app.models.jd_analysis import JDAnalysis


def test_jd_analysis_can_be_created_with_all_fields() -> None:
    analysis = JDAnalysis(
        title="Software Engineer",
        seniority="Senior",
        required_skills=["Python", "SQL"],
        preferred_skills=["AWS"],
        responsibilities=["Build services"],
        experience_min_years=5,
        experience_max_years=7,
        keywords=["backend", "cloud"],
    )

    assert analysis.title == "Software Engineer"
    assert analysis.experience_min_years == 5
    assert analysis.experience_max_years == 7


def test_seniority_can_be_none() -> None:
    analysis = JDAnalysis(
        title="Software Engineer",
        seniority=None,
        required_skills=[],
        preferred_skills=[],
        responsibilities=[],
        keywords=[],
    )

    assert analysis.seniority is None


def test_experience_years_can_be_none() -> None:
    analysis = JDAnalysis(
        title="Software Engineer",
        seniority="Senior",
        required_skills=[],
        preferred_skills=[],
        responsibilities=[],
        keywords=[],
    )

    assert analysis.experience_min_years is None
    assert analysis.experience_max_years is None


@pytest.mark.parametrize("field", ["experience_min_years", "experience_max_years"])
def test_experience_years_cannot_be_negative(field: str) -> None:
    with pytest.raises(ValidationError):
        JDAnalysis.model_validate(
            {
                "title": "Software Engineer",
                "seniority": "Senior",
                "required_skills": [],
                "preferred_skills": [],
                "responsibilities": [],
                "keywords": [],
                field: -1,
            }
        )


def test_experience_min_years_cannot_exceed_max_years() -> None:
    with pytest.raises(ValidationError):
        JDAnalysis(
            title="Software Engineer",
            seniority="Senior",
            required_skills=[],
            preferred_skills=[],
            responsibilities=[],
            experience_min_years=8,
            experience_max_years=5,
            keywords=[],
        )


def test_title_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        JDAnalysis(
            title="",
            seniority="Senior",
            required_skills=[],
            preferred_skills=[],
            responsibilities=[],
            keywords=[],
        )


def test_seniority_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        JDAnalysis(
            title="Software Engineer",
            seniority="",
            required_skills=[],
            preferred_skills=[],
            responsibilities=[],
            keywords=[],
        )
