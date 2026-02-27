"""Core request handler for Jarvis CLI."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Tuple

from jarvis import errors

VERSION = "1.0"
ALLOWED_MODES = {"idle", "awake"}
ALLOWED_INPUT_TYPES = {"text", "audio_ref"}


def _required(d: Dict[str, Any], key: str) -> bool:
    return key in d and d[key] is not None


def _validate_request(req: Dict[str, Any]) -> Tuple[bool, str | None]:
    if not _required(req, "version"):
        return False, "missing version"
    if not _required(req, "trace_id"):
        return False, "missing trace_id"
    if req.get("mode") not in ALLOWED_MODES:
        return False, "invalid mode"

    input_obj = req.get("input")
    if not isinstance(input_obj, dict):
        return False, "missing input"
    if input_obj.get("type") not in ALLOWED_INPUT_TYPES:
        return False, "invalid input.type"
    if input_obj.get("type") == "text" and not isinstance(input_obj.get("text"), str):
        return False, "text input requires text"
    if input_obj.get("type") == "audio_ref":
        audio_ref = input_obj.get("audio_ref")
        if not isinstance(audio_ref, str) or not audio_ref.strip():
            return False, "audio_ref input requires audio_ref path"
        if not Path(audio_ref).exists():
            return False, "audio_ref file does not exist"

    if not isinstance(req.get("player_context"), dict):
        return False, "missing player_context"
    if not isinstance(req.get("policy"), dict):
        return False, "missing policy"

    return True, None


def _base_response(trace_id: str) -> Dict[str, Any]:
    return {
        "version": VERSION,
        "trace_id": trace_id,
        "ok": True,
        "type": "reply",
        "message": "",
        "intent": None,
        "command": None,
        "requires_confirm": False,
        "error_code": None,
        "latency_ms": 0,
    }


def _error_response(trace_id: str, code: str, message: str) -> Dict[str, Any]:
    res = _base_response(trace_id)
    res["ok"] = False
    res["type"] = "error"
    res["message"] = message
    res["error_code"] = code
    return res


def handle_request(req: Dict[str, Any]) -> Dict[str, Any]:
    start = time.perf_counter()
    trace_id = req.get("trace_id", "unknown") if isinstance(req, dict) else "unknown"

    if not isinstance(req, dict):
        res = _error_response(trace_id, errors.INVALID_REQUEST, "request must be a JSON object")
        res["latency_ms"] = int((time.perf_counter() - start) * 1000)
        return res

    ok, reason = _validate_request(req)
    if not ok:
        res = _error_response(trace_id, errors.INVALID_REQUEST, f"invalid request: {reason}")
        res["latency_ms"] = int((time.perf_counter() - start) * 1000)
        return res

    limits = req.get("limits") or {}
    requested_value = limits.get("requested_value")
    limit = limits.get("limit")
    if isinstance(requested_value, (int, float)) and isinstance(limit, (int, float)) and requested_value > limit:
        res = _error_response(
            trace_id,
            errors.LIMIT_EXCEEDED,
            "上限を超過しているため処理を実行できません。入力値を調整して再実行してください。",
        )
        res["latency_ms"] = int((time.perf_counter() - start) * 1000)
        return res

    player = req["player_context"]
    policy = req["policy"]

    is_multiplayer = bool(player.get("is_multiplayer", False))
    is_op = bool(player.get("is_op", False))
    execution_mode = policy.get("execution_mode", "suggest")

    if is_multiplayer and not is_op and execution_mode == "auto":
        res = _error_response(trace_id, errors.PERMISSION_DENIED, "権限不足のため自動実行はできません。")
        res["latency_ms"] = int((time.perf_counter() - start) * 1000)
        return res

    res = _base_response(trace_id)
    input_obj = req.get("input", {})
    input_type = input_obj.get("type")
    text = (input_obj.get("text") or "").strip()

    if req.get("mode") == "idle":
        res["message"] = "IDLE mode: wake word detector is managed by Mod side."
        res["intent"] = "idle_status"
    elif input_type == "audio_ref":
        res["message"] = f"音声入力を受信しました: {input_obj.get('audio_ref')}"
        res["intent"] = "audio_received"
    elif "朝" in text or "/time set day" in text:
        res["message"] = "朝に変更します。"
        res["intent"] = "minecraft_command"
        res["command"] = "/time set day"
        res["requires_confirm"] = execution_mode != "auto"
    elif text:
        res["message"] = f"受信しました: {text}"
        res["intent"] = "chat"
    else:
        res["message"] = "入力が空です。"
        res["intent"] = "chat"

    res["latency_ms"] = int((time.perf_counter() - start) * 1000)
    return res
