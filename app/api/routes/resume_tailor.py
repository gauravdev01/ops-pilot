from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.resume_tailor import ResumeTailorAgent, ResumeTailorInput
from app.api.dependencies import get_resume_tailor
from app.models.resume_tailor import ResumeTailorResult

router = APIRouter(prefix="/api/v1/resume-tailor", tags=["resume tailoring"])


@router.post("/tailor", response_model=ResumeTailorResult)
async def tailor_resume(
    request: ResumeTailorInput,
    agent: Annotated[ResumeTailorAgent, Depends(get_resume_tailor)],
) -> ResumeTailorResult:
    """Tailor a resume analysis to a job analysis."""
    return await agent.execute(request)
