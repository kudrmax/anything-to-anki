FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontends/web/package*.json ./
RUN npm install --prefer-offline
COPY frontends/web/ ./
ARG VITE_APP_ENV=development
ENV VITE_APP_ENV=$VITE_APP_ENV
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY backend/pyproject.toml ./backend/
RUN mkdir -p ./backend/src/backend && touch ./backend/src/backend/__init__.py
RUN pip install --no-cache-dir ./backend

COPY backend/src/ ./backend/src/
RUN pip install --no-deps --no-cache-dir ./backend

COPY config /app/config

COPY --from=frontend /build/dist ./frontend/dist

ENV FRONTEND_DIST=/app/frontend/dist
ENV DATA_DIR=/data

EXPOSE 8000
CMD ["uvicorn", "backend.infrastructure.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
