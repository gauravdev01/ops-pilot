import json
from pathlib import Path

import pytest

from app.pr_reviewer.models import ImpactAnalysis, PRContext
from app.pr_reviewer.reviewers import (
    APIReviewer,
    ArchitectureReviewer,
    BusinessLogicReviewer,
    ConcurrencyReviewer,
    ConfigurationReviewer,
    CorrectnessReviewer,
    DatabaseReviewer,
    DependencyReviewer,
    DeploymentReviewer,
    ErrorHandlingReviewer,
    MergeRiskReviewer,
    PerformanceReviewer,
    ReviewContext,
    SecurityReviewer,
    TestingReviewer,
)

FIXTURE = Path(__file__).parent / "fixtures" / "pr_reviewer" / "specialized_context.json"


def shared_context() -> ReviewContext:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return ReviewContext(
        pull_request=PRContext.model_validate(
            {"metadata": payload["metadata"], "files": payload["files"]}
        ),
        impact=ImpactAnalysis.model_validate(payload["impact"]),
    )


@pytest.mark.parametrize(
    ("reviewer_type", "expected_category", "expected_title"),
    [
        (CorrectnessReviewer, "correctness", "Incomplete implementation marker in changed code"),
        (SecurityReviewer, "security", "TLS certificate verification is disabled"),
        (APIReviewer, "api", "API route has no declared response model"),
        (DatabaseReviewer, "database", "Query selects all columns"),
        (PerformanceReviewer, "performance", "Repository-wide scan may run inside an iteration"),
        (ConcurrencyReviewer, "concurrency", "Blocking sleep in async code"),
        (ErrorHandlingReviewer, "error_handling", "Broad exception is silently swallowed"),
        (TestingReviewer, "testing", "Changed Python source has no related tests"),
        (DependencyReviewer, "dependencies", "Dependency files changed"),
        (ConfigurationReviewer, "configuration", "Configuration surface is affected"),
        (DeploymentReviewer, "deployment", "Deployment configuration changed"),
        (MergeRiskReviewer, "merge", "Pull request is reported as not mergeable"),
        (BusinessLogicReviewer, "business_logic", "Business workflow marker is incomplete"),
    ],
)
def test_specialized_reviewer_reports_evidence_backed_finding(
    reviewer_type: type,
    expected_category: str,
    expected_title: str,
) -> None:
    findings = reviewer_type().review(shared_context())

    finding = next(item for item in findings if item.title == expected_title)
    assert finding.category == expected_category
    assert finding.evidence
    assert finding.suggested_fix


def test_architecture_reviewer_reports_broad_caller_surface() -> None:
    context = shared_context()
    context = context.__class__(
        pull_request=context.pull_request,
        impact=context.impact.model_copy(
            update={"callers": [f"app/caller_{index}.py" for index in range(21)]}
        ),
    )

    findings = ArchitectureReviewer().review(context)

    assert findings[0].category == "architecture"
    assert "broad caller surface" in findings[0].title.lower()


def test_specialized_reviewers_share_one_context_and_do_not_call_llm() -> None:
    context = shared_context()
    reviewers = [
        SecurityReviewer(),
        APIReviewer(),
        DatabaseReviewer(),
        MergeRiskReviewer(),
    ]

    findings = [finding for reviewer in reviewers for finding in reviewer.review(context)]

    assert {finding.category for finding in findings} >= {
        "security",
        "api",
        "database",
        "merge",
    }
