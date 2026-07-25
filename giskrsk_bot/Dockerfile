# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# System deps (WeasyPrint needs libpango, libcairo)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

EXPOSE 8000

# Основной процесс: FastAPI + бот (фоновые задачи включены при RUN_BACKGROUND_TASKS=true).
# Отдельный worker-образ собирать НЕ нужно: docker-compose использует этот же образ
# и переопределяет команду на  python -m app.worker_entry
# Запуск worker:  docker compose --profile worker up -d
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
