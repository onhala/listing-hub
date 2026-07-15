# ==========================================================
# Listing Hub & AI Editor - Dockerfile (Optimized & Lightweight)
# Brand: TERMS a.s. / Roboton Custom Platform
# Base: Debian Bookworm Slim with Chromium only
# ==========================================================

FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright

# 1. Instalace systémových závislostí
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    fluxbox \
    novnc \
    websockify \
    supervisor \
    procps \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Vytvoření neprivilegovaného uživatele a pracovních adresářů
RUN groupadd -g 1000 roboton && \
    useradd -u 1000 -g roboton -d /app -s /bin/bash roboton && \
    mkdir -p /var/log/supervisor /var/run/supervisor /tmp/.X11-unix /app/.cache/ms-playwright /app/config /app/data /app/photos && \
    chown -R roboton:roboton /var/log/supervisor /var/run/supervisor /tmp/.X11-unix /app

WORKDIR /app

# 3. Instalace Python závislostí a Chromium prohlížeče (Tato těžká vrstva zůstane zacachovaná)
COPY --chown=roboton:roboton requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps chromium && \
    rm -rf /root/.cache

# 4. Kopírování aplikačního kódu s přímým nastavením vlastnictví (Bez duplicity chown -R)
COPY --chown=roboton:roboton . /app/

# Expozice portů (5001: Flask App, 6080: noVNC)
EXPOSE 5001
EXPOSE 6080

USER roboton

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
