import pytest
from pydantic import ValidationError

from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.models.resume_analysis import ResumeAnalysis

VALID_RESPONSE = (
    '{"name":"Alex Morgan","current_role":"Software Engineer",'
    '"years_of_experience":6.5,"skills":["Python","AWS"],'
    '"experience":[{"company":"Acme Corp","role":"Software Engineer",'
    '"highlights":["Built backend services"]}],'
    '"projects":[{"name":"Resume Parser",'
    '"description":"A resume parsing tool",'
    '"technologies":["Python"]}],'
    '"education":[{"institution":"State University",'
    '"degree":"BSc Computer Science","graduation_year":2020}],'
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
) -> tuple[ResumeAnalyzerAgent, FakeModelGateway]:
    gateway = FakeModelGateway(response)
    return ResumeAnalyzerAgent(gateway), gateway  # type: ignore[arg-type]


def test_resume_analyzer_name() -> None:
    agent, _ = create_agent()

    assert agent.name == "resume-analyzer"


@pytest.mark.asyncio
async def test_execute_returns_valid_resume_analysis() -> None:
    agent, _ = create_agent()

    result = await agent.execute(
        "Alex Morgan\nSoftware Engineer\nPython and AWS experience."
    )

    assert isinstance(result, ResumeAnalysis)
    assert result.name == "Alex Morgan"
    assert result.skills == ["Python", "AWS"]


@pytest.mark.asyncio
async def test_execute_rejects_empty_resume() -> None:
    agent, gateway = create_agent()

    with pytest.raises(ValueError, match="Resume cannot be empty"):
        await agent.execute("")

    assert gateway.prompts == []


@pytest.mark.asyncio
async def test_execute_rejects_whitespace_resume() -> None:
    agent, gateway = create_agent()

    with pytest.raises(ValueError, match="Resume cannot be empty"):
        await agent.execute(" \n\t ")

    assert gateway.prompts == []


@pytest.mark.asyncio
async def test_execute_rejects_invalid_json() -> None:
    agent, _ = create_agent("not valid JSON")

    with pytest.raises(ValueError, match="Model returned invalid JSON"):
        await agent.execute("Alex Morgan")


@pytest.mark.asyncio
async def test_execute_rejects_invalid_resume_schema() -> None:
    agent, _ = create_agent('{"name":"Alex Morgan"}')

    with pytest.raises(ValidationError):
        await agent.execute("Alex Morgan")


@pytest.mark.asyncio
async def test_execute_sends_resume_text_to_gateway() -> None:
    agent, gateway = create_agent()
    resume_text = "Known resume for a Python platform engineer."

    await agent.execute(resume_text)

    assert len(gateway.prompts) == 1
    assert resume_text in gateway.prompts[0]
