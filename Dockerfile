FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build deps for psycopg2/scipy/hmmlearn wheels on slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY workers ./workers
COPY config ./config

# Install runtime deps. `feedparser` ships sgmllib3k as a source-only dep
# that fails to build on slim; the auto-sell worker doesn't need news,
# so install feedparser without deps and pick up the rest normally.
RUN pip install --no-deps feedparser \
    && pip install .

CMD ["python", "-m", "workers.auto_sell_tick"]
