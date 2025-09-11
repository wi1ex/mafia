FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONOPTIMIZE=1 PYTHONPATH=/app
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates && rm -rf /var/lib/apt/lists/* && update-ca-certificates
COPY pyproject.toml poetry.lock* /app/
RUN pip install --upgrade pip && pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --only main --no-root
COPY . /app

RUN useradd -u 999 -r -s /usr/sbin/nologin appuser && chown -R appuser:appuser /app
USER appuser

ENV GUNICORN_CMD_ARGS="--bind 0.0.0.0:8000 --workers 2 --threads 1 --keep-alive 75 --timeout 60 --graceful-timeout 20 --backlog 2048 --forwarded-allow-ips 127.0.0.1,172.19.0.6,172.18.0.7 --log-level info --access-logfile - --error-logfile -"
CMD ["gunicorn","app.main:app","-k","uvicorn.workers.UvicornWorker"]
