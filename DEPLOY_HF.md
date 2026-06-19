# Deploy WaitCost to Hugging Face Spaces (free, single service)

One container: FastAPI serves **both** the React app and the JSON API, on port **7860**,
in **`WAITCOST_PLANNER=rule`** mode — deterministic, no Ollama/LLM/GPU. Full app, every
chart and number works; only the *phrasing* is rule-based instead of Gemma (show Gemma
live in your video). Free CPU tier is plenty.

## What's already wired (no edits needed)
- **`Dockerfile`** (repo root) — builds the frontend, runs `uvicorn ... --port 7860`, sets `WAITCOST_PLANNER=rule`.
- **`README.md`** front-matter — `sdk: docker`, `app_port: 7860` (HF reads this).
- **`api/main.py`** — serves `frontend/dist` at `/` (all API routes win); input hardening (clamped Monte-Carlo, clean 400s).
- **`frontend/src/api/client.ts`** — same-origin in production (`VITE_API_BASE=""`, baked into the image).
- The server + Gemma stack is preserved separately in `Dockerfile.backend` + `docker-compose.yml`.

## Deploy (≈5 minutes)
1. Create a Space → **huggingface.co/new-space** → SDK **Docker** → **Blank** → name it e.g. `waitcost`.
2. Push this folder to the Space's git repo:
   ```bash
   git clone https://huggingface.co/spaces/<your-username>/waitcost hf-space
   rsync -a --exclude .git --exclude .venv --exclude frontend/node_modules \
         --exclude frontend/dist ./  hf-space/      # copy the project in
   cd hf-space && git add -A && git commit -m "WaitCost" && git push
   ```
   (Or just add the Space as a remote and push.)
3. HF builds the `Dockerfile` automatically (~3-5 min) and serves the app at
   `https://<your-username>-waitcost.hf.space`. Judges open that URL — no signup.

That's it. `WAITCOST_PLANNER=rule` is baked into the image, so there's nothing else to configure.

## Test it locally first (optional but recommended)
```bash
# A) without Docker — exactly what the Space runs:
cd frontend && VITE_API_BASE="" npm run build && cd ..
WAITCOST_PLANNER=rule FRONTEND_DIST=$PWD/frontend/dist \
  uvicorn api.main:app --host 0.0.0.0 --port 7860
# open http://localhost:7860

# B) with Docker — identical to HF:
docker build -t waitcost .
docker run --rm -p 7860:7860 waitcost
# open http://localhost:7860
```

## Notes
- **Cold start:** HF free Spaces sleep after ~48h idle (far better than most free tiers).
- **Ephemeral disk:** the `MEMORY.md` / `outputs/` audit files reset on rebuild — harmless (internal log).
- **Latency:** each `/ask` runs 400 Monte-Carlo sims (~2-4 s on free CPU). To make it snappier,
  lower `monte_carlo_runs` in `config/params.yaml` (e.g. 200) before deploying.
- **Hardware upgrade is unnecessary** — rule mode needs no GPU.
