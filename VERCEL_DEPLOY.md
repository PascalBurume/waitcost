# Deploy WaitCost to Vercel (full-stack: static frontend + Python serverless API)

One Vercel project serves **both** the React app (static) and the FastAPI engine
(Python serverless functions) under one URL:

```
  /            → React app          (frontend/dist, built by Vercel)
  /api/*       → FastAPI engine     (api/index.py, Python serverless function)
```

Everything is same-origin, so there's **no CORS to configure**. The brain runs in
`WAITCOST_PLANNER=auto`: **Claude Sonnet 4.6** when `ANTHROPIC_API_KEY` is set, else a
silent fall-back to the deterministic rule planner.

> **No PII can leak** — the system holds only public, aggregate HUD/Census data and
> refuses individual-level questions, so nothing sensitive is sent to the API.

## ⚠️ Read first — the Pro-plan timeout requirement
Each `/ask` runs 400 Monte-Carlo sims **plus** several Claude calls (plan → narrate →
decision → evaluator), so a Claude-live request takes ~10–20 s.

- **Vercel Hobby (free) caps serverless functions at 10 s** → Claude-live `/ask` will
  time out. Use the **Pro plan** and raise the limit (below), **or** run without the key
  (rule mode answers in ~2–4 s and fits Hobby).
- After deploying on **Pro**: **Project → Settings → Functions → Max Duration → 60 s**
  (300 s max). This applies to the Python function and is the simplest way to set it.

## What's already wired (in this repo)
- **`vercel.json`** — builds the frontend (`@vercel/static-build` → `frontend/dist`) and the
  Python function (`@vercel/python` on `api/index.py`), routes `/api/*` to the function and
  everything else to the SPA. `includeFiles` bundles `config/ data/ model/ data_sources/`
  (the engine's runtime data); `maxLambdaSize` is raised for numpy/pandas.
- **`api/index.py`** — the serverless entrypoint; mounts the FastAPI app under `/api` and
  points the audit log + brief artifacts at `/tmp` (the only writable dir on Vercel).
- **`api/requirements.txt`** — lean function deps (no uvicorn/streamlit/plotly) to stay under
  Vercel's 250 MB unzipped limit.
- **`.vercelignore`** — excludes `.venv`, `node_modules`, `eval/ skills/ app/ notebooks/`, and
  the alternate Docker files from the upload/bundle.
- The frontend reads `VITE_API_BASE` at build time and calls `/api/*` when it's `/api`.

## Environment variables (Project → Settings → Environment Variables)
| Name | Value | Scope | Notes |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Production (+ Preview) | **Secret.** Enables the Claude brain. Omit to run rule mode. |
| `VITE_API_BASE` | `/api` | Production + Preview | **Build-time** — makes the frontend call the function. Required. |

`WAITCOST_PLANNER=auto`, `WAITCOST_MEMORY_PATH=/tmp/...`, and `WAITCOST_OUT_DIR=/tmp/...`
are already defaulted in `api/index.py`; set them explicitly only to override.

## Deploy

### Option A — Git integration (recommended)
1. Push this repo to GitHub/GitLab.
2. **vercel.com → Add New → Project →** import the repo. Set **Root Directory** to the folder
   that contains `vercel.json` (this `inactioncost/` directory).
3. Leave the build settings to `vercel.json` (don't override the framework — the `builds`
   array drives it). Add the env vars above.
4. **Deploy.** Vercel builds the frontend and the Python function and serves them at
   `https://<project>.vercel.app`.
5. On Pro, set **Max Duration = 60 s** (Settings → Functions), then redeploy.

### Option B — Vercel CLI
```bash
npm i -g vercel
cd inactioncost
vercel link                       # connect to a project (interactive, one-time)
vercel env add ANTHROPIC_API_KEY  # paste your key (choose Production/Preview)
vercel env add VITE_API_BASE      # value: /api
vercel --prod                     # build + deploy
```

## Verify after deploy
- `https://<project>.vercel.app/api/health` → `{"status":"ok"}` (or 200).
- `https://<project>.vercel.app/api/tools` → `agents: 5, capabilities: 16, charts: 18`.
- Open the app, ask *"What if we wait 3 years on a $15M program?"* — the `planner` field in
  the `/api/ask` response reads `claude` when the key is wired (`rule_based_fallback` otherwise).

## Notes & limits
- **Streaming:** Vercel serverless buffers responses, so the SSE route `/api/ask/stream`
  won't stream token-by-token. The app uses the non-streaming `/api/ask` (it reveals the
  trajectory client-side), so the demo is unaffected.
- **Cold starts:** the first request after idle pays a ~2–5 s numpy/pandas import cost.
- **Ephemeral disk:** the `/tmp` audit log + brief files reset between invocations — harmless
  (the `/ask` JSON is self-contained; `brief_markdown` is in the response body).
- **Cost:** in `auto` with a key, every `/ask` spends Anthropic tokens on a public URL. Deploy
  without the key (rule mode) if you'd rather not meter it.
- **Snappier responses:** lower `monte_carlo_runs` in `config/params.yaml` (e.g. 200) to cut
  latency before deploying.
- The single-container **Hugging Face** deploy (`DEPLOY_HF.md`, root `Dockerfile`) remains a
  working alternative that has no function-timeout limit.
