import json
import os
import unittest
from pathlib import Path
from urllib import error, request

from jarvis.cli import _multipart_body, _resolve_api_key
from jarvis.core import handle_request

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "online"


class TestVoiceOnlineE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_online = os.getenv("RUN_ONLINE_E2E") == "1"
        cls.api_key = os.getenv("OPENAI_API_KEY") or _resolve_api_key()
        if not cls.run_online:
            raise unittest.SkipTest("RUN_ONLINE_E2E != 1")
        if not cls.api_key:
            raise unittest.SkipTest("OPENAI_API_KEY is not set")

    def transcribe(self, wav_path: Path) -> str:
        body, content_type = _multipart_body({"model": "gpt-4o-mini-transcribe"}, "file", wav_path)
        req = request.Request(
            url="https://api.openai.com/v1/audio/transcriptions",
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": content_type,
            },
            data=body,
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            self.fail(f"transcription API error: {detail}")
        except error.URLError as e:
            self.fail(f"network error during transcription: {e.reason}")
        return (payload.get("text") or "").strip()

    def test_audio_fixtures_action_routing(self):
        # Ordered by the user's recording sequence in OneDrive folder.
        cases = [
            ("01.wav", "execute", "/time set day"),
            ("02.wav", "reject", None),
            ("03.wav", "confirm", None),
            ("04.wav", "execute", "/time set day"),
            ("05.wav", "execute", "/time set day"),
            ("06.wav", "reject", None),
            ("07.wav", "reject", None),
            ("08.wav", "confirm", None),
            ("09.wav", "confirm", None),
            ("10.wav", "reject", None),
        ]

        for filename, expected_action, expected_command in cases:
            wav_path = FIXTURE_DIR / filename
            self.assertTrue(wav_path.exists(), f"missing fixture: {wav_path}")

            transcript = self.transcribe(wav_path)
            req = {
                "version": "1.0",
                "trace_id": f"online-{filename}",
                "input": {"type": "text", "text": transcript},
                "player_context": {"is_multiplayer": False, "is_op": True},
            }
            out = handle_request(req)

            with self.subTest(file=filename, transcript=transcript):
                self.assertEqual(out["action"], expected_action)
                if expected_command is None:
                    self.assertIsNone(out["command"])
                else:
                    self.assertEqual(out["command"], expected_command)


if __name__ == "__main__":
    unittest.main()
