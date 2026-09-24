from pathlib import Path

from app.pr_reviewer.analyzer import RepositoryContextAnalyzer
from app.pr_reviewer.models import ChangedFile, PRContext, PRMetadata

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pr_reviewer" / "repository"


def fixture_context() -> PRContext:
    changed_path = "app/domain/child.py"
    changed_content = (FIXTURE_ROOT / changed_path).read_text(encoding="utf-8")
    return PRContext(
        metadata=PRMetadata(
            title="Update child service",
            source_branch="feature/child",
            target_branch="main",
        ),
        files=[
            ChangedFile(
                path=changed_path,
                status="modified",
                content=changed_content,
            ),
            ChangedFile(
                path="requirements.txt",
                status="modified",
                base_content="fastapi==0.99.0\nhttpx==0.24.0\n",
                content=(FIXTURE_ROOT / "requirements.txt").read_text(),
            ),
        ],
    )


def test_package_resolution_finds_relative_imports_and_reexports() -> None:
    impact = RepositoryContextAnalyzer(FIXTURE_ROOT).impact(fixture_context())

    relationships = {(item.relationship, item.source, item.target) for item in impact.relationships}
    assert (
        "reexports",
        "app/domain/__init__.py",
        "app.domain.child.ChildService",
    ) in relationships
    assert any(item.relationship == "reexports" for item in impact.relationships)
    assert any(item.target.endswith("BaseService") for item in impact.relationships)


def test_symbol_impact_tracks_callers_subclasses_and_overrides() -> None:
    impact = RepositoryContextAnalyzer(FIXTURE_ROOT).impact(fixture_context())

    assert any(item.endswith("ChildService") for item in impact.changed_symbols)
    assert any(item.endswith("changed_function") for item in impact.changed_symbols)
    assert any(item.relationship == "subclass" for item in impact.relationships)
    assert any(item.relationship == "overrides" for item in impact.relationships)
    assert any(item.relationship == "test_caller" for item in impact.relationships)
    assert all(item.evidence and 0 < item.confidence <= 1 for item in impact.relationships)


def test_endpoint_impact_captures_route_registration_dependencies_and_models() -> None:
    impact = RepositoryContextAnalyzer(FIXTURE_ROOT).impact(fixture_context())

    endpoint = next(item for item in impact.endpoints if item.path == "/items")
    assert endpoint.method == "POST"
    assert endpoint.router == "router"
    assert "Depends" in endpoint.dependencies
    assert endpoint.request_models == ["ItemRequest"]
    assert endpoint.response_models == ["ItemResponse"]
    assert any(item.relationship == "router_registration" for item in impact.relationships)


def test_test_configuration_dependency_and_ranked_impact_are_retained() -> None:
    impact = RepositoryContextAnalyzer(FIXTURE_ROOT).impact(fixture_context())

    assert any(item.path.endswith("test_child.py") for item in impact.test_impacts)
    assert any(item.path == "app/config.py" and "SERVICE_URL" in item.variables for item in impact.configuration_impacts)
    assert impact.dependency_impacts[0].path == "requirements.txt"
    assert impact.dependency_impacts[0].removed == ["fastapi==0.99.0"]
    assert impact.dependency_impacts[0].added == ["fastapi==0.100.0"]
    assert impact.ranked_files[0].path in {"app/domain/child.py", "requirements.txt"}
    assert all(
        item.evidence and 0 < item.confidence <= 1
        for item in impact.ranked_files
        if item.score > 0
    )


def test_context_ranking_prefers_changed_files_and_includes_package_context() -> None:
    analyzer = RepositoryContextAnalyzer(FIXTURE_ROOT, max_files=5)
    selected = analyzer.select_files(fixture_context())

    assert selected[0] in {"app/domain/child.py", "requirements.txt"}
    assert "app/domain/__init__.py" in selected
    assert "tests/test_child.py" in selected
