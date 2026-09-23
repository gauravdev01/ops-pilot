from pydantic import BaseModel, Field


class JobMatchResult(BaseModel):
    """Structured result of matching a resume against a job description."""

    match_percentage: float = Field(ge=0, le=100)
    matched_required_skills: list[str]
    missing_required_skills: list[str]
    matched_preferred_skills: list[str]
    missing_preferred_skills: list[str]
    experience_match: bool | None = None
    seniority_match: bool | None = None
    explanation: str = Field(min_length=1)
