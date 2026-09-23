from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.agents.resume_tailor import ResumeTailorAgent, ResumeTailorInput
from app.api.dependencies import get_resume_tailor
from app.api.main import app
from app.models.resume_tailor import ResumeTailorResult


class FakeResumeTailorAgent(ResumeTailorAgent):
    def __init__(self, result: ResumeTailorResult) -> None:
        self.result = result
        self.received_input: ResumeTailorInput | None = None

    @property
    def name(self) -> str:
        return "fake-resume-tailor"

    async def execute(self, input_data: ResumeTailorInput) -> ResumeTailorResult:
        self.received_input = input_data
        return self.result


@pytest.fixture
def client() -> Iterator[TestClient]:
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def valid_payload() -> dict[str, object]:
    return {
        "job": {
            "title": "Backend Engineer",
            "seniority": "Senior",
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["AWS"],
            "responsibilities": ["Build backend services"],
            "experience_min_years": 5,
            "experience_max_years": None,
            "keywords": ["backend", "APIs"],
        },
        "resume": {
            "name": "Alex Morgan",
            "current_role": "Software Engineer",
            "years_of_experience": 6,
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "experience": [],
            "projects": [],
            "education": [],
            "keywords": ["backend", "APIs"],
        },
    }


def create_agent() -> tuple[FakeResumeTailorAgent, ResumeTailorResult]:
    result = ResumeTailorResult(
        summary="Backend-focused engineer with Python experience.",
        experience_bullets=["Built Python backend services"],
        projects=["Created a platform monitoring tool"],
        skills_to_highlight=["Python", "FastAPI"],
        keywords_to_include=["backend", "APIs"],
    )
    return FakeResumeTailorAgent(result), result


def test_resume_tailor_returns_expected_result(client: TestClient) -> None:
    agent, result = create_agent()
    app.dependency_overrides[get_resume_tailor] = lambda: agent

    response = client.post(
        "/api/v1/resume-tailor/tailor",
        json=valid_payload(),
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data == result.model_dump()
    assert set(response_data) == {
        "summary",
        "experience_bullets",
        "projects",
        "skills_to_highlight",
        "keywords_to_include",
    }


def test_resume_tailor_passes_typed_request_to_agent(
    client: TestClient,
) -> None:
    agent, _ = create_agent()
    app.dependency_overrides[get_resume_tailor] = lambda: agent
    payload = valid_payload()

    response = client.post("/api/v1/resume-tailor/tailor", json=payload)

    assert response.status_code == 200
    assert isinstance(agent.received_input, ResumeTailorInput)
    assert agent.received_input.resume.name == payload["resume"]["name"]
    assert agent.received_input.job.title == payload["job"]["title"]


def test_resume_tailor_rejects_missing_resume(
    client: TestClient,
) -> None:
    agent, _ = create_agent()
    app.dependency_overrides[get_resume_tailor] = lambda: agent
    payload = valid_payload()
    del payload["resume"]

    response = client.post("/api/v1/resume-tailor/tailor", json=payload)

    assert response.status_code == 422
    assert agent.received_input is None


def test_resume_tailor_rejects_missing_job(
    client: TestClient,
) -> None:
    agent, _ = create_agent()
    app.dependency_overrides[get_resume_tailor] = lambda: agent
    payload = valid_payload()
    del payload["job"]

    response = client.post("/api/v1/resume-tailor/tailor", json=payload)

    assert response.status_code == 422
    assert agent.received_input is None
