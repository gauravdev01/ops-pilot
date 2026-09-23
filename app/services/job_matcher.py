from typing import ClassVar

from app.models.jd_analysis import JDAnalysis
from app.models.job_match import JobMatchResult
from app.models.resume_analysis import ResumeAnalysis


class JobMatcherService:
    """Deterministically match a resume analysis against a job analysis."""

    _SENIORITY_LEVELS: ClassVar[dict[str, int]] = {
        "intern": 0,
        "junior": 1,
        "sde-1": 2,
        "sde-2": 3,
        "senior": 4,
        "lead": 5,
        "principal": 6,
    }

    def match(self, job: JDAnalysis, resume: ResumeAnalysis) -> JobMatchResult:
        """Return a deterministic match result for a job and resume."""
        resume_skills = self._unique_skills(resume.skills)
        required_skills = self._unique_skills(job.required_skills)
        preferred_skills = self._unique_skills(job.preferred_skills)

        matched_required = [
            original
            for normalized, original in resume_skills.items()
            if normalized in required_skills
        ]
        matched_required_names = {self._normalize(skill) for skill in matched_required}
        missing_required = [
            original
            for normalized, original in required_skills.items()
            if normalized not in matched_required_names
        ]
        matched_preferred = [
            original
            for normalized, original in resume_skills.items()
            if normalized in preferred_skills
        ]
        matched_preferred_names = {
            self._normalize(skill) for skill in matched_preferred
        }
        missing_preferred = [
            original
            for normalized, original in preferred_skills.items()
            if normalized not in matched_preferred_names
        ]

        required_coverage = self._coverage(
            len(matched_required_names), len(required_skills)
        )
        preferred_coverage = self._coverage(
            len(matched_preferred_names), len(preferred_skills)
        )
        match_percentage = round(
            (required_coverage * 80) + (preferred_coverage * 20),
            2,
        )

        return JobMatchResult(
            match_percentage=match_percentage,
            matched_required_skills=matched_required,
            missing_required_skills=missing_required,
            matched_preferred_skills=matched_preferred,
            missing_preferred_skills=missing_preferred,
            experience_match=self._experience_match(job, resume),
            seniority_match=self._seniority_match(job, resume),
            explanation=(
                f"Required skills matched: {len(matched_required_names)} of "
                f"{len(required_skills)}; preferred skills matched: "
                f"{len(matched_preferred_names)} of {len(preferred_skills)}."
            ),
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower()

    @classmethod
    def _unique_skills(cls, skills: list[str]) -> dict[str, str]:
        unique: dict[str, str] = {}
        for skill in skills:
            normalized = cls._normalize(skill)
            unique.setdefault(normalized, skill)
        return unique

    @staticmethod
    def _coverage(matched: int, total: int) -> float:
        return matched / total if total else 1.0

    @staticmethod
    def _experience_match(
        job: JDAnalysis,
        resume: ResumeAnalysis,
    ) -> bool | None:
        minimum = job.experience_min_years
        maximum = job.experience_max_years
        years = resume.years_of_experience
        if (minimum is None and maximum is None) or years is None:
            return None
        if minimum is not None and years < minimum:
            return False
        return not (maximum is not None and years > maximum)

    @classmethod
    def _seniority_match(
        cls,
        job: JDAnalysis,
        resume: ResumeAnalysis,
    ) -> bool | None:
        if job.seniority is None or resume.current_role is None:
            return None
        job_level = cls._SENIORITY_LEVELS.get(cls._normalize(job.seniority))
        resume_level = cls._SENIORITY_LEVELS.get(cls._normalize(resume.current_role))
        if job_level is None or resume_level is None:
            return None
        return resume_level >= job_level
