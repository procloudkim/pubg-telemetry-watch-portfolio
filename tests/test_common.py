import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common import api_key


class ApiKeyTest(unittest.TestCase):
    def test_blank_dotenv_falls_back_to_process_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("PUBG_API_KEY=  \n", encoding="utf-8")
            with (
                patch("src.adapters.credentials.ROOT", root),
                patch.dict(os.environ, {"PUBG_API_KEY": "env-key"}, clear=True),
            ):
                self.assertEqual(api_key(), "env-key")

    def test_blank_dotenv_and_environment_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("PUBG_API_KEY=  \n", encoding="utf-8")
            with (
                patch("src.adapters.credentials.ROOT", root),
                patch.dict(os.environ, {}, clear=True),
            ):
                with self.assertRaisesRegex(SystemExit, "PUBG_API_KEY 없음"):
                    api_key()


if __name__ == "__main__":
    unittest.main()
