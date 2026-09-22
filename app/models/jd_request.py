from pydantic import BaseModel, field_validator


class JDAnalysisRequest(BaseModel):
    """Request containing a job description to analyze."""

    job_description: str

    @field_validator("job_description")
    @classmethod
    def validate_job_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("job_description cannot be empty")
        return value
