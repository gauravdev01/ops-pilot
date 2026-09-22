from app.agents.base import BaseAgent
from app.core.json_utils import parse_json_response
from app.models.resume_analysis import ResumeAnalysis
from app.services.model_gateway import ModelGateway


class ResumeAnalyzerAgent(BaseAgent[str, ResumeAnalysis]):
    """Analyze resume text into structured data."""

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "resume-analyzer"

    async def execute(self, input_data: str) -> ResumeAnalysis:
        """Analyze resume text and return validated structured data."""
        if not input_data.strip():
            raise ValueError("Resume cannot be empty")

        prompt = f"""Analyze the following resume.
Return ONLY valid JSON matching this exact ResumeAnalysis structure:
{{
    "name": "string",
    "current_role": "string or null",
    "years_of_experience": 0,
    "skills": [],
    "experience": [
        {{
            "company": "string",
            "role": "string",
            "highlights": []
        }}
    ],
    "projects": [
        {{
            "name": "string",
            "description": "string or null",
            "technologies": []
        }}
    ],
    "education": [
        {{
            "institution": "string",
            "degree": "string or null",
            "graduation_year": 0
        }}
    ],
    "keywords": []
}}

Rules:
- experience MUST be a JSON array.
- Every experience item MUST contain company, role, and highlights.
- highlights MUST be an array of strings.
- projects MUST be a JSON array.
- Every project MUST contain name, description, and technologies.
- technologies MUST be an array of strings.
- education MUST be a JSON array, even if there is only one education entry.
- Every education item MUST contain institution, degree, and graduation_year.
- Use the exact field name graduation_year, never year.
- Use null for optional scalar values when information is missing.
- Use [] for missing list values.
- Do not omit required fields.
- Do not invent information not supported by the resume text.

Resume:
{input_data}
"""
        response = await self._gateway.generate(prompt)
        payload = parse_json_response(response)
        return ResumeAnalysis.model_validate(payload)
