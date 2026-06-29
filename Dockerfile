# ==========================================
# Bazoš Automat & AI Editor - Dockerfile
# Brand: TERMS a.s. / Roboton Custom Platform
# ==========================================

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

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
    && rm -rf /var/lib/apt/lists/*

# Nastavení pracovního adresáře
WORKDIR /app

# Kopírování requirements.txt a instalace python knihoven
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Kopírování celého kódu aplikace do kontejneru
COPY . /app/

# Nastavení environment proměnných pro Playwright a Xvfb
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

# Expozice portů:
# - 5001: Flask Web App
# - 6080: noVNC (přístup k prohlížeči přes WebSockets)
EXPOSE 5001
EXPOSE 6080

# Výchozí příkaz spustí Supervisor, který nastartuje všechny procesy
CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
