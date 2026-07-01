# Průvodce produkčním nasazením za Nginx proxy v Dockeru

Tato dokumentace popisuje postup pro bezpečné a optimální nasazení aplikace **Bazoš Automat & AI Editor** na domácím serveru (TrueNAS, Unraid, Debian atd.) za reverzní proxy Nginx, v souladu s principy **Zero-Trust** a **Cyber Resilience Act (CRA)**.

---

## 1. Architektura a zabezpečení (CRA & Zero-Trust)

- **Běh bez root práv (Non-root Execution)**: Kontejner je navržen tak, aby veškeré procesy (Flask, Xvfb, websockify, Playwright) běžely pod neprivilegovaným systémovým uživatelem `roboton` (UID `1000`, GID `1000`). Tím se eliminuje riziko zneužití případné zranitelnosti k průniku na hostitelský systém.
- **Externí konfigurace (Twelve-Factor App)**: Citlivé přihlašovací údaje a API klíče se doporučuje předávat jako environment proměnné do kontejneru. Nemusí tak být uloženy v textové podobě v lokálním JSON souboru uvnitř svazku.
- **SSL / HTTPS vynucení**: Veškerá komunikace s administrací (včetně WebSocketu pro VNC přenos obrazu) musí být šifrovaná přes SSL.

---

## 2. Konfigurace Docker Compose (`docker-compose.yml`)

Zde je doporučená konfigurace pro produkční nasazení s environmentálními proměnnými:

```yaml
version: '3.8'

services:
  bazos-automat:
    image: ghcr.io/onhala/bazos-automat:latest
    container_name: bazos-automat
    restart: unless-stopped
    ports:
      - "5001:5001" # Flask Web UI (lze skrýt a zpřístupnit pouze přes proxy)
      - "6080:6080" # noVNC VNC (lze skrýt a zpřístupnit pouze přes proxy)
    volumes:
      # Perzistentní úložiště pro inzeráty a relace
      - ./data/bazos_active_listings.json:/app/bazos_active_listings.json
      - ./data/bazos_session.json:/app/bazos_session.json
      - ./data/photos:/app/photos
    environment:
      - DISPLAY=:99
      - PYTHONUNBUFFERED=1
      # --- KONFIGURACE PŘES ENV PROMĚNNÉ (Doporučeno) ---
      - BAZOS_EMAIL=ondrej.hala@roboton.com
      - BAZOS_PHONE=605207116
      - BAZOS_PASSWORD=tvoje_heslo_na_bazos
      - GEMINI_API_KEY=AIzaSy...tvoj_gemini_key
      # --- AUTOMATICKÝ REFRESH ---
      - AUTO_REFRESH_ENABLED=true
      - AUTO_REFRESH_INTERVAL=720 # v minutách (720 minut = 12 hodin)
      # --- PROXY KONFIGURACE ---
      # Pokud běžíš na https://bazos.mojedomena.cz, nastav tuto proměnnou:
      - BAZOS_VNC_URL=https://bazos.mojedomena.cz/vnc/vnc.html?autoconnect=true&resize=scale&reconnect=true
```

> [!IMPORTANT]
> Nezapomeňte vytvořit složku `./data` a nastavit jí správná oprávnění pro uživatele s UID 1000 (`chown -R 1000:1000 ./data`), aby mohl kontejner bezpečně zapisovat inzeráty a relace.

---

## 3. Konfigurace Nginx Reverzní Proxy

Pro správné fungování noVNC přenosu obrazu je nutné v Nginx povolit předávání WebSocketů. Níže je kompletní konfigurační blok pro váš Nginx virtuální host:

```nginx
server {
    listen 80;
    server_name bazos.mojedomena.cz;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name bazos.mojedomena.cz;

    # SSL Certifikát (např. Let's Encrypt / Certbot)
    ssl_certificate /etc/letsencrypt/live/bazos.mojedomena.cz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bazos.mojedomena.cz/privkey.pem;
    
    # Bezpečnostní hlavičky
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-XSS-Protection "1; mode=block";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # 1. Hlavní Flask aplikace (port 5001)
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Pro dlouho běžící synchronizace navýšíme timeouty
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # 2. noVNC rozhraní a statické soubory (port 6080)
    location /vnc/ {
        # Přesměruje na vnitřní websockify noVNC web server
        proxy_pass http://127.0.0.1:6080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 3. WebSocket tunel pro VNC RFB protokol (websockify)
    location /websockify {
        proxy_pass http://127.0.0.1:6080/websockify;
        proxy_http_version 1.1;
        
        # Klíčové hlavičky pro WebSocket upgrade
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Zamezení odpojení neaktivního WebSocketu
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

---

## 4. Spuštění a kontrola stavu

Po nastavení proxy a spuštění kontejneru můžete zkontrolovat logy:
```bash
docker compose logs -f
```

Ujistěte se, že všechny služby (xvfb, fluxbox, x11vnc, websockify, flask-app) nastartovaly správně pod uživatelem `roboton`. To lze ověřit přímo uvnitř kontejneru:
```bash
docker exec -it bazos-automat ps aux
```
Ve sloupci `USER` byste měli vidět výhradně uživatele `roboton` (nebo UID `1000`).
