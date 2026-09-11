# ==========================================================
# Listing Hub & AI Editor - Dockerfile
# Base: Debian Bookworm Slim with Native System Chromium
# Fully TrueNAS SCALE & Docker Compose Compatible
# ==========================================================

FROM python:3.11-slim-bookworm

# OpenContainers, TrueNAS SCALE & Unraid Metadata Labels
LABEL org.opencontainers.image.title="Listing Hub & AI Editor" \
      org.opencontainers.image.description="Autonomní správa inzerce pro Bazoš.cz a Aukro.cz s AI Gemini Vision poradcem pro fotky a ceny" \
      org.opencontainers.image.version="3.8.7" \
      org.opencontainers.image.authors="Ondřej Hála <ondrej.hala@roboton.com>" \
      org.opencontainers.image.vendor="Ondřej Hála" \
      org.opencontainers.image.url="https://github.com/onhala/listing-hub" \
      org.opencontainers.image.source="https://github.com/onhala/listing-hub" \
      org.opencontainers.image.documentation="https://github.com/onhala/listing-hub/blob/main/README.md" \
      org.opencontainers.image.licenses="MIT" \
      com.truenas.app.title="Listing Hub" \
      com.truenas.app.description="Autonomní správa inzerce pro Bazoš.cz a Aukro.cz s AI Gemini Vision" \
      com.truenas.app.category="productivity" \
      com.truenas.app.port="5001" \
      com.truenas.app.webui="http://[HOST]:[PORT:5001]" \
      com.truenas.app.icon="https://raw.githubusercontent.com/onhala/listing-hub/main/static/icon.png" \
      net.unraid.docker.icon="https://raw.githubusercontent.com/onhala/listing-hub/main/static/icon.png" \
      net.unraid.docker.webui="http://[IP]:[PORT:5001]"

ARG GIT_COMMIT_SHA=unknown
ENV GIT_COMMIT_SHA=$GIT_COMMIT_SHA

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV HEADLESS=true
ENV PUID=1000
ENV PGID=1000
ENV U2NET_HOME=/app/data/.u2net

# 1. Instalace systémových závislostí + systémové Chromium z Debianu + gosu pro TrueNAS PUID/PGID
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-sandbox \
    procps \
    git \
    gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /usr/share/doc /usr/share/man

# 2. Vytvoření neprivilegovaného uživatele appuser
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -d /app -s /bin/bash appuser && \
    mkdir -p /app/config /app/data /app/photos /app/export && \
    chown -R appuser:appuser /app

WORKDIR /app

# 3. Instalace Python závislostí
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache /tmp/*

# 4. Kopírování aplikačního kódu a entrypoint skriptu
COPY . /app/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chown -R appuser:appuser /app

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5001/api/refresh/status')" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "app.py"]
