# One image: the built web app plus the API that serves it. Run locally with Docker, and later on a host.
#   docker build -t tokenizer-lab .
#   docker run -p 7860:7860 -e HF_TOKEN=hf_xxx tokenizer-lab     then open http://localhost:7860

# ---- stage 1: build the web app ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: the API ----
FROM python:3.12-slim

# Run as an ordinary user, not root.
RUN useradd -m -u 1000 user
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/user/.cache/huggingface

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=user config ./config
COPY --chown=user data ./data
COPY --chown=user src ./src
COPY --chown=user api ./api
COPY --chown=user --from=web /web/dist ./frontend/dist

USER user

# Public-site settings (all off when you run the app locally):
#   RATE_LIMIT_PER_MIN   calls per minute and visitor to the /api routes
#   TRUST_PROXY_HOPS     proxies in front of the app; needed to tell visitors apart
#   WARMUP               1 = load the tokenizers in the background at start-up (off: the free plan has 512 MB RAM)
# HF_TOKEN (a Read token for the gated Llama and Gemma tokenizers) is NOT set here: add it as a secret (docker compose reads it from your shell).
# A host may set PORT; 7860 is the default.
ENV FRONTEND_DIST=/app/frontend/dist \
    RATE_LIMIT_PER_MIN=120 \
    TRUST_PROXY_HOPS=1 \
    WARMUP=0

EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-7860}"]
