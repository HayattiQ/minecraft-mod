"""CLI entrypoint for Jarvis core."""

from __future__ import annotations

import json
import sys

from jarvis import errors
from jarvis.core import handle_request


def main() -> int:
    raw = sys.stdin.read()
    trace_id = "unknown"

    try:
        req = json.loads(raw)
        if isinstance(req, dict) and req.get("trace_id"):
            trace_id = req["trace_id"]
    except json.JSONDecodeError:
        req = {
            "trace_id": trace_id,
        }
        response = {
            "version": "1.0",
            "trace_id": trace_id,
            "ok": False,
            "type": "error",
            "message": "invalid JSON input",
            "intent": None,
            "command": None,
            "requires_confirm": False,
            "error_code": errors.INVALID_REQUEST,
            "latency_ms": 0,
        }
        print(json.dumps(response, ensure_ascii=False))
        return 0

    try:
        response = handle_request(req)
    except Exception:
        response = {
            "version": "1.0",
            "trace_id": trace_id,
            "ok": False,
            "type": "error",
            "message": "internal error",
            "intent": None,
            "command": None,
            "requires_confirm": False,
            "error_code": errors.INTERNAL_ERROR,
            "latency_ms": 0,
        }

    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
