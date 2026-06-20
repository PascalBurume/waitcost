# Deploy WaitCost to Hugging Face Spaces (free, single service)

One container: FastAPI serves **both** the React app and the JSON API, on port **7860**,
in **`WAITCOST_PLANNER=auto`** mode. With an `ANTHROPIC_API_KEY` set as a Space **secret**,
the live app uses the **Claude Sonnet 4.6** brain (planner + narrator); with no key it falls
back **silently** to the deterministic rule planner — so the app works either way, and never
stalls or crashes. Every chart and number is identical in both modes (the engine owns all
figures); only the *phrasing* and routing differ. Free CPU tier is plenty (no GPU).

> **No PII can leak.** The system holds only public, aggregate HUD/Census data and refuses
> individual-level questions, so nothing sensitive is ever sent to the API — by design.

## What's already wired (no edits needed)
- **`Dockerfile`** (repo root) — builds the frontend, installs `requirements-deploy.txt`
  (which includes `anthropic`), runs `uvicorn ... --port 7860`, sets `WAITCOST_PLANNER=auto`.
- **`README.md`** front-matter — `sdk: docker`, `app_port: 7860` (HF reads this).
- **`api/main.py`** — serves `frontend/dist` at `/` (all API routes win); input hardening
  (clamped Monte-Carlo, clean 400s).
- **`frontend/src/api/client.ts`** — same-origin in production (`VITE_API_BASE=""`, baked into the image).
- The multi-service local stack is preserved separately in `Dockerfile.backend` + `docker-compose.yml`.

## Deploy (≈5 minutes)
1. Create a Space → **huggingface.co/new-space** → SDK **Docker** → **Blank** → name it e.g. `waitcost`.
2. **Add the Claude key as a secret** → Space **Settings → Variables and secrets → New secret**:
   - Name: `ANTHROPIC_API_KEY`  ·  Value: your `sk-ant-...` key.
   - (Add it as a **secret**, not a public variable. Skip this step to run the Space in
     deterministic rule mode with no key — the app still works fully.)
3. Push this folder to the Space's git repo:
   ```bash
   git clone https://huggingface.co/spaces/<your-username>/waitcost hf-space
   rsync -a --exclude .git --exclude .venv --exclude frontend/node_modules \
         --exclude frontend/dist ./  hf-space/      # copy the project in
   cd hf-space && git add -A && git commit -m "WaitCost" && git push
   ```
   (Or just add the Space as a remote and push.)
4. HF builds the `Dockerfile` automatically (~3–5 min) and serves the app at
   `https://<your-username>-waitcost.hf.space`. Judges open that URL — no signup.

The `planner` field in each `/ask` response reports which brain ran (`claude` /
`rule_based_fallback`), so you can confirm the key is wired correctly.

## Test it locally first (optional but recommended)
```bash
# A) without Docker — exactly what the Space runs:
cd frontend && VITE_API_BASE="" npm run build && cd ..
export ANTHROPIC_API_KEY=sk-ant-...        # omit to test the rule fallback
WAITCOST_PLANNER=auto FRONTEND_DIST=$PWD/frontend/dist \
  uvicorn api.main:app --host 0.0.0.0 --port 7860
# open http://localhost:7860

# B) with Docker — identical to HF (pass the key at runtime, never bake it in):
docker build -t waitcost .
docker run --rm -p 7860:7860 -e ANTHROPIC_API_KEY=sk-ant-... waitcost
# open http://localhost:7860   (omit -e to run the rule fallback)
```

## Notes
- **Secrets, not code:** the key lives only in the Space's secret store / your shell env —
  never in the image, the repo, or a committed file. `.env` is gitignored.
- **Cost:** in `auto` with a key, each `/ask` makes Claude calls (planning + narration, and
  more if `WAITCOST_AGENT=toolloop`). It's small per request, but it is real token spend on
  a public URL — if you'd rather not meter it, deploy without the secret (rule mode).
- **Cold start:** HF free Spaces sleep after ~48h idle (far better than most free tiers).
- **Ephemeral disk:** the `MEMORY.md` / `outputs/` audit files reset on rebuild — harmless (internal log).
- **Latency:** each `/ask` runs 400 Monte-Carlo sims (~2–4 s on free CPU) plus the Claude
  round-trip. To make it snappier, lower `monte_carlo_runs` in `config/params.yaml` (e.g. 200).
- **Hardware upgrade is unnecessary** — neither mode needs a GPU.
