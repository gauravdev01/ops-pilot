from typing import Self

from pydantic import BaseModel, Field, model_validator


class JDAnalysis(BaseModel):
    """Structured analysis of a software engineering job description."""

    title: str = Field(min_length=1)
    seniority: str | None = Field(default=None, min_length=1)
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: list[str]
    experience_min_years: int | None = Field(default=None, ge=0)
    experience_max_years: int | None = Field(default=None, ge=0)
    keywords: list[str]

    @model_validator(mode="after")
    def validate_experience_range(self) -> Self:
        if (
            self.experience_min_years is not None
            and self.experience_max_years is not None
            and self.experience_min_years > self.experience_max_years
        ):
            raise ValueError(
                "experience_min_years must be less than or equal to "
                "experience_max_years"
            )
        return self
