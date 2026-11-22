# API + monthly jobs image. Build context is the repo root:
#   docker compose -f deploy/oracle/docker-compose.yml build
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 FASTEMBED_CACHE_PATH=/app/.cache/fastembed

COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install -r apps/api/requirements.txt requests

COPY . .
# Bake the ONNX query model into the image so the first search never downloads it.
RUN ML_EMBEDDER=fastembed python -m ml.prefetch_model

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --workers ${API_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*'"]
