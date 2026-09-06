# MediKiosk -- single-service image: the API also serves the built React app,
# so there is one origin, no CORS, and the websocket shares the host.

# ---------- Stage 1: build the frontend ----------
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim
WORKDIR /app

# pypdfium2 needs libgl/libglib for PDF rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist

# Uploads and the SQLite file are written at runtime. On most free hosts this
# filesystem is ephemeral -- documents and events do not survive a restart.
# Mount a volume here if the platform offers one.
RUN mkdir -p backend/app/uploads

# Hugging Face Spaces runs the container as UID 1000, not root. Files copied in
# as root would be unwritable, so the SQLite file and the uploads directory must
# be owned by that user or the app fails on its first write.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend
# 7860 is the port Hugging Face Spaces expects. Hosts that inject their own PORT
# (Koyeb, Fly, Cloud Run) override it.
ENV PYTHONUNBUFFERED=1 PORT=7860
EXPOSE 7860

# GEMINI_API_KEY must be supplied as a platform secret, never baked into the
# image. Without it the conversational flow still works; document OCR does not.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
