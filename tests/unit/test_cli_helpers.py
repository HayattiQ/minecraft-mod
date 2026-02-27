import tempfile
import unittest
from pathlib import Path

from jarvis.cli import _extract_output_text, _parse_dotenv


class TestCliHelpers(unittest.TestCase):
    def test_parse_dotenv(self):
        with tempfile.TemporaryDirectory() as td:
            env = Path(td) / ".env.local"
            env.write_text(
                "# comment\nOPENAI_API_KEY=sk-test\nEMPTY=\nQUOTED='abc'\n", encoding="utf-8"
            )
            parsed = _parse_dotenv(env)
            self.assertEqual(parsed["OPENAI_API_KEY"], "sk-test")
            self.assertEqual(parsed["EMPTY"], "")
            self.assertEqual(parsed["QUOTED"], "abc")

    def test_extract_output_text_prefers_output_text(self):
        resp = {"output_text": "hello"}
        self.assertEqual(_extract_output_text(resp), "hello")

    def test_extract_output_text_from_output_content(self):
        resp = {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": "line1"},
                        {"type": "output_text", "text": "line2"},
                    ]
                }
            ]
        }
        self.assertEqual(_extract_output_text(resp), "line1\nline2")


if __name__ == "__main__":
    unittest.main()
