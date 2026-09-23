from enum import StrEnum

from pydantic import BaseModel, Field


class ReviewSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ReviewStatus(StrEnum):
    APPROVE = "APPROVE"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ChangedFile(BaseModel):
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    patch: str = ""
    content: str = ""
    base_content: str = ""
    is_binary: bool = False
    renamed_from: str | None = None


class CommitInfo(BaseModel):
    sha: str
    message: str
    author: str | None = None


class PRMetadata(BaseModel):
    number: int | None = None
    title: str
    description: str = ""
    source_branch: str
    target_branch: str
    author: str = ""
    labels: list[str] = Field(default_factory=list)
    repository: str | None = None
    mergeable: bool | None = None
    mergeable_state: str | None = None


class PRContext(BaseModel):
    metadata: PRMetadata
    files: list[ChangedFile] = Field(default_factory=list)
    commits: list[CommitInfo] = Field(default_factory=list)
    diff: str = ""
    base_sha: str | None = None
    head_sha: str | None = None
    merge_conflicts: list[str] = Field(default_factory=list)


class ImpactAnalysis(BaseModel):
    changed_symbols: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    callers: list[str] = Field(default_factory=list)
    callees: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    configuration: list[str] = Field(default_factory=list)
    dependency_changes: list[str] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    category: str
    severity: ReviewSeverity
    confidence: float = Field(ge=0, le=1)
    title: str
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    problem: str
    why_it_matters: str
    evidence: str
    suggested_fix: str
    tests_to_add: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    blocking: bool = False


class ReviewReport(BaseModel):
    status: ReviewStatus
    risk: ReviewSeverity
    files_analyzed: int
    findings: list[ReviewFinding] = Field(default_factory=list)
    testing_gaps: list[str] = Field(default_factory=list)
    deployment_concerns: list[str] = Field(default_factory=list)
    merge_concerns: list[str] = Field(default_factory=list)
    recommended_verification: list[str] = Field(default_factory=list)
    context_summary: str = ""


class LLMReviewResult(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)
    testing_gaps: list[str] = Field(default_factory=list)
    deployment_concerns: list[str] = Field(default_factory=list)
    merge_concerns: list[str] = Field(default_factory=list)
    recommended_verification: list[str] = Field(default_factory=list)
