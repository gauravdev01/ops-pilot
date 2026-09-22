from app.agents.base import BaseAgent
from app.models.job_match import JobMatchResult
from app.models.job_match_request import JobMatchRequest
from app.services.job_matcher import JobMatcherService
from app.services.model_gateway import ModelGateway


class JobMatcherAgent(BaseAgent[JobMatchRequest, JobMatchResult]):
    """Match a job and resume, then generate a human-readable explanation."""

    def __init__(
        self,
        gateway: ModelGateway,
        matcher: JobMatcherService,
    ) -> None:
        self._gateway = gateway
        self._matcher = matcher

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "job-matcher"

    async def execute(self, input_data: JobMatchRequest) -> JobMatchResult:
        """Return deterministic match fields with a generated explanation."""
        deterministic_result = self._matcher.match(input_data.job, input_data.resume)
        prompt = f"""Write a concise human-readable explanation for this job match.
Use the deterministic result below as the source of truth. Explain the skill
coverage clearly, but do not calculate or change any match fields. Do not
reassess matched skills, missing skills, experience_match, seniority_match, or
match_percentage. Return only the explanation as plain text.

Deterministic result:
{deterministic_result.model_dump()}
"""
        explanation = await self._gateway.generate(prompt)
        if not explanation.strip():
            raise ValueError("Model returned an empty explanation")

        return deterministic_result.model_copy(
            update={"explanation": explanation.strip()}
        )
