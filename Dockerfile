# ==========================================================
# Listing Hub & AI Editor - Dockerfile (Ultra-Compressed)
# Base: Debian Bookworm Slim with Native System Chromium
# Target Size: ~450 MB
# ==========================================================

FROM python:3.11-slim-bookworm

# OpenContainers & TrueNAS Metadata Labels
LABEL org.opencontainers.image.title="Listing Hub" \
      org.opencontainers.image.description="Automatizovaná správa inzerátů a AI poradce cen pro Bazoš.cz a Aukro.cz" \
      org.opencontainers.image.version="3.2.0" \
      org.opencontainers.image.vendor="Ondřej Hála" \
      org.opencontainers.image.url="https://github.com/onhala/listing-hub" \
      org.opencontainers.image.source="https://github.com/onhala/listing-hub" \
      org.opencontainers.image.icon="https://raw.githubusercontent.com/onhala/listing-hub/main/static/icon.png" \
      net.unraid.docker.icon="https://raw.githubusercontent.com/onhala/listing-hub/main/static/icon.png"

ARG GIT_COMMIT_SHA=unknown
ENV GIT_COMMIT_SHA=$GIT_COMMIT_SHA

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV HEADLESS=true

# 1. Instalace systémových závislostí + systémové Chromium z Debianu
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-sandbox \
    procps \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /usr/share/doc /usr/share/man

# 2. Vytvoření neprivilegovaného uživatele appuser
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -d /app -s /bin/bash appuser && \
    mkdir -p /app/config /app/data /app/photos && \
    chown -R appuser:appuser /app

WORKDIR /app

# 3. Instalace Python závislostí
COPY --chown=appuser:appuser requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache /tmp/*

# 4. Kopírování aplikačního kódu
COPY --chown=appuser:appuser . /app/

EXPOSE 5001

USER appuser

CMD ["python", "app.py"]
