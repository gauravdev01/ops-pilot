from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_tailor import ResumeTailorResult


class ResumeTailorService:
    """Validate resume-tailoring lists against the source resume."""

    def sanitize(
        self,
        result: ResumeTailorResult,
        resume: ResumeAnalysis,
    ) -> ResumeTailorResult:
        """Remove unsupported skills and keywords from a tailoring result."""
        resume_skills = {self._normalize(value) for value in resume.skills}
        resume_keywords = {self._normalize(value) for value in resume.keywords}
        supported_keywords = resume_skills | resume_keywords

        return result.model_copy(
            update={
                "skills_to_highlight": [
                    value
                    for value in result.skills_to_highlight
                    if self._normalize(value) in resume_skills
                ],
                "keywords_to_include": [
                    value
                    for value in result.keywords_to_include
                    if self._normalize(value) in supported_keywords
                ],
            }
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower()
