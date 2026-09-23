import ast
import re
from pathlib import Path

from app.pr_reviewer.models import ChangedFile, ImpactAnalysis, PRContext
from app.pr_reviewer.security import redact_secrets


class RepositoryContextAnalyzer:
    """Select focused repository context and derive deterministic relationships."""

    _SYMBOL_PATTERN = re.compile(
        r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", re.MULTILINE
    )
    _IMPORT_PATTERN = re.compile(r"(?:from|import)\s+([\w.]+)")

    def __init__(
        self,
        repository: Path,
        max_files: int = 40,
        max_file_size: int = 120_000,
        max_context_chars: int = 400_000,
    ) -> None:
        self.repository = repository
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.max_context_chars = max_context_chars

    def impact(self, context: PRContext) -> ImpactAnalysis:
        changed_symbols = sorted(
            {
                symbol
                for item in context.files
                for symbol in self._defined_symbols(item.content)
            }
        )
        related_files = self.select_files(context)
        changed_paths = {item.path for item in context.files}
        callers = self._find_callers(changed_symbols, changed_paths)
        tests = [path for path in related_files if self._is_test(path)]
        configuration = [
            path
            for path in related_files
            if self._is_configuration(path)
            or path.startswith(".github/")
        ]
        configuration.extend(
            path
            for item in context.files
            for path in self._referenced_configuration(item.content)
            if path not in configuration
        )
        dependency_changes = [
            item.path
            for item in context.files
            if item.path.endswith(("pyproject.toml", "requirements.txt", "poetry.lock"))
        ]
        return ImpactAnalysis(
            changed_symbols=changed_symbols,
            related_files=related_files,
            callers=sorted(callers),
            callees=self._imports(context.files),
            interfaces=self._interfaces(context.files),
            tests=tests,
            configuration=configuration,
            dependency_changes=dependency_changes,
        )

    def select_files(self, context: PRContext) -> list[str]:
        changed = [item.path for item in context.files]
        candidates = set(changed)
        for item in context.files:
            for imported in self._import_modules(item.content):
                relative = self._module_path(imported)
                if (self.repository / relative).exists():
                    candidates.add(relative)
            stem = Path(item.path).stem
            candidates.update(
                str(path.relative_to(self.repository))
                for path in self.repository.rglob(f"test_{stem}.py")
                if path.is_file()
            )
        candidates.update(
            path
            for path in ("pyproject.toml", "requirements.txt", ".env.example")
            if (self.repository / path).exists()
        )
        return sorted(candidates, key=lambda path: (path not in changed, path))[: self.max_files]

    def build_context(self, context: PRContext, impact: ImpactAnalysis) -> str:
        chunks = [
            "PR METADATA:\n" + redact_secrets(context.metadata.model_dump_json()),
            "COMMITS:\n" + redact_secrets(
                "\n".join(f"{item.sha[:12]} {item.message}" for item in context.commits)
            ),
            "IMPACT ANALYSIS:\n" + redact_secrets(impact.model_dump_json()),
            "DIFF:\n" + redact_secrets(context.diff),
        ]
        selected = set(impact.related_files)
        for item in context.files:
            if item.path in selected:
                chunks.append(
                    f"FILE {item.path} ({item.status})\n"
                    + redact_secrets(item.content[: self.max_file_size])
                )
        for path in impact.related_files:
            if path in {item.path for item in context.files}:
                continue
            file_path = self.repository / path
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")[: self.max_file_size]
                except (OSError, UnicodeDecodeError):
                    continue
                chunks.append(f"RELATED FILE {path}\n{redact_secrets(content)}")
        return "\n\n".join(chunks)[: self.max_context_chars]

    def _imports(self, files: list[ChangedFile]) -> list[str]:
        imports: set[str] = set()
        for item in files:
            try:
                tree = ast.parse(item.content)
            except SyntaxError:
                imports.update(self._fallback_imports(item.content))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.update(f"{node.module}.{alias.name}" for alias in node.names)
        return sorted(imports)

    @staticmethod
    def _fallback_imports(content: str) -> set[str]:
        imports: set[str] = set()
        for line in content.splitlines():
            from_match = re.match(
                r"\s*from\s+([\w.]+)\s+import\s+(.+)", line
            )
            if from_match:
                module, names = from_match.groups()
                imports.update(
                    f"{module}.{name.strip().split(' as ', 1)[0]}"
                    for name in names.split(",")
                )
                continue
            import_match = re.match(r"\s*import\s+(.+)", line)
            if import_match:
                imports.update(
                    name.strip().split(" as ", 1)[0]
                    for name in import_match.group(1).split(",")
                )
        return imports

    @staticmethod
    def _interfaces(files: list[ChangedFile]) -> list[str]:
        interfaces: set[str] = set()
        for item in files:
            try:
                tree = ast.parse(item.content)
            except SyntaxError:
                interfaces.update(
                    parent
                    for parent in re.findall(
                        r"class\s+\w+\(([^)]+)\)", item.content
                    )
                )
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    interfaces.update(
                        base.id
                        if isinstance(base, ast.Name)
                        else ast.unparse(base)
                        for base in node.bases
                    )
        return sorted(interfaces)

    def _find_callers(
        self, symbols: list[str], changed_paths: set[str]
    ) -> set[str]:
        callers: set[str] = set()
        for path in self._python_files():
            relative = str(path.relative_to(self.repository))
            if relative in changed_paths:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            names = {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
            }
            attributes = {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
            }
            if any(symbol in names or symbol in attributes for symbol in symbols):
                callers.add(relative)
        return callers

    def _defined_symbols(self, content: str) -> set[str]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return set(self._SYMBOL_PATTERN.findall(content))
        return {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }

    def _import_modules(self, content: str) -> set[str]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return set(self._IMPORT_PATTERN.findall(content))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        return modules

    @staticmethod
    def _module_path(module: str) -> str:
        return module.replace(".", "/") + ".py"

    def _python_files(self) -> list[Path]:
        return [
            path
            for path in self.repository.rglob("*.py")
            if ".venv" not in path.parts and "__pycache__" not in path.parts
        ]

    @staticmethod
    def _is_configuration(path: str) -> bool:
        return path.endswith(
            ("pyproject.toml", "requirements.txt", ".env", ".env.example")
        ) or "/config" in path or path.startswith("config/")

    def _referenced_configuration(self, content: str) -> set[str]:
        if re.search(r"(?i)(get_settings|BaseSettings|os\.getenv|environ|getenv)", content):
            return {
                str(path.relative_to(self.repository))
                for path in self.repository.rglob("*config*.py")
                if path.is_file()
            }
        return set()

    @staticmethod
    def _is_test(path: str) -> bool:
        return path.startswith("tests/") or Path(path).name.startswith("test_")
