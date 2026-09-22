import pytest

from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.models.resume_analysis import ResumeAnalysis
from app.services.model_gateway import ModelGateway
from app.services.ollama_provider import OllamaProvider


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resume_analyzer_with_local_ollama() -> None:
    """Integration test requiring Ollama and qwen2.5:7b to run locally."""
    resume_text = """
    Alex Morgan
    Senior Software Engineer

    Software engineer with seven years of experience building backend platforms
    and distributed services. Currently working as a Senior Software Engineer
    at Acme Cloud, designing production systems and mentoring engineers.

    Work Experience
    Acme Cloud, Senior Software Engineer, 2020-present
    - Built Java and Spring Boot microservices for customer-facing products.
    - Developed Python automation and internal platform tools.
    - Designed PostgreSQL schemas and REST APIs.
    - Containerized services with Docker and deployed them to AWS.

    Bright Systems, Software Engineer, 2017-2020
    - Implemented backend services, automated tests, and production monitoring.
    - Collaborated with product and frontend teams on API-driven features.

    Projects
    Event Processing Platform: Built a Java and Spring Boot event-processing
    service using PostgreSQL, Docker, and AWS.

    Education
    Bachelor of Science in Computer Science, State University, 2017.
    """
    provider = OllamaProvider(model="qwen2.5:7b")
    gateway = ModelGateway(provider)
    agent = ResumeAnalyzerAgent(gateway)

    result = await agent.execute(resume_text)

    assert isinstance(result, ResumeAnalysis)
    assert isinstance(result.name, str)
    assert result.name.strip()
    assert isinstance(result.skills, list)
    assert isinstance(result.experience, list)
    assert isinstance(result.projects, list)
    assert isinstance(result.education, list)
    assert isinstance(result.keywords, list)
