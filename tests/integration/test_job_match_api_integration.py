import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.mark.integration
def test_job_match_api_with_local_ollama() -> None:
    """Integration test requiring local Ollama with the qwen2.5:7b model."""
    payload = {
        "job": {
            "title": "Backend Engineer",
            "seniority": "senior",
            "required_skills": ["Java", "Spring Boot", "PostgreSQL"],
            "preferred_skills": ["AWS", "Docker"],
            "responsibilities": [
                "Build backend services",
                "Design reliable APIs",
            ],
            "experience_min_years": 5,
            "experience_max_years": 8,
            "keywords": ["backend", "microservices"],
        },
        "resume": {
            "name": "Alex Morgan",
            "current_role": "senior",
            "years_of_experience": 6,
            "skills": ["Java", "Spring Boot", "PostgreSQL", "AWS", "Docker"],
            "experience": [
                {
                    "company": "Acme Cloud",
                    "role": "Senior Backend Engineer",
                    "highlights": ["Built Java services"],
                }
            ],
            "projects": [
                {
                    "name": "Payments Platform",
                    "description": "Distributed payment services",
                    "technologies": ["Java", "Spring Boot"],
                }
            ],
            "education": [
                {
                    "institution": "State University",
                    "degree": "BSc Computer Science",
                    "graduation_year": 2020,
                }
            ],
            "keywords": ["backend", "microservices"],
        },
    }

    response = TestClient(app).post("/api/v1/job-match/match", json=payload)

    assert response.status_code == 200
    result = response.json()
    expected_fields = {
        "match_percentage",
        "matched_required_skills",
        "missing_required_skills",
        "matched_preferred_skills",
        "missing_preferred_skills",
        "experience_match",
        "seniority_match",
        "explanation",
    }
    assert expected_fields <= result.keys()
    assert 0 <= result["match_percentage"] <= 100
    assert isinstance(result["matched_required_skills"], list)
    assert isinstance(result["missing_required_skills"], list)
    assert isinstance(result["matched_preferred_skills"], list)
    assert isinstance(result["missing_preferred_skills"], list)
    assert result["experience_match"] in {True, False, None}
    assert result["seniority_match"] in {True, False, None}
    assert isinstance(result["explanation"], str)
    assert result["explanation"].strip()
    assert result["missing_required_skills"] == []
    assert result["missing_preferred_skills"] == []
    assert result["experience_match"] is True
    assert result["seniority_match"] is True
