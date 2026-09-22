from app.agents.jd_analyzer import JDAnalyzerAgent
from app.core.config import get_settings
from app.services.model_gateway import ModelGateway
from app.services.ollama_provider import OllamaProvider


def get_jd_analyzer() -> JDAnalyzerAgent:
    """Create the job-description analyzer dependency."""
    settings = get_settings()
    model = settings.model_name or "qwen2.5:7b"
    provider = OllamaProvider(model=model)
    gateway = ModelGateway(provider)
    return JDAnalyzerAgent(gateway)
