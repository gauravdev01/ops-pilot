from pathlib import Path

from app.pr_reviewer.analyzer import RepositoryContextAnalyzer
from app.pr_reviewer.models import ChangedFile, PRContext, PRMetadata


def create_context(files: list[ChangedFile]) -> PRContext:
    return PRContext(
        metadata=PRMetadata(
            title="Analyzer test",
            description="A secret=do-not-leak",
            source_branch="feature",
            target_branch="main",
        ),
        files=files,
        diff="API_KEY=do-not-leak",
    )


def test_impact_reports_dependency_changes_and_config_references(
    tmp_path: Path,
) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "config.py").write_text(
        "class Settings: pass\n", encoding="utf-8"
    )
    requirements = ChangedFile(
        path="requirements.txt",
        status="modified",
        content="fastapi\n",
    )
    settings_user = ChangedFile(
        path="app/service.py",
        status="modified",
        content="from app.config import Settings\nsettings = Settings()\n",
    )

    impact = RepositoryContextAnalyzer(tmp_path).impact(
        create_context([requirements, settings_user])
    )

    assert impact.dependency_changes == ["requirements.txt"]
    assert "app/config.py" in impact.configuration


def test_impact_uses_fallback_parsing_for_invalid_python(tmp_path: Path) -> None:
    changed = ChangedFile(
        path="app/broken.py",
        status="modified",
        content=(
            "from app.helper import run\n"
            "class Broken(Base):\n"
            "    def changed(:\n"
        ),
    )

    impact = RepositoryContextAnalyzer(tmp_path).impact(create_context([changed]))

    assert "Broken" in impact.changed_symbols
    assert "app.helper.run" in impact.callees
    assert "Base" in impact.interfaces


def test_build_context_redacts_secrets_and_respects_character_limit(
    tmp_path: Path,
) -> None:
    changed = ChangedFile(
        path="app/service.py",
        status="modified",
        content="TOKEN=super-secret\n" + ("x" * 500),
    )
    analyzer = RepositoryContextAnalyzer(tmp_path, max_context_chars=180)
    context = create_context([changed])
    impact = analyzer.impact(context)

    review_context = analyzer.build_context(context, impact)

    assert "super-secret" not in review_context
    assert "do-not-leak" not in review_context
    assert len(review_context) <= 180


def test_impact_excludes_changed_files_from_callers(tmp_path: Path) -> None:
    changed = ChangedFile(
        path="app/service.py",
        status="modified",
        content="def changed():\n    return 1\nchanged()\n",
    )
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "service.py").write_text(
        changed.content, encoding="utf-8"
    )

    impact = RepositoryContextAnalyzer(tmp_path).impact(create_context([changed]))

    assert "app/service.py" not in impact.callers
