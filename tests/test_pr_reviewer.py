import json
import subprocess
from pathlib import Path

import pytest

from app.pr_reviewer.analyzer import RepositoryContextAnalyzer
from app.pr_reviewer.git_collector import LocalGitCollector
from app.pr_reviewer.models import (
    ChangedFile,
    PRContext,
    PRMetadata,
    ReviewFinding,
    ReviewReport,
    ReviewSeverity,
    ReviewStatus,
)
from app.pr_reviewer.pipeline import ReviewPipeline
from app.pr_reviewer.report import render_markdown
from app.pr_reviewer.reviewers import SecurityReviewer
from app.pr_reviewer.security import redact_secrets


class FakeGateway:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def make_context() -> PRContext:
    return PRContext(
        metadata=PRMetadata(
            title="Improve API",
            source_branch="feature/api",
            target_branch="main",
        ),
        files=[
            ChangedFile(
                path="app/example.py",
                status="modified",
                additions=2,
                content="def changed():\n    return 1\n",
                patch="@@ -1 +1,2 @@\n+def changed():\n+    return 1\n",
            )
        ],
        diff="diff --git a/app/example.py b/app/example.py",
    )


def test_secret_redaction_removes_credentials() -> None:
    value = "API_KEY=secret-value\nAuthorization: Bearer abc.def.ghi"

    redacted = redact_secrets(value)

    assert "secret-value" not in redacted
    assert "abc.def.ghi" not in redacted
    assert "[REDACTED]" in redacted


def test_local_collector_identifies_changed_files(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test User")
    source = tmp_path / "service.py"
    source.write_text("def before():\n    return 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "initial")
    git("branch", "-M", "main")
    git("switch", "-qc", "feature")
    source.write_text("def after():\n    return 2\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "change service")

    context = LocalGitCollector(tmp_path).collect(base="main")

    assert [item.path for item in context.files] == ["service.py"]
    assert context.files[0].additions == 2
    assert "def after" in context.files[0].content
    assert context.commits[0].message == "change service"
    assert context.recent_history
    assert context.recent_history[0].message == "change service"


def test_context_selection_includes_related_tests_and_dependencies(tmp_path: Path) -> None:
    source = tmp_path / "app" / "service.py"
    source.parent.mkdir()
    source.write_text("from app.helper import run\n\ndef change():\n    return run()\n", encoding="utf-8")
    (tmp_path / "app" / "helper.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_service.py").write_text("def test_change(): pass\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    context = PRContext(
        metadata=PRMetadata(title="change", source_branch="feature", target_branch="main"),
        files=[ChangedFile(path="app/service.py", status="modified", content=source.read_text())],
    )

    selected = RepositoryContextAnalyzer(tmp_path).select_files(context)

    assert "app/service.py" in selected
    assert "app/helper.py" in selected
    assert "tests/test_service.py" in selected
    assert "pyproject.toml" in selected


def test_impact_analysis_finds_symbols_callers_interfaces_and_configuration(
    tmp_path: Path,
) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "app" / "config.py").write_text(
        "from pydantic_settings import BaseSettings\n\nclass Settings(BaseSettings): pass\n",
        encoding="utf-8",
    )
    changed_content = (
        "from app.config import Settings\n\n"
        "class Child(Base):\n"
        "    def changed(self):\n"
        "        return Settings()\n"
    )
    (tmp_path / "app" / "service.py").write_text(changed_content, encoding="utf-8")
    (tmp_path / "app" / "caller.py").write_text(
        "from app.service import Child\n\nChild().changed()\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_service.py").write_text(
        "def test_changed(): pass\n", encoding="utf-8"
    )
    context = PRContext(
        metadata=PRMetadata(title="change", source_branch="feature", target_branch="main"),
        files=[
            ChangedFile(
                path="app/service.py",
                status="modified",
                content=changed_content,
            )
        ],
    )

    impact = RepositoryContextAnalyzer(tmp_path).impact(context)

    assert "Child" in impact.changed_symbols
    assert "changed" in impact.changed_symbols
    assert "app/caller.py" in impact.callers
    assert "app.config.Settings" in impact.callees
    assert "Base" in impact.interfaces
    assert "tests/test_service.py" in impact.tests
    assert "app/config.py" in impact.configuration


@pytest.mark.asyncio
async def test_pipeline_scrubs_invalid_locations_and_deduplicates(tmp_path: Path) -> None:
    response = json.dumps(
        {
            "findings": [
                {
                    "category": "correctness",
                    "severity": "MEDIUM",
                    "confidence": 0.9,
                    "title": "Duplicate issue",
                    "file": "app/example.py",
                    "line": 1,
                    "end_line": 1,
                    "problem": "Issue",
                    "why_it_matters": "Impact",
                    "evidence": "Evidence",
                    "suggested_fix": "Fix",
                    "blocking": False,
                },
                {
                    "category": "correctness",
                    "severity": "MEDIUM",
                    "confidence": 0.9,
                    "title": "Duplicate issue",
                    "file": "app/example.py",
                    "line": 1,
                    "end_line": 1,
                    "problem": "Issue",
                    "why_it_matters": "Impact",
                    "evidence": "Evidence",
                    "suggested_fix": "Fix",
                    "blocking": False,
                },
                {
                    "category": "security",
                    "severity": "HIGH",
                    "confidence": 0.8,
                    "title": "Unknown location",
                    "file": "not-a-real-file.py",
                    "line": 999,
                    "end_line": 999,
                    "problem": "Issue",
                    "why_it_matters": "Impact",
                    "evidence": "Evidence",
                    "suggested_fix": "Fix",
                    "blocking": True,
                },
            ]
        }
    )
    gateway = FakeGateway(response)
    pipeline = ReviewPipeline(RepositoryContextAnalyzer(tmp_path), gateway)  # type: ignore[arg-type]

    report = await pipeline.review(make_context())

    assert len([item for item in report.findings if item.title == "Duplicate issue"]) == 1
    unknown = next(item for item in report.findings if item.title == "Unknown location")
    assert unknown.file is None
    assert unknown.line is None
    assert report.status is ReviewStatus.CHANGES_REQUESTED
    assert report.risk is ReviewSeverity.HIGH


@pytest.mark.asyncio
async def test_pipeline_handles_malformed_model_response(tmp_path: Path) -> None:
    gateway = FakeGateway("not JSON")
    pipeline = ReviewPipeline(RepositoryContextAnalyzer(tmp_path), gateway)  # type: ignore[arg-type]

    report = await pipeline.review(make_context())

    assert report.status is ReviewStatus.REVIEW_REQUIRED
    assert any(item.title == "Structured review stage failed" for item in report.findings)


@pytest.mark.asyncio
async def test_pipeline_uses_one_shared_llm_review_call_with_specialized_reviewers(
    tmp_path: Path,
) -> None:
    gateway = FakeGateway('{"findings": []}')
    pipeline = ReviewPipeline(RepositoryContextAnalyzer(tmp_path), gateway)  # type: ignore[arg-type]

    await pipeline.review(make_context())

    assert len(gateway.prompts) == 1


@pytest.mark.asyncio
async def test_pipeline_accepts_injected_specialized_reviewer(
    tmp_path: Path,
) -> None:
    gateway = FakeGateway('{"findings": []}')
    context = make_context().model_copy(
        update={
            "files": [
                ChangedFile(
                    path="app/security.py",
                    status="modified",
                    content="client.get(url, verify=False)\n",
                )
            ]
        }
    )
    pipeline = ReviewPipeline(
        RepositoryContextAnalyzer(tmp_path),
        gateway,  # type: ignore[arg-type]
        reviewers=[SecurityReviewer],
    )

    report = await pipeline.review(context)

    assert any(
        item.category == "security"
        and item.title == "TLS certificate verification is disabled"
        for item in report.findings
    )
    assert len(gateway.prompts) == 1


def test_report_contains_status_and_finding() -> None:
    report = ReviewReport(
        status=ReviewStatus.CHANGES_REQUESTED,
        risk=ReviewSeverity.HIGH,
        files_analyzed=1,
        findings=[
            ReviewFinding(
                category="security",
                severity=ReviewSeverity.HIGH,
                confidence=0.95,
                title="Unsafe input",
                file="app/service.py",
                line=12,
                problem="Input is executed.",
                why_it_matters="Can enable command injection.",
                evidence="shell=True",
                suggested_fix="Use an allowlist.",
                blocking=True,
            )
        ],
    )

    markdown = render_markdown(report)

    assert "CHANGES_REQUESTED" in markdown
    assert "[HIGH] Unsafe input" in markdown
    assert "app/service.py:12" in markdown
    assert "ops-pilot-pr-review" in markdown
