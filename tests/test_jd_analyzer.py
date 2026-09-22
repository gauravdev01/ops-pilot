import pytest
from pydantic import ValidationError

from app.agents.jd_analyzer import JDAnalyzerAgent
from app.models.jd_analysis import JDAnalysis

VALID_RESPONSE = (
    '{"title":"Backend Engineer","seniority":"Senior",'
    '"required_skills":["Python","SQL"],"preferred_skills":["AWS"],'
    '"responsibilities":["Build APIs"],"experience_min_years":5,'
    '"experience_max_years":7,'
    '"keywords":["backend","cloud"]}'
)


class FakeModelGateway:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def create_agent(
    response: str = VALID_RESPONSE,
) -> tuple[JDAnalyzerAgent, FakeModelGateway]:
    gateway = FakeModelGateway(response)
    return JDAnalyzerAgent(gateway), gateway  # type: ignore[arg-type]


def test_jd_analyzer_name() -> None:
    agent, _ = create_agent()

    assert agent.name == "jd-analyzer"


@pytest.mark.asyncio
async def test_execute_returns_valid_jd_analysis() -> None:
    agent, _ = create_agent()

    result = await agent.execute(
        "Build and maintain Python backend services with SQL databases."
    )

    assert isinstance(result, JDAnalysis)
    assert result.title == "Backend Engineer"
    assert result.required_skills == ["Python", "SQL"]


@pytest.mark.asyncio
async def test_execute_rejects_empty_job_description() -> None:
    agent, gateway = create_agent()

    with pytest.raises(ValueError):
        await agent.execute("")

    assert gateway.prompts == []


@pytest.mark.asyncio
async def test_execute_rejects_whitespace_job_description() -> None:
    agent, gateway = create_agent()

    with pytest.raises(ValueError):
        await agent.execute(" \n\t ")

    assert gateway.prompts == []


@pytest.mark.asyncio
async def test_execute_rejects_invalid_json() -> None:
    agent, _ = create_agent("not valid JSON")

    with pytest.raises(ValueError, match="Model returned invalid JSON"):
        await agent.execute("Analyze this job description")


@pytest.mark.asyncio
async def test_execute_rejects_invalid_jd_schema() -> None:
    agent, _ = create_agent('{"title":"Backend Engineer"}')

    with pytest.raises(ValidationError):
        await agent.execute("Analyze this job description")


@pytest.mark.asyncio
async def test_execute_sends_job_description_to_gateway() -> None:
    agent, gateway = create_agent()
    job_description = "Known job description for a Python platform engineer."

    await agent.execute(job_description)

    assert len(gateway.prompts) == 1
    assert job_description in gateway.prompts[0]
