import pytest

from app.services.model_gateway import ModelGateway, ModelProvider


class FakeModelProvider(ModelProvider):
    def __init__(self) -> None:
        self.last_prompt = ""

    @property
    def name(self) -> str:
        return "fake"

    async def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return "fake response"


def test_fake_provider_name() -> None:
    assert FakeModelProvider().name == "fake"


@pytest.mark.asyncio
async def test_model_gateway_delegates_to_provider() -> None:
    provider = FakeModelProvider()
    gateway = ModelGateway(provider)

    response = await gateway.generate("test prompt")

    assert provider.last_prompt == "test prompt"
    assert response == "fake response"
