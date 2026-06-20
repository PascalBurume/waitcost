# WaitCost — single-service image for Hugging Face Spaces (Docker SDK).
# FastAPI serves BOTH the JSON API and the built React app, on port 7860, in
# WAITCOST_PLANNER=auto: Claude Sonnet 4.6 when ANTHROPIC_API_KEY is set (add it as an
# HF Space secret), otherwise it falls back silently to the deterministic rule planner
# (no network, no GPU) — so the app runs with or without the key. See DEPLOY_HF.md.

# ---- stage 1: build the React frontend -------------------------------------
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE=""
RUN npm run build            # -> /app/frontend/dist

# ---- stage 2: python runtime -----------------------------------------------
FROM python:3.11-slim
WORKDIR /app

# Lean runtime deps only (numpy/pandas/reportlab ship manylinux wheels → no build tools needed).
COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

# App code (respects .dockerignore) + the built frontend from stage 1.
COPY . .
COPY --from=frontend /app/frontend/dist ./frontend/dist

ENV WAITCOST_PLANNER=auto \
    FRONTEND_DIST=/app/frontend/dist \
    PYTHONUNBUFFERED=1 \
    HOME=/app
# ANTHROPIC_API_KEY is NOT baked in — set it as a Space secret (Settings → Secrets) to
# enable the Claude brain. With no key, `auto` runs the deterministic rule planner.
# HF Spaces run as uid 1000 and expect the app on 7860; /app must be writable for the
# ephemeral MEMORY.md / outputs/ audit files the agent appends to.
RUN mkdir -p /app/outputs && chmod -R a+rwX /app
EXPOSE 7860
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
