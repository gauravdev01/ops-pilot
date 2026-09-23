from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_tailor import ResumeTailorResult
from app.services.resume_tailor import ResumeTailorService


def create_resume(
    skills: list[str] | None = None,
    keywords: list[str] | None = None,
) -> ResumeAnalysis:
    return ResumeAnalysis(
        name="Alex Morgan",
        current_role="Software Engineer",
        years_of_experience=6,
        skills=[] if skills is None else skills,
        experience=[],
        projects=[],
        education=[],
        keywords=[] if keywords is None else keywords,
    )


def create_result(
    skills_to_highlight: list[str] | None = None,
    keywords_to_include: list[str] | None = None,
) -> ResumeTailorResult:
    return ResumeTailorResult(
        summary="Backend-focused engineer.",
        experience_bullets=["Built backend services"],
        projects=["Created a platform"],
        skills_to_highlight=(
            [] if skills_to_highlight is None else skills_to_highlight
        ),
        keywords_to_include=(
            [] if keywords_to_include is None else keywords_to_include
        ),
    )


def test_sanitize_keeps_supported_skills() -> None:
    resume = create_resume(skills=["Python", "FastAPI"])
    result = create_result(skills_to_highlight=["Python", "FastAPI"])

    sanitized = ResumeTailorService().sanitize(result, resume)

    assert sanitized.skills_to_highlight == ["Python", "FastAPI"]


def test_sanitize_removes_unsupported_skills() -> None:
    resume = create_resume(skills=["Python"])
    result = create_result(skills_to_highlight=["Python", "Java"])

    sanitized = ResumeTailorService().sanitize(result, resume)

    assert sanitized.skills_to_highlight == ["Python"]


def test_sanitize_keeps_supported_keywords() -> None:
    resume = create_resume(skills=["Python"], keywords=["backend"])
    result = create_result(keywords_to_include=["Python", "backend"])

    sanitized = ResumeTailorService().sanitize(result, resume)

    assert sanitized.keywords_to_include == ["Python", "backend"]


def test_sanitize_removes_unsupported_keywords() -> None:
    resume = create_resume(skills=["Python"], keywords=["backend"])
    result = create_result(keywords_to_include=["microservices"])

    sanitized = ResumeTailorService().sanitize(result, resume)

    assert sanitized.keywords_to_include == []


def test_sanitize_is_case_insensitive() -> None:
    resume = create_resume(skills=["Python"])
    result = create_result(skills_to_highlight=[" python "])

    sanitized = ResumeTailorService().sanitize(result, resume)

    assert sanitized.skills_to_highlight == [" python "]


def test_sanitize_does_not_modify_other_result_fields() -> None:
    resume = create_resume(skills=["Python"])
    result = create_result(
        skills_to_highlight=["Python"],
        keywords_to_include=["backend"],
    )

    sanitized = ResumeTailorService().sanitize(result, resume)

    assert sanitized.summary == result.summary
    assert sanitized.experience_bullets == result.experience_bullets
    assert sanitized.projects == result.projects
