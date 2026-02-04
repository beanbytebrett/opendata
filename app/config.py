import os
from pathlib import Path

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

_BASE_DIR = Path(__file__).parent.parent
SUBMISSIONS_DIR = Path(os.environ.get("SUBMISSIONS_DIR", _BASE_DIR / "data" / "submissions"))
