# ═══════════════════════════════════════════════════════════════
#  ARFM Backend — Optimized Dockerfile
#  Python 3.11-slim · Uvicorn ASGI Server
# ═══════════════════════════════════════════════════════════════

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Dependencies layer (cached unless requirements.txt changes) ─
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application code ────────────────────────────────────────────
COPY . .

# ── Runtime ─────────────────────────────────────────────────────
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
