import json
import subprocess
import sys
import unittest


class TestCliE2E(unittest.TestCase):
    def run_cli(self, payload: str):
        proc = subprocess.run(
            [sys.executable, "-m", "jarvis.cli"],
            input=payload,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(proc.stdout.strip())

    def test_success(self):
        payload = json.dumps(
            {
                "version": "1.0",
                "trace_id": "e2e-1",
                "mode": "awake",
                "input": {"type": "text", "text": "朝にして"},
                "player_context": {"is_multiplayer": False, "is_op": True},
                "policy": {"execution_mode": "suggest", "permission_preset": "Normal"},
            }
        )
        out = self.run_cli(payload)
        self.assertTrue(out["ok"])
        self.assertEqual(out["command"], "/time set day")

    def test_invalid_json(self):
        out = self.run_cli("{bad json")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error_code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
