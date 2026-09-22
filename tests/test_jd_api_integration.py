import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.mark.integration
def test_jd_analyze_api_with_local_ollama() -> None:
    """Integration test requiring local Ollama with the qwen2.5:7b model."""
    job_description = """
    We are hiring a Software Engineer for our backend platform team. The role
    involves designing and maintaining reliable services for customer-facing
    products and collaborating with product and frontend engineers.

    Required experience includes Python, FastAPI, PostgreSQL, REST APIs,
    Docker, and AWS. Responsibilities include implementing maintainable code,
    designing database schemas, improving observability, reviewing pull
    requests, troubleshooting production issues, and writing automated tests.
    Experience with Kubernetes, Redis, and event-driven systems is preferred.
    """

    response = TestClient(app).post(
        "/api/v1/jd/analyze",
        json={"job_description": job_description},
    )

    assert response.status_code == 200
    payload = response.json()
    expected_fields = {
        "title",
        "seniority",
        "required_skills",
        "preferred_skills",
        "responsibilities",
        "experience_min_years",
        "experience_max_years",
        "keywords",
    }
    assert expected_fields <= payload.keys()
    assert isinstance(payload["title"], str)
    assert payload["title"].strip()
    assert isinstance(payload["required_skills"], list)
    assert isinstance(payload["responsibilities"], list)
    assert isinstance(payload["keywords"], list)
