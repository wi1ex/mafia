FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONOPTIMIZE=1 PYTHONPATH=/app
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates && rm -rf /var/lib/apt/lists/* && update-ca-certificates
COPY pyproject.toml poetry.lock /app/
RUN pip install --upgrade pip==26.1.2 && pip install poetry==2.4.1 && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --only main --no-root
COPY . /app

RUN useradd -u 999 -r -m -d /home/appuser -s /usr/sbin/nologin appuser && chown -R appuser:appuser /app /home/appuser
ENV HOME=/home/appuser
USER appuser

CMD ["gunicorn","app.main:app","-k","uvicorn.workers.UvicornWorker"]
