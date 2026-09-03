from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


class ConfigurationExamplesTest(unittest.TestCase):
    def test_json_examples_are_valid_and_neutral(self) -> None:
        for path in sorted(CONFIG.glob("*.json.example")):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, re.compile(r"https?://|webhook|token|secret|password", re.I))

    def test_expected_shapes(self) -> None:
        esp32 = json.loads((CONFIG / "esp32_settings.json.example").read_text())
        self.assertEqual(set(esp32), {"host", "port", "enabled"})
        self.assertIsInstance(esp32["host"], str)
        self.assertGreaterEqual(esp32["port"], 1)
        self.assertLessEqual(esp32["port"], 65535)
        self.assertFalse(esp32["enabled"])

        assignments = json.loads(
            (CONFIG / "esp32_button_categories.json.example").read_text()
        )
        self.assertEqual(len(assignments["assignments"]), 3)

    def test_diff_contains_no_secret_or_webhook(self) -> None:
        diff = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--", "."],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=False,
        ).stdout
        diff = diff.decode("utf-8", errors="replace")
        candidate_text = diff + "\n" + "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(CONFIG.glob("*.example"))
        )
        self.assertNotRegex(
            candidate_text,
            re.compile(r"https?://[^\s]*webhook|(?:secret|token|password)\s*[:=]\s*[^\s]+", re.I),
        )


if __name__ == "__main__":
    unittest.main()
