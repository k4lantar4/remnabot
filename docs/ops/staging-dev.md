# Staging & ship workflow (same host as production)

## Topology — one server, two stacks

```
                    ┌─────────────────────────────────────────┐
                    │           Same server (/opt/bot-remnawave) │
                    └─────────────────────────────────────────┘
   Production          │                    Staging
   docker compose     │                    docker compose.staging.yml
   project: default   │                    project: remnawave-staging
                      │
   remnawave_bot       │   remnawave_staging_bot     :8081→8080
   cabinet_frontend    │   remnawave_staging_cabinet :3021→80
   postgres_data       │   staging_postgres_data      (isolated)
   redis_data          │   staging_redis_data
   .env                │   .env.staging
   @MOONVPN_BOT (prod) │   @staging_bot (separate token)
```

**Never** smoke i18n/UX on the production bot while iterating — use the staging bot only.

## Subdomains — لازم است؟

| حالت | ساب‌دامین | توضیح |
|------|-----------|--------|
| **Webhook (پیشنهادی)** | **بله** — ۲ ساب‌دامین | هر ربات Telegram یک `WEBHOOK_URL` جدا می‌خواهد. prod و staging نمی‌توانند یک URL مشترک داشته باشند. |
| Polling (جایگزین ساده) | خیر | `BOT_RUN_MODE=polling` در `.env.staging` — بدون webhook؛ شبیه prod نیست. |

**پیشنهاد (همان IP prod):**

| ساب‌دامین | نقش | Caddy → |
|-----------|-----|---------|
| `staging-hooks.rookari.com` | webhook staging bot | `localhost:8081` یا `remnawave_staging_bot:8080` |
| `staging-cabinet.rookari.com` | کابینت staging | `localhost:3021` یا `remnawave_staging_cabinet:80` |

دامنه‌های prod (`hooks`, `cabinet`) بدون تغییر — همان IP، مسیر Caddy متفاوت.

## First-time setup (same host)

1. `.env.staging` در ریشه repo (gitignored) — از `.env.staging.example`
2. **پورت‌ها در `.env.staging`:**
   - `WEB_API_PORT=8081`
   - `CABINET_PORT=3021`
3. ربات **جدید** BotFather + `BOT_TOKEN` / `BOT_USERNAME` / `VITE_TELEGRAM_BOT_USERNAME`
4. `WEBHOOK_URL=https://staging-hooks.rookari.com` (DNS A → همین سرور)
5. `CABINET_URL` / `MINIAPP_CUSTOM_URL` → `https://staging-cabinet.rookari.com`
6. `POSTGRES_DB=remnawave_bot_staging` (توصیه — volume جدا)
7. `REMNAWAVE_API_URL` — همان پنل prod روی `remnawave-network` یا پنل تست
8. Caddy: دو route جدید به پورت‌های 8081 و 3021
9. اولین بالا آوردن:
   ```bash
   ./tools/deploy-staging.sh --migrate
   ```

## Daily sprint loop

```
branch → commits → smoke-map → ./tools/deploy-staging.sh
  → smoke روی ربات staging در Telegram
  → CONFIRM_SHIP=1 ./tools/ship-after-smoke.sh <branch>
  → merge PR
  → CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh   # همان سرور، استک prod
  → smoke کوتاه prod
```

## Config checklist (`.env.staging`)

| Variable | Note |
|----------|------|
| `WEB_API_PORT` | **8081** (not 8080) |
| `CABINET_PORT` | **3021** (not 3020) |
| `MINIAPP_CUSTOM_URL` | staging cabinet URL, not prod |
| `BOT_TOKEN` | staging bot only |
| `ADMIN_NOTIFICATIONS_*` | optional: topic جدا تا نوتیف staging به prod نرود |

## Scripts (همه روی همین سرور)

| Script | Stack |
|--------|--------|
| `make staging-rebuild` | Full staging deploy (smoke + build + up) |
| `make staging-health` | Verify health + HTTPS endpoints |
| `make staging-cabinet-build` | Rebuild cabinet only (VITE / @username change) |
| `CONFIRM_PROD_DEPLOY=1 make prod-deploy` | Production after merge |
| `CONFIRM_SHIP=1 make ship BRANCH=i18n/foo` | Push + PR after user smoke |

## Resources

استک staging ≈ **+1–2 GB RAM** (Postgres + Redis + bot + cabinet دوم). prod در حین توسعه دست‌نخورده می‌ماند.

## Security

- `.env.staging` never commit
- staging token ≠ prod token
- C2C/payments: آگاه باشید روی staging فعال است
