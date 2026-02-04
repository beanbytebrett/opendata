# CLAUDE.md

Project-specific guidance for Claude Code.

## Project Overview

Open data project. Repository: https://github.com/beanbytebrett/opendata

**Current state**: Early development.

**Tech stack**: Python 3.13, FastAPI, Uvicorn, Jinja2, Docker.

## Project Structure

```
opendata/
├── app/                    # FastAPI server (deployed via Docker)
│   ├── main.py
│   ├── config.py
│   ├── admin.py
│   ├── telemetry.py
│   ├── static/
│   └── templates/
├── crawlers/               # Data crawlers (NOT in Docker image)
│   ├── base.py             # BaseCrawler ABC
│   ├── conditions.py       # Done condition classes
│   ├── runner.py           # CLI: python -m crawlers.runner <name>
│   ├── requirements.txt    # Crawler-only dependencies
│   └── sources/
│       └── congress_contacts.py
├── data/
│   └── public/             # Parquet files served by API (git-ignored)
├── .github/workflows/
│   └── deploy.yml          # Dokploy webhook on push to main
├── Dockerfile
├── .dockerignore
└── requirements.txt        # Server dependencies only
```

## Development

```bash
# Server (requires Python 3.13+)
pip install -r requirements.txt
uvicorn app.main:app --reload

# Crawlers (can run from NAS, server, or local)
pip install -r crawlers/requirements.txt
python -m crawlers.runner congress_contacts --output-dir ./data/public

# SCP dataset to server
scp data/public/congress_contacts.parquet user@212.1.213.176:/app/data/public/

# Docker (server only, crawlers excluded)
docker build -t opendata .
docker run -p 8000:8000 opendata
```

The site runs on port 8000. Health check at `/health`.
The server auto-detects new/updated Parquet files in `data/public/` without restart.

## Git Configuration

This repo uses a non-default SSH key. The local git config is set to:

```
core.sshCommand = ssh -i /Users/brett/code/beanbytebrett/.ssh/id_ed25519_research -o IdentitiesOnly=yes
```

If cloning fresh, re-apply with:

```bash
git config core.sshCommand "ssh -i /Users/brett/code/beanbytebrett/.ssh/id_ed25519_research -o IdentitiesOnly=yes"
```

## Git Workflow

- Commit directly to `main` during early development
- One commit per logical unit of work
- Run lint/tests for changed code before committing

## Infrastructure

- **Host**: `212.1.213.176` (Dokploy at `https://dokploy.opendata.rest`)
- **Domain**: `opendata.rest`
- **Deployment**: Push to `main` triggers GitHub Actions webhook to Dokploy
- **SSL**: Let's Encrypt via Dokploy/Traefik

### Environment Variables

Stored in `.env` (git-ignored). See `.env` for current values:

| Variable | Description |
|----------|-------------|
| `DOKPLOY_API_KEY` | Dokploy API authentication token |
| `DOKPLOY_HOST` | Dokploy instance URL |
| `DOMAIN` | Production domain |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for form submission notifications |
| `SLACK_CLIENT_ID` | Slack app client ID |
| `SLACK_CLIENT_SECRET` | Slack app client secret |
| `SLACK_SIGNING_SECRET` | Slack app signing secret |
| `SLACK_VERIFICATION_TOKEN` | Slack app verification token |

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DOKPLOY_WEBHOOK_URL` | Webhook URL from Dokploy application settings |

## Communication Preferences

- When asking clarifying questions, break them into small sections (3-4 questions max per message)
- Allow the user to respond to each section before moving to the next
- Avoid long scrolling lists of questions

## Design Philosophy

- **Simplicity first** - Keep implementations simple. Only add complexity when clearly necessary.
- **Procedural over LLM for repeat actions** - If something is done repeatedly, script it.
- **Validation at boundaries only** - Trust internal code, validate external input.
- **Fail fast** - Clear error messages over silent recovery.
