import gzip
import hashlib
import hmac
import json
import time
from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import ADMIN_PASSWORD, LOGS_DIR, SUBMISSIONS_DIR
from app.telemetry import _get_client_ip

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

_TOKEN_TTL = 86400 * 7  # 7 days


def _make_token() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(ADMIN_PASSWORD.encode(), ts.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{ts}.{sig}"


def _verify_token(token: str) -> bool:
    if not ADMIN_PASSWORD or not token:
        return False
    parts = token.split(".", 1)
    if len(parts) != 2:
        return False
    ts, sig = parts
    try:
        if time.time() - int(ts) > _TOKEN_TTL:
            return False
    except ValueError:
        return False
    expected = hmac.new(ADMIN_PASSWORD.encode(), ts.encode(), hashlib.sha256).hexdigest()[:16]
    return hmac.compare_digest(sig, expected)


def _is_authed(request: Request) -> bool:
    return _verify_token(request.cookies.get("_admin", ""))


def _require_auth(request: Request):
    if not _is_authed(request):
        return RedirectResponse("/admin/login", status_code=303)
    return None


# ---- Auth routes ----

@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": None,
    })


@router.post("/login")
async def login_post(request: Request, password: str = Form(...)):
    if not ADMIN_PASSWORD:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Admin access is not configured.",
        })
    if not hmac.compare_digest(password, ADMIN_PASSWORD):
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Invalid password.",
        })
    response = RedirectResponse("/admin/submissions", status_code=303)
    response.set_cookie(
        "_admin", _make_token(),
        httponly=True, samesite="lax",
        max_age=_TOKEN_TTL, path="/admin",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie("_admin", path="/admin")
    return response


# ---- Submissions ----

@router.get("/submissions")
async def list_submissions(request: Request, form_type: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    submissions = []
    if SUBMISSIONS_DIR.exists():
        for f in sorted(SUBMISSIONS_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                if form_type and data.get("form") != form_type:
                    continue
                submissions.append({
                    "filename": f.name,
                    "form": data.get("form", ""),
                    "iso": data.get("iso", ""),
                    "ip": data.get("ip", ""),
                    "name": data.get("fields", {}).get("full_name")
                        or data.get("fields", {}).get("contact_name", ""),
                    "email": data.get("fields", {}).get("email", ""),
                })
            except Exception:
                continue

    return templates.TemplateResponse("admin_submissions.html", {
        "request": request,
        "submissions": submissions,
        "form_type": form_type,
        "client_ip": _get_client_ip(request),
        "is_admin": True,
    })


@router.get("/submissions/{filename}")
async def view_submission(request: Request, filename: str):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    path = SUBMISSIONS_DIR / filename
    if not path.exists() or not path.name.endswith(".json"):
        return RedirectResponse("/admin/submissions", status_code=303)

    data = json.loads(path.read_text())

    return templates.TemplateResponse("admin_submission_detail.html", {
        "request": request,
        "filename": filename,
        "data": data,
        "data_json": json.dumps(data, indent=2, default=str),
        "client_ip": _get_client_ip(request),
        "is_admin": True,
    })


# ---- Logs ----

def _get_log_dates() -> list[str]:
    """Get sorted list of available log dates (handles both .jsonl and .jsonl.gz)."""
    dates = set()
    if LOGS_DIR.exists():
        for f in LOGS_DIR.glob("*.jsonl"):
            dates.add(f.stem)
        for f in LOGS_DIR.glob("*.jsonl.gz"):
            dates.add(f.stem.replace(".jsonl", ""))
    return sorted(dates, reverse=True)


def _read_log_file(log_date: str) -> str | None:
    """Read log file content, trying uncompressed first, then compressed."""
    jsonl_path = LOGS_DIR / f"{log_date}.jsonl"
    gz_path = LOGS_DIR / f"{log_date}.jsonl.gz"

    if jsonl_path.exists():
        return jsonl_path.read_text()
    elif gz_path.exists():
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            return f.read()
    return None


@router.get("/logs")
async def list_logs(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    today = date.today().isoformat()
    if (LOGS_DIR / f"{today}.jsonl").exists():
        return RedirectResponse(f"/admin/logs/{today}", status_code=303)

    dates = _get_log_dates()

    return templates.TemplateResponse("admin_logs.html", {
        "request": request,
        "dates": dates,
        "entries": None,
        "selected_date": None,
        "event_filter": "",
        "status_filter": "",
        "client_ip": _get_client_ip(request),
        "is_admin": True,
    })


@router.get("/logs/{date}")
async def view_log(
    request: Request,
    date: str,
    event: str = "",
    status: str = "",
    page: int = 1,
    per_page: int = 50,
    sort: str = "ts",
    order: str = "desc",
):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    entries = []
    log_content = _read_log_file(date)
    if log_content:
        for line in log_content.strip().split("\n"):
            if not line:
                continue
            try:
                entry = json.loads(line)
                if event and entry.get("event") != event:
                    continue
                if status:
                    entry_status = entry.get("status")
                    if entry_status is None:
                        continue
                    if not str(entry_status).startswith(status[0]):
                        continue
                entries.append(entry)
            except Exception:
                continue

    # Sort
    reverse = order == "desc"
    entries.sort(key=lambda e: e.get(sort, ""), reverse=reverse)

    # Paginate
    per_page = max(10, min(per_page, 500))
    page = max(1, page)
    total = len(entries)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    entries = entries[start:start + per_page]

    dates = _get_log_dates()

    def paginate_url(p: int) -> str:
        params = f"?page={p}&per_page={per_page}&sort={sort}&order={order}"
        if event:
            params += f"&event={event}"
        if status:
            params += f"&status={status}"
        return f"/admin/logs/{date}{params}"

    return templates.TemplateResponse("admin_logs.html", {
        "request": request,
        "dates": dates,
        "entries": entries,
        "selected_date": date,
        "event_filter": event,
        "status_filter": status,
        "client_ip": _get_client_ip(request),
        "is_admin": True,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "sort": sort,
        "order": order,
        "paginate_url": paginate_url,
    })
