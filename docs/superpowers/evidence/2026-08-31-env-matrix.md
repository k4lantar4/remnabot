# RC environment A–E matrix

Date: 2026-08-31  
Host: RC (`bot-v4` / `91.107.144.95`)  
Task: M1-T3 · **Revision 2026-08-31:** RC public URLs from live `/opt/remnabot1/.env` (`panel.rookari.com`), not `staging-host-*`.  
Authority: MVP plan `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`  
Branch: `prod-cutover` (re-check HEAD at commit)

## Goal

Classify important production env keys A–E. Fill gitignored RC env so class D/E secrets are absent. Record fingerprints only.

## Sources (verified live)

| Source | Path | Role |
|---|---|---|
| Production bot env | `/opt/bot-remnawave/.env` via `ssh bot` | Behavioral reference (13152 bytes, 380 keys) |
| Production Remnawave env | `/opt/remnawave/.env` via `ssh bot` | JWT / domains / RW Telegram |
| Production subscription env | `/opt/remnawave/.env.subscription` via `ssh bot` | `SUB` prefix / panel URL |
| Production Caddy env | `/opt/caddy-remnawave/.env` via `ssh bot` | Class D pgAdmin / panel hostnames |
| RC sandbox bot env | `/opt/remnabot1/.env` | **Working RC.** Public-URL source (`panel.rookari.com`). Also the **test** `BOT_TOKEN` source |
| RC rehearsal bot env | `/opt/remnabot1/.env.rehearsal` | Gitignored; filled this task |
| RC rehearsal RW env | `/opt/remnabot1/.env.rehearsal-rw` | Gitignored; class-C JWT + RC hostnames |
| Cutover stub | `/opt/remnabot1/.env.cutover` | Gitignored; class-D **key names only**, empty values; not referenced by rehearsal `env_file` |

Local `/opt/remnawave/.env` is the RC/dev panel sandbox (`backend:3` lineage) — **not** used as the production reference.

## Fingerprint method

`sha256(utf-8)[:16]` — same as `app.custom.safety.token_guard.token_fingerprint`.

## Token / JWT identity (must differ)

| Secret | Production fp | RC fp | Match? |
|---|---|---|---|
| Bot `BOT_TOKEN` | `818cf61ccf8f100d` | `458863639bbe6d6b` (test `@mrj7_bot`) | **no** |
| `CABINET_JWT_SECRET` | `818cf61ccf8f100d` (same as prod `BOT_TOKEN`) | `6e66e417433351da` (generated) | **no** |
| RW `JWT_AUTH_SECRET` | `75f5b7ae8dc28251` | `e12d8fd465f7a591` (generated, len 256) | **no** |
| RW `JWT_API_TOKENS_SECRET` | `c1da9fba4aed4f31` | `826aa21cf0873d9c` (generated, len 256) | **no** |
| Bot `POSTGRES_PASSWORD` | `f130130e0da93aaa` | `96fae5b8c1326872` (`rehearsal_bot_pg_placeholder`) | **no** |
| RW `POSTGRES_PASSWORD` | `a942b37ccfaf5a81` | `a1b491ed68159629` (`rehearsal_rw_pg_placeholder`) | **no** |
| `REMNAWAVE_API_KEY` | `d5a708fa4415227e` | `921a2ac8644ae058` (rehearsal placeholder) | **no** |
| `WEB_API_DEFAULT_TOKEN` | `077277ce0deb77be` | `770b485b55fce85b` (generated) | **no** |

`.env.rehearsal` sets `PRODUCTION_BOT_TOKEN_FINGERPRINT=818cf61ccf8f100d` and `ALLOW_PRODUCTION_BOT_TOKEN=false` (M1-T2 fail-closed).

Sandbox `CABINET_JWT_SECRET` was the sandbox Telegram token (fp `458863639bbe6d6b`) — **not** copied. Production `CABINET_JWT_SECRET` equals production `BOT_TOKEN` — **not** copied.

## Classification (important keys)

RC action: **preserve** = copy non-secret production behavior; **override** = class B RC value; **generate** = class C; **omit** = absent from RC env.

### Telegram / webhook / cabinet URLs

| Key | Class | Prod (safe / fp) | RC action | RC |
|---|---|---|---|---|
| `BOT_TOKEN` | B (RC) / D+E (prod value) | fp `818cf61ccf8f100d` | override | test token fp `458863639bbe6d6b` |
| `BOT_USERNAME` | B | `moonvpn_bot` | override | `mrj7_bot` (getMe on test token) |
| `ADMIN_IDS` | D-adjacent | fp `f3342fe3d550dd90` | override | `0` |
| `BOT_RUN_MODE` | B | `webhook` | override | `polling` |
| `WEBHOOK_URL` | B / E (prod URL) | `https://hooks.rookari.com` | override | `panel.rookari.com` (live `.env`) |
| `WEBHOOK_PATH` | A | `/webhook` | preserve | `/webhook` |
| `WEBHOOK_SECRET_TOKEN` | D | fp `45ba583af2ce63f3` | omit value | empty (polling) |
| `WEBHOOK_IP` | B | absent | omit | absent |
| `CABINET_ENABLED` | A | `true` | preserve | `true` |
| `CABINET_URL` | B | `https://cabinet.rookari.com` | override | `https://panel.rookari.com` |
| `CABINET_ALLOWED_ORIGINS` | B | `https://cabinet.rookari.com` | override | `*` (live `.env`) |
| `CABINET_JWT_SECRET` | C (RC) / D (prod) | fp `818cf61ccf8f100d` | generate | fp `6e66e417433351da` |
| `WEB_API_ALLOWED_ORIGINS` | B | `*` | preserve (live RC) | `*` |
| `WEB_API_ENABLED` | A | `true` | preserve | `true` |
| `MINIAPP_CUSTOM_URL` | B | `https://cabinet.rookari.com` | override | `panel.rookari.com` |
| `PRODUCTION_BOT_TOKEN_FINGERPRINT` | B | n/a | set | `818cf61ccf8f100d` |
| `ALLOW_PRODUCTION_BOT_TOKEN` | B | absent | set | `false` |

### Language / Toman / product flags (class A)

Toman dual-scale is **code** (`format_price` / display helpers), not an env key. Production `PRICE_*` and `TRAFFIC_PACKAGES_CONFIG` use production storage units and are preserved.

| Key | Class | Production | RC |
|---|---|---|---|
| `DEFAULT_LANGUAGE` | A | `fa` | `fa` |
| `AVAILABLE_LANGUAGES` | A | `ru,en,ua,zh,fa` | same |
| `LANGUAGE_SELECTION_ENABLED` | A | `false` | `false` |
| `TZ` | A | `Asia/Tehran` | `Asia/Tehran` |
| `PRICE_ROUNDING_ENABLED` | A | `true` | `true` |
| `MULTI_TARIFF_ENABLED` | A | `true` | `true` |
| `SALES_MODE` | A | `tariffs` | `tariffs` |
| `PRICE_14_DAYS` … `PRICE_360_DAYS` | A | `0,20000,40000,60000,80000,160000` | same |
| `TRAFFIC_PACKAGES_CONFIG` | A | production packages (5GB…unlimited) | same |
| `PRICE_TRAFFIC_UNLIMITED` | A | `10000000` | same |
| `PRICE_PER_DEVICE` | A | `100000` | same |
| `AVAILABLE_SUBSCRIPTION_PERIODS` | A | `30,90,180` | same |
| `TRAFFIC_RESET_PRICE_MODE` | A | `traffic_with_purchased` | same |
| `PARTNER_DISCOUNT_*` | A | enabled, 10% | same |
| `WHOLESALE_*` | A | **absent** in production env | absent (partner keys cover wholesale UX) |

### C2C

| Key | Class | Production | RC action |
|---|---|---|---|
| `C2C_ENABLED` | B | `true` | **`true`** (live `.env`; admin chat empty). Empty chat is **not** G8 PASS |
| `C2C_ADMIN_CHAT_ID` | E | key present, **value empty** | **omit** (do not invent; do not copy) |
| `C2C_CARDS` | E-adjacent (PAN) | present, fp `0bc52870ca6942f9` | **omit** |
| `C2C_DISPLAY_NAME` | A | `کارت به کارت 💳` | preserve |
| `C2C_MIN_AMOUNT_KOPEKS` / `MAX` / `TTL` / `GUIDE_TEXT` | A | production copy/limits | preserve |

G8 remains INCOMPLETE until an isolated test admin chat exists. Restored `c2c_receipts` rows are allowed later; posting to production admin chat is forbidden.

### Remnawave (bot → panel)

| Key | Class | Production | RC |
|---|---|---|---|
| `REMNAWAVE_API_URL` | B | `http://remnawave:3000` | `http://rehearsal_rw:3000` |
| `REMNAWAVE_AUTH_TYPE` | A | `api_key` | `api_key` |
| `REMNAWAVE_API_KEY` | D | fp `d5a708fa4415227e` | generate placeholder fp `921a2ac8644ae058` (real key at M2 boot) |
| `REMNAWAVE_USERNAME` / `PASSWORD` | D | present | **omit** |
| `REMNAWAVE_WEBHOOK_SECRET` | D | fp `0ed58a1254b1526e` | **omit**; `REMNAWAVE_WEBHOOK_ENABLED=false` |
| `REMNAWAVE_AUTO_SYNC_ENABLED` | B | `true` | `false` until rehearsal panel exists |

### Remnawave panel process (`.env.rehearsal-rw`)

| Key | Class | Production | RC |
|---|---|---|---|
| `JWT_AUTH_SECRET` | C / D | fp `75f5b7ae8dc28251` | generated fp `e12d8fd465f7a591` |
| `JWT_API_TOKENS_SECRET` | C / D | fp `c1da9fba4aed4f31` | generated fp `826aa21cf0873d9c` |
| `FRONT_END_DOMAIN` | B | `master.rookari.com` | `*` (live `/opt/remnawave/.env`) |
| `PANEL_DOMAIN` | B | `master.rookari.com` | `rw.rookari.com` (live RW env) |
| `SUB_PUBLIC_DOMAIN` | B | `sub.rookari.com/sub` | `config.rookari.com/sub` (live RW env) |
| `IS_TELEGRAM_NOTIFICATIONS_ENABLED` | B | `true` | `false` |
| `TELEGRAM_BOT_TOKEN` (RW) | E | fp `be30421b5770d1ff` | **omit** |
| `CLOUDFLARE_TOKEN` | D | fp `f4bf9a2aea8bdfe6` | **omit** |
| `WEBHOOK_ENABLED` (RW) | B | `false` | `false` |

Moved off `deploy/remnawave/docker-compose.rehearsal.yml` into gitignored `env_file: ../../.env.rehearsal-rw`.

### Payments (class E secrets omitted; flags OK)

Production enabled **money** method is C2C only. Provider secrets that exist while disabled still must not enter RC.

| Key | Class | Production | RC |
|---|---|---|---|
| `TELEGRAM_STARS_ENABLED` | A | `false` | `false` |
| `TRIBUTE_ENABLED` | A | `false` | `false` |
| `YOOKASSA_*` | A / E | **absent** | `YOOKASSA_ENABLED=false`, no secrets |
| `CRYPTOBOT_ENABLED` | A | `false` | `false` |
| `CRYPTOBOT_API_TOKEN` | E | present, fp `c489b6d31dee57d2` | **omit** |
| `HELEKET_*` / `WATA_*` / `CLOUDPAYMENTS_*` / `NALOGO_*` | A / E | enabled=false; secrets empty except as fingerprinted | flags false; secrets omitted |
| `PLATEGA_*` / `LAVA_*` / `CISPAY_*` | A | absent | `*_ENABLED=false`, no secrets |

### Database / runtime (class C placeholders)

| Key | Class | Production | RC |
|---|---|---|---|
| `POSTGRES_PASSWORD` (bot) | D / C | fp `f130130e0da93aaa` | `rehearsal_bot_pg_placeholder` (matches compose) |
| `POSTGRES_HOST` | B | `postgres` | `rehearsal_bot_db` |
| `REDIS_URL` | B | `redis://redis:6379/0` | `redis://rehearsal_bot_redis:6379/0` |
| `SKIP_MIGRATION` | B | absent | `true` |
| `DATABASE_MODE` | A | `auto` | `auto` |

### Admin / backup chats (do not copy production)

| Key | Class | Production | RC |
|---|---|---|---|
| `ADMIN_NOTIFICATIONS_CHAT_ID` | E-adjacent | fp `8eaf065493815cba` | omit; `ADMIN_NOTIFICATIONS_ENABLED=false` |
| `BACKUP_SEND_CHAT_ID` | E-adjacent | same fp as admin chat | omit; `BACKUP_SEND_ENABLED=false` |
| `MAINTENANCE_MODE` | B (RC ops) | `true` (live ops lock) | `false` so RC is not locked |

### Cutover-only class D (`.env.cutover` names, empty values)

`BOT_TOKEN`, `WEBHOOK_SECRET_TOKEN`, `CABINET_JWT_SECRET`, `WEB_API_DEFAULT_TOKEN`, `REMNAWAVE_API_KEY`, `JWT_AUTH_SECRET`, `JWT_API_TOKENS_SECRET`, `REMNAWAVE_USERNAME`, `REMNAWAVE_PASSWORD`, `REMNAWAVE_WEBHOOK_SECRET`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `CLOUDFLARE_TOKEN`, `PGADMIN_DEFAULT_PASSWORD`, `METRICS_PASS`.

Not listed in rehearsal `env_file`.

Cabinet Vite: `VITE_API_URL=/api` remains. `VITE_TELEGRAM_BOT_USERNAME=mrj7_bot` in `docker-compose.rehearsal.yml`.

## Verification

```bash
# 1) RC BOT_TOKEN fingerprint ≠ production; D/E keys absent (python inspect)
# 2) Do not use `staging-host-*` as live RC app URLs (`panel.rookari.com` is the source)
# 3) docker compose config (no up; --profile bot-app only to render rehearsal_bot env)
docker compose -p rehearsal -f docker-compose.rehearsal.yml config
docker compose -p rehearsal -f docker-compose.rehearsal.yml --profile bot-app config
docker compose -p rehearsal -f deploy/remnawave/docker-compose.rehearsal.yml --env-file .env.rehearsal-rw config
```

Outcomes (2026-08-31, this host; **revised same day** to match live `.env`):

- Bare bot compose config exit 0 (profile hides `rehearsal_bot` — expected)
- `--profile bot-app` config: `BOT_TOKEN` fp `458863639bbe6d6b` ≠ `PRODUCTION_BOT_TOKEN_FINGERPRINT=818cf61ccf8f100d`; `ALLOW_PRODUCTION_BOT_TOKEN=false`; `C2C_ENABLED=true` (live `.env`; admin chat empty); `WEB_API_ALLOWED_ORIGINS=*`; `WEBHOOK_URL=panel.rookari.com`; `CABINET_URL=https://panel.rookari.com`; `REMNAWAVE_API_URL=http://rehearsal_rw:3000`; `SKIP_MIGRATION=true`
- RW compose config: `FRONT_END_DOMAIN=*`; `PANEL_DOMAIN=rw.rookari.com`; `SUB_PUBLIC_DOMAIN=config.rookari.com/sub`; `IS_TELEGRAM_NOTIFICATIONS_ENABLED=false`; JWT fps `e12d8fd465f7a591` / `826aa21cf0873d9c`; no `TELEGRAM_BOT_TOKEN` / `CLOUDFLARE_TOKEN`
- No production `hooks.rookari.com` / `cabinet.rookari.com` as RC app URLs; no `staging-host-*` in rehearsal env public URLs
- `WEBHOOK_IP` absent
- Class E payment tokens absent from `.env.rehearsal` / `.env.rehearsal-rw`
- No `compose up`; no alembic; no restore

## P1

Isolated C2C test admin chat: **UNKNOWN**. Live RC `C2C_ENABLED=true` with empty `C2C_ADMIN_CHAT_ID`. G8 incomplete ⇒ not MVP-VERIFIED.

## Notes / non-blockers

- Production `TRAFFIC_EXCLUDED_USER_UUIDS` empty; not copied.
- Production `REMNAWAVE_USER_USERNAME_TEMPLATE=u_{full_name}` preserved (non-secret).
- Rehearsal RW `DATABASE_URL` still uses compose placeholder user `rehearsal_rw` (not production `postgres` user).
- `rehearsal_sub` still has compose placeholder `REMNAWAVE_API_TOKEN` (not production sub token fp `72f3bb7d63a1a5d6`).

## M2-T0 follow-up (2026-09-01)

2.8.1 refuses to boot without `METRICS_USER` / `METRICS_PASS`. Production values are class D (listed above). Rehearsal now has **generated class C** in gitignored `.env.rehearsal-rw`: `METRICS_USER=rehearsal_metrics`, `METRICS_PASS` fp `c4c0153ab9431b28` (≠ production). See `docs/superpowers/evidence/2026-09-01-m2-t0-rw-281-pin.md`.
