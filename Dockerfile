FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \ 
    && apt-get install -y --no-install-recommends build-essential libpq-dev git \ 
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md requirements.txt ./
COPY src ./src
COPY rules ./rules
COPY assets ./assets
COPY config ./config

RUN pip install --upgrade pip \ 
    && pip install -e .

CMD ["python", "-m", "logistics_bot.cli", "api"]
