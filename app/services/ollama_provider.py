import httpx

from app.services.model_gateway import ModelProvider


class OllamaProvider(ModelProvider):
    """Generate responses through an Ollama server."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._timeout = timeout

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "ollama"

    async def generate(self, prompt: str) -> str:
        """Generate a response for the supplied prompt."""
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        ) as client:
            response = await client.post(
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            payload = response.json()

        generated = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(generated, str):
            raise TypeError("Ollama response is missing a string 'response' field")
        return generated
