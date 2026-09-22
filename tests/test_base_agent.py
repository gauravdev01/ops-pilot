import inspect

import pytest

from app.agents.base import BaseAgent


class TestAgent(BaseAgent[str, str]):
    @property
    def name(self) -> str:
        return "test-agent"

    async def execute(self, input_data: str) -> str:
        return f"processed: {input_data}"


def test_base_agent_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        BaseAgent()


def test_test_agent_name() -> None:
    assert TestAgent().name == "test-agent"


@pytest.mark.asyncio
async def test_test_agent_execute() -> None:
    agent = TestAgent()

    assert inspect.iscoroutinefunction(agent.execute)
    assert await agent.execute("job search") == "processed: job search"
