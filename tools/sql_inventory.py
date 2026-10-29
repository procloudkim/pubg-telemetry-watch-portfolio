"""Inventory SQL call sites, literals, scripts and dynamic helper callers. No DB writes."""

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/sql/inventory.json"
SQL = re.compile(
    r"^\s*(?:SELECT\b|WITH\b|INSERT\s+INTO\b|UPDATE\s+\w+\s+SET\b|DELETE\s+FROM\b|CREATE\s+(?:TEMP\s+)?(?:TABLE|INDEX|VIEW|TRIGGER)\b|PRAGMA\b|BEGIN\b|COMMIT\b)",
    re.I,
)
METHODS = {"execute", "executemany", "executescript"}
HELPERS = {"_row", "_group_rows", "read"}

# Each concrete persistence operation belongs to exactly one existing SQL contract.
STORE_CONTRACTS = {
    "begin": "connection",
    "batch": "batch-read",
    "add_batch": "registration",
    "job": "registration",
    "add_job": "registration",
    "link_job": "registration",
    "recover": "recovery",
    "next_attempt": "processing",
    "claim": "processing",
    "project": "processing",
    "add_measures": "processing",
    "add_signals": "processing",
    "add_case": "processing",
    "succeed": "processing",
    "fail": "processing",
    "record_timing": "processing",
    "queued_jobs": "work",
    "retry": "retry",
    "jobs": "status",
    "attempts": "status",
    "review_list": "review-read",
    "review_evidence": "review-read",
    "review_history": "review-read",
    "review_case": "review-write",
    "next_review_sequence": "review-write",
    "change_review": "review-write",
    "report_rows": "report",
}


def inventory(root=ROOT):
    rows = []

    def add(path, symbol, line, kind, expression, parameters="none"):
        domain = "audit" if "audit" in str(path) else "ops"
        if str(path).startswith("tests/") or kind == "example":
            contract = "test"
        elif path.suffix == ".sql":
            contract = (
                domain + "-schema"
                if not expression.lstrip().upper().startswith("WITH")
                else "ops-compute"
            )
        elif symbol.startswith("SQLiteStore."):
            contract = STORE_CONTRACTS.get(symbol.split(".")[1], "UNASSIGNED")
        elif symbol == "SQLiteAudit.calculate":
            contract = "audit-load"
        elif symbol.split(".")[0] in {"_row", "_group_rows", "_insert_rows", "audit_run"}:
            contract = (
                "audit-read" if symbol.split(".")[0] in {"_row", "_group_rows"} else "audit-load"
            )
        else:
            contract = {
                "connect": "connection",
                "register": "registration",
                "_batch": "batch-read",
                "recover": "recovery",
                "_process": "processing",
                "sql_measures": "ops-compute",
                "work": "work",
                "retry_job": "retry",
                "status": "status",
                "_report_batch": "report",
                "main": "cli",
                "benchmark": "benchmark",
                "synthetic_results": "benchmark",
                "query_plan": "benchmark",
                "review_list": "review-read",
                "review_show": "review-read",
                "review_change": "review-write",
                "walkthrough": "backup",
            }.get(symbol.split(".")[0], "UNASSIGNED")
        rows.append(
            {
                "source": str(path),
                "symbol": symbol,
                "line": line,
                "kind": kind,
                "sql_or_expression": expression,
                "bindings": parameters,
                "contract": contract,
            }
        )

    def scan(path, source, prefix="", offset=0):
        tree = ast.parse(source)
        query_literals = {
            id(value)
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in METHODS
            and call.args
            for value in ast.walk(call.args[0])
            if isinstance(value, ast.Constant)
        }

        class Visitor(ast.NodeVisitor):
            symbol = prefix or "<module>"

            def visit_FunctionDef(self, node):
                before = self.symbol
                self.symbol = (before + "." if before != "<module>" else "") + node.name
                self.generic_visit(node)
                self.symbol = before

            visit_AsyncFunctionDef = visit_FunctionDef
            visit_ClassDef = visit_FunctionDef

            def visit_Call(self, node):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", "")
                )
                is_helper = name in {"_row", "_group_rows"} or (
                    name == "read"
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self"
                    and str(path).startswith("tests/")
                )
                if (name in METHODS or is_helper) and node.args:
                    expression = ast.get_source_segment(source, node.args[0]) or ast.unparse(
                        node.args[0]
                    )
                    bindings = ", ".join(ast.unparse(arg) for arg in node.args[1:]) or "none"
                    add(
                        path,
                        self.symbol,
                        node.lineno + offset,
                        "call" if name in METHODS else "helper-call",
                        expression,
                        bindings,
                    )
                self.generic_visit(node)

            def visit_Constant(self, node):
                if isinstance(node.value, str):
                    if SQL.match(node.value) and (
                        node.value.upper() not in {"BEGIN", "COMMIT"} or id(node) in query_literals
                    ):
                        add(path, self.symbol, node.lineno + offset, "literal", node.value)
                    elif re.search(r"\b(?:execute|executemany|executescript)\(", node.value):
                        try:
                            scan(
                                path,
                                node.value,
                                self.symbol + ".embedded",
                                node.lineno + offset - 1,
                            )
                        except SyntaxError:
                            raise ValueError(
                                f"Unparsed embedded SQL script: {path}:{node.lineno}"
                            ) from None

        Visitor().visit(tree)

    for folder in ("src", "tests", "tools"):
        for path in sorted((root / folder).rglob("*.py")):
            if path.name != "sql_inventory.py":
                scan(path.relative_to(root), path.read_text(encoding="utf-8"))
    for path in sorted((root / "sql").rglob("*.sql")):
        buffer, start = "", 1
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(True), 1):
            if not buffer and (not line.strip() or line.lstrip().startswith("--")):
                start = number + 1
                continue
            buffer += line
            if sqlite3.complete_statement(buffer):
                add(path.relative_to(root), "<script>", start, "statement", buffer.strip())
                buffer, start = "", number + 1
        if buffer.strip():
            raise ValueError(f"Incomplete SQL: {path}")
    # Public examples can introduce queries without introducing Python call sites.
    for path in [root / "README.md", *sorted((root / "docs").rglob("*.md"))]:
        if path.is_relative_to(root / "docs/sql"):
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"```sql\s*\n(.*?)```", text, re.S):
            add(
                path.relative_to(root),
                "<example>",
                text[: match.start()].count("\n") + 1,
                "example",
                match.group(1).strip(),
            )
    rows.sort(key=lambda row: (row["source"], row["line"], row["kind"], row["sql_or_expression"]))
    for i, row in enumerate(rows, 1):
        row["id"] = f"SQL-{i:03d}"
        row["sha256"] = hashlib.sha256(row["sql_or_expression"].encode()).hexdigest()
    queries = {
        re.sub(r"\s+", " ", row["sql_or_expression"]).strip()
        for row in rows
        if row["kind"] in {"literal", "statement", "example"}
    }
    return {
        "counts": {
            "call_sites": sum(row["kind"] == "call" for row in rows),
            "helper_calls": sum(row["kind"] == "helper-call" for row in rows),
            "distinct_static_texts": len(queries),
            "entries": len(rows),
        },
        "note": "Call sites and static texts are different counts; dynamic SQL is described by its contract.",
        "entries": rows,
    }


def validate_contracts(body, contracts, owners, root=ROOT):
    """Every source entry has a contract, and every contract has exactly one document owner."""
    for row in body["entries"]:
        if row["contract"] not in contracts:
            raise ValueError("Missing contract: " + row["contract"])
    assigned = Counter(contract for group in owners.values() for contract in group)
    if set(assigned) != set(contracts) or any(count != 1 for count in assigned.values()):
        raise ValueError("SQL owners must partition all contracts exactly once")
    for owner in owners:
        path = (root / "docs/sql" / owner).resolve()
        if not path.is_relative_to((root / "docs/sql").resolve()) or not path.is_file():
            raise ValueError("Invalid SQL owner document: " + owner)
    required = {
        "purpose",
        "grain_keys",
        "null_duplicates",
        "transaction",
        "indexes",
        "verification",
    }
    for contract in contracts.values():
        if not required.issubset(contract) or any(not contract[key] for key in required):
            raise ValueError("Incomplete SQL contract")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    body = inventory()
    contracts = json.loads((OUTPUT.parent / "contracts.json").read_text(encoding="utf-8"))
    owners = json.loads((OUTPUT.parent / "owners.json").read_text(encoding="utf-8"))
    validate_contracts(body, contracts, owners)
    rendered = json.dumps(body, ensure_ascii=False, indent=2) + "\n"
    lines = [
        "# SQL source inventory",
        "",
        "Generated by `python tools/sql_inventory.py`; CI checks exact source coverage.",
        "",
        "Each entry carries its SQL/expression and bindings in [inventory.json](inventory.json).",
        "Purpose, grain, keys, NULL/duplicate semantics, transaction, indexes and verification are",
        "resolved through its named [contract](contracts.json); [guide](README.md) describes dynamic expansions.",
        "",
        "`" + json.dumps(body["counts"]) + "`",
        "",
        "| ID | Source / symbol | Kind | Contract |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {r['id']} | [{r['source']}:{r['line']}](../../{r['source']}#L{r['line']}) · `{r['symbol']}` | {r['kind']} | `{r['contract']}` |"
        for r in body["entries"]
    ]
    markdown = "\n".join(lines) + "\n"
    if args.check:
        if (
            OUTPUT.read_text(encoding="utf-8") != rendered
            or OUTPUT.with_suffix(".md").read_text(encoding="utf-8") != markdown
        ):
            raise SystemExit("SQL_INVENTORY_STALE: python tools/sql_inventory.py")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(rendered, encoding="utf-8")
        OUTPUT.with_suffix(".md").write_text(markdown, encoding="utf-8")
    print(json.dumps(body["counts"]))


if __name__ == "__main__":
    main()
