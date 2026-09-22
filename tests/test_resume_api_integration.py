import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.mark.integration
def test_resume_analyze_api_with_local_ollama() -> None:
    """Integration test requiring local Ollama with the qwen2.5:7b model."""
    resume = """
    Gaurav Kumar Dev
    Software Development Engineer
    InPrime Finserv
    Experience with Java, Spring Boot, Microservices, PostgreSQL, AWS.
    Built backend APIs and distributed services.
    Bachelor of Technology from VIT, graduated in 2025.
    """

    response = TestClient(app).post(
        "/api/v1/resume/analyze",
        json={"resume": resume},
    )

    assert response.status_code == 200
    payload = response.json()
    expected_fields = {
        "name",
        "skills",
        "experience",
        "projects",
        "education",
        "keywords",
    }
    assert expected_fields <= payload.keys()
    assert isinstance(payload["skills"], list)
    assert isinstance(payload["experience"], list)
    assert isinstance(payload["projects"], list)
    assert isinstance(payload["education"], list)
    assert isinstance(payload["keywords"], list)
