import unittest

from jarvis.core import handle_request


class TestContract(unittest.TestCase):
    def setUp(self):
        self.req = {
            "version": "1.0",
            "trace_id": "contract-1",
            "input": {"type": "text", "text": "hello"},
            "player_context": {"is_multiplayer": False, "is_op": True},
        }

    def test_response_required_fields(self):
        res = handle_request(self.req)
        required = {
            "version",
            "trace_id",
            "ok",
            "type",
            "message",
            "action",
            "confidence",
            "reason_code",
            "error_code",
            "latency_ms",
        }
        self.assertTrue(required.issubset(set(res.keys())))

    def test_missing_player_context(self):
        req = dict(self.req)
        del req["player_context"]
        res = handle_request(req)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
