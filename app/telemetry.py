import json
import threading
import time
import urllib.request
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from pathlib import Path

from app.config import LOGS_DIR, SLACK_WEBHOOK_URL, SUBMISSIONS_DIR

# 1x1 transparent GIF
_PIXEL = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
    b"\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)


_log_lock = threading.Lock()


def emit_event(event_type: str, data: dict) -> None:
    record = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event_type,
        **data,
    }
    line = json.dumps(record, default=str)
    print(line, flush=True)
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        logfile = LOGS_DIR / f"{time.strftime('%Y-%m-%d', time.gmtime())}.jsonl"
        with _log_lock:
            with open(logfile, "a") as f:
                f.write(line + "\n")
    except Exception:
        pass


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


_MAX_BODY_LOG = 10000  # Max bytes to log for POST bodies


class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        sid = request.cookies.get("_sid")
        new_session = sid is None
        if new_session:
            sid = uuid.uuid4().hex

        ip = _get_client_ip(request)

        request.state.sid = sid
        request.state.ip = ip

        # Capture POST/PUT/PATCH body for logging
        body_text = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_text = body_bytes[:_MAX_BODY_LOG].decode("utf-8", errors="replace")
                    if len(body_bytes) > _MAX_BODY_LOG:
                        body_text += f"... [truncated, {len(body_bytes)} bytes total]"
            except Exception:
                body_text = "[error reading body]"

        response = await call_next(request)

        # Skip logging for internal health checks
        if request.url.path == "/health" and ip == "127.0.0.1":
            return response

        duration_ms = (time.perf_counter() - start) * 1000

        if new_session:
            response.set_cookie(
                "_sid",
                sid,
                httponly=True,
                samesite="lax",
                max_age=86400 * 365,
                path="/",
            )
            emit_event("session_start", {"sid": sid, "ip": ip})

        event_data = {
            "sid": sid,
            "ip": ip,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query),
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "user_agent": request.headers.get("user-agent", ""),
            "referer": request.headers.get("referer", ""),
            "accept_language": request.headers.get("accept-language", ""),
        }
        if body_text:
            event_data["body"] = body_text

        emit_event("request", event_data)

        return response


def _notify_slack(form_name: str, ip: str, fields: dict) -> None:
    if not SLACK_WEBHOOK_URL:
        return
    try:
        lines = [f"*New {form_name} submission*", f"IP: `{ip}`"]
        for k, v in fields.items():
            if v:
                label = k.replace("_", " ").title()
                val = ", ".join(v) if isinstance(v, list) else v
                lines.append(f"*{label}:* {val}")
        payload = json.dumps({"text": "\n".join(lines)}).encode()
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        emit_event("slack_error", {"error": str(e)})


def _save_submission(form_name: str, record: dict) -> None:
    try:
        SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        filename = f"{form_name}_{ts}_{uuid.uuid4().hex[:8]}.json"
        path = SUBMISSIONS_DIR / filename
        path.write_text(json.dumps(record, indent=2, default=str))
    except Exception as e:
        emit_event("save_error", {"error": str(e)})


def log_form_submission(request: Request, form_name: str, fields: dict) -> None:
    record = {
        "sid": request.state.sid,
        "ip": request.state.ip,
        "form": form_name,
        "path": request.url.path,
        "user_agent": request.headers.get("user-agent", ""),
        "referer": request.headers.get("referer", ""),
        "fields": fields,
    }
    emit_event("form_submission", record)
    _save_submission(form_name, {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **record,
    })
    threading.Thread(
        target=_notify_slack,
        args=(form_name, request.state.ip, fields),
        daemon=True,
    ).start()


async def handle_beacon(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception:
        body = {}

    emit_event(
        "beacon",
        {
            "sid": request.state.sid,
            "ip": request.state.ip,
            "user_agent": request.headers.get("user-agent", ""),
            "payload": body,
        },
    )

    return Response(
        content=_PIXEL,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache"},
    )
