from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.job_matcher import JobMatcherAgent
from app.models.jd_analysis import JDAnalysis
from app.models.job_match import JobMatchResult
from app.models.job_match_request import JobMatchRequest
from app.models.resume_analysis import ResumeAnalysis
from app.services.job_matcher import JobMatcherService
from app.services.model_gateway import ModelGateway


def create_request() -> JobMatchRequest:
    return JobMatchRequest(
        job=JDAnalysis(
            title="Backend Engineer",
            seniority="senior",
            required_skills=["Java", "Spring Boot"],
            preferred_skills=["AWS"],
            responsibilities=["Build services"],
            experience_min_years=5,
            experience_max_years=8,
            keywords=["backend"],
        ),
        resume=ResumeAnalysis(
            name="Alex Morgan",
            current_role="senior",
            years_of_experience=6,
            skills=["Java", "Spring Boot", "AWS"],
            experience=[],
            projects=[],
            education=[],
            keywords=["backend"],
        ),
    )


def create_result() -> JobMatchResult:
    return JobMatchResult(
        match_percentage=92.5,
        matched_required_skills=["Java", "Spring Boot"],
        missing_required_skills=[],
        matched_preferred_skills=["AWS"],
        missing_preferred_skills=[],
        experience_match=True,
        seniority_match=True,
        explanation="Deterministic explanation.",
    )


def create_agent(
    result: JobMatchResult,
    explanation: str = "Strong backend fit.",
) -> tuple[JobMatcherAgent, Mock, Mock]:
    matcher = Mock(spec=JobMatcherService)
    matcher.match.return_value = result
    gateway = Mock(spec=ModelGateway)
    gateway.generate = AsyncMock(return_value=explanation)
    return JobMatcherAgent(gateway, matcher), matcher, gateway


def test_job_matcher_name() -> None:
    agent, _, _ = create_agent(create_result())

    assert agent.name == "job-matcher"


@pytest.mark.asyncio
async def test_execute_delegates_exact_job_and_resume_objects() -> None:
    request = create_request()
    agent, matcher, _ = create_agent(create_result())

    await agent.execute(request)

    matcher.match.assert_called_once_with(request.job, request.resume)


@pytest.mark.asyncio
async def test_execute_calls_gateway_once_after_deterministic_match() -> None:
    agent, matcher, gateway = create_agent(create_result())

    await agent.execute(create_request())

    matcher.match.assert_called_once()
    gateway.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_preserves_deterministic_fields() -> None:
    deterministic = create_result()
    agent, _, _ = create_agent(deterministic, "Model explanation.")

    result = await agent.execute(create_request())

    assert result.match_percentage == deterministic.match_percentage
    assert result.matched_required_skills == deterministic.matched_required_skills
    assert result.missing_required_skills == deterministic.missing_required_skills
    assert result.matched_preferred_skills == deterministic.matched_preferred_skills
    assert result.missing_preferred_skills == deterministic.missing_preferred_skills
    assert result.experience_match is deterministic.experience_match
    assert result.seniority_match is deterministic.seniority_match
    assert result.explanation == "Model explanation."


@pytest.mark.asyncio
async def test_execute_prompt_contains_result_and_prohibits_recalculation() -> None:
    deterministic = create_result()
    agent, _, gateway = create_agent(deterministic)

    await agent.execute(create_request())

    prompt = gateway.generate.await_args.args[0]
    normalized_prompt = " ".join(prompt.lower().split())
    assert "match_percentage" in prompt
    assert str(deterministic.match_percentage) in prompt
    assert "do not calculate or change any match fields" in normalized_prompt
    assert "do not reassess matched skills" in normalized_prompt


@pytest.mark.asyncio
async def test_execute_rejects_empty_model_explanation() -> None:
    agent, _, gateway = create_agent(create_result(), " \n\t ")

    with pytest.raises(ValueError, match="Model returned an empty explanation"):
        await agent.execute(create_request())

    gateway.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_does_not_call_gateway_when_matching_fails() -> None:
    matcher = Mock(spec=JobMatcherService)
    matcher.match.side_effect = RuntimeError("matching failed")
    gateway = Mock(spec=ModelGateway)
    gateway.generate = AsyncMock()
    agent = JobMatcherAgent(gateway, matcher)

    with pytest.raises(RuntimeError, match="matching failed"):
        await agent.execute(create_request())

    gateway.generate.assert_not_awaited()
