from pathlib import Path
from uuid import uuid4

import pyarrow.parquet as pq
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.telemetry import TelemetryMiddleware, handle_beacon, log_form_submission

app = FastAPI(title="OpenData Exchange", docs_url=None, redoc_url=None)

base_dir = Path(__file__).parent
data_dir = base_dir.parent / "data"
public_data_dir = data_dir / "public"

app.mount("/static", StaticFiles(directory=base_dir / "static"), name="static")
templates = Jinja2Templates(directory=base_dir / "templates")

app.add_middleware(TelemetryMiddleware)


# ---- Dataset helpers ----

def _scan_datasets() -> dict:
    datasets = {}
    if not public_data_dir.exists():
        return datasets
    for f in sorted(public_data_dir.glob("*.parquet")):
        try:
            pf = pq.ParquetFile(f)
            schema = pf.schema_arrow
            datasets[f.stem] = {
                "name": f.stem,
                "file": f,
                "num_rows": pf.metadata.num_rows,
                "columns": [
                    {"name": field.name, "type": str(field.type)}
                    for field in schema
                ],
            }
        except Exception:
            continue
    return datasets


_datasets: dict = {}


@app.on_event("startup")
async def _load_datasets():
    global _datasets
    _datasets = _scan_datasets()


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
    return [
        {
            "name": ds["name"],
            "num_rows": ds["num_rows"],
            "columns": ds["columns"],
        }
        for ds in _datasets.values()
    ]


@app.get("/api/v1/datasets/{name}")
async def get_dataset(name: str):
    ds = _datasets.get(name)
    if not ds:
        return JSONResponse({"error": "Dataset not found"}, status_code=404)
    return {
        "name": ds["name"],
        "num_rows": ds["num_rows"],
        "columns": ds["columns"],
    }


@app.get("/api/v1/datasets/{name}/records")
async def get_dataset_records(name: str, limit: int = 100, offset: int = 0):
    ds = _datasets.get(name)
    if not ds:
        return JSONResponse({"error": "Dataset not found"}, status_code=404)

    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    table = pq.read_table(ds["file"])
    total = table.num_rows

    sliced = table.slice(offset, limit)
    records = sliced.to_pydict()
    rows = [
        {col: records[col][i] for col in records}
        for i in range(sliced.num_rows)
    ]

    return {
        "name": name,
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(rows),
        "records": rows,
    }


# ---- Health check ----

@app.get("/health")
async def health():
    return {"status": "healthy"}
