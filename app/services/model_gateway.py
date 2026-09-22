from abc import ABC, abstractmethod


class ModelProvider(ABC):
    """Define the provider contract used by the model gateway."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider's name."""
        raise NotImplementedError

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate text for a prompt."""
        raise NotImplementedError


class ModelGateway:
    """Delegate model generation to an injected provider."""

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    async def generate(self, prompt: str) -> str:
        """Generate text through the configured provider."""
        return await self._provider.generate(prompt)
