"""CLI entrypoint for Jarvis core."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from jarvis import errors
from jarvis.core import handle_request


def _error(trace_id: str, message: str, code: str) -> dict:
    return {
        "version": "1.0",
        "trace_id": trace_id,
        "ok": False,
        "type": "error",
        "message": message,
        "intent": None,
        "command": None,
        "action": "reject",
        "confidence": 0.0,
        "requires_confirm": False,
        "reason_code": "OUT_OF_SCOPE",
        "error_code": code,
        "latency_ms": 0,
    }


def _parse_dotenv(path: Path) -> dict:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _resolve_api_key() -> str | None:
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_API_KEY")
    root = Path(__file__).resolve().parent.parent
    for rel in [".env.local", ".env"]:
        parsed = _parse_dotenv(root / rel)
        if parsed.get("OPENAI_API_KEY"):
            return parsed["OPENAI_API_KEY"]
    return None


def _multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----jarvis-{uuid.uuid4().hex}"
    parts: list[bytes] = []

    for key, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    ctype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    data = file_path.read_bytes()
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode("utf-8")
    )
    parts.append(f"Content-Type: {ctype}\r\n\r\n".encode("utf-8"))
    parts.append(data)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _http_json(url: str, api_key: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url=url,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_multipart(url: str, api_key: str, body: bytes, content_type: str) -> dict:
    req = urllib.request.Request(
        url=url,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
        },
        data=body,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_output_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str) and response["output_text"].strip():
        return response["output_text"].strip()

    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _voice_mode(args: argparse.Namespace) -> int:
    api_key = _resolve_api_key()
    if not api_key:
        print("OPENAI_API_KEY is not set (.env.local or environment).", file=sys.stderr)
        return 1

    work_dir = Path(__file__).resolve().parent.parent / "artifacts" / "voice"
    work_dir.mkdir(parents=True, exist_ok=True)
    if args.audio_file:
        wav_path = Path(args.audio_file).expanduser().resolve()
        if not wav_path.exists():
            print(f"[jarvis] audio file not found: {wav_path}", file=sys.stderr)
            return 1
        print(f"[jarvis] using audio file: {wav_path}", flush=True)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        wav_path = work_dir / f"input-{stamp}.wav"

        record_cmd = [
            "arecord",
            "-f",
            "S16_LE",
            "-c",
            "1",
            "-r",
            "16000",
            "-d",
            str(args.seconds),
        ]
        if args.device:
            record_cmd.extend(["-D", args.device])
        record_cmd.append(str(wav_path))

        print(f"[jarvis] listening for {args.seconds}s...", flush=True)
        try:
            subprocess.run(record_cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            print("[jarvis] arecord not found. Please install ALSA tools.", file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            print(f"[jarvis] audio capture failed: {detail}", file=sys.stderr)
            return 1

    print("[jarvis] transcribing...", flush=True)
    try:
        body, ctype = _multipart_body({"model": args.stt_model}, "file", wav_path)
        stt = _http_multipart("https://api.openai.com/v1/audio/transcriptions", api_key, body, ctype)
        transcript = (stt.get("text") or "").strip()
        if not transcript:
            print("[jarvis] transcription returned empty text.", file=sys.stderr)
            return 1
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"[jarvis] transcription API error: {detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"[jarvis] network error during transcription: {e.reason}", file=sys.stderr)
        return 1

    print(f"[you] {transcript}", flush=True)
    print("[jarvis] thinking...", flush=True)

    payload = {
        "model": args.model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": args.system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": transcript}]},
        ],
    }
    try:
        resp = _http_json("https://api.openai.com/v1/responses", api_key, payload)
        answer = _extract_output_text(resp) or "(no response text)"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"[jarvis] LLM API error: {detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"[jarvis] network error during LLM call: {e.reason}", file=sys.stderr)
        return 1

    print(f"[jarvis] {answer}")
    return 0


def _json_mode() -> int:
    raw = sys.stdin.read()
    trace_id = "unknown"

    try:
        req = json.loads(raw)
        if isinstance(req, dict) and req.get("trace_id"):
            trace_id = req["trace_id"]
    except json.JSONDecodeError:
        response = _error(trace_id, "invalid JSON input", errors.INVALID_REQUEST)
        print(json.dumps(response, ensure_ascii=False))
        return 0

    try:
        response = handle_request(req)
    except Exception:
        response = _error(trace_id, "internal error", errors.INTERNAL_ERROR)

    print(json.dumps(response, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis CLI")
    parser.add_argument("--voice", action="store_true", help="Record voice and send to OpenAI")
    parser.add_argument("--audio-file", type=str, default=None, help="Use existing audio file instead of recording")
    parser.add_argument("--seconds", type=int, default=10, help="Audio capture duration in seconds")
    parser.add_argument("--device", type=str, default=None, help="ALSA device for arecord (e.g. plughw:0,0)")
    parser.add_argument("--stt-model", type=str, default="gpt-4o-mini-transcribe")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument(
        "--system-prompt",
        type=str,
        default="You are Jarvis, a concise Japanese voice assistant for Minecraft players.",
    )
    args = parser.parse_args(argv)

    if args.voice:
        if args.seconds <= 0:
            print("--seconds must be greater than 0", file=sys.stderr)
            return 2
        return _voice_mode(args)
    return _json_mode()


if __name__ == "__main__":
    raise SystemExit(main())
