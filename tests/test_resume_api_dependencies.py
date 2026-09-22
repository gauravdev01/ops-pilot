from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.api.dependencies import get_resume_analyzer


def test_get_resume_analyzer_uses_configured_local_model() -> None:
    settings = SimpleNamespace(model_provider="local", model_name="test-model")

    with (
        patch("app.api.dependencies.get_settings", return_value=settings),
        patch("app.api.dependencies.OllamaProvider") as provider_class,
        patch("app.api.dependencies.ModelGateway") as gateway_class,
    ):
        analyzer = get_resume_analyzer()

    assert isinstance(analyzer, ResumeAnalyzerAgent)
    provider_class.assert_called_once_with(model="test-model")
    gateway_class.assert_called_once_with(provider_class.return_value)


def test_get_resume_analyzer_rejects_missing_local_model() -> None:
    settings = SimpleNamespace(model_provider="local", model_name="")

    with (
        patch("app.api.dependencies.get_settings", return_value=settings),
        pytest.raises(
            ValueError,
            match="MODEL_NAME must be configured for the local provider",
        ),
    ):
        get_resume_analyzer()


def test_get_resume_analyzer_rejects_unsupported_provider() -> None:
    settings = SimpleNamespace(model_provider="remote", model_name="test-model")

    with (
        patch("app.api.dependencies.get_settings", return_value=settings),
        pytest.raises(ValueError, match="Unsupported model provider: remote"),
    ):
        get_resume_analyzer()
