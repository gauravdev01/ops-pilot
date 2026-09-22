import pytest
from pydantic import ValidationError

from app.models.job_match import JobMatchResult


def test_job_match_result_can_be_created_with_all_fields() -> None:
    result = JobMatchResult(
        match_percentage=75.5,
        matched_required_skills=["Java", "Spring Boot"],
        missing_required_skills=["Kafka"],
        matched_preferred_skills=["AWS"],
        missing_preferred_skills=["Kubernetes"],
        experience_match=True,
        seniority_match=None,
        explanation="Strong backend fit.",
    )

    assert result.match_percentage == 75.5
    assert result.matched_required_skills == ["Java", "Spring Boot"]
    assert result.experience_match is True
    assert result.seniority_match is None


@pytest.mark.parametrize("match_percentage", [0, 100])
def test_match_percentage_boundaries_are_accepted(match_percentage: int) -> None:
    result = JobMatchResult(
        match_percentage=match_percentage,
        matched_required_skills=[],
        missing_required_skills=[],
        matched_preferred_skills=[],
        missing_preferred_skills=[],
        explanation="Boundary match.",
    )

    assert result.match_percentage == match_percentage


@pytest.mark.parametrize("match_percentage", [-0.1, 100.1])
def test_match_percentage_out_of_range_is_rejected(
    match_percentage: float,
) -> None:
    with pytest.raises(ValidationError):
        JobMatchResult(
            match_percentage=match_percentage,
            matched_required_skills=[],
            missing_required_skills=[],
            matched_preferred_skills=[],
            missing_preferred_skills=[],
            explanation="Invalid percentage.",
        )


def test_empty_explanation_is_rejected() -> None:
    with pytest.raises(ValidationError):
        JobMatchResult(
            match_percentage=50,
            matched_required_skills=[],
            missing_required_skills=[],
            matched_preferred_skills=[],
            missing_preferred_skills=[],
            explanation="",
        )


def test_experience_match_can_be_none() -> None:
    result = JobMatchResult(
        match_percentage=50,
        matched_required_skills=[],
        missing_required_skills=[],
        matched_preferred_skills=[],
        missing_preferred_skills=[],
        experience_match=None,
        explanation="Experience was not specified.",
    )

    assert result.experience_match is None


def test_seniority_match_can_be_none() -> None:
    result = JobMatchResult(
        match_percentage=50,
        matched_required_skills=[],
        missing_required_skills=[],
        matched_preferred_skills=[],
        missing_preferred_skills=[],
        seniority_match=None,
        explanation="Seniority was not specified.",
    )

    assert result.seniority_match is None


def test_optional_match_fields_default_to_none() -> None:
    result = JobMatchResult(
        match_percentage=50,
        matched_required_skills=[],
        missing_required_skills=[],
        matched_preferred_skills=[],
        missing_preferred_skills=[],
        explanation="Optional fields were omitted.",
    )

    assert result.experience_match is None
    assert result.seniority_match is None
