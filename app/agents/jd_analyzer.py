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
    Return ONLY valid JSON matching this exact structure:
    {{
        "title": "string",
        "seniority": "string or null",
        "required_skills": [],
        "preferred_skills": [],
        "responsibilities": [],
        "experience_min_years": null,
        "experience_max_years": null,
        "keywords": []
    }}

    Schema rules:
    - title MUST be a JSON string.
    - seniority MUST be a JSON string or null.
    - required_skills MUST be an array of strings.
    - preferred_skills MUST be an array of strings.
    - responsibilities MUST be an array of strings.
    - keywords MUST be an array of strings.
    - experience_min_years MUST be an integer or null.
    - experience_max_years MUST be an integer or null.
    - Never return null for an array field.
    - If no values exist for an array field, return [].
    - Never return an array where a string is expected.
    - Do not invent information that is not supported by the job description.

    For experience requirements:
    - "3-5 years" -> min=3, max=5.
    - "5+ years" -> min=5, max=null.
    - "2 years" -> min=2, max=2.
    - If no maximum is explicitly stated, max MUST be null.
    - Never invent a maximum experience value.
    - If experience is not specified, both must be null.

    Return ONLY valid JSON.
    Do not use markdown fences.
    Do not include explanatory text outside the JSON.

Job description:
{input_data}
"""
        response = await self._gateway.generate(prompt)
        payload = parse_json_response(response)
        return JDAnalysis.model_validate(payload)
