from pydantic import BaseModel

from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis


class JobMatchRequest(BaseModel):
    """Request containing a job analysis and resume analysis to match."""

    job: JDAnalysis
    resume: ResumeAnalysis
