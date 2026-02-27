import unittest

from jarvis.core import handle_request


def base_req():
    return {
        "version": "1.0",
        "trace_id": "test-1",
        "mode": "awake",
        "input": {"type": "text", "text": "朝にして"},
        "player_context": {
            "player_name": "Steve",
            "is_multiplayer": False,
            "is_op": True,
            "world": "overworld",
        },
        "policy": {
            "execution_mode": "suggest",
            "permission_preset": "Normal",
        },
    }


class TestCore(unittest.TestCase):
    def test_command_detection(self):
        res = handle_request(base_req())
        self.assertTrue(res["ok"])
        self.assertEqual(res["intent"], "minecraft_command")
        self.assertEqual(res["command"], "/time set day")
        self.assertTrue(res["requires_confirm"])

    def test_limit_exceeded(self):
        req = base_req()
        req["limits"] = {"requested_value": 11, "limit": 10}
        res = handle_request(req)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "LIMIT_EXCEEDED")

    def test_permission_denied_auto_non_op(self):
        req = base_req()
        req["player_context"]["is_multiplayer"] = True
        req["player_context"]["is_op"] = False
        req["policy"]["execution_mode"] = "auto"
        res = handle_request(req)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "PERMISSION_DENIED")

    def test_invalid_request(self):
        req = base_req()
        del req["policy"]
        res = handle_request(req)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
