from fastapi.testclient import TestClient

from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.api.dependencies import get_resume_analyzer
from app.api.main import app
from app.models.resume_analysis import ResumeAnalysis


class FakeResumeAnalyzer(ResumeAnalyzerAgent):
    def __init__(self, result: ResumeAnalysis) -> None:
        self.result = result
        self.received_resume: str | None = None

    @property
    def name(self) -> str:
        return "fake-resume-analyzer"

    async def execute(self, input_data: str) -> ResumeAnalysis:
        self.received_resume = input_data
        return self.result


def create_analysis() -> ResumeAnalysis:
    return ResumeAnalysis(
        name="John Doe",
        current_role="Software Engineer",
        years_of_experience=None,
        skills=["Python", "Java", "Spring Boot"],
        experience=[],
        projects=[],
        education=[],
        keywords=["Python", "Java"],
    )


def test_resume_analyze_returns_expected_response() -> None:
    fake_analyzer = FakeResumeAnalyzer(create_analysis())
    app.dependency_overrides[get_resume_analyzer] = lambda: fake_analyzer

    try:
        response = TestClient(app).post(
            "/api/v1/resume/analyze",
            json={"resume": "John Doe\nSoftware Engineer\nPython, Java, Spring Boot"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == create_analysis().model_dump()


def test_resume_analyze_passes_submitted_resume_to_analyzer() -> None:
    fake_analyzer = FakeResumeAnalyzer(create_analysis())
    resume = "John Doe\nSoftware Engineer\nPython, Java, Spring Boot"
    app.dependency_overrides[get_resume_analyzer] = lambda: fake_analyzer

    try:
        response = TestClient(app).post(
            "/api/v1/resume/analyze",
            json={"resume": resume},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_analyzer.received_resume == resume
