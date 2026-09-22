from app.agents.base import BaseAgent
from app.core.json_utils import parse_json_response
from app.models.jd_analysis import JDAnalysis
from app.services.model_gateway import ModelGateway


class JDAnalyzerAgent(BaseAgent[str, JDAnalysis]):
    """Analyze a job description into structured data."""

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "jd-analyzer"

    async def execute(self, input_data: str) -> JDAnalysis:
        """Analyze a job description and return validated structured data."""
        if not input_data.strip():
            raise ValueError("Job description cannot be empty")

        prompt = f"""Analyze the following software engineering job description.
Return ONLY valid JSON matching this exact structure, with these fields:
- title
- seniority
- required_skills
- preferred_skills
- responsibilities
- experience_min_years
- experience_max_years
- keywords

For experience requirements:
- For a range such as "3-5 years", return 3 and 5.
- For "5+ years", return 5 and null.
- For a single requirement such as "2 years", return 2 and 2.
- If experience is not specified, return null for both.

Job description:
{input_data}
"""
        response = await self._gateway.generate(prompt)
        payload = parse_json_response(response)
        return JDAnalysis.model_validate(payload)
