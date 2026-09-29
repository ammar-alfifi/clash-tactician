FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    DATABASE_PATH=/data/bot.sqlite3 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install .

RUN useradd --create-home botuser \
    && mkdir -p /data \
    && chown -R botuser:botuser /data
USER botuser

EXPOSE 8080
CMD ["python", "-m", "app"]