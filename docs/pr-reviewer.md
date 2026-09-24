# Ops-Pilot PR Reviewer

## Architecture

The reviewer is an isolated pipeline under `app/pr_reviewer`:

1. `LocalGitCollector` or `GitHubClient` collects PR metadata, commits, changed-file patches, base/head contents, renames, and binary markers.
2. `RepositoryContextAnalyzer` selects changed files, imports, callers, related tests, configuration, and dependency files. It performs deterministic symbol and impact scans before any model call.
3. Secret redaction removes common tokens, passwords, API keys, bearer credentials, and private keys from model context.
4. Specialized deterministic reviewers consume the same shared context for correctness, security, API, database, performance, concurrency, error handling, testing, architecture, dependencies, configuration, deployment, merge, and business-logic checks.
5. `ReviewPipeline` runs deterministic checks, sends one focused structured request to the configured model, validates locations and findings, deduplicates findings, and aggregates risk. Specialized reviewers never make separate LLM calls.
5. `report.py` writes JSON and Markdown. GitHub publishing updates one marked issue comment instead of spamming a pull request.

The existing Ops-Pilot agents and API routes are independent of this pipeline.

## Configuration

Copy `.env.example` to `.env` and configure:

- `MODEL_PROVIDER=local`
- `MODEL_NAME=qwen2.5:7b`
- `GITHUB_TOKEN` for GitHub mode
- `GITHUB_REPOSITORY=owner/repository`
- `GITHUB_API_URL` for GitHub Enterprise when needed
- `REVIEWER_MAX_FILES`, `REVIEWER_MAX_FILE_SIZE`, `REVIEWER_MAX_CONTEXT_CHARS`, and `REVIEWER_MAX_FINDINGS`

The current model integration is Ollama. GitHub Actions therefore requires a self-hosted runner with Ollama and the configured model available. The workflow checks out the trusted default branch and never executes PR code.

## Local development

From the repository root:

```bash
source .venv/bin/activate
python -m app.pr_reviewer --local --dry-run
```

Use `--base main` to select a different local base ref. Reports are written to `reports/pr-review.json` and `reports/pr-review.md`.

## GitHub mode and dry run

```bash
GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repository \
python -m app.pr_reviewer --pull-request 42 --repo owner/repository --dry-run
```

Without `--dry-run`, the reviewer publishes validated inline findings through GitHub's pull-request review API when the finding points to a changed file and valid changed line, then updates or creates one summary comment marked `ops-pilot-pr-review`. Inline comments carry stable finding markers so reruns do not duplicate them. Findings without exact locations remain in the summary only.

## Review categories and severity

The pipeline checks correctness, regression risk, security, API behavior, database concerns, performance, concurrency, error handling, testing, architecture, dependencies, configuration, observability, deployment, merge risk, and business logic. Deterministic checks run before the model review.

- `CRITICAL`: likely security catastrophe, data loss, or outage
- `HIGH`: strong production bug or serious security/data issue
- `MEDIUM`: meaningful pre-merge risk
- `LOW`: limited-impact issue
- `INFO`: observation or optional improvement

Only evidence-backed findings should block a merge. Unknown file paths and line numbers from the model are removed rather than published as inline locations.

## Security model

The workflow uses `pull_request`, not `pull_request_target`, checks out the trusted default branch, grants read access to contents, write access only to pull-request reviews and issue comments, and does not run changed PR code. Context is redacted before it is sent to the model, and tokens are never included in reports. `--dry-run` performs collection and analysis but skips all publishing requests.

## Troubleshooting

- If local collection fails, verify the base ref exists and the current branch has a merge base.
- If structured review fails, inspect the provider response and rerun with the same context; deterministic checks still appear in the report.
- If GitHub publishing fails, verify `GITHUB_TOKEN` has issue write permission and the repository identifier is `owner/name`.
- If reports are too large, reduce the reviewer context limits.

## Future phases

The current implementation provides Phase 1 collection/reporting, Phase 2 deterministic impact analysis, and Phase 3 shared-context specialized reviewers. Exact inline GitHub reviews, repository-analysis caching, and richer history/business-flow analysis can be added behind the existing typed pipeline contracts.
