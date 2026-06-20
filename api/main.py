"""FastAPI bridge — exposes the WaitCost engine to any frontend (React/TS, etc.).

Run from the repo root:
    uvicorn api.main:app --reload --port 8000
Then open http://localhost:8000/docs for an auto-generated, clickable test page.

Thin layer: every route delegates to a pure function in api/payloads.py (which
calls the same skills the agent uses), so the data logic is testable without a
server and every number stays traceable to a simulation output.
"""
import json
import os
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.env import load_dotenv
load_dotenv()   # pick up ANTHROPIC_API_KEY etc. from .env (no-override)

from api import brief_export as BE
from api import payloads as P

app = FastAPI(title="WaitCost API", version="1.0",
              description="Cost-of-delay simulator for homelessness intervention (CA-600).")

# Read-only public API (no auth, no cookies) — safe to allow any origin. The
# deployed single-service build is same-origin anyway; this just avoids a CORS
# foot-gun if the frontend is ever hosted separately.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"],
)

# Bound runaway inputs so a public URL can't be used to exhaust the box.
MAX_N_MC = 400        # caps the Monte-Carlo work a single /scenario can request


@app.exception_handler(ValueError)
def _value_error(_req: Request, exc: ValueError):
    """Turn bad user input (unknown CoC, unparseable budgets, …) into a clean 400
    instead of a 500 with a server stack trace."""
    return JSONResponse(status_code=400, content={"error": str(exc)})


class AskRequest(BaseModel):
    question: str
    approve_allocation: bool = False
    coc: str | None = None


class ScenarioRequest(BaseModel):
    budget_musd: float = 50.0
    delay_years: int = 3
    n_mc: int = 200
    mix: dict | None = None
    coc: str | None = None


class CompareCitiesRequest(BaseModel):
    question: str | None = None
    budget_musd: float = 15.0
    delay_years: int = 3
    coc_a: str = "CA-600"
    coc_b: str = "IL-510"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/params")
def params():
    return P.params_payload()


@app.get("/provenance")
def provenance():
    """Feature ① — where every on-screen number comes from, keyed by metric family
    (source + vintage + 'range, not a point' note). Sourced from SOURCES_MANIFEST.md."""
    return P.provenance_payload()


@app.get("/cocs")
def cocs():
    """The cities the same model + engine can run."""
    return P.cocs_payload()


@app.get("/tools")
def tools():
    """The agent's function-calling catalog: how many tools and what they do."""
    return P.tools_payload()


@app.get("/context")
def context(coc: str = "CA-600"):
    """Retrieve essential US public indicators for a city (decision context)."""
    return P.context_payload(coc)


@app.get("/equity")
def equity(coc: str = "CA-600"):
    """Population-level racial-disparity analysis (never individual-level)."""
    return P.equity_payload(coc)


@app.get("/city-brief")
def city_brief(coc: str = "CA-600"):
    """Grounded city homelessness brief (third agent) — general context, not the cost model."""
    return P.city_brief_payload(coc)


@app.get("/city-sources")
def city_sources(coc: str = "CA-600"):
    """The raw curated source registry entry for a CoC (+ national frameworks)."""
    return P.city_sources_payload(coc)


@app.get("/charts")
def charts():
    """The visualization agent's chart catalog."""
    return P.charts_payload()


@app.get("/chart")
def chart(name: str, coc: str = "CA-600", budget_musd: float = 50.0, delay_years: int = 3,
          budgets: str | None = None):
    """Build one render-ready chart spec for a city/scenario. `budgets` is an
    optional comma-separated list (e.g. '1,15') for the per-budget sweep chart."""
    blist = [float(b) for b in budgets.split(",") if b.strip()] if budgets else None
    return P.chart_payload(name, coc=coc, budget=budget_musd, delay=delay_years, budgets=blist)


@app.post("/ask")
def ask(req: AskRequest):
    """Run the full agent loop on a natural-language question (optionally for another CoC)."""
    return P.ask_payload(req.question, approve_allocation=req.approve_allocation, coc=req.coc)


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """Feature ① — stream each agent step as it executes (Server-Sent Events).

    Runs answer() in a background thread that pushes step events to a thread-safe
    queue; the SSE generator drains it. Emits one `event: step` per executed
    skill (label + tier + detail), then a final `event: result` whose payload is
    identical to what synchronous /ask returns (the frontend falls back to /ask
    if SSE fails)."""
    q: queue.Queue = queue.Queue()
    SENTINEL = object()

    def on_step(ev):
        q.put(("step", ev))

    def worker():
        try:
            result = P.run_agent(req.question, approve_allocation=req.approve_allocation,
                                 coc=req.coc, on_step=on_step)
            q.put(("result", P.jsonable(result)))
        except Exception as e:   # never leave the stream hanging
            q.put(("error", {"message": str(e)}))
        finally:
            q.put(SENTINEL)

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is SENTINEL:
                break
            event, data = item
            yield f"event: {event}\ndata: {json.dumps(P.jsonable(data))}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/brief/export")
def brief_export(format: str = "pdf",
                 question: str = "What if we wait 3 years on a $15M program?",
                 coc: str | None = None, approve_allocation: bool = False):
    """Feature ② — download the decision brief as a one-page PDF or Word file.

    Reuses the engine's real figures (headline + range + sources + disclaimer);
    no number is recomputed differently from /ask."""
    result = P.run_agent(question, approve_allocation=approve_allocation, coc=coc)
    if format.lower() == "docx":
        data = BE.build_docx(result)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = "waitcost_brief.docx"
    else:
        data = BE.build_pdf(result)
        media, filename = "application/pdf", "waitcost_brief.pdf"
    return Response(content=data, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/compare-cities")
def compare_cities(req: CompareCitiesRequest):
    """Feature ④ — run the same question across two cities + a numeric delta."""
    return P.compare_cities_payload(req.question, req.budget_musd, req.delay_years,
                                    req.coc_a, req.coc_b)


@app.post("/scenario")
def scenario(req: ScenarioRequest):
    """Run status-quo / act-now / delay and return yearly cost bands + cost-of-waiting."""
    n_mc = max(1, min(int(req.n_mc), MAX_N_MC))   # clamp: never let a request run unbounded MC
    return P.scenario_payload(budget=req.budget_musd, delay=req.delay_years,
                              n_mc=n_mc, mix=req.mix, coc=req.coc)


@app.get("/effect-band")
def effect_band(budget_musd: float = 50.0, delay_years: int = 3):
    """Cost-of-waiting under +/-50% intervention-effect priors."""
    return P.effect_band_payload(budget=budget_musd, delay=delay_years)


@app.get("/model")
def model():
    """Learned inflow model: held-out R^2, SHAP, SPM cross-validation, calibration."""
    return P.model_payload()


@app.get("/backtest")
def backtest():
    """Face-validity backtest: seed 2023 PIT, predict 2024, compare to observed."""
    return P.backtest_payload()


@app.get("/coc-points")
def coc_points():
    """The 15 training CoCs as map points (location, homelessness, housing cost)."""
    return P.coc_points()


@app.get("/geo")
def geo():
    """Same CoC points as a GeoJSON FeatureCollection for Leaflet/MapLibre."""
    return P.geo_payload()


# --- single-service deploy: serve the built React app from this same server -----
# Mounted LAST so all API routes above win; the SPA is served at "/" (html=True
# returns index.html). Only mounts if a production build exists, so dev/tests are
# unaffected. Override the location with FRONTEND_DIST if needed.
_DIST = Path(os.environ.get("FRONTEND_DIST",
             Path(__file__).resolve().parent.parent / "frontend" / "dist"))
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
