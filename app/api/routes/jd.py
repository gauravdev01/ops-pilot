from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.jd_analyzer import JDAnalyzerAgent
from app.api.dependencies import get_jd_analyzer
from app.models.jd_analysis import JDAnalysis
from app.models.jd_request import JDAnalysisRequest

router = APIRouter(prefix="/api/v1/jd", tags=["job descriptions"])


@router.post("/analyze", response_model=JDAnalysis)
async def analyze_job_description(
    request: JDAnalysisRequest,
    analyzer: Annotated[JDAnalyzerAgent, Depends(get_jd_analyzer)],
) -> JDAnalysis:
    """Analyze a submitted job description."""
    return await analyzer.execute(request.job_description)
