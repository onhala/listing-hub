#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Pouze pokud proces startuje jako root (standardní Docker / TrueNAS start),
# přizpůsobíme UID/GID pro perzistentní svazky a přepneme na neprivilegovaného uživatele.
if [ "$(id -u)" = "0" ]; then
    # Změna GID a UID pokud se liší od výchozího 1000
    if [ "$PGID" != "1000" ]; then
        groupmod -o -g "$PGID" appuser 2>/dev/null || true
    fi
    if [ "$PUID" != "1000" ]; then
        usermod -o -u "$PUID" -g "$PGID" appuser 2>/dev/null || true
    fi

    # Zajištění existence a správných oprávnění pro složky inzerátů a fotek
    mkdir -p /app/config /app/data /app/photos /app/export /tmp/.X11-unix
    chmod 1777 /tmp/.X11-unix 2>/dev/null || true
    chown -R "$PUID:$PGID" /app/config /app/data /app/photos /app/export 2>/dev/null || true

    # Spuštění procesu pod požadovaným uživatelem
    exec gosu "$PUID:$PGID" "$@"
fi

# Pokud již kontejner běží jako neprivilegovaný uživatel, rovnou spustíme CMD
exec "$@"
