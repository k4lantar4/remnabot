# Setting up the Telegram subscription mini app

This guide describes how to serve the static page from `miniapp/index.html`, connect it to the bot’s admin API, and publish it through a reverse proxy (nginx or Caddy). The page shows the user’s current subscription and uses Telegram WebApp init data for authorization.

## 1. Requirements

- A deployed Bedolaga bot with an up-to-date database.
- Admin API enabled (`WEB_API_ENABLED=true`).
- A domain name with a valid TLS certificate (Telegram opens web apps only over HTTPS).
- Ability to host the static files (`miniapp/index.html` and `miniapp/app-config.json`) and proxy `/miniapp/*` requests to the bot.

## 2. Environment setup

1. Copy the example configuration and enable the web API.
2. Set at least the following variables:
   ```env
   WEB_API_ENABLED=true                  # enables FastAPI
   WEB_API_HOST=0.0.0.0
   WEB_API_PORT=8080
   WEB_API_ALLOWED_ORIGINS=https://miniapp.example.com
   WEB_API_DEFAULT_TOKEN=super-secret-token
   ```
   - `WEB_API_ALLOWED_ORIGINS` must contain the domain from which the mini app will be opened.
   - `WEB_API_DEFAULT_TOKEN` creates a bootstrap token for page requests. You can replace it with a token created via `POST /tokens`.

## 3. Starting the admin API

After startup, check availability:

```bash
curl -H "X-API-Key: super-secret-token" https://miniapp.example.com/miniapp/health || \
curl -H "X-API-Key: super-secret-token" http://127.0.0.1:8080/health
```

## 4. Preparing static files

1. If needed, edit `miniapp/app-config.json` to configure instructions and links to the required clients.
2. Make sure the files are readable by the web-server user.

## 5. Serving static files in Docker

If the reverse proxy (nginx or Caddy) runs inside a container, mount the `miniapp` directory into it at `/miniapp`. Then `index.html` and `app-config.json` are available to the server without rebuilding the image every time they change.

### docker-compose example with Caddy

```yaml
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    volumes:
      - ./miniapp:/miniapp:ro          # mount the local folder into the container
      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro
    ports:
      - "80:80"
      - "443:443"
```

### docker-compose example with nginx

```yaml
services:
  nginx:
    image: nginx:1.25-alpine
    restart: unless-stopped
    volumes:
      - ./miniapp:/miniapp:ro          # shared static-files directory
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    ports:
      - "80:80"
      - "443:443"
```

In the proxy configuration, set `/miniapp` as the document root for static files, or use an `alias` directive.
After a project rebuild the layout stays the same; updating files in the local folder is enough.

## 6. Configuring the button in Telegram

1. In the bot admin panel, set the parameters: **Bot configuration → Other → Miniapp**.
2. Restart the bot.
3. If needed, set a custom mini-app button via `@BotFather` (`/setmenu` → Web App URL).

## 7. nginx configuration

```nginx
server {
    listen 80;
    listen 443 ssl http2;
    server_name miniapp.example.com;

    ssl_certificate     /etc/letsencrypt/live/miniapp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/miniapp.example.com/privkey.pem;

    # Mini-app static files
    root /miniapp;
    index index.html;

    location = /miniapp/app-config.json {
        add_header Access-Control-Allow-Origin "*";
        try_files $uri =404;
    }

    location / {
        try_files $uri /index.html =404;
    }

    # Proxy requests to the admin API
    location /miniapp/ {
        proxy_pass http://127.0.0.1:8080/miniapp/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # To proxy other API endpoints, add similar location blocks.
}
```

## 8. Caddy configuration

```caddy
miniapp.example.com {
    encode gzip zstd
    root * /miniapp
    file_server

    @config path /app-config.json
    header @config Access-Control-Allow-Origin "*"

    reverse_proxy /miniapp/* 127.0.0.1:8080 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
    }
}
```

Caddy issues certificates automatically via ACME. Make sure port 443 is forwarded and the domain points at the server.

## 9. Verifying it works

1. Open the mini app directly in Telegram or in a browser: `https://miniapp.example.com`.
2. In the developer console, confirm that the request to `https://miniapp.example.com/miniapp/subscription` returns JSON with subscription data.
3. Confirm that links from the **Connect subscription** block open and copy without errors.

## 10. Diagnostics

| Symptom | Possible cause | Check |
|---------|----------------|-------|
| White screen and 401 error | Wrong `X-API-Key` or `WEB_API_ALLOWED_ORIGINS`. | Check the token and request headers; regenerate the token via `/tokens`. |
| 404 on `/miniapp/subscription` | The proxy is not forwarding requests, or the API is not running. | Check the nginx/Caddy log and confirm the bot is started with `WEB_API_ENABLED=true`. |
| Mini App does not open in Telegram | The URL is not HTTPS, or the certificate is missing. | Renew certificates and confirm the domain is reachable over HTTPS. |
| No subscription links | RemnaWave integration is not configured, or the user has no active subscription. | Check `REMNAWAVE_API_URL`/`KEY` and the user’s subscription status. |

## 11. `/miniapp/payments/methods` response format

`POST /miniapp/payments/methods` returns the list of available payment methods. Each item in the `methods` array contains base fields (`id`, `title`, `description`, amount limits) and extra attributes that control frontend integration:

- `integration_type` — integration type, required. Possible values:
  - `iframe` — the payment form must be shown inside the mini app in an `<iframe>`.
  - `redirect` — the client must navigate to an external page.
- `iframe_config` — settings object, present only when `integration_type = "iframe"`.
  - `expected_origin` — origin of the payment-provider page. Used when checking `event.origin` for messages received via `postMessage` from the payment iframe.

Example response fragment:

```json
{
  "methods": [
    {
      "id": "mulenpay",
      "title": "Bank card",
      "integration_type": "iframe",
      "iframe_config": {
        "expected_origin": "https://checkout.example"
      }
    },
    {
      "id": "cryptobot",
      "title": "CryptoBot",
      "integration_type": "redirect"
    }
  ]
}
```

After setup you can use the mini app in the bot menu and send the link to users directly.
