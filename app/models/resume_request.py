from pydantic import BaseModel, field_validator


class ResumeAnalysisRequest(BaseModel):
    """Request containing resume text to analyze."""

    resume: str

    @field_validator("resume")
    @classmethod
    def validate_resume(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("resume cannot be empty")
        return value
