import os
from pathlib import Path
import tempfile
import unittest

from tools.sql_inventory import inventory, validate_contracts
from tools.offline_check import verify_namespace


class SqlInventoryTest(unittest.TestCase):
    def test_detects_dynamic_calls_embedded_scripts_and_document_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("src", "tests", "tools", "sql", "docs"):
                (root / name).mkdir()
            (root / "src/sample.py").write_text("""def f(db, query):
    db.execute(query, (1,))
    db.execute("SELECT 1")
script = 'db.execute("SELECT 2")'
""")
            (root / "sql/schema.sql").write_text("CREATE TABLE t (n INTEGER);\nSELECT * FROM t;\n")
            (root / "README.md").write_text("```sql\nSELECT 3;\n```\n")
            first = inventory(root)
            self.assertEqual(first["counts"]["call_sites"], 3)
            self.assertTrue(any(r["kind"] == "example" for r in first["entries"]))
            self.assertTrue(any("embedded" in r["symbol"] for r in first["entries"]))
            (root / "src/sample.py").write_text(
                'class Reader:\n    def fetch(self, db):\n        db.execute("SELECT 4")\n'
            )
            second = inventory(root)
            self.assertNotEqual(first, second)
            self.assertEqual(second["entries"][0]["source"], "README.md")
            self.assertTrue(any(row["symbol"] == "Reader.fetch" for row in second["entries"]))

    def test_offline_check_rejects_unchanged_namespace(self):
        with self.assertRaisesRegex(RuntimeError, "NETWORK_NAMESPACE_NOT_ISOLATED"):
            verify_namespace(os.readlink("/proc/self/ns/net"))

    def test_contract_ownership_is_complete_disjoint_and_local(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/sql/operations").mkdir(parents=True)
            (root / "docs/sql/operations/batch.md").write_text("Batch SQL", encoding="utf-8")
            contract = dict.fromkeys(
                (
                    "purpose",
                    "grain_keys",
                    "null_duplicates",
                    "transaction",
                    "indexes",
                    "verification",
                ),
                "documented",
            )
            body = {"entries": [{"contract": "one"}]}
            contracts = {"one": contract, "two": contract}
            owners = {"operations/batch.md": ["one", "two"]}
            validate_contracts(body, contracts, owners, root)
            for invalid in (
                {"operations/batch.md": ["one"]},
                {"operations/batch.md": ["one", "two", "one"]},
                {"../outside.md": ["one", "two"]},
            ):
                with self.subTest(owners=invalid), self.assertRaises(ValueError):
                    validate_contracts(body, contracts, invalid, root)
            with self.assertRaisesRegex(ValueError, "Missing contract"):
                validate_contracts(
                    {"entries": [{"contract": "UNASSIGNED"}]}, contracts, owners, root
                )


if __name__ == "__main__":
    unittest.main()
