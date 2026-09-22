import pytest

from app.agents.jd_analyzer import JDAnalyzerAgent
from app.models.jd_analysis import JDAnalysis
from app.services.model_gateway import ModelGateway
from app.services.ollama_provider import OllamaProvider


@pytest.mark.integration
@pytest.mark.asyncio
async def test_jd_analyzer_with_local_ollama() -> None:
    """Integration test requiring Ollama and qwen2.5:7b to run locally."""
    job_description = """
    We are looking for a Software Development Engineer to join our backend
    platform team. You will design, build, and maintain scalable services for
    our customer-facing products, collaborating with product managers and
    frontend engineers to deliver reliable features.

    The ideal candidate has professional experience with Python, FastAPI,
    PostgreSQL, REST APIs, Docker, and AWS. Responsibilities include writing
    maintainable code, designing database schemas, improving service
    observability, reviewing pull requests, troubleshooting production issues,
    and contributing to automated testing and continuous delivery. Experience
    with Kubernetes, Redis, and event-driven systems is a plus.
    """
    provider = OllamaProvider(model="qwen2.5:7b")
    gateway = ModelGateway(provider)
    agent = JDAnalyzerAgent(gateway)

    result = await agent.execute(job_description)

    assert isinstance(result, JDAnalysis)
    assert result.title.strip()
    assert result.seniority is None or result.seniority.strip()
    assert isinstance(result.required_skills, list)
    assert isinstance(result.responsibilities, list)
    assert isinstance(result.keywords, list)
    assert result.required_skills or result.keywords
