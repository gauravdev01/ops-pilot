from dataclasses import dataclass
from typing import Protocol

from app.pr_reviewer.models import (
    ChangedFile,
    ImpactAnalysis,
    PRContext,
    ReviewFinding,
    ReviewSeverity,
)


@dataclass(frozen=True)
class ReviewContext:
    """Shared deterministic context passed to every specialized reviewer."""

    pull_request: PRContext
    impact: ImpactAnalysis


class SpecializedReviewer(Protocol):
    """Contract for a focused reviewer that does not make its own LLM call."""

    category: str

    def review(self, context: ReviewContext) -> list[ReviewFinding]:
        """Return evidence-backed findings for the shared context."""


class _ContentReviewer:
    category = ""

    def review(self, context: ReviewContext) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        for changed_file in context.pull_request.files:
            findings.extend(self._review_file(changed_file, context))
        findings.extend(self._review_context(context))
        return findings

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        return []

    def _review_context(self, context: ReviewContext) -> list[ReviewFinding]:
        return []

    def _finding(
        self,
        changed_file: ChangedFile | None,
        title: str,
        severity: ReviewSeverity,
        problem: str,
        why_it_matters: str,
        evidence: str,
        suggested_fix: str,
        *,
        blocking: bool = False,
        tests_to_add: list[str] | None = None,
    ) -> ReviewFinding:
        return ReviewFinding(
            category=self.category,
            severity=severity,
            confidence=0.9,
            title=title,
            file=changed_file.path if changed_file else None,
            problem=problem,
            why_it_matters=why_it_matters,
            evidence=evidence,
            suggested_fix=suggested_fix,
            blocking=blocking,
            tests_to_add=tests_to_add or [],
        )


class CorrectnessReviewer(_ContentReviewer):
    category = "correctness"

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        if "TODO" in changed_file.content or "NotImplementedError" in changed_file.content:
            return [
                self._finding(
                    changed_file,
                    "Incomplete implementation marker in changed code",
                    ReviewSeverity.MEDIUM,
                    "The changed file contains an explicit TODO or NotImplementedError marker.",
                    "The change may ship a missing branch or incomplete behavior.",
                    "Matched TODO/NotImplementedError in changed file.",
                    "Complete the implementation or document why the marker is intentional.",
                )
            ]
        return []


class SecurityReviewer(_ContentReviewer):
    category = "security"

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        content = changed_file.content.lower()
        if "verify=false" in content or "verify = false" in content:
            return [
                self._finding(
                    changed_file,
                    "TLS certificate verification is disabled",
                    ReviewSeverity.HIGH,
                    "The changed code disables TLS certificate verification.",
                    "Man-in-the-middle attacks become possible for the affected connection.",
                    "Found verify=False in changed file.",
                    "Keep certificate verification enabled and configure a trusted CA when required.",
                    blocking=True,
                )
            ]
        return []


class PerformanceReviewer(_ContentReviewer):
    category = "performance"

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        if "for " in changed_file.content and "rglob(" in changed_file.content:
            return [
                self._finding(
                    changed_file,
                    "Repository-wide scan may run inside an iteration",
                    ReviewSeverity.MEDIUM,
                    "The changed code combines iteration with a recursive repository scan.",
                    "Repeated filesystem traversal can create substantial latency and load.",
                    "Found a for-loop and rglob() in the changed file.",
                    "Hoist the scan, cache its result, or narrow the traversal before iterating.",
                )
            ]
        return []


class ConcurrencyReviewer(_ContentReviewer):
    category = "concurrency"

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        if "async def" in changed_file.content and "time.sleep(" in changed_file.content:
            return [
                self._finding(
                    changed_file,
                    "Blocking sleep in async code",
                    ReviewSeverity.HIGH,
                    "An async function calls time.sleep().",
                    "The event loop is blocked and concurrent requests can stall.",
                    "Found async def alongside time.sleep().",
                    "Use await asyncio.sleep() or move blocking work to a worker thread.",
                    blocking=True,
                )
            ]
        return []


class ErrorHandlingReviewer(_ContentReviewer):
    category = "error_handling"

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        if "except Exception:" in changed_file.content and "pass" in changed_file.content:
            return [
                self._finding(
                    changed_file,
                    "Broad exception is silently swallowed",
                    ReviewSeverity.MEDIUM,
                    "The changed code catches Exception and does not handle or report it.",
                    "Failures can disappear while leaving state or callers inconsistent.",
                    "Found except Exception: with pass in changed file.",
                    "Catch expected exceptions narrowly and log or propagate unexpected failures.",
                )
            ]
        return []


class APIReviewer(_ContentReviewer):
    category = "api"

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        if "@router." in changed_file.content and "response_model=" not in changed_file.content:
            return [
                self._finding(
                    changed_file,
                    "API route has no declared response model",
                    ReviewSeverity.LOW,
                    "The changed route does not declare a response model.",
                    "Response shape can drift without a contract enforced at the API boundary.",
                    "Found router decorator without response_model=.",
                    "Declare the response model or document why an unconstrained response is required.",
                )
            ]
        return []


class DatabaseReviewer(_ContentReviewer):
    category = "database"

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        if "SELECT *" in changed_file.content.upper():
            return [
                self._finding(
                    changed_file,
                    "Query selects all columns",
                    ReviewSeverity.LOW,
                    "The changed query uses SELECT *.",
                    "Schema growth increases transfer and processing cost and can expose unintended columns.",
                    "Found SELECT * in changed file.",
                    "Select the required columns explicitly and add or verify supporting indexes.",
                )
            ]
        return []


class TestingReviewer(_ContentReviewer):
    category = "testing"

    def _review_context(self, context: ReviewContext) -> list[ReviewFinding]:
        changed_sources = [
            item for item in context.pull_request.files
            if item.path.endswith(".py") and not item.path.startswith("tests/")
        ]
        if changed_sources and not context.impact.tests:
            return [
                self._finding(
                    None,
                    "Changed Python source has no related tests",
                    ReviewSeverity.MEDIUM,
                    "No related test file was selected for changed Python source.",
                    "Behavioral regressions may reach production without focused coverage.",
                    "Impact analysis selected no test files.",
                    "Add focused success, validation, and failure-path tests.",
                    tests_to_add=["Cover the changed public behavior and its failure modes."],
                )
            ]
        return []


class ArchitectureReviewer(_ContentReviewer):
    category = "architecture"

    def _review_context(self, context: ReviewContext) -> list[ReviewFinding]:
        if len(context.impact.callers) > 20:
            return [
                self._finding(
                    None,
                    "Change has a broad caller surface",
                    ReviewSeverity.MEDIUM,
                    "Impact analysis found more than twenty caller files for changed symbols.",
                    "A small behavioral change may affect many consumers and needs compatibility review.",
                    f"Found {len(context.impact.callers)} caller files.",
                    "Review each caller contract and add compatibility coverage before merging.",
                )
            ]
        return []


class DependencyReviewer(_ContentReviewer):
    category = "dependencies"

    def _review_context(self, context: ReviewContext) -> list[ReviewFinding]:
        if context.impact.dependency_changes:
            return [
                self._finding(
                    None,
                    "Dependency files changed",
                    ReviewSeverity.INFO,
                    "The pull request changes dependency declarations.",
                    "Dependency changes can affect reproducibility, security, and deployment environments.",
                    ", ".join(context.impact.dependency_changes),
                    "Run a clean install and dependency vulnerability/compatibility checks.",
                )
            ]
        return []


class ConfigurationReviewer(_ContentReviewer):
    category = "configuration"

    def _review_context(self, context: ReviewContext) -> list[ReviewFinding]:
        if context.impact.configuration:
            return [
                self._finding(
                    None,
                    "Configuration surface is affected",
                    ReviewSeverity.INFO,
                    "Changed code is related to configuration files or environment settings.",
                    "Missing or incompatible deployment configuration can prevent startup or change runtime behavior.",
                    ", ".join(context.impact.configuration),
                    "Verify development, CI, and production configuration values and defaults.",
                )
            ]
        return []


class DeploymentReviewer(_ContentReviewer):
    category = "deployment"

    def _review_context(self, context: ReviewContext) -> list[ReviewFinding]:
        changed = {item.path for item in context.pull_request.files}
        deployment_files = sorted(
            path for path in changed if path.startswith(".github/") or "Dockerfile" in path
        )
        if deployment_files:
            return [
                self._finding(
                    None,
                    "Deployment configuration changed",
                    ReviewSeverity.INFO,
                    "The pull request changes deployment or CI configuration.",
                    "A workflow or image change can affect release safety and rollback behavior.",
                    ", ".join(deployment_files),
                    "Validate the workflow on a clean runner and verify rollback compatibility.",
                )
            ]
        return []


class MergeRiskReviewer(_ContentReviewer):
    category = "merge"

    def _review_context(self, context: ReviewContext) -> list[ReviewFinding]:
        if context.pull_request.metadata.mergeable is False:
            return [
                self._finding(
                    None,
                    "Pull request is reported as not mergeable",
                    ReviewSeverity.HIGH,
                    "GitHub reports mergeable=false for this pull request.",
                    "The change cannot safely merge until conflicts are resolved.",
                    context.pull_request.metadata.mergeable_state or "mergeable=false",
                    "Resolve conflicts and rerun the review.",
                    blocking=True,
                )
            ]
        if context.pull_request.merge_conflicts:
            return [
                self._finding(
                    None,
                    "Merge conflicts were detected",
                    ReviewSeverity.HIGH,
                    "The collected pull request context includes merge conflicts.",
                    "Conflicting code cannot be integrated safely without reconciliation.",
                    ", ".join(context.pull_request.merge_conflicts),
                    "Resolve the listed conflicts and rerun the reviewer.",
                    blocking=True,
                )
            ]
        return []


class BusinessLogicReviewer(_ContentReviewer):
    category = "business_logic"

    def _review_file(
        self, changed_file: ChangedFile, context: ReviewContext
    ) -> list[ReviewFinding]:
        if "TODO" in changed_file.content and any(
            token in changed_file.content.lower()
            for token in ("status", "state", "approval", "payment", "permission")
        ):
            return [
                self._finding(
                    changed_file,
                    "Business workflow marker is incomplete",
                    ReviewSeverity.MEDIUM,
                    "The changed workflow-related code contains an unresolved TODO.",
                    "Incomplete state or approval logic can create inconsistent business outcomes.",
                    "Found TODO near workflow-related terms.",
                    "Complete the transition logic and test allowed and rejected transitions.",
                )
            ]
        return []


DEFAULT_REVIEWERS: tuple[type[_ContentReviewer], ...] = (
    CorrectnessReviewer,
    SecurityReviewer,
    APIReviewer,
    DatabaseReviewer,
    PerformanceReviewer,
    ConcurrencyReviewer,
    ErrorHandlingReviewer,
    TestingReviewer,
    ArchitectureReviewer,
    DependencyReviewer,
    ConfigurationReviewer,
    DeploymentReviewer,
    MergeRiskReviewer,
    BusinessLogicReviewer,
)
