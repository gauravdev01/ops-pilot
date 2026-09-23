from pydantic import BaseModel

from app.agents.base import BaseAgent
from app.core.json_utils import parse_json_response
from app.models.jd_analysis import JDAnalysis
from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_tailor import ResumeTailorResult
from app.services.model_gateway import ModelGateway
from app.services.resume_tailor import ResumeTailorService


class ResumeTailorInput(BaseModel):
    """Input containing a resume analysis and job analysis."""

    job: JDAnalysis
    resume: ResumeAnalysis


class ResumeTailorAgent(BaseAgent[ResumeTailorInput, ResumeTailorResult]):
    """Tailor resume content to a job description without inventing facts."""

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        self._service = ResumeTailorService()

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "resume-tailor"

    async def execute(self, input_data: ResumeTailorInput) -> ResumeTailorResult:
        """Generate validated resume tailoring suggestions."""

        prompt = f"""Tailor the candidate's resume to the job analysis below.
The resume is the ONLY source of truth for candidate experience, projects,
technologies, achievements, and skills.

Anti-hallucination rules:
- Never invent a technology, responsibility, achievement, company, project, metric, or experience.
- Never claim the candidate has experience with a job skill unless that skill is supported by the resume.
- Use the job analysis only to determine relevance, wording, and which existing skills and experience should be emphasized.
- Do not add missing job skills to skills_to_highlight unless they already exist in the resume.
- Do not fabricate experience bullets.
- Preserve factual meaning from the resume.
- Improve wording for relevance and clarity, but do not change facts.
- keywords_to_include may contain job keywords that are supported by the resume.
- If a job keyword is not supported by the resume, do not include it.
- If there is insufficient relevant information, return an empty list rather than inventing content.

Return ONLY valid JSON matching exactly this structure:
{{
  "summary": "string",
  "experience_bullets": ["string"],
  "projects": ["string"],
  "skills_to_highlight": ["string"],
  "keywords_to_include": ["string"]
}}

Output rules:
- All list fields MUST always be JSON arrays and never null.
- summary MUST be a non-empty string.
- Do not return markdown.
- Do not return explanatory text outside the JSON.
- Do not add extra JSON fields.

Resume analysis:
{input_data.resume.model_dump_json()}

Job analysis:
{input_data.job.model_dump_json()}
"""
        response = await self._gateway.generate(prompt)
        payload = parse_json_response(response)
        result = ResumeTailorResult.model_validate(payload)
        return self._service.sanitize(result, input_data.resume)
