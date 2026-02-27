import json
import subprocess
import sys
import unittest


class TestModBridgeStyle(unittest.TestCase):
    def test_process_builder_style_roundtrip(self):
        req = {
            "version": "1.0",
            "trace_id": "bridge-1",
            "input": {"type": "text", "text": "hello"},
            "player_context": {"is_multiplayer": False, "is_op": True},
        }

        proc = subprocess.Popen(
            [sys.executable, "-m", "jarvis.cli"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(json.dumps(req), timeout=3)
        self.assertEqual(proc.returncode, 0, msg=stderr)

        out = json.loads(stdout.strip())
        self.assertEqual(out["trace_id"], "bridge-1")
        self.assertIn("message", out)


if __name__ == "__main__":
    unittest.main()
