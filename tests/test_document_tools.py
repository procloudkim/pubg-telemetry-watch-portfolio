from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import quote

from tools.export_architecture import check_image, export


class DocumentToolsTest(unittest.TestCase):
    def test_upward_edge_ends_at_lower_boundary_of_target(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.drawio"
            source.write_text(
                """<mxfile><diagram id="D01"><mxGraphModel><root>
<mxCell id="a" vertex="1"><mxGeometry x="0" y="200" width="200" height="100"/></mxCell>
<mxCell id="b" vertex="1"><mxGeometry x="300" y="0" width="200" height="100"/></mxCell>
<mxCell id="e" edge="1" source="a" target="b"/>
</root></mxGraphModel></diagram></mxfile>""",
                encoding="utf-8",
            )
            export(source)
            self.assertIn(
                "M100.0 200.0 L400.0 100.0", source.with_name("D01.svg").read_text(encoding="utf-8")
            )

    def test_document_id_cannot_escape_export_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.drawio"
            source.write_text(
                '<mxfile><diagram id="../outside" name="test"/></mxfile>', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "diagram ID"):
                export(source)
            self.assertEqual(list(root.iterdir()), [source])

    def test_embedded_icons_cannot_load_remote_or_active_content(self):
        check_image(
            "data:image/svg+xml,"
            + quote('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
        )
        check_image(
            "data:image/svg+xml,"
            + quote(
                "<svg><defs><style>.st0 {fill: none;} .st1 {fill: #4285f4;}</style></defs></svg>"
            )
        )
        unsafe = ["https://example.invalid/icon.svg"]
        unsafe += [
            "data:image/svg+xml," + quote(value)
            for value in (
                "<svg><script>alert(1)</script></svg>",
                '<svg onload="alert(1)"/>',
                '<svg><use href="https://example.invalid/icon.svg"/></svg>',
                '<svg><path fill="url(https://example.invalid/icon.svg)"/></svg>',
                '<svg xml:base="https://example.invalid/"><use href="#a"/></svg>',
                '<svg><path style="fill:red"/></svg>',
                '<svg><style>@import "https://example.invalid/style.css";</style></svg>',
                "<svg><style>.st0 {fill: url(https://example.invalid/icon.svg);}</style></svg>",
            )
        ]
        for uri in unsafe:
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                check_image(uri)

    def test_optimized_python_cannot_report_unchecked_walkthrough_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not-created"
            child = subprocess.run(
                [sys.executable, "-O", "tools/operations_walkthrough.py", "--output", str(output)],
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertNotEqual(child.returncode, 0)
            self.assertIn("WALKTHROUGH_REQUIRES_ASSERTIONS", child.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
