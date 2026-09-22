from pydantic import BaseModel, Field


class ResumeExperience(BaseModel):
    """A professional experience entry from a resume."""

    company: str = Field(min_length=1)
    role: str = Field(min_length=1)
    highlights: list[str]


class ResumeProject(BaseModel):
    """A project entry from a resume."""

    name: str = Field(min_length=1)
    description: str | None = None
    technologies: list[str]


class ResumeEducation(BaseModel):
    """An education entry from a resume."""

    institution: str = Field(min_length=1)
    degree: str | None = None
    graduation_year: int | None = Field(default=None, ge=1900)


class ResumeAnalysis(BaseModel):
    """Structured analysis of a resume."""

    name: str = Field(min_length=1)
    current_role: str | None = None
    years_of_experience: float | None = Field(default=None, ge=0)
    skills: list[str]
    experience: list[ResumeExperience]
    projects: list[ResumeProject]
    education: list[ResumeEducation]
    keywords: list[str]
