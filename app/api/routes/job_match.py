from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.job_matcher import JobMatcherAgent
from app.api.dependencies import get_job_matcher
from app.models.job_match import JobMatchResult
from app.models.job_match_request import JobMatchRequest

router = APIRouter(prefix="/api/v1/job-match", tags=["job matching"])


@router.post("/match", response_model=JobMatchResult)
async def match_job(
    request: JobMatchRequest,
    agent: Annotated[JobMatcherAgent, Depends(get_job_matcher)],
) -> JobMatchResult:
    """Match a job analysis against a resume analysis."""
    return await agent.execute(request)
