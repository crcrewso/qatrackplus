# Builder stage
FROM python:3.12-bookworm AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/qatrackplus
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Pinned to match the uv version CI and Read the Docs use - see the
# `version:` input on setup-uv in .github/workflows/ci.yml.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY qatrack ./qatrack

# Install dependencies from the committed lockfile rather than resolving
# them fresh at build time. Previously this ran `pip install ".[docker,
# postgres]"` against pyproject.toml alone - uv.lock was not even copied
# into the image - so the deployed artifact was the one thing in this
# project built from an unpinned resolve. Two builds of the same commit
# could ship different dependency versions, and nothing tested by CI
# (which does use the lockfile) necessarily matched what shipped.
#
# `uv export --locked` fails if uv.lock has drifted from pyproject.toml,
# matching the CI behaviour. The exported file carries hashes for every
# package, so pip verifies each download against the lockfile too.
RUN uv export --locked --no-dev --extra docker --extra postgres         --no-emit-project --format requirements-txt -o /tmp/requirements.txt     && pip install --no-cache-dir -r /tmp/requirements.txt     && pip install --no-cache-dir --no-deps .     && rm /tmp/requirements.txt

# Runtime stage
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y \
    postgresql-client \
    cifs-utils \
    chromium \
    libpq5 \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /usr/src/qatrackplus
# Cache bust 2
COPY . .

# Ensure necessary directories exist
RUN mkdir -p logs qatrack/media qatrack/static

# Make entrypoint executable and move it out of the volume mount
RUN cp deploy/docker/django/entrypoint.sh /entrypoint.sh && \
    dos2unix /entrypoint.sh && \
    chmod +x /entrypoint.sh


EXPOSE 8000
CMD ["/entrypoint.sh"]
# Cache bust 1
