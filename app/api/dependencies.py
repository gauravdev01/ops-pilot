from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.job_matcher import JobMatcherAgent
from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.agents.resume_tailor import ResumeTailorAgent
from app.core.config import get_settings
from app.services.job_matcher import JobMatcherService
from app.services.model_gateway import ModelGateway
from app.services.ollama_provider import OllamaProvider


def get_jd_analyzer() -> JDAnalyzerAgent:
    """Create the job-description analyzer dependency."""
    settings = get_settings()
    if settings.model_provider == "local":
        if not settings.model_name:
            raise ValueError("MODEL_NAME must be configured for the local provider")
        provider = OllamaProvider(model=settings.model_name)
    else:
        raise ValueError(f"Unsupported model provider: {settings.model_provider}")

    gateway = ModelGateway(provider)
    return JDAnalyzerAgent(gateway)


def get_resume_analyzer() -> ResumeAnalyzerAgent:
    """Create the resume analyzer dependency."""
    settings = get_settings()
    if settings.model_provider == "local":
        if not settings.model_name:
            raise ValueError("MODEL_NAME must be configured for the local provider")
        provider = OllamaProvider(model=settings.model_name)
    else:
        raise ValueError(f"Unsupported model provider: {settings.model_provider}")

    gateway = ModelGateway(provider)
    return ResumeAnalyzerAgent(gateway)


def get_resume_tailor() -> ResumeTailorAgent:
    """Create the resume tailor dependency."""
    settings = get_settings()
    if settings.model_provider == "local":
        if not settings.model_name:
            raise ValueError("MODEL_NAME must be configured for the local provider")
        provider = OllamaProvider(model=settings.model_name)
    else:
        raise ValueError(f"Unsupported model provider: {settings.model_provider}")

    gateway = ModelGateway(provider)
    return ResumeTailorAgent(gateway)


def get_job_matcher() -> JobMatcherAgent:
    """Create the job matcher dependency."""
    settings = get_settings()
    if settings.model_provider == "local":
        if not settings.model_name:
            raise ValueError("MODEL_NAME must be configured for the local provider")
        provider = OllamaProvider(model=settings.model_name)
    else:
        raise ValueError(f"Unsupported model provider: {settings.model_provider}")

    gateway = ModelGateway(provider)
    matcher = JobMatcherService()
    return JobMatcherAgent(gateway, matcher)
