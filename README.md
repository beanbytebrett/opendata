# OpenData Exchange

A data broker website built with FastAPI, serving public datasets via API and collecting visitor telemetry.

## Architecture

```
opendata/
├── app/
│   ├── main.py              # FastAPI routes, dataset API, form handlers
│   ├── telemetry.py          # Request middleware, structured JSON logging, beacon handler
│   ├── static/
│   │   ├── style.css         # Dark-theme design system
│   │   └── a.js              # Client-side analytics collector
│   └── templates/
│       ├── base.html         # Base template (nav, footer, script includes)
│       ├── index.html        # Landing page
│       ├── takedown.html     # Data takedown request form
│       ├── brokers.html      # Data broker partnership inquiry
│       └── api_access.html   # API access request form
├── data/
│   ├── public/               # Parquet files served via API
│   └── private/              # Internal-only Parquet files (git-ignored)
├── .github/workflows/
│   └── deploy.yml            # Dokploy webhook on push to main
├── Dockerfile
└── requirements.txt
```

## Pages

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Landing page with service overview |
| `/takedown` | GET/POST | Data removal request form |
| `/brokers` | GET/POST | Data partnership inquiry form |
| `/api-access` | GET/POST | API access request form |

## Dataset API

Serves Parquet files from `data/public/`. Each `.parquet` file becomes a named dataset.

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/datasets` | List all public datasets with schema info |
| `GET /api/v1/datasets/{name}` | Dataset metadata and column definitions |
| `GET /api/v1/datasets/{name}/records?limit=100&offset=0` | Paginated records (max 1000 per request) |

Private datasets in `data/private/` are never exposed.

## Telemetry

All telemetry is structured JSON written to stdout.

**Server-side** (`telemetry.py`): ASGI middleware logs every request with IP, User-Agent, Referrer, Accept-Language, session ID, path, method, and response time. Form submissions log all field values. Sessions tracked via `_sid` cookie.

**Client-side** (`a.js`): Collects browser fingerprint (canvas, WebGL, audio context), device info (screen, memory, cores, timezone), interaction data (mouse movement, clicks, scroll depth, form field dwell times, paste events), and WebRTC local IP. Sends beacons to `POST /cdn/pixel.gif` every 15 seconds and on page exit.

**Event types**: `session_start`, `request`, `form_submission`, `beacon`

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Site runs on http://localhost:8000. Health check at `/health`.

## Docker

```bash
docker build -t opendata .
docker run -p 8000:8000 opendata
```

## Deployment

Push to `main` triggers a GitHub Actions workflow that sends a webhook to Dokploy. The `DOKPLOY_WEBHOOK_URL` GitHub secret must be set from the Dokploy application settings.

- **Domain**: opendata.rest
- **Host**: Dokploy at dokploy.opendata.rest
- **SSL**: Let's Encrypt via Traefik
