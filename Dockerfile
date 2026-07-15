# ==========================================================
# Listing Hub & AI Editor - Dockerfile (Lightweight)
# Brand: TERMS a.s. / Roboton Custom Platform
# Base: Debian Bookworm Slim with Chromium only
# ==========================================================

FROM python:3.11-slim-bookworm

# Nastavení neinteraktivního režimu instalace
ENV DEBIAN_FRONTEND=noninteractive

# Instalace systémových závislostí pro Xvfb, VNC, fluxbox, supervisor a noVNC
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

# Vytvoření neprivilegovaného uživatele a skupiny roboton (pro CRA bezpečnost a non-root běh)
RUN groupadd -g 1000 roboton && \
    useradd -u 1000 -g roboton -d /app -s /bin/bash roboton && \
    mkdir -p /var/log/supervisor /var/run/supervisor /tmp/.X11-unix && \
    chown -R roboton:roboton /var/log/supervisor /var/run/supervisor /tmp/.X11-unix /var/log

# Nastavení pracovního adresáře
WORKDIR /app

# Definování pevné cesty pro Playwright cache, aby byla přístupná i non-root uživateli
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright

# Kopírování requirements.txt a instalace python knihoven
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Instalace POUZE Chromium prohlížeče a jeho systémových závislostí v Playwrightu do sdílené složky
RUN mkdir -p /app/.cache/ms-playwright && \
    playwright install --with-deps chromium

# Kopírování celého kódu aplikace do kontejneru
COPY . /app/

# Změna vlastnictví všech souborů aplikace na uživatele roboton
RUN chown -R roboton:roboton /app

# Nastavení environment proměnných pro Playwright a Xvfb
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright

# Expozice portů:
# - 5001: Flask Web App
# - 6080: noVNC (přístup k prohlížeči přes WebSockets)
EXPOSE 5001
EXPOSE 6080

# Běh pod neprivilegovaným uživatelem
USER roboton

# Výchozí příkaz spustí Supervisor, který nastartuje všechny procesy
CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
