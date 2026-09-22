from fastapi.testclient import TestClient

from app.agents.jd_analyzer import JDAnalyzerAgent
from app.api.dependencies import get_jd_analyzer
from app.api.main import app
from app.models.jd_analysis import JDAnalysis


class FakeAnalyzer(JDAnalyzerAgent):
    def __init__(self, result: JDAnalysis) -> None:
        self.result = result
        self.received_job_description: str | None = None

    @property
    def name(self) -> str:
        return "fake-analyzer"

    async def execute(self, input_data: str) -> JDAnalysis:
        self.received_job_description = input_data
        return self.result


def test_jd_analyze_returns_analysis_and_forwards_description() -> None:
    analysis = JDAnalysis(
        title="Backend Engineer",
        seniority="Senior",
        required_skills=["Python"],
        preferred_skills=["AWS"],
        responsibilities=["Build services"],
        experience_min_years=5,
        experience_max_years=7,
        keywords=["backend"],
    )
    fake_analyzer = FakeAnalyzer(analysis)
    job_description = "Build reliable Python backend services."
    app.dependency_overrides[get_jd_analyzer] = lambda: fake_analyzer

    try:
        response = TestClient(app).post(
            "/api/v1/jd/analyze",
            json={"job_description": job_description},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == analysis.model_dump()
    assert fake_analyzer.received_job_description == job_description


def test_jd_analyze_rejects_empty_job_description() -> None:
    fake_analyzer = FakeAnalyzer(
        JDAnalysis(
            title="Backend Engineer",
            seniority=None,
            required_skills=[],
            preferred_skills=[],
            responsibilities=[],
            keywords=[],
        )
    )
    app.dependency_overrides[get_jd_analyzer] = lambda: fake_analyzer

    try:
        response = TestClient(app).post(
            "/api/v1/jd/analyze",
            json={"job_description": ""},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert fake_analyzer.received_job_description is None
