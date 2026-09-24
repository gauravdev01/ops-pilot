import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.pr_reviewer.analyzer import RepositoryContextAnalyzer
from app.pr_reviewer.git_collector import LocalGitCollector
from app.pr_reviewer.github import GitHubClient
from app.pr_reviewer.pipeline import ReviewPipeline
from app.pr_reviewer.report import render_markdown
from app.services.model_gateway import ModelGateway
from app.services.ollama_provider import OllamaProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review a GitHub pull request with Ops-Pilot")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--local", action="store_true", help="Review the current local branch")
    source.add_argument("--pull-request", type=int, help="Review a GitHub pull request number")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--base", help="Local base branch or ref")
    parser.add_argument("--repo", help="GitHub owner/repository")
    parser.add_argument("--dry-run", action="store_true", help="Analyze but do not publish to GitHub")
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    return parser


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    provider = OllamaProvider(model=settings.model_name)
    gateway = ModelGateway(provider)
    repository = args.repository.resolve()
    analyzer = RepositoryContextAnalyzer(
        repository,
        max_files=settings.reviewer_max_files,
        max_file_size=settings.reviewer_max_file_size,
        max_context_chars=settings.reviewer_max_context_chars,
    )
    github: GitHubClient | None = None
    if args.local:
        context = LocalGitCollector(repository).collect(base=args.base)
    else:
        token = settings.github_token
        repo = args.repo or settings.github_repository
        if not token or not repo:
            raise ValueError("GITHUB_TOKEN and GITHUB_REPOSITORY are required for GitHub mode")
        github = GitHubClient(token, settings.github_api_url)
        context = await github.collect_pull_request(repo, args.pull_request)

    report = await ReviewPipeline(
        analyzer, gateway, max_findings=settings.reviewer_max_findings
    ).review(context)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "pr-review.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "pr-review.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    if github is not None:
        await github.publish_review(context, report, dry_run=args.dry_run)
    return 0


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(run(args)))

if __name__ == "__main__":
    main()