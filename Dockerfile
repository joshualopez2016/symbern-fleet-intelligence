# --- Stage 1: build the React frontend ---
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime (API + simulator + built frontend) ---
FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
COPY simulator/requirements.txt simulator/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt -r simulator/requirements.txt

COPY backend/ backend/
COPY simulator/ simulator/
COPY sql/ sql/
COPY --from=frontend /fe/dist frontend/dist

ENV STATIC_DIR=/app/frontend/dist
ENV PYTHONUNBUFFERED=1
# One service serves the API, the WebSocket, and the built UI, and runs the
# telemetry simulator in-process. Render provides $PORT.
ENV RUN_SIMULATOR=1
EXPOSE 8000
WORKDIR /app/backend
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
