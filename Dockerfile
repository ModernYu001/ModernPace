# Pace — container image for Cloud Run (FastAPI web UI in web/server.py).
# Build context is the pace/ project root.
FROM python:3.12-slim

# Faster, quieter Python; no .pyc, unbuffered logs for Cloud Run.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first so the layer caches when only source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app (the .dockerignore keeps .env, .venv, caches out of the image).
COPY . .

# Cloud Run sends traffic to $PORT (defaults to 8080). Bind uvicorn to it.
ENV PORT=8080
EXPOSE 8080

# Shell form so $PORT is expanded at runtime.
CMD exec uvicorn web.server:app --host 0.0.0.0 --port ${PORT}
