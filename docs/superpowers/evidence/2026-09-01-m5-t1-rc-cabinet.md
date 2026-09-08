# M5-T1 RC cabinet from `/opt/cabinet`

Date: 2026-09-01  
Host: RC (`bot-v4` / `91.107.144.95`)  
Authority: `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`

## Goal

Serve cabinet on `https://panel.rookari.com` from `/opt/cabinet`, with `/api` → `remnawave_bot:8080`. Split compose so RC joins `remnawave-network` and rehearsal (if used) joins `rehearsal_net` — not both, and not `staging-host-cabinet`.

## Git (cabinet)

| Field | Value |
|---|---|
| Tree | `/opt/cabinet` |
| Branch | `prod-cutover` |
| HEAD | `95d49d8b359afd7d587c6bf3fbdcd9b09a537c15` |
| Message | `feat(M5-T1): RC split compose + network` |
| origin | `k4lantar4/cabinet` · pushed `origin/prod-cutover` |
| Base | `35e5aa9e` (1.67.0). Did not merge origin `f52c7ec6` (`webpack.yml`). |
| `/opt/cabinet1` | ABSENT |

Files added:

- `docker-compose.rc.yml` — RC overlay; `remnawave-network` only; `VITE_API_URL=/api`; `VITE_TELEGRAM_BOT_USERNAME=mrj7_bot`
- `docker-compose.rehearsal.yml` — parse-only overlay; `rehearsal_net` only; **not** `up` in this batch

Upstream `docker-compose.yml` restored (no hardcoded dual networks).

## Runtime

| Item | Verified |
|---|---|
| Recreate | `docker compose -f docker-compose.yml -f docker-compose.rc.yml up -d` (no `--build`) |
| `cabinet_frontend` networks | `remnawave-network` only (was also on `bot_bot_network`) |
| Compose files | `/opt/cabinet/docker-compose.yml,/opt/cabinet/docker-compose.rc.yml` |
| `remnawave_bot` | **unchanged** id `3a8fbdb915d3…`; not rebuilt |
| `rehearsal_bot` app | absent / not polled (`rehearsal_bot_db` only) |
| Caddy | `/opt/caddy/Caddyfile` unchanged; `panel.rookari.com` `/api/*` → `remnawave_bot:8080` |

## G9 agent probes (2026-09-01)

| Probe | Result |
|---|---|
| `GET https://panel.rookari.com/` | 200 `text/html` |
| `GET https://panel.rookari.com/api/health` | 200 `bot_version=4.2.0` |
| `GET https://panel.rookari.com/api/cabinet/auth/me` | 401 `Authentication required` |
| `GET https://panel.rookari.com/api/cabinet/branding/telegram-widget` | 200 `bot_username=mrj7_bot` |
| `POST https://panel.rookari.com/api/cabinet/auth/deeplink/request` | 200 `bot_username=mrj7_bot` (token omitted) |
| baked index JS | `mrj7_bot` present; relative `/api`; no `staging-host` |
| `https://panel.rookari.com/assets/fa-jipKNG6p.js` | `تومان` ×2; `ورود با تلگرام` ×1 |

Browser UI login (Telegram widget click-through) is **user smoke** — Playwright Chrome was not installed on this host.

## Not done (later tasks)

- M5-T2 source-of-truth grep on remnabot1 rehearsal compose
- M5-T3 `CABINET_JWT_SECRET` fingerprint vs production
- G8 C2C / polling `rehearsal_bot`
