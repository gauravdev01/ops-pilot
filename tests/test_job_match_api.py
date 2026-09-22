from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.agents.job_matcher import JobMatcherAgent
from app.api.dependencies import get_job_matcher
from app.api.main import app
from app.models.job_match import JobMatchResult
from app.models.job_match_request import JobMatchRequest


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
            "required_skills": ["Java", "Spring Boot"],
            "preferred_skills": ["AWS"],
            "responsibilities": ["Build backend services"],
            "experience_min_years": 5,
            "experience_max_years": 8,
            "keywords": ["backend", "microservices"],
        },
        "resume": {
            "name": "Alex Morgan",
            "current_role": "Senior",
            "years_of_experience": 6,
            "skills": ["Java", "Spring Boot", "AWS"],
            "experience": [],
            "projects": [],
            "education": [],
            "keywords": ["backend", "cloud"],
        },
    }


def create_agent() -> tuple[Mock, JobMatchResult]:
    result = JobMatchResult(
        match_percentage=92.5,
        matched_required_skills=["Java", "Spring Boot"],
        missing_required_skills=[],
        matched_preferred_skills=["AWS"],
        missing_preferred_skills=[],
        experience_match=True,
        seniority_match=True,
        explanation="Strong backend fit.",
    )
    agent = Mock(spec=JobMatcherAgent)
    agent.execute = AsyncMock(return_value=result)
    return agent, result


def test_job_match_returns_expected_result(
    client: TestClient,
) -> None:
    agent, result = create_agent()
    app.dependency_overrides[get_job_matcher] = lambda: agent
    payload = valid_payload()

    response = client.post("/api/v1/job-match/match", json=payload)

    assert response.status_code == 200
    assert response.json() == result.model_dump()
    agent.execute.assert_awaited_once()

    request = agent.execute.await_args.args[0]
    assert isinstance(request, JobMatchRequest)
    assert request.job.title == payload["job"]["title"]
    assert request.resume.name == payload["resume"]["name"]


def test_job_match_rejects_invalid_job_payload(
    client: TestClient,
) -> None:
    agent, _ = create_agent()
    app.dependency_overrides[get_job_matcher] = lambda: agent
    payload = valid_payload()
    payload["job"]["title"] = ""

    response = client.post("/api/v1/job-match/match", json=payload)

    assert response.status_code == 422
    agent.execute.assert_not_awaited()
