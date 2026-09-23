import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.pr_reviewer.models import (
    ChangedFile,
    ConfigurationImpact,
    DependencyImpact,
    EndpointImpact,
    ImpactAnalysis,
    ImpactEvidence,
    ImpactRelationship,
    PRContext,
    RankedFile,
    TestImpact,
)
from app.pr_reviewer.security import redact_secrets


@dataclass
class _Symbol:
    qualified: str
    name: str
    kind: str
    path: str
    line: int
    parent: str | None = None


@dataclass
class _Module:
    name: str
    path: str
    content: str
    tree: ast.Module | None
    symbols: list[_Symbol] = field(default_factory=list)
    imports: dict[str, str] = field(default_factory=dict)
    reexports: dict[str, str] = field(default_factory=dict)
    is_package: bool = False


class RepositoryContextAnalyzer:
    """Resolve repository relationships and rank review context deterministically."""

    _SYMBOL_PATTERN = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", re.MULTILINE)
    _IMPORT_PATTERN = re.compile(r"(?:from|import)\s+([\w.]+)")
    _ENV_PATTERN = re.compile(r"(?:os\.(?:getenv|environ\.get)|getenv)\(\s*[\"']([A-Z][A-Z0-9_]*)")

    def __init__(self, repository: Path, max_files: int = 40, max_file_size: int = 120_000, max_context_chars: int = 400_000) -> None:
        self.repository = repository
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.max_context_chars = max_context_chars
        self._modules: dict[str, _Module] = {}
        self._changed_content: dict[str, str] = {}

    def impact(self, context: PRContext) -> ImpactAnalysis:
        self._changed_content = {item.path: item.content for item in context.files}
        self._index_repository()
        changed_paths = set(self._changed_content)
        changed_symbols = self._changed_symbols(changed_paths)
        relationships = self._relationships(changed_symbols, changed_paths)
        endpoints = self._endpoints()
        test_impacts = self._test_impacts(changed_symbols, endpoints)
        configuration_impacts = self._configuration_impacts()
        dependency_impacts = self._dependency_impacts(context)
        ranked_files = self._rank_files(context, relationships, endpoints, test_impacts, configuration_impacts, dependency_impacts)
        return ImpactAnalysis(
            changed_symbols=sorted(changed_symbols | {item.rsplit(".", 1)[-1] for item in changed_symbols}),
            related_files=[item.path for item in ranked_files[: self.max_files]],
            callers=sorted({item.source for item in relationships if item.relationship in {"caller", "test_caller"}}),
            callees=sorted(
                {
                    *(
                        item.target
                        for item in relationships
                        if item.relationship in {"imports", "reexports", "callee"}
                    ),
                    *(value for item in context.files for value in self._fallback_imports(item.content)),
                }
            ),
            interfaces=sorted(
                {
                    *(
                        item.target
                        for item in relationships
                        if item.relationship in {"subclass", "overrides"}
                    ),
                    *(value for item in context.files for value in self._fallback_bases(item.content)),
                }
            ),
            tests=sorted({item.path for item in test_impacts}),
            configuration=sorted({item.path for item in configuration_impacts}),
            dependency_changes=sorted({item.path for item in dependency_impacts}),
            relationships=relationships,
            endpoints=endpoints,
            test_impacts=test_impacts,
            configuration_impacts=configuration_impacts,
            dependency_impacts=dependency_impacts,
            ranked_files=ranked_files,
        )

    def select_files(self, context: PRContext) -> list[str]:
        self._changed_content = {item.path: item.content for item in context.files}
        self._index_repository()
        changed_paths = set(self._changed_content)
        changed_symbols = self._changed_symbols(changed_paths)
        paths = self._rank_files(
            context,
            self._relationships(changed_symbols, changed_paths),
            self._endpoints(),
            self._test_impacts(changed_symbols, self._endpoints()),
            self._configuration_impacts(),
            self._dependency_impacts(context),
        )
        return [item.path for item in paths[: self.max_files]]

    def build_context(self, context: PRContext, impact: ImpactAnalysis) -> str:
        chunks = [
            "PR METADATA:\n" + redact_secrets(context.metadata.model_dump_json()),
            "COMMITS:\n" + redact_secrets("\n".join(f"{item.sha[:12]} {item.message}" for item in context.commits)),
            "RECENT HISTORY:\n" + redact_secrets("\n".join(f"{item.sha[:12]} {item.message}" for item in context.recent_history)),
            "IMPACT ANALYSIS:\n" + redact_secrets(impact.model_dump_json()),
            "DIFF:\n" + redact_secrets(context.diff),
        ]
        changed = {item.path: item for item in context.files}
        paths = impact.related_files or [item.path for item in impact.ranked_files]
        for path in paths:
            if path in changed:
                content = changed[path].content
            else:
                try:
                    content = (self.repository / path).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
            chunks.append(f"FILE {path}\n{redact_secrets(content[: self.max_file_size])}")
        return "\n\n".join(chunks)[: self.max_context_chars]

    def _index_repository(self) -> None:
        files: dict[str, str] = {}
        for path in self._python_files():
            relative = str(path.relative_to(self.repository))
            try:
                files[relative] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        files.update(self._changed_content)
        self._modules.clear()
        for path, content in files.items():
            try:
                tree = ast.parse(content)
            except SyntaxError:
                tree = None
            module = _Module(
                self._module_name(path),
                path,
                content,
                tree,
                is_package=path.endswith("/__init__.py") or path == "__init__.py",
            )
            self._modules[module.name] = module
            if tree is not None:
                self._extract(module)
            else:
                module.symbols = [
                    _Symbol(f"{module.name}.{name}", name, "unknown", path, 0)
                    for name in self._SYMBOL_PATTERN.findall(content)
                ]
                module.imports = {
                    item.rsplit(".", 1)[-1]: item
                    for item in self._fallback_imports(content)
                }
        for module in self._modules.values():
            module.imports = {
                local: self._resolve_import(module.name, target, module.is_package)
                for local, target in module.imports.items()
            }
            module.reexports = {
                local: self._resolve_import(module.name, target, module.is_package)
                for local, target in module.reexports.items()
            }

    def _extract(self, module: _Module) -> None:
        assert module.tree is not None
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module.imports[alias.asname or alias.name.split(".")[0]] = alias.name
            elif isinstance(node, ast.ImportFrom):
                base = "." * node.level + (node.module or "")
                for alias in node.names:
                    target = f"{base}:{alias.name}"
                    local = alias.asname or alias.name
                    module.imports[local] = target
                    if module.path.endswith("/__init__.py") or module.path == "__init__.py":
                        module.reexports[local] = target
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                parent = self._parent_class(module.tree, node)
                qualified = f"{module.name}.{node.name}" if parent is None else f"{module.name}.{parent}.{node.name}"
                module.symbols.append(_Symbol(qualified, node.name, "class" if isinstance(node, ast.ClassDef) else "function", module.path, node.lineno, parent))

    def _changed_symbols(self, paths: set[str]) -> set[str]:
        return {symbol.qualified for module in self._modules.values() if module.path in paths for symbol in module.symbols}

    def _relationships(self, changed: set[str], changed_paths: set[str]) -> list[ImpactRelationship]:
        names = {item.rsplit(".", 1)[-1] for item in changed}
        result: list[ImpactRelationship] = []
        for module in self._modules.values():
            if module.tree is None:
                continue
            is_changed = module.path in changed_paths
            for local, target in {**module.imports, **module.reexports}.items():
                resolved = self._resolve_reexport(target)
                if is_changed:
                    kind = "reexports" if local in module.reexports else "callee"
                    result.append(self._relationship(module.path, resolved, kind, f"changed-module binding {local}", 0.85))
                elif self._matches(resolved, changed, names):
                    kind = "reexports" if local in module.reexports else "imports"
                    result.append(self._relationship(module.path, resolved, kind, f"binding {local}", 0.9))
            for node in ast.walk(module.tree):
                if isinstance(node, ast.Call):
                    name = self._expr(node.func)
                    if name.endswith(".include_router") and node.args:
                        result.append(
                            self._relationship(
                                module.path,
                                self._expr(node.args[0]),
                                "router_registration",
                                f"router registration at line {node.lineno}",
                                0.9,
                            )
                        )
                    target = module.imports.get(name, self._local_symbol(module, name))
                    if target:
                        target = self._resolve_reexport(target)
                    if target and self._matches(target, changed, names) and not is_changed:
                        kind = "test_caller" if self._is_test(module.path) else "caller"
                        result.append(self._relationship(module.path, target, kind, f"call at line {node.lineno}", 0.85))
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        name = self._expr(base)
                        target = module.imports.get(name, name)
                        if self._matches(target, changed, names):
                            result.append(self._relationship(module.path, target, "subclass", f"{node.name} inherits {name} at line {node.lineno}", 0.8))
                    for method in [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                        if any(symbol.endswith(f".{node.name}.{method.name}") for symbol in changed):
                            result.append(self._relationship(module.path, f"{module.name}.{node.name}.{method.name}", "overrides", f"method {method.name} at line {method.lineno}", 0.7))
            if self._is_test(module.path):
                for name in names:
                    if re.search(rf"\b{re.escape(name)}\b", module.content):
                        result.append(self._relationship(module.path, name, "test_caller", "symbol appears in test source", 0.65))
        return self._unique(result)

    def _endpoints(self) -> list[EndpointImpact]:
        result: list[EndpointImpact] = []
        for module in self._modules.values():
            if module.tree is None:
                continue
            for node in ast.walk(module.tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute) or decorator.func.attr not in {"get", "post", "put", "patch", "delete", "options", "head"} or not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                        continue
                    result.append(EndpointImpact(method=decorator.func.attr.upper(), path=str(decorator.args[0].value), file=module.path, symbol=node.name, router=self._expr(decorator.func.value), dependencies=sorted({self._expr(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and self._expr(call.func) == "Depends"}), request_models=sorted({self._expr(arg.annotation) for index, arg in enumerate(node.args.args) if arg.annotation and not self._has_depends_default(node, index)}), response_models=sorted(self._keyword(decorator, "response_model")), evidence=[ImpactEvidence(source=module.path, detail=f"route decorator line {node.lineno}", confidence=0.95)], confidence=0.95))
        return result

    def _test_impacts(self, changed: set[str], endpoints: list[EndpointImpact]) -> list[TestImpact]:
        names = {item.rsplit(".", 1)[-1] for item in changed}
        changed_stems = {
            Path(module.path).stem
            for module in self._modules.values()
            if module.path in self._changed_content
        }
        result: list[TestImpact] = []
        for module in self._modules.values():
            if not self._is_test(module.path):
                continue
            symbols = sorted(name for name in names if re.search(rf"\b{re.escape(name)}\b", module.content))
            routes = sorted(endpoint.path for endpoint in endpoints if endpoint.path in module.content)
            filename_match = any(
                Path(module.path).stem == f"test_{stem}"
                for stem in changed_stems
            )
            if symbols or routes or filename_match:
                reason = "direct symbol or endpoint reference" if symbols or routes else "matching test module"
                confidence = 0.75 if symbols or routes else 0.65
                result.append(TestImpact(path=module.path, reason=reason, covered_symbols=symbols, covered_endpoints=routes, evidence=[ImpactEvidence(source=module.path, detail="test source reference" if symbols or routes else "test filename matches changed module", confidence=confidence)], confidence=confidence))
        return result

    def _configuration_impacts(self) -> list[ConfigurationImpact]:
        result: list[ConfigurationImpact] = []
        for module in self._modules.values():
            variables = sorted(set(self._ENV_PATTERN.findall(module.content)))
            variables.extend(sorted(set(re.findall(r"\bsettings\.([A-Za-z_]\w*)", module.content))))
            if variables or self._is_configuration(module.path) or module.path.startswith(".github/"):
                result.append(ConfigurationImpact(path=module.path, variables=variables, evidence=[ImpactEvidence(source=module.path, detail="configuration or deployment reference", confidence=0.85)], confidence=0.85))
        return result

    def _dependency_impacts(self, context: PRContext) -> list[DependencyImpact]:
        result: list[DependencyImpact] = []
        for item in context.files:
            if item.path.endswith(("requirements.txt", "pyproject.toml", "poetry.lock")):
                added, removed = self._line_delta(item.base_content, item.content)
                result.append(DependencyImpact(path=item.path, added=added, removed=removed, changed=sorted(set(added) & set(removed)), imported_modules=sorted(self._imports([item])), evidence=[ImpactEvidence(source=item.path, detail="dependency declaration changed", confidence=0.98)], confidence=0.98))
        return result

    def _rank_files(self, context: PRContext, relationships: list[ImpactRelationship], endpoints: list[EndpointImpact], tests: list[TestImpact], configs: list[ConfigurationImpact], dependencies: list[DependencyImpact]) -> list[RankedFile]:
        paths = {module.path for module in self._modules.values()} | {item.path for item in context.files}
        paths.update(
            path
            for path in ("pyproject.toml", "requirements.txt", ".env.example")
            if (self.repository / path).exists()
        )
        changed = {item.path for item in context.files}
        scores = {path: (1000.0 if path in changed else 0.0) for path in paths}
        reasons = {path: (["changed file"] if path in changed else []) for path in paths}
        evidence: dict[str, list[ImpactEvidence]] = {path: [] for path in paths}
        for item in relationships:
            scores[item.source] = scores.get(item.source, 0) + 30
            reasons.setdefault(item.source, []).append(item.relationship)
            evidence.setdefault(item.source, []).extend(item.evidence)
            target_path = self._symbol_path(item.target)
            if target_path:
                scores[target_path] = scores.get(target_path, 0) + 25
                reasons.setdefault(target_path, []).append("relationship target")
                evidence.setdefault(target_path, []).extend(item.evidence)
        for item in tests:
            scores[item.path] += 20
            reasons[item.path].append("test impact")
            evidence[item.path].extend(item.evidence)
        for item in configs:
            scores[item.path] += 15
            reasons[item.path].append("configuration impact")
            evidence[item.path].extend(item.evidence)
        for item in dependencies:
            scores[item.path] += 12
            reasons[item.path].append("dependency impact")
            evidence[item.path].extend(item.evidence)
        for item in endpoints:
            scores[item.file] += 25
            reasons[item.file].append("endpoint impact")
            evidence[item.file].extend(item.evidence)
        return [RankedFile(path=path, score=scores[path], reasons=sorted(set(reasons[path])), evidence=evidence[path], confidence=max((item.confidence for item in evidence[path]), default=1.0 if path in changed else 0.5)) for path in sorted(paths, key=lambda value: (-scores[value], value))]

    def _resolve_import(self, current: str, target: str, is_package: bool = False) -> str:
        if ":" not in target:
            return target
        relative, symbol = target.split(":", 1)
        level = len(relative) - len(relative.lstrip("."))
        module = relative.lstrip(".")
        if level == 0:
            return f"{module}.{symbol}" if module else symbol
        parts = current.split(".")
        package = parts if is_package else parts[:-1]
        base = package[: max(0, len(package) - level + 1)]
        resolved = ".".join([*base, module] if module else base)
        return f"{resolved}.{symbol}" if resolved else symbol

    def _resolve_reexport(self, target: str) -> str:
        module, _, symbol = target.rpartition(".")
        candidate = self._modules.get(module)
        if candidate and symbol in candidate.reexports:
            return self._resolve_reexport(candidate.reexports[symbol])
        return target

    def _local_symbol(self, module: _Module, name: str) -> str | None:
        matches = [item.qualified for item in module.symbols if item.name == name]
        return matches[0] if matches else None

    def _matches(self, target: str, changed: set[str], names: set[str]) -> bool:
        return target in changed or target.rsplit(".", 1)[-1] in names

    def _symbol_path(self, target: str) -> str | None:
        return next((module.path for module in self._modules.values() if any(item.qualified == target for item in module.symbols)), None)

    @staticmethod
    def _has_depends_default(
        node: ast.FunctionDef | ast.AsyncFunctionDef, index: int
    ) -> bool:
        defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(
            node.args.defaults
        )
        default = defaults[index]
        return isinstance(default, ast.Call) and RepositoryContextAnalyzer._expr(
            default.func
        ) == "Depends"
    @staticmethod
    def _relationship(source: str, target: str, kind: str, detail: str, confidence: float) -> ImpactRelationship:
        return ImpactRelationship(source=source, target=target, relationship=kind, evidence=[ImpactEvidence(source=source, detail=detail, confidence=confidence)], confidence=confidence)

    @staticmethod
    def _unique(items: list[ImpactRelationship]) -> list[ImpactRelationship]:
        seen: set[tuple[str, str, str]] = set()
        result: list[ImpactRelationship] = []
        for item in items:
            key = (item.source, item.target, item.relationship)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @staticmethod
    def _module_name(path: str) -> str:
        parts = Path(path).with_suffix("").parts
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)

    @staticmethod
    def _parent_class(tree: ast.Module, node: ast.AST) -> str | None:
        return next((parent.name for parent in ast.walk(tree) if isinstance(parent, ast.ClassDef) and node in parent.body), None)

    @staticmethod
    def _expr(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = RepositoryContextAnalyzer._expr(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ast.unparse(node)

    @staticmethod
    def _keyword(call: ast.Call, name: str) -> list[str]:
        return [RepositoryContextAnalyzer._expr(item.value) for item in call.keywords if item.arg == name]

    def _imports(self, files: list[ChangedFile]) -> list[str]:
        return sorted({item for file in files for item in self._fallback_imports(file.content)})

    def _fallback_imports(self, content: str) -> set[str]:
        result: set[str] = set()
        for line in content.splitlines():
            match = re.match(r"\s*from\s+([\w.]+)\s+import\s+(.+)", line)
            if match:
                result.update(f"{match.group(1)}.{name.strip().split(' as ', 1)[0]}" for name in match.group(2).split(","))
            else:
                match = re.match(r"\s*import\s+(.+)", line)
                if match:
                    result.update(name.strip().split(" as ", 1)[0] for name in match.group(1).split(","))
        return result

    def _fallback_bases(self, content: str) -> set[str]:
        return {
            base.strip()
            for base in re.findall(r"class\s+\w+\(([^)]+)\)", content)
            for base in base.split(",")
        }

    @staticmethod
    def _line_delta(base: str, current: str) -> tuple[list[str], list[str]]:
        return sorted(set(current.splitlines()) - set(base.splitlines())), sorted(set(base.splitlines()) - set(current.splitlines()))

    def _python_files(self) -> list[Path]:
        return [path for path in self.repository.rglob("*.py") if ".venv" not in path.parts and "__pycache__" not in path.parts]

    @staticmethod
    def _is_test(path: str) -> bool:
        return path.startswith("tests/") or Path(path).name.startswith("test_")

    @staticmethod
    def _is_configuration(path: str) -> bool:
        return path.endswith(("pyproject.toml", "requirements.txt", ".env", ".env.example")) or "/config" in path or path.startswith(("config/", ".github/"))
