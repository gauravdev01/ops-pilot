import subprocess
from pathlib import Path

from app.pr_reviewer.models import ChangedFile, CommitInfo, PRContext, PRMetadata


class GitCommandError(RuntimeError):
    """Raised when a required Git command fails."""


class LocalGitCollector:
    """Collect a pull-request-shaped context from a local checkout."""

    def __init__(self, repository: Path) -> None:
        self.repository = repository

    def collect(
        self,
        base: str | None = None,
        head: str = "HEAD",
    ) -> PRContext:
        source_branch = self._run("branch", "--show-current").strip() or head
        target_branch = base or self._default_base()
        merge_base = self._run("merge-base", target_branch, head).strip()
        diff = self._run("diff", "--find-renames", "--unified=80", merge_base, head)
        files = self._collect_files(merge_base, head, diff)
        commits = self._collect_commits(merge_base, head)
        title = commits[0].message.splitlines()[0] if commits else source_branch
        metadata = PRMetadata(
            title=title,
            description="Local review of the current branch.",
            source_branch=source_branch,
            target_branch=target_branch,
            author=self._run("log", "-1", "--format=%an", head).strip(),
        )
        return PRContext(
            metadata=metadata,
            files=files,
            commits=commits,
            diff=diff,
            base_sha=merge_base,
            head_sha=self._run("rev-parse", head).strip(),
        )

    def _collect_files(self, base: str, head: str, diff: str) -> list[ChangedFile]:
        names = self._run("diff", "--name-status", "--find-renames", base, head)
        numstats = self._run("diff", "--numstat", "--find-renames", base, head)
        stat_by_path: dict[str, tuple[int, int]] = {}
        for line in numstats.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                stat_by_path[parts[-1]] = (int(parts[0]), int(parts[1]))

        files: list[ChangedFile] = []
        for line in names.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0]
            old_path = parts[1] if status.startswith("R") and len(parts) > 2 else None
            path = parts[2] if old_path else parts[1]
            additions, deletions = stat_by_path.get(path, (0, 0))
            content = self._file_at_head(path, head)
            base_content = self._file_at_base(path, base)
            patch = self._patch_for_path(base, head, path)
            files.append(
                ChangedFile(
                    path=path,
                    status=status,
                    additions=additions,
                    deletions=deletions,
                    patch=patch,
                    content=content,
                    base_content=base_content,
                    is_binary="GIT binary patch" in patch or "Binary files" in patch,
                    renamed_from=old_path,
                )
            )
        if not files and diff:
            return files
        return files

    def _collect_commits(self, base: str, head: str) -> list[CommitInfo]:
        raw = self._run("log", "--format=%H%x09%an%x09%s", f"{base}..{head}")
        commits: list[CommitInfo] = []
        for line in raw.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                sha, author, message = parts
                commits.append(CommitInfo(sha=sha, author=author, message=message))
        return commits

    def _default_base(self) -> str:
        for candidate in ("origin/main", "main", "origin/master", "master"):
            if self._succeeds("rev-parse", "--verify", candidate):
                return candidate
        return "HEAD~1"

    def _file_at_head(self, path: str, head: str) -> str:
        if self._succeeds("cat-file", "-e", f"{head}:{path}"):
            return self._run("show", f"{head}:{path}")
        return ""

    def _file_at_base(self, path: str, base: str) -> str:
        if self._succeeds("cat-file", "-e", f"{base}:{path}"):
            return self._run("show", f"{base}:{path}")
        return ""

    def _patch_for_path(self, base: str, head: str, path: str) -> str:
        return self._run("diff", "--find-renames", "--unified=80", base, head, "--", path)

    def _succeeds(self, *args: str) -> bool:
        return subprocess.run(
            ["git", *args],
            cwd=self.repository,
            capture_output=True,
            text=True,
            check=False,
        ).returncode == 0

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repository,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise GitCommandError(result.stderr.strip() or "Git command failed")
        return result.stdout
