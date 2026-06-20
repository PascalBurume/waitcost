"""Minimal, dependency-free `.env` loader for the app entry points.

Reads `KEY=VALUE` lines from a `.env` file in the repo root and sets them in
`os.environ` **without overriding** anything already set (an exported var always
wins). Called explicitly by the entry points (run_demo, the API, the dashboard,
the skill CLI) — never on import — so the test suite stays hermetic.
"""
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path=None):
    """Load `.env` into os.environ (no-override). Returns True if a file was read."""
    path = Path(path) if path else _ROOT / ".env"
    if not path.exists():
        return False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, val)   # existing env wins
    return True
