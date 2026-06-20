"""Vercel serverless entrypoint for the WaitCost API.

Vercel serves files under /api as serverless functions and routes `/api/(.*)` here
(see vercel.json). The real FastAPI app (api/main.py) defines routes like `/ask` and
`/tools`, so we mount it under `/api` to match the frontend's `VITE_API_BASE=/api`.
The frontend itself is served by Vercel as static files — not by this function.
"""
import os
import sys

# Make the repo root importable so `import api.main` resolves inside the function bundle.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# On Vercel only /tmp is writable — redirect the audit log + brief artifacts there.
os.environ.setdefault("WAITCOST_MEMORY_PATH", "/tmp/waitcost-memory.md")
os.environ.setdefault("WAITCOST_OUT_DIR", "/tmp/waitcost-outputs")
# Claude brain with silent rule fallback; set ANTHROPIC_API_KEY in the Vercel project.
os.environ.setdefault("WAITCOST_PLANNER", "auto")

from fastapi import FastAPI
from api.main import app as _waitcost_app

# Vercel passes the full path (e.g. /api/ask) to the function; mounting the inner app
# at /api maps it onto the app's own /ask route. (api/main.py only mounts the static
# frontend when FRONTEND_DIST exists, which it doesn't here, so this serves the API.)
app = FastAPI(title="WaitCost on Vercel")
app.mount("/api", _waitcost_app)
