# Build context is the project ROOT (lit-survey-app/), not backend/ --
# see docker-compose.yml, which sets `context: .` and
# `dockerfile: backend/Dockerfile`. This lets the image include both
# backend/ and frontend/ without a path that escapes the build context.

FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
