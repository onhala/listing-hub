# ==========================================================
# Listing Hub & AI Editor - Dockerfile (Ultra-Compressed)
# Brand: TERMS a.s. / Roboton Custom Platform
# Base: Debian Bookworm Slim with Native System Chromium
# Target Size: ~450 MB (Reduced from ~1.1 GB)
# ==========================================================

FROM python:3.11-slim-bookworm

# OpenContainers & TrueNAS Metadata Labels
LABEL org.opencontainers.image.title="Listing Hub" \
      org.opencontainers.image.description="Automatizovaná správa inzerátů a AI poradce cen pro Bazoš.cz a Aukro.cz" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.vendor="TERMS a.s. / Roboton" \
      org.opencontainers.image.url="https://github.com/onhala/listing-hub" \
      org.opencontainers.image.source="https://github.com/onhala/listing-hub" \
      org.opencontainers.image.icon="https://raw.githubusercontent.com/onhala/listing-hub/main/static/icon.png" \
      net.unraid.docker.icon="https://raw.githubusercontent.com/onhala/listing-hub/main/static/icon.png"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# 1. Instalace systémových závislostí + systémové Chromium z Debianu
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-sandbox \
    xvfb \
    x11vnc \
    fluxbox \
    novnc \
    websockify \
    supervisor \
    procps \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /usr/share/doc /usr/share/man

# 2. Vytvoření neprivilegovaného uživatele a pracovních adresářů
RUN groupadd -g 1000 roboton && \
    useradd -u 1000 -g roboton -d /app -s /bin/bash roboton && \
    mkdir -p /var/log/supervisor /var/run/supervisor /tmp/.X11-unix /app/config /app/data /app/photos && \
    chown -R roboton:roboton /var/log/supervisor /var/run/supervisor /tmp/.X11-unix /app

WORKDIR /app

# 3. Instalace Python závislostí (BEZ těžkého stahování Chromium v Playwrightu)
COPY --chown=roboton:roboton requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache /tmp/*

# 4. Kopírování aplikačního kódu
COPY --chown=roboton:roboton . /app/

EXPOSE 5001
EXPOSE 6080

USER roboton

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
