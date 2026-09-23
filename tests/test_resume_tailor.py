import pytest
from pydantic import ValidationError

from app.agents.resume_tailor import ResumeTailorAgent, ResumeTailorInput
from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_tailor import ResumeTailorResult

VALID_RESPONSE = (
    '{"summary":"Backend-focused engineer with Python experience.",'
    '"experience_bullets":["Built Python backend services"],'
    '"projects":["Created a platform monitoring tool"],'
    '"skills_to_highlight":["Python","FastAPI"],'
    '"keywords_to_include":["backend","APIs"]}'
)


class FakeModelGateway:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def create_input() -> ResumeTailorInput:
    return ResumeTailorInput(
        resume=ResumeAnalysis(
            name="Alex Morgan",
            current_role="Software Engineer",
            years_of_experience=6,
            skills=["Python", "FastAPI", "PostgreSQL"],
            experience=[],
            projects=[],
            education=[],
            keywords=["backend", "APIs"],
        ),
        job=JDAnalysis(
            title="Backend Engineer",
            seniority="Senior",
            required_skills=["Python", "FastAPI"],
            preferred_skills=["AWS"],
            responsibilities=["Build backend APIs"],
            experience_min_years=5,
            experience_max_years=None,
            keywords=["backend", "APIs"],
        ),
    )


def create_agent(
    response: str = VALID_RESPONSE,
) -> tuple[ResumeTailorAgent, FakeModelGateway]:
    gateway = FakeModelGateway(response)
    return ResumeTailorAgent(gateway), gateway  # type: ignore[arg-type]


def test_resume_tailor_name() -> None:
    agent, _ = create_agent()

    assert agent.name == "resume-tailor"


@pytest.mark.asyncio
async def test_execute_returns_valid_result() -> None:
    agent, _ = create_agent()

    result = await agent.execute(create_input())

    assert isinstance(result, ResumeTailorResult)
    assert result.summary == "Backend-focused engineer with Python experience."
    assert result.experience_bullets == ["Built Python backend services"]
    assert result.skills_to_highlight == ["Python", "FastAPI"]


@pytest.mark.asyncio
async def test_execute_removes_unsupported_skills_and_keywords() -> None:
    response = (
        '{"summary":"Backend-focused engineer.",'
        '"experience_bullets":[],"projects":[],'
        '"skills_to_highlight":["Python","Java"],'
        '"keywords_to_include":["backend","microservices"]}'
    )
    agent, _ = create_agent(response)

    result = await agent.execute(create_input())

    assert result.skills_to_highlight == ["Python"]
    assert result.keywords_to_include == ["backend"]


@pytest.mark.asyncio
async def test_execute_rejects_invalid_json() -> None:
    agent, _ = create_agent("not valid JSON")

    with pytest.raises(ValueError, match="Model returned invalid JSON"):
        await agent.execute(create_input())


@pytest.mark.asyncio
async def test_execute_rejects_invalid_schema() -> None:
    agent, _ = create_agent('{"summary":"Tailored summary"}')

    with pytest.raises(ValidationError):
        await agent.execute(create_input())


@pytest.mark.asyncio
async def test_execute_sends_resume_and_job_analysis_to_gateway() -> None:
    agent, gateway = create_agent()
    input_data = create_input()

    await agent.execute(input_data)

    assert len(gateway.prompts) == 1
    prompt = gateway.prompts[0]
    assert input_data.resume.name in prompt
    assert input_data.resume.skills[0] in prompt
    assert input_data.job.title in prompt
    assert input_data.job.required_skills[0] in prompt


@pytest.mark.asyncio
async def test_execute_rejects_null_list_field() -> None:
    response = (
        '{"summary":"Tailored summary",'
        '"experience_bullets":null,"projects":[],'
        '"skills_to_highlight":[],"keywords_to_include":[]}'
    )
    agent, _ = create_agent(response)

    with pytest.raises(ValidationError):
        await agent.execute(create_input())
