"""Keep dependency direction and complete runtime provenance executable."""

import ast
from pathlib import Path
import tempfile
import unittest

from src.adapters.files import ROOT
from src.adapters.provenance import fingerprint


def source_modules():
    return {
        ".".join(path.relative_to(ROOT).with_suffix("").parts).removesuffix(".__init__"): path
        for path in (ROOT / "src").rglob("*.py")
    }


def imports(module, path, modules):
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = (
                package.split(".")[: len(package.split(".")) - node.level + 1] if node.level else []
            )
            base = ".".join([*prefix, *([node.module] if node.module else [])])
            for alias in node.names:
                candidate = base + "." + alias.name
                yield candidate if candidate in modules else base


class ArchitectureTest(unittest.TestCase):
    def test_dependencies_point_inward_and_have_no_cycles(self):
        modules = source_modules()
        graph = {}
        external_io = {
            "argparse",
            "sqlite3",
            "requests",
            "rdflib",
            "pyshacl",
            "subprocess",
            "socket",
            "os",
            "sys",
            "time",
            "tempfile",
            "shutil",
            "uuid",
        }
        for module, path in modules.items():
            dependencies = set(imports(module, path, modules))
            graph[module] = dependencies & modules.keys()
            if module.startswith(("src.domain.", "src.application.")):
                for dependency in dependencies:
                    self.assertNotIn(dependency.split(".")[0], external_io, (module, dependency))
                    if dependency.startswith("src."):
                        allowed = (
                            ("src.domain",)
                            if module.startswith("src.domain.")
                            else ("src.domain", "src.application")
                        )
                        self.assertTrue(dependency.startswith(allowed), (module, dependency))
            if module.startswith(("src.adapters.", "src.cli.")):
                self.assertFalse(
                    any(
                        dep.startswith("src.")
                        and dep.count(".") == 1
                        and dep not in {"src.domain", "src.application", "src.adapters", "src.cli"}
                        for dep in dependencies
                    ),
                    (module, dependencies),
                )

        visited, active = set(), []

        def visit(module):
            self.assertNotIn(module, active, " -> ".join([*active, module]))
            if module in visited:
                return
            active.append(module)
            for target in graph[module]:
                visit(target)
            active.pop()
            visited.add(module)

        for module in graph:
            visit(module)

    def test_domain_has_no_resource_calls_and_application_uses_ports(self):
        resource_calls = {
            "open",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "exists",
            "is_file",
            "stat",
            "resolve",
            "glob",
            "rglob",
            "mkdir",
            "unlink",
            "connect",
            "execute",
            "executemany",
            "executescript",
            "now",
            "sleep",
        }
        for layer in ("domain", "application"):
            for path in (ROOT / "src" / layer).rglob("*.py"):
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    if not isinstance(node, ast.Call):
                        continue
                    name = (
                        node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else getattr(node.func, "id", "")
                    )
                    if name not in resource_calls:
                        continue
                    target = ast.unparse(node.func)
                    self.assertEqual(layer, "application", (path.name, target))
                    self.assertTrue(
                        target.startswith(("self.files.", "self.clock.", "self.engine.")),
                        (path.name, target),
                    )

    def test_fingerprint_includes_nested_runtime_and_sql_but_not_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src/domain/pubg").mkdir(parents=True)
            (root / "sql/nested").mkdir(parents=True)
            source = root / "src/domain/pubg/rule.py"
            source.write_text("VALUE = 1\n", encoding="utf-8")
            first = fingerprint(root)
            (root / "README.md").write_text("documentation", encoding="utf-8")
            self.assertEqual(first, fingerprint(root))
            source.write_text("VALUE = 2\n", encoding="utf-8")
            second = fingerprint(root)
            self.assertNotEqual(first, second)
            (root / "sql/nested/query.sql").write_text("SELECT 1;", encoding="utf-8")
            self.assertNotEqual(second, fingerprint(root))
