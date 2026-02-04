import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import ADMIN_PASSWORD, LOGS_DIR, SUBMISSIONS_DIR

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
        "is_admin": True,
    })


# ---- Logs ----

@router.get("/logs")
async def list_logs(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    dates = []
    if LOGS_DIR.exists():
        for f in sorted(LOGS_DIR.glob("*.jsonl"), reverse=True):
            dates.append(f.stem)

    return templates.TemplateResponse("admin_logs.html", {
        "request": request,
        "dates": dates,
        "entries": None,
        "selected_date": None,
        "event_filter": "",
        "is_admin": True,
    })


@router.get("/logs/{date}")
async def view_log(request: Request, date: str, event: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    logfile = LOGS_DIR / f"{date}.jsonl"
    entries = []
    if logfile.exists():
        for line in logfile.read_text().strip().split("\n"):
            if not line:
                continue
            try:
                entry = json.loads(line)
                if event and entry.get("event") != event:
                    continue
                entries.append(entry)
            except Exception:
                continue
    entries.reverse()

    dates = []
    if LOGS_DIR.exists():
        for f in sorted(LOGS_DIR.glob("*.jsonl"), reverse=True):
            dates.append(f.stem)

    return templates.TemplateResponse("admin_logs.html", {
        "request": request,
        "dates": dates,
        "entries": entries,
        "selected_date": date,
        "event_filter": event,
        "is_admin": True,
    })
