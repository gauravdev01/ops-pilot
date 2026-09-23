from pydantic import BaseModel, Field


class ResumeTailorResult(BaseModel):
    """Tailored resume content based on a job description."""

    summary: str = Field(min_length=1)
    experience_bullets: list[str]
    projects: list[str]
    skills_to_highlight: list[str]
    keywords_to_include: list[str]
