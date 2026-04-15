FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md CHANGELOG.md LICENSE ./
COPY config ./config
COPY gestalt ./gestalt
COPY tests ./tests

RUN python -m pip install --upgrade pip \
    && python -m pip install -e .[dev]

EXPOSE 8080

CMD ["uvicorn", "gestalt.main:app", "--host", "0.0.0.0", "--port", "8080"]
