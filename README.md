## Ops-Pilot

Ops-Pilot provides structured job-description, resume, job-matching, and resume-tailoring agents. It also includes a production-oriented pull-request reviewer.

### Pull request review

Run a review against the current local branch without GitHub credentials:

```bash
source .venv/bin/activate
python -m app.pr_reviewer --local --dry-run
```

The reviewer writes `reports/pr-review.json` and `reports/pr-review.md`. See [docs/pr-reviewer.md](docs/pr-reviewer.md) for GitHub Actions, security, configuration, and troubleshooting.
