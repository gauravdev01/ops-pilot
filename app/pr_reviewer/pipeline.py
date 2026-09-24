import re
from collections.abc import Iterable, Sequence

from pydantic import ValidationError

from app.core.json_utils import parse_json_response
from app.pr_reviewer.analyzer import RepositoryContextAnalyzer
from app.pr_reviewer.models import (
    ImpactAnalysis,
    LLMReviewResult,
    PRContext,
    ReviewFinding,
    ReviewReport,
    ReviewSeverity,
    ReviewStatus,
)
from app.pr_reviewer.reviewers import (
    DEFAULT_REVIEWERS,
    ReviewContext,
    SpecializedReviewer,
)
from app.services.model_gateway import ModelGateway


class ReviewPipeline:
    """Run deterministic checks, one focused LLM review, and risk aggregation."""

    def __init__(
        self,
        analyzer: RepositoryContextAnalyzer,
        gateway: ModelGateway,
        max_findings: int = 50,
        reviewers: Sequence[
            SpecializedReviewer | type[SpecializedReviewer]
        ] | None = None,
    ) -> None:
        self.analyzer = analyzer
        self.gateway = gateway
        self.max_findings = max_findings
        configured_reviewers = (
            DEFAULT_REVIEWERS if reviewers is None else reviewers
        )
        self.reviewers = tuple(
            reviewer() if isinstance(reviewer, type) else reviewer
            for reviewer in configured_reviewers
        )

    async def review(self, context: PRContext) -> ReviewReport:
        impact = self.analyzer.impact(context)
        shared_context = ReviewContext(pull_request=context, impact=impact)
        deterministic = [
            *self._deterministic_findings(context, impact),
            *self._specialized_findings(shared_context),
        ]
        llm_result, llm_error = await self._llm_review(context, impact)
        findings = self._deduplicate(
            [*deterministic, *llm_result.findings], context
        )[: self.max_findings]
        if llm_error:
            findings.append(
                ReviewFinding(
                    category="architecture",
                    severity=ReviewSeverity.MEDIUM,
                    confidence=1.0,
                    title="Structured review stage failed",
                    problem="The language-model review stage did not produce valid structured output.",
                    why_it_matters="The deterministic checks completed, but the full semantic review is incomplete.",
                    evidence=llm_error,
                    suggested_fix="Inspect the model/provider response and rerun the review.",
                    blocking=False,
                )
            )
        risk = self._risk(findings)
        status = (
            ReviewStatus.CHANGES_REQUESTED
            if any(item.blocking for item in findings)
            else ReviewStatus.REVIEW_REQUIRED
            if findings or llm_error
            else ReviewStatus.APPROVE
        )
        return ReviewReport(
            status=status,
            risk=risk,
            files_analyzed=len(context.files),
            findings=findings,
            testing_gaps=llm_result.testing_gaps,
            deployment_concerns=llm_result.deployment_concerns,
            merge_concerns=llm_result.merge_concerns,
            recommended_verification=llm_result.recommended_verification,
            context_summary=(
                f"Analyzed {len(context.files)} changed files, "
                f"{len(impact.related_files)} selected context files, and "
                f"{len(context.commits)} commits."
            ),
        )

    def _specialized_findings(
        self, context: ReviewContext
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        for reviewer in self.reviewers:
            findings.extend(reviewer.review(context))
        return findings

    async def _llm_review(
        self, context: PRContext, impact: ImpactAnalysis
    ) -> tuple[LLMReviewResult, str | None]:
        prompt = self._prompt(context, impact)
        try:
            raw = await self.gateway.generate(prompt)
            parsed = parse_json_response(raw)
            result = LLMReviewResult.model_validate(parsed)
            return self._validate_locations(result, context), None
        except (ValueError, ValidationError, TypeError) as exc:
            return LLMReviewResult(), str(exc)

    def _prompt(self, context: PRContext, impact: ImpactAnalysis) -> str:
        review_context = self.analyzer.build_context(context, impact)
        return f"""You are a staff-level production code reviewer. Review this pull request as a complete engineering change, not only its diff.

Inspect correctness, regression risk, security, API behavior, database risks, performance, concurrency, error handling, tests, architecture, dependencies, configuration, observability, deployment, merge risk, and business logic. Report only evidence-backed issues introduced or materially affected by this change. Do not invent paths or line numbers. Use null locations when an exact inline location cannot be established. Do not report secrets.

Return ONLY valid JSON with exactly this shape:
{{
  "findings": [{{
    "category": "correctness|regression|security|api|database|performance|concurrency|error_handling|testing|architecture|dependencies|configuration|observability|deployment|merge|business_logic",
    "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
    "confidence": 0.0,
    "title": "short title",
    "file": "changed or selected path, or null",
    "line": 1,
    "end_line": 1,
    "problem": "what is wrong",
    "why_it_matters": "production impact",
    "evidence": "specific code or context evidence",
    "suggested_fix": "concrete fix",
    "tests_to_add": [],
    "related_files": [],
    "blocking": false
  }}],
  "testing_gaps": [],
  "deployment_concerns": [],
  "merge_concerns": [],
  "recommended_verification": []
}}

Severity policy: CRITICAL means likely security catastrophe, data loss, or outage; HIGH means a strong production bug or serious security/data issue; MEDIUM means a meaningful pre-merge risk; LOW and INFO are non-blocking. Be precise and prefer no finding over speculation.

REVIEW CONTEXT:
{review_context}
"""

    @staticmethod
    def _validate_locations(
        result: LLMReviewResult, context: PRContext
    ) -> LLMReviewResult:
        known = {item.path: item for item in context.files}
        findings: list[ReviewFinding] = []
        for finding in result.findings:
            if finding.file not in known:
                finding = finding.model_copy(update={"file": None, "line": None, "end_line": None})
            elif finding.line is not None:
                max_line = len(known[finding.file].content.splitlines()) or 1
                if finding.line > max_line:
                    finding = finding.model_copy(update={"line": None, "end_line": None})
            if finding.file is not None and finding.file not in known:
                finding = finding.model_copy(update={"related_files": []})
            finding = finding.model_copy(
                update={"related_files": [path for path in finding.related_files if path in known]}
            )
            findings.append(finding)
        return result.model_copy(update={"findings": findings})

    @staticmethod
    def _deterministic_findings(
        context: PRContext, impact: ImpactAnalysis
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        for item in context.files:
            if item.is_binary:
                findings.append(
                    ReviewFinding(
                        category="architecture",
                        severity=ReviewSeverity.INFO,
                        confidence=1.0,
                        title="Binary file changed",
                        file=item.path,
                        problem="A binary file changed and cannot be reviewed semantically from source content.",
                        why_it_matters="Binary changes may hide behavior or deployment impact from a source review.",
                        evidence=item.path,
                        suggested_fix="Review the binary artifact and its provenance separately.",
                    )
                )
            if re.search(r"(?i)(eval\(|exec\(|os\.system\(|subprocess\.run\([^)]*shell\s*=\s*True)", item.content):
                findings.append(
                    ReviewFinding(
                        category="security",
                        severity=ReviewSeverity.HIGH,
                        confidence=0.8,
                        title="Dynamic or shell execution requires security review",
                        file=item.path,
                        problem="The changed file contains dynamic or shell command execution.",
                        why_it_matters="Untrusted input reaching these operations can become code or command injection.",
                        evidence="Matched execution primitive in changed file.",
                        suggested_fix="Avoid dynamic execution or use strict allowlisted arguments without a shell.",
                        blocking=True,
                    )
                )
            if item.path.endswith(".py") and not item.path.startswith("tests/") and not any(
                path.endswith(item.path.rsplit("/", 1)[-1].replace(".py", ""))
                or path == f"tests/test_{item.path.rsplit('/', 1)[-1]}"
                for path in impact.tests
            ):
                findings.append(
                    ReviewFinding(
                        category="testing",
                        severity=ReviewSeverity.MEDIUM,
                        confidence=0.9,
                        title="Changed Python source has no selected test coverage",
                        file=item.path,
                        problem="No directly related test file was selected for the changed source file.",
                        why_it_matters="Behavioral regressions may reach production without a focused regression test.",
                        evidence="Deterministic repository context selection found no matching test file.",
                        suggested_fix="Add or update a focused test for the changed behavior.",
                        tests_to_add=["Exercise success, validation, and failure paths for the changed behavior."],
                    )
                )
        if context.metadata.mergeable is False:
            findings.append(
                ReviewFinding(
                    category="merge",
                    severity=ReviewSeverity.HIGH,
                    confidence=1.0,
                    title="GitHub reports the pull request is not mergeable",
                    problem="The pull request has a mergeable=false state.",
                    why_it_matters="The change cannot safely merge until conflicts or repository checks are resolved.",
                    evidence=context.metadata.mergeable_state or "mergeable=false",
                    suggested_fix="Resolve the reported merge conflicts and rerun review.",
                    blocking=True,
                )
            )
        return findings

    @staticmethod
    def _deduplicate(findings: Iterable[ReviewFinding], context: PRContext) -> list[ReviewFinding]:
        seen: set[tuple[str, str, str | None, int | None]] = set()
        unique: list[ReviewFinding] = []
        known = {item.path for item in context.files}
        for finding in findings:
            if finding.file not in known:
                finding = finding.model_copy(update={"file": None, "line": None})
            key = (finding.category.lower(), finding.title.strip().lower(), finding.file, finding.line)
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        return unique

    @staticmethod
    def _risk(findings: list[ReviewFinding]) -> ReviewSeverity:
        order = {
            ReviewSeverity.INFO: 0,
            ReviewSeverity.LOW: 1,
            ReviewSeverity.MEDIUM: 2,
            ReviewSeverity.HIGH: 3,
            ReviewSeverity.CRITICAL: 4,
        }
        return max((item.severity for item in findings), key=order.get, default=ReviewSeverity.INFO)
