from app.pr_reviewer.models import ReviewFinding, ReviewReport


def render_markdown(report: ReviewReport) -> str:
    """Render a stable human-readable report for local files or GitHub comments."""
    lines = [
        "# Ops-Pilot PR Review",
        "",
        f"**Status:** {report.status.value}",
        f"**Risk:** {report.risk.value}",
        f"**Files analyzed:** {report.files_analyzed}",
        f"**Findings:** {len(report.findings)}",
        "",
        report.context_summary,
        "",
        "## Findings",
    ]
    if not report.findings:
        lines.append("No evidence-backed findings were identified.")
    for index, finding in enumerate(report.findings, 1):
        lines.extend(_finding_lines(index, finding))
    for title, values in (
        ("Testing gaps", report.testing_gaps),
        ("Deployment concerns", report.deployment_concerns),
        ("Merge concerns", report.merge_concerns),
        ("Recommended verification", report.recommended_verification),
    ):
        if values:
            lines.extend(["", f"## {title}"])
            lines.extend(f"- {value}" for value in values)
    lines.extend(["", "<!-- ops-pilot-pr-review -->"])
    return "\n".join(lines)


def _finding_lines(index: int, finding: ReviewFinding) -> list[str]:
    location = finding.file or "summary"
    if finding.line is not None:
        location += f":{finding.line}"
    return [
        "",
        f"### {index}. [{finding.severity.value}] {finding.title}",
        f"- **Category:** {finding.category}",
        f"- **Location:** `{location}`",
        f"- **Confidence:** {finding.confidence:.2f}",
        f"- **Problem:** {finding.problem}",
        f"- **Why it matters:** {finding.why_it_matters}",
        f"- **Evidence:** {finding.evidence}",
        f"- **Suggested fix:** {finding.suggested_fix}",
    ]
