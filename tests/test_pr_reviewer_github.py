from typing import Any, ClassVar, Self

import pytest

from app.pr_reviewer.github import GitHubClient
from app.pr_reviewer.models import (
    ChangedFile,
    PRContext,
    PRMetadata,
    ReviewFinding,
    ReviewReport,
    ReviewSeverity,
    ReviewStatus,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeAsyncClient:
    instances: ClassVar[list["FakeAsyncClient"]] = []
    get_payloads: ClassVar[dict[str, list[dict[str, Any]]]] = {}

    def __init__(self, **_: object) -> None:
        self.get_calls: list[str] = []
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.patch_calls: list[tuple[str, dict[str, Any]]] = []
        self.__class__.instances.append(self)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, path: str) -> FakeResponse:
        self.get_calls.append(path)
        for prefix, payload in self.get_payloads.items():
            if path.startswith(prefix):
                return FakeResponse({"items": payload}) if False else FakeResponse(payload)
        return FakeResponse([])  # type: ignore[arg-type]

    async def post(self, path: str, json: dict[str, Any]) -> FakeResponse:
        self.post_calls.append((path, json))
        if path.endswith("/reviews"):
            return FakeResponse({"id": 101})
        return FakeResponse({"id": 202})

    async def patch(self, path: str, json: dict[str, Any]) -> FakeResponse:
        self.patch_calls.append((path, json))
        return FakeResponse({"id": 202})


def context() -> PRContext:
    return PRContext(
        metadata=PRMetadata(
            number=42,
            title="Review change",
            source_branch="feature/change",
            target_branch="main",
            repository="owner/repo",
        ),
        files=[
            ChangedFile(
                path="app/service.py",
                status="modified",
                content="line one\nline two\nline three\n",
            )
        ],
        head_sha="head-sha-123",
    )


def report() -> ReviewReport:
    return ReviewReport(
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
                line=2,
                problem="Input is unsafe.",
                why_it_matters="It can be exploited.",
                evidence="Line two",
                suggested_fix="Validate input.",
                blocking=True,
            ),
            ReviewFinding(
                category="testing",
                severity=ReviewSeverity.MEDIUM,
                confidence=0.9,
                title="Missing test",
                problem="A test is missing.",
                why_it_matters="Regressions may escape.",
                evidence="No test selected.",
                suggested_fix="Add a regression test.",
            ),
        ],
    )


@pytest.fixture(autouse=True)
def reset_fake_client() -> None:
    FakeAsyncClient.instances.clear()
    FakeAsyncClient.get_payloads = {}


@pytest.mark.asyncio
async def test_publish_review_uses_exact_inline_review_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.pr_reviewer.github.httpx.AsyncClient", FakeAsyncClient)

    published = await GitHubClient("token").publish_review(context(), report())

    client = FakeAsyncClient.instances[0]
    review_path, review_payload = next(
        call for call in client.post_calls if call[0].endswith("/reviews")
    )
    assert review_path == "/repos/owner/repo/pulls/42/reviews"
    assert review_payload["commit_id"] == "head-sha-123"
    assert review_payload["event"] == "COMMENT"
    assert review_payload["comments"] == [
        {
            "body": review_payload["comments"][0]["body"],
            "path": "app/service.py",
            "line": 2,
            "side": "RIGHT",
        }
    ]
    assert "Unsafe input" in review_payload["comments"][0]["body"]
    assert published == [101, 202]
    assert any(call[0].endswith("/issues/42/comments") for call in client.post_calls)


@pytest.mark.asyncio
async def test_publish_review_does_not_duplicate_existing_inline_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.pr_reviewer.github.httpx.AsyncClient", FakeAsyncClient)
    finding = report().findings[0]
    marker = GitHubClient._finding_marker(finding)
    FakeAsyncClient.get_payloads = {
        "/repos/owner/repo/pulls/42/comments": [{"body": f"{marker}\nold comment"}],
    }

    await GitHubClient("token").publish_review(context(), report())

    client = FakeAsyncClient.instances[0]
    assert not any(path.endswith("/reviews") for path, _ in client.post_calls)
    assert any(path.endswith("/issues/42/comments") for path, _ in client.post_calls)


@pytest.mark.asyncio
async def test_publish_review_dry_run_makes_no_http_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_constructed(**_: object) -> None:
        raise AssertionError("dry-run must not construct an HTTP client")

    monkeypatch.setattr("app.pr_reviewer.github.httpx.AsyncClient", fail_if_constructed)

    assert await GitHubClient("token").publish_review(
        context(), report(), dry_run=True
    ) == []


@pytest.mark.asyncio
async def test_publish_review_keeps_summary_for_unlocated_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.pr_reviewer.github.httpx.AsyncClient", FakeAsyncClient)
    unlocated = report().model_copy(
        update={"findings": [report().findings[1]]}
    )

    await GitHubClient("token").publish_review(context(), unlocated)

    client = FakeAsyncClient.instances[0]
    assert not any(path.endswith("/reviews") for path, _ in client.post_calls)
    summary_path, summary_payload = next(
        call for call in client.post_calls if call[0].endswith("/issues/42/comments")
    )
    assert summary_path == "/repos/owner/repo/issues/42/comments"
    assert "Missing test" in summary_payload["body"]
