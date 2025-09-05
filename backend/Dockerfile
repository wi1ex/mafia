FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONOPTIMIZE=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock* /app/
RUN pip install --upgrade pip && pip install poetry \
 && poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --only main --no-root

COPY . /app

RUN useradd -u 999 -r -s /usr/sbin/nologin appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips=*"]
