import base64
import hashlib

import httpx

from app.pr_reviewer.models import (
    ChangedFile,
    CommitInfo,
    PRContext,
    PRMetadata,
    ReviewFinding,
    ReviewReport,
)
from app.pr_reviewer.report import render_markdown


class GitHubClient:
    """Small GitHub REST client for pull-request review workflows."""

    def __init__(
        self,
        token: str,
        api_url: str = "https://api.github.com",
        timeout: float = 30.0,
    ) -> None:
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout

    async def collect_pull_request(self, repository: str, number: int) -> PRContext:
        async with httpx.AsyncClient(
            base_url=self._api_url,
            headers=self._headers,
            timeout=self._timeout,
        ) as client:
            pull = await self._get(client, f"/repos/{repository}/pulls/{number}")
            files = await self._all(client, f"/repos/{repository}/pulls/{number}/files")
            commits = await self._all(
                client, f"/repos/{repository}/pulls/{number}/commits"
            )
            changed_files = [
                await self._changed_file(client, repository, pull, item) for item in files
            ]

        metadata = PRMetadata(
            number=number,
            title=pull.get("title", ""),
            description=pull.get("body") or "",
            source_branch=pull.get("head", {}).get("ref", ""),
            target_branch=pull.get("base", {}).get("ref", ""),
            author=pull.get("user", {}).get("login", ""),
            labels=[label.get("name", "") for label in pull.get("labels", [])],
            repository=repository,
            mergeable=pull.get("mergeable"),
            mergeable_state=pull.get("mergeable_state"),
        )
        return PRContext(
            metadata=metadata,
            files=changed_files,
            commits=[
                CommitInfo(
                    sha=item.get("sha", ""),
                    message=item.get("commit", {}).get("message", ""),
                    author=(item.get("commit", {}).get("author") or {}).get("name"),
                )
                for item in commits
            ],
            diff="\n\n".join(item.patch for item in changed_files if item.patch),
            base_sha=pull.get("base", {}).get("sha"),
            head_sha=pull.get("head", {}).get("sha"),
        )

    async def publish_report(self, context: PRContext, markdown: str) -> int:
        if context.metadata.repository is None or context.metadata.number is None:
            raise ValueError("GitHub repository and pull request number are required")
        async with httpx.AsyncClient(
            base_url=self._api_url,
            headers=self._headers,
            timeout=self._timeout,
        ) as client:
            return await self._publish_summary(client, context, markdown)

    async def publish_review(
        self,
        context: PRContext,
        report: ReviewReport,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        """Publish inline findings and an idempotent summary comment.

        Only findings with a changed-file path, a validated line, and a head
        commit can be sent to GitHub's inline review API. Other findings remain
        in the summary report and are never assigned a fabricated location.
        """
        if context.metadata.repository is None or context.metadata.number is None:
            raise ValueError("GitHub repository and pull request number are required")
        if dry_run:
            return []

        async with httpx.AsyncClient(
            base_url=self._api_url,
            headers=self._headers,
            timeout=self._timeout,
        ) as client:
            published_ids = await self._publish_inline_findings(
                client, context, report.findings
            )
            published_ids.append(
                await self._publish_summary(client, context, render_markdown(report))
            )
            return published_ids

    async def _publish_inline_findings(
        self,
        client: httpx.AsyncClient,
        context: PRContext,
        findings: list[ReviewFinding],
    ) -> list[int]:
        if context.metadata.repository is None or context.metadata.number is None:
            return []
        if context.head_sha is None:
            return []
        changed_files = {item.path: item for item in context.files}
        existing = await self._all(
            client,
            f"/repos/{context.metadata.repository}/pulls/"
            f"{context.metadata.number}/comments",
        )
        existing_markers = {
            self._finding_marker_from_body(str(item.get("body", "")))
            for item in existing
        }
        comments: list[dict[str, object]] = []
        for finding in findings:
            if not finding.file or finding.line is None:
                continue
            changed_file = changed_files.get(finding.file)
            if changed_file is None:
                continue
            line_count = len(changed_file.content.splitlines())
            if finding.line > line_count:
                continue
            marker = self._finding_marker(finding)
            if marker in existing_markers:
                continue
            comments.append(
                {
                    "body": f"{marker}\n{self._finding_body(finding)}",
                    "path": finding.file,
                    "line": finding.line,
                    "side": "RIGHT",
                }
            )
        if not comments:
            return []
        response = await client.post(
            f"/repos/{context.metadata.repository}/pulls/"
            f"{context.metadata.number}/reviews",
            json={
                "commit_id": context.head_sha,
                "body": "Ops-Pilot inline review findings",
                "event": "COMMENT",
                "comments": comments,
            },
        )
        response.raise_for_status()
        review_id = response.json().get("id")
        return [review_id] if isinstance(review_id, int) else []

    async def _publish_summary(
        self,
        client: httpx.AsyncClient,
        context: PRContext,
        markdown: str,
    ) -> int:
        if context.metadata.repository is None or context.metadata.number is None:
            raise ValueError("GitHub repository and pull request number are required")
        marker = "<!-- ops-pilot-pr-review -->"
        body = f"{marker}\n{markdown}"
        comments = await self._all(
            client,
            f"/repos/{context.metadata.repository}/issues/"
            f"{context.metadata.number}/comments",
        )
        existing = next(
            (item for item in comments if marker in item.get("body", "")), None
        )
        if existing:
            response = await client.patch(
                f"/repos/{context.metadata.repository}/issues/comments/"
                f"{existing['id']}",
                json={"body": body},
            )
        else:
            response = await client.post(
                f"/repos/{context.metadata.repository}/issues/"
                f"{context.metadata.number}/comments",
                json={"body": body},
            )
        response.raise_for_status()
        return response.json()["id"]

    @staticmethod
    def _finding_marker(finding: ReviewFinding) -> str:
        value = "|".join(
            (
                finding.category,
                finding.title,
                finding.file or "",
                str(finding.line or ""),
                finding.problem,
            )
        )
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
        return f"<!-- ops-pilot-pr-review-finding:{digest} -->"

    @staticmethod
    def _finding_marker_from_body(body: str) -> str | None:
        start = body.find("<!-- ops-pilot-pr-review-finding:")
        if start == -1:
            return None
        end = body.find(" -->", start)
        return body[start : end + 4] if end != -1 else None

    @staticmethod
    def _finding_body(finding: ReviewFinding) -> str:
        return (
            f"**[{finding.severity.value}] {finding.title}**\n\n"
            f"{finding.problem}\n\n"
            f"**Why it matters:** {finding.why_it_matters}\n\n"
            f"**Evidence:** {finding.evidence}\n\n"
            f"**Suggested fix:** {finding.suggested_fix}"
        )

    async def _changed_file(
        self,
        client: httpx.AsyncClient,
        repository: str,
        pull: dict[str, object],
        item: dict[str, object],
    ) -> ChangedFile:
        path = str(item.get("filename", ""))
        head_sha = str(pull.get("head", {}).get("sha", ""))
        base_sha = str(pull.get("base", {}).get("sha", ""))
        content = await self._content(client, repository, path, head_sha)
        base_content = await self._content(client, repository, path, base_sha)
        patch = item.get("patch") or ""
        return ChangedFile(
            path=path,
            status=str(item.get("status", "modified")),
            additions=int(item.get("additions", 0)),
            deletions=int(item.get("deletions", 0)),
            patch=str(patch),
            content=content,
            base_content=base_content,
            is_binary=not bool(item.get("patch")),
            renamed_from=item.get("previous_filename"),
        )

    async def _content(
        self,
        client: httpx.AsyncClient,
        repository: str,
        path: str,
        ref: str,
    ) -> str:
        payload = await self._get(client, f"/repos/{repository}/contents/{path}?ref={ref}")
        if payload.get("encoding") != "base64":
            return ""
        return base64.b64decode(payload.get("content", "")).decode("utf-8", "replace")

    async def _all(
        self, client: httpx.AsyncClient, path: str
    ) -> list[dict[str, object]]:
        values: list[dict[str, object]] = []
        page = 1
        while True:
            payload = await self._get(client, f"{path}?per_page=100&page={page}")
            if not isinstance(payload, list):
                return values
            values.extend(payload)
            if len(payload) < 100:
                return values
            page += 1

    async def _get(self, client: httpx.AsyncClient, path: str) -> dict[str, object] | list[object]:
        response = await client.get(path)
        response.raise_for_status()
        return response.json()
