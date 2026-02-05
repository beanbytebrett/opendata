import os
from pathlib import Path
from uuid import uuid4

import pyarrow.parquet as pq
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.admin import router as admin_router
from app.telemetry import TelemetryMiddleware, handle_beacon, log_form_submission, maintain_logs

app = FastAPI(title="OpenData Exchange", docs_url=None, redoc_url=None)
app.include_router(admin_router)

base_dir = Path(__file__).parent
data_dir = base_dir.parent / "data"
public_data_dir = data_dir / "public"

app.mount("/static", StaticFiles(directory=base_dir / "static"), name="static")
templates = Jinja2Templates(directory=base_dir / "templates")

app.add_middleware(TelemetryMiddleware)


# ---- Dataset store ----

class DatasetStore:
    """Manages Parquet datasets with mtime-based refresh."""

    def __init__(self, data_dir: Path):
        self._dir = data_dir
        self._meta: dict[str, dict] = {}
        self._data: dict[str, list[dict]] = {}
        self._index: dict[str, dict[str, dict]] = {}

    def scan(self) -> dict[str, dict]:
        """Re-scan directory, reload metadata for changed files."""
        current_files = {}
        if self._dir.exists():
            for f in sorted(self._dir.glob("*.parquet")):
                current_files[f.stem] = f

        # Remove datasets whose files are gone
        for name in list(self._meta.keys()):
            if name not in current_files:
                self._meta.pop(name, None)
                self._data.pop(name, None)
                self._index.pop(name, None)

        # Add/update metadata for each file
        for name, f in current_files.items():
            mtime = os.path.getmtime(f)
            existing = self._meta.get(name)
            if existing and existing["mtime"] == mtime:
                continue
            try:
                pf = pq.ParquetFile(f)
                schema = pf.schema_arrow
                self._meta[name] = {
                    "name": name,
                    "file": f,
                    "mtime": mtime,
                    "num_rows": pf.metadata.num_rows,
                    "columns": [
                        {"name": field.name, "type": str(field.type)}
                        for field in schema
                    ],
                }
                # Invalidate cached data so it reloads on next access
                self._data.pop(name, None)
                self._index.pop(name, None)
            except Exception:
                continue
        return self._meta

    def get_meta(self, name: str) -> dict | None:
        self.scan()
        return self._meta.get(name)

    def get_records(self, name: str) -> list[dict] | None:
        meta = self.get_meta(name)
        if not meta:
            return None
        if name not in self._data:
            table = pq.read_table(meta["file"])
            cols = table.column_names
            rows = table.to_pydict()
            self._data[name] = [
                {col: rows[col][i] for col in cols}
                for i in range(table.num_rows)
            ]
            self._index[name] = {}
            for row in self._data[name]:
                row_id = row.get("id")
                if row_id is not None:
                    self._index[name][str(row_id)] = row
        return self._data[name]

    def get_record_by_id(self, name: str, record_id: str) -> dict | None:
        self.get_records(name)
        idx = self._index.get(name)
        if idx is None:
            return None
        return idx.get(record_id)


datasets = DatasetStore(public_data_dir)


@app.on_event("startup")
async def _startup():
    datasets.scan()
    maintain_logs()  # Compress old logs, delete expired logs


# ---- Page routes ----

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/takedown")
async def takedown_get(request: Request):
    return templates.TemplateResponse("takedown.html", {"request": request})


@app.post("/takedown")
async def takedown_post(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    date_of_birth: str = Form(...),
    street_address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    zip_code: str = Form(...),
    country: str = Form(...),
    ssn_last4: str = Form(""),
    gov_id: str = Form(""),
    data_description: str = Form(...),
    discovery_method: str = Form(""),
    comments: str = Form(""),
):
    fields = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "date_of_birth": date_of_birth,
        "street_address": street_address,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "country": country,
        "ssn_last4": ssn_last4,
        "gov_id": gov_id,
        "data_description": data_description,
        "discovery_method": discovery_method,
        "comments": comments,
    }
    log_form_submission(request, "takedown", fields)
    ref = uuid4().hex[:12].upper()
    return templates.TemplateResponse(
        "takedown.html",
        {"request": request, "success": True, "reference_id": ref},
    )


@app.get("/brokers")
async def brokers_get(request: Request):
    return templates.TemplateResponse("brokers.html", {"request": request})


@app.post("/brokers")
async def brokers_post(
    request: Request,
    company_name: str = Form(...),
    contact_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    website: str = Form(""),
    categories: list[str] = Form(default=[]),
    volume: str = Form(""),
    use_case: str = Form(...),
):
    fields = {
        "company_name": company_name,
        "contact_name": contact_name,
        "email": email,
        "phone": phone,
        "website": website,
        "categories": categories,
        "volume": volume,
        "use_case": use_case,
    }
    log_form_submission(request, "broker_inquiry", fields)
    ref = uuid4().hex[:12].upper()
    return templates.TemplateResponse(
        "brokers.html",
        {"request": request, "success": True, "reference_id": ref},
    )


@app.get("/api-access")
async def api_access_get(request: Request):
    return templates.TemplateResponse("api_access.html", {"request": request})


@app.post("/api-access")
async def api_access_post(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    organization: str = Form(""),
    role: str = Form(""),
    intended_use: str = Form(...),
    project_description: str = Form(...),
    api_volume: str = Form(""),
):
    fields = {
        "full_name": full_name,
        "email": email,
        "organization": organization,
        "role": role,
        "intended_use": intended_use,
        "project_description": project_description,
        "api_volume": api_volume,
    }
    log_form_submission(request, "api_access", fields)
    ref = uuid4().hex[:12].upper()
    return templates.TemplateResponse(
        "api_access.html",
        {"request": request, "success": True, "reference_id": ref},
    )


# ---- Telemetry beacon ----

@app.post("/cdn/pixel.gif")
async def beacon(request: Request):
    return await handle_beacon(request)


# ---- Dataset API ----

@app.get("/api/v1/datasets")
async def list_datasets():
    datasets.scan()
    return [
        {
            "name": ds["name"],
            "num_rows": ds["num_rows"],
            "columns": ds["columns"],
        }
        for ds in datasets._meta.values()
    ]


@app.get("/api/v1/datasets/{name}")
async def get_dataset(name: str):
    meta = datasets.get_meta(name)
    if not meta:
        return JSONResponse({"error": "Dataset not found"}, status_code=404)
    return {
        "name": meta["name"],
        "num_rows": meta["num_rows"],
        "columns": meta["columns"],
    }


@app.get("/api/v1/datasets/{name}/records")
async def get_dataset_records(name: str, limit: int = 100, offset: int = 0):
    records = datasets.get_records(name)
    if records is None:
        return JSONResponse({"error": "Dataset not found"}, status_code=404)

    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    total = len(records)
    sliced = records[offset:offset + limit]

    return {
        "name": name,
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(sliced),
        "records": sliced,
    }


@app.get("/api/v1/datasets/{name}/records/{record_id}")
async def get_dataset_record(name: str, record_id: str):
    record = datasets.get_record_by_id(name, record_id)
    if record is None:
        meta = datasets.get_meta(name)
        if not meta:
            return JSONResponse({"error": "Dataset not found"}, status_code=404)
        return JSONResponse({"error": "Record not found"}, status_code=404)
    return {"name": name, "record": record}


# ---- Health check ----

@app.get("/health")
async def health():
    return {"status": "healthy"}
