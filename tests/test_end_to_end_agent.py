import pytest

from app.agents.base import BaseAgent
from app.services.model_gateway import ModelGateway
from app.services.ollama_provider import OllamaProvider


class SmokeTestAgent(BaseAgent[str, str]):
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    @property
    def name(self) -> str:
        return "smoke-test"

    async def execute(self, input_data: str) -> str:
        return await self._gateway.generate(input_data)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_architecture_with_ollama() -> None:
    provider = OllamaProvider(model="qwen2.5:7b")
    gateway = ModelGateway(provider)
    agent = SmokeTestAgent(gateway)

    response = await agent.execute(
        "Explain what a Java microservice is in exactly two short sentences."
    )

    assert agent.name == "smoke-test"
    assert isinstance(response, str) and response.strip()
    assert any(
        term in response.lower()
        for term in ("java", "microservice", "service", "spring")
    )
