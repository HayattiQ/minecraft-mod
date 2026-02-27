"""Core request handler for Jarvis CLI."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Tuple

from jarvis import errors

VERSION = "1.0"
ALLOWED_INPUT_TYPES = {"text", "audio_ref"}


def _required(d: Dict[str, Any], key: str) -> bool:
    return key in d and d[key] is not None


def _validate_request(req: Dict[str, Any]) -> Tuple[bool, str | None]:
    if not _required(req, "version"):
        return False, "missing version"
    if not _required(req, "trace_id"):
        return False, "missing trace_id"

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
        "action": "reject",
        "confidence": 0.0,
        "requires_confirm": False,
        "reason_code": "NONE",
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
        res["action"] = "reject"
        res["reason_code"] = "OUT_OF_SCOPE"
        res["latency_ms"] = int((time.perf_counter() - start) * 1000)
        return res

    player = req["player_context"]

    is_multiplayer = bool(player.get("is_multiplayer", False))
    is_op = bool(player.get("is_op", False))

    res = _base_response(trace_id)
    input_obj = req.get("input", {})
    input_type = input_obj.get("type")
    text = (input_obj.get("text") or "").strip()

    if input_type == "audio_ref":
        res["message"] = "音声を受け取りました。内容を確認して提案します。"
        res["intent"] = "audio_received"
        res["action"] = "confirm"
        res["confidence"] = 0.3
        res["requires_confirm"] = True
        res["reason_code"] = "AMBIGUOUS"
    elif "全部消して" in text or "全部壊して" in text or "destroy all" in text.lower():
        res["ok"] = False
        res["intent"] = "need_confirmation"
        res["message"] = "危ない操作なので、そのままは実行しません。範囲を指定してくれる？"
        res["command"] = None
        res["action"] = "confirm"
        res["confidence"] = 0.4
        res["requires_confirm"] = True
        res["reason_code"] = "UNSAFE"
        res["error_code"] = errors.PERMISSION_DENIED
    elif (
        "朝" in text
        or "/time set day" in text
        or "デイ" in text
        or "day" in text.lower()
    ):
        if is_multiplayer and not is_op:
            res["ok"] = False
            res["intent"] = "need_confirmation"
            res["message"] = "朝にする命令は了解。実行権限が足りないかも。OP権限を確認して。"
            res["command"] = None
            res["action"] = "confirm"
            res["confidence"] = 0.7
            res["requires_confirm"] = True
            res["reason_code"] = "PERMISSION_RISK"
            res["error_code"] = errors.PERMISSION_DENIED
        else:
            res["message"] = "了解。朝にします。"
            res["intent"] = "minecraft_command"
            res["command"] = "/time set day"
            res["action"] = "execute"
            res["confidence"] = 0.95
            res["requires_confirm"] = False
            res["reason_code"] = "NONE"
    elif text:
        if "気分" in text:
            res["message"] = "元気です。あなたはどう？"
        elif "こんにちは" in text:
            res["message"] = "こんにちは。今日は何をする？"
        elif "夜にして" in text or "昼にして" in text:
            res["message"] = "その時間変更はまだ対応していません。朝ならすぐできます。"
            res["action"] = "confirm"
            res["confidence"] = 0.6
            res["requires_confirm"] = True
            res["reason_code"] = "OUT_OF_SCOPE"
            res["intent"] = "need_confirmation"
            res["ok"] = False
            res["error_code"] = errors.ENGINE_UNAVAILABLE
        else:
            res["message"] = f"「{text}」了解。必要なら実行したい操作を具体的に教えて。"
        if res["intent"] is None:
            res["intent"] = "chat"
        if res["action"] == "reject":
            res["confidence"] = 0.9
            res["requires_confirm"] = False
            res["reason_code"] = "NONE"
    else:
        res["message"] = "音声をうまく認識できませんでした。もう一度、短くはっきり話してください。"
        res["intent"] = "chat"
        res["action"] = "reject"
        res["confidence"] = 0.1
        res["requires_confirm"] = False
        res["reason_code"] = "AMBIGUOUS"

    res["latency_ms"] = int((time.perf_counter() - start) * 1000)
    return res
