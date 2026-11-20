# Single-image build for simple hosting (Render, Fly.io, a VPS...):
# builds the React app, then serves it and the API from one Flask/gunicorn process.
#   docker build -t subsmate .  &&  docker run -p 5000:5000 -e SECRET_KEY=change-me subsmate
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/subsmate.db \
    FRONTEND_DIST=/app/static \
    PORT=5000

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/run.py .
COPY --from=frontend /app/dist ./static

RUN useradd --create-home --uid 10001 subsmate \
    && mkdir -p /data && chown subsmate:subsmate /data
USER subsmate
EXPOSE 5000

# Hosts like Render inject $PORT; locally it defaults to 5000.
# One worker: SQLite favours a single writer process. Threads handle concurrency.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --access-logfile - run:app"]
