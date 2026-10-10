FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
RUN pip install -e .
COPY . .

CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
