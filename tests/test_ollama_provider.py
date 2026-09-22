from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.ollama_provider import OllamaProvider


@pytest.fixture
def mock_async_client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[AsyncMock, MagicMock]:
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    response = MagicMock()
    client.post.return_value = response
    monkeypatch.setattr(
        "app.services.ollama_provider.httpx.AsyncClient",
        lambda **_: client,
    )
    return client, response


def test_ollama_provider_name() -> None:
    assert OllamaProvider(model="test-model").name == "ollama"


@pytest.mark.asyncio
async def test_generate_posts_request_and_returns_response(
    mock_async_client: tuple[AsyncMock, MagicMock],
) -> None:
    client, response = mock_async_client
    response.json.return_value = {"response": "test response"}
    provider = OllamaProvider(model="test-model")

    result = await provider.generate("test prompt")

    client.post.assert_awaited_once_with(
        "/api/generate",
        json={
            "model": "test-model",
            "prompt": "test prompt",
            "stream": False,
        },
    )
    assert result == "test response"


@pytest.mark.asyncio
async def test_generate_raises_for_http_error(
    mock_async_client: tuple[AsyncMock, MagicMock],
) -> None:
    _, response = mock_async_client
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server error",
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
        response=httpx.Response(500),
    )
    provider = OllamaProvider(model="test-model")

    with pytest.raises(httpx.HTTPStatusError):
        await provider.generate("test prompt")


@pytest.mark.asyncio
async def test_generate_raises_for_invalid_response(
    mock_async_client: tuple[AsyncMock, MagicMock],
) -> None:
    _, response = mock_async_client
    response.json.return_value = {"unexpected": "value"}
    provider = OllamaProvider(model="test-model")

    with pytest.raises(TypeError):
        await provider.generate("test prompt")
