import pytest

from app.models.jd_analysis import JDAnalysis
from app.models.job_match import JobMatchResult
from app.models.resume_analysis import (
    ResumeAnalysis,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
)
from app.services.job_matcher import JobMatcherService


def create_job(
    required_skills: list[str] | None = None,
    preferred_skills: list[str] | None = None,
    experience_min_years: int | None = None,
    experience_max_years: int | None = None,
    seniority: str | None = None,
) -> JDAnalysis:
    return JDAnalysis(
        title="Backend Engineer",
        seniority=seniority,
        required_skills=[] if required_skills is None else required_skills,
        preferred_skills=[] if preferred_skills is None else preferred_skills,
        responsibilities=[],
        experience_min_years=experience_min_years,
        experience_max_years=experience_max_years,
        keywords=[],
    )


def create_resume(
    skills: list[str] | None = None,
    years_of_experience: float | None = None,
    current_role: str | None = None,
) -> ResumeAnalysis:
    return ResumeAnalysis(
        name="Alex Morgan",
        current_role=current_role,
        years_of_experience=years_of_experience,
        skills=[] if skills is None else skills,
        experience=[
            ResumeExperience(
                company="Acme Corp",
                role="Engineer",
                highlights=["Built services"],
            )
        ],
        projects=[
            ResumeProject(
                name="Platform",
                description="Backend platform",
                technologies=["Python"],
            )
        ],
        education=[
            ResumeEducation(
                institution="State University",
                degree="BSc",
                graduation_year=2020,
            )
        ],
        keywords=["backend"],
    )


def test_all_required_and_preferred_skills_match() -> None:
    result = JobMatcherService().match(
        create_job(
            required_skills=["Java", "Spring Boot"],
            preferred_skills=["AWS"],
        ),
        create_resume(skills=["Java", "Spring Boot", "AWS"]),
    )

    assert isinstance(result, JobMatchResult)
    assert result.matched_required_skills == ["Java", "Spring Boot"]
    assert result.missing_required_skills == []
    assert result.matched_preferred_skills == ["AWS"]
    assert result.missing_preferred_skills == []
    assert result.match_percentage == 100


def test_required_skills_partially_match() -> None:
    result = JobMatcherService().match(
        create_job(
            required_skills=["Java", "Spring Boot", "Kafka"],
            preferred_skills=["AWS"],
        ),
        create_resume(skills=["Java", "Spring Boot", "Redis", "AWS"]),
    )

    assert result.matched_required_skills == ["Java", "Spring Boot"]
    assert result.missing_required_skills == ["Kafka"]
    assert result.matched_preferred_skills == ["AWS"]
    assert result.missing_preferred_skills == []
    assert result.match_percentage == pytest.approx(73.33)


def test_preferred_skills_partially_match() -> None:
    result = JobMatcherService().match(
        create_job(
            required_skills=["Java"],
            preferred_skills=["AWS", "Kubernetes"],
        ),
        create_resume(skills=["Java", "AWS"]),
    )

    assert result.matched_preferred_skills == ["AWS"]
    assert result.missing_preferred_skills == ["Kubernetes"]
    assert result.match_percentage == 90


def test_skill_matching_is_case_and_whitespace_insensitive() -> None:
    result = JobMatcherService().match(
        create_job(required_skills=["Java", " Spring Boot "]),
        create_resume(skills=["java", "spring boot"]),
    )

    assert result.matched_required_skills == ["java", "spring boot"]
    assert result.missing_required_skills == []
    assert result.match_percentage == 100


def test_duplicate_normalized_skills_do_not_inflate_score() -> None:
    result = JobMatcherService().match(
        create_job(required_skills=["Java", " java ", "Python"]),
        create_resume(skills=["java", "JAVA"]),
    )

    assert result.matched_required_skills == ["java"]
    assert result.missing_required_skills == ["Python"]
    assert result.match_percentage == 60


def test_no_required_skills_do_not_reduce_score() -> None:
    result = JobMatcherService().match(
        create_job(preferred_skills=["AWS"]),
        create_resume(skills=["AWS"]),
    )

    assert result.match_percentage == 100


def test_no_preferred_skills_do_not_reduce_score() -> None:
    result = JobMatcherService().match(
        create_job(required_skills=["Java"]),
        create_resume(skills=["Java"]),
    )

    assert result.match_percentage == 100


def test_empty_required_and_preferred_skills_match_fully() -> None:
    result = JobMatcherService().match(create_job(), create_resume())

    assert result.match_percentage == 100


@pytest.mark.parametrize(
    ("minimum", "maximum", "years", "expected"),
    [
        (None, None, 5, None),
        (5, None, 5, True),
        (5, None, 4, False),
        (None, 8, 8, True),
        (None, 8, 9, False),
        (5, 8, 6, True),
        (5, 8, 4, False),
        (5, 8, 5, True),
        (5, 8, 8, True),
    ],
)
def test_experience_matching(
    minimum: int | None,
    maximum: int | None,
    years: float | None,
    expected: bool | None,
) -> None:
    result = JobMatcherService().match(
        create_job(experience_min_years=minimum, experience_max_years=maximum),
        create_resume(years_of_experience=years),
    )

    assert result.experience_match is expected


def test_unknown_resume_experience_returns_none() -> None:
    result = JobMatcherService().match(
        create_job(experience_min_years=5),
        create_resume(years_of_experience=None),
    )

    assert result.experience_match is None


@pytest.mark.parametrize(
    ("job_seniority", "resume_role", "expected"),
    [
        ("senior", "senior", True),
        ("senior", "lead", True),
        ("senior", "junior", False),
        (None, "senior", None),
        ("senior", None, None),
        ("architect", "senior", None),
        ("senior", "architect", None),
        ("senior", "Software Development Engineer", None),
    ],
)
def test_seniority_matching(
    job_seniority: str | None,
    resume_role: str | None,
    expected: bool | None,
) -> None:
    result = JobMatcherService().match(
        create_job(seniority=job_seniority),
        create_resume(current_role=resume_role),
    )

    assert result.seniority_match is expected


def test_explanation_contains_skill_coverage_counts() -> None:
    result = JobMatcherService().match(
        create_job(
            required_skills=["Java", "Python"],
            preferred_skills=["AWS", "Kafka"],
        ),
        create_resume(skills=["Java", "AWS"]),
    )

    assert "Required skills matched: 1 of 2" in result.explanation
    assert "preferred skills matched: 1 of 2" in result.explanation
