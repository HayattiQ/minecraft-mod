import unittest

from jarvis.core import handle_request


def base_req():
    return {
        "version": "1.0",
        "trace_id": "test-1",
        "input": {"type": "text", "text": "朝にして"},
        "player_context": {
            "player_name": "Steve",
            "is_multiplayer": False,
            "is_op": True,
            "world": "overworld",
        },
    }


class TestCore(unittest.TestCase):
    def test_command_detection(self):
        res = handle_request(base_req())
        self.assertTrue(res["ok"])
        self.assertEqual(res["intent"], "minecraft_command")
        self.assertEqual(res["command"], "/time set day")
        self.assertEqual(res["action"], "execute")
        self.assertFalse(res["requires_confirm"])

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
        res = handle_request(req)
        self.assertFalse(res["ok"])
        self.assertEqual(res["intent"], "need_confirmation")
        self.assertEqual(res["action"], "confirm")
        self.assertEqual(res["reason_code"], "PERMISSION_RISK")

    def test_invalid_request(self):
        req = base_req()
        del req["player_context"]
        res = handle_request(req)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
