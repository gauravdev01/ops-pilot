from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.api.dependencies import get_resume_analyzer
from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_request import ResumeAnalysisRequest

router = APIRouter(prefix="/api/v1/resume", tags=["resumes"])


@router.post("/analyze", response_model=ResumeAnalysis)
async def analyze_resume(
    request: ResumeAnalysisRequest,
    analyzer: Annotated[ResumeAnalyzerAgent, Depends(get_resume_analyzer)],
) -> ResumeAnalysis:
    """Analyze submitted resume text."""
    return await analyzer.execute(request.resume)
