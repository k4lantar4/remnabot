# Production Cutover MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: **superpowers:executing-plans**. Code tasks use TDD; operational tasks use evidence gates. "Container started" / "build passed" is **never** a PASS. Named-start + STOP classes (Session contract) are binding. Do **not** invoke finishing-a-development-branch until the user says the cutover work is done. Do **not** run M7–M9 from a next-pointer. Frozen full-text history: `docs/superpowers/plans/archive/2026-08-28-production-cutover-mvp.full.md` (default **off** — do not read unless reconstructing a past decision or `PLAN REVISION`). If archive and this file disagree, **this file wins** for execution.
>
> **Next pointer (2026-09-02):** open = **M6-T5** (e2e RC smoke; G8 PASS). M6-T1…**T4 DONE**. Checkpoint **M6.2** complete. M1-T4 cancelled. `rehearsal_bot` may stay polling on the test token (G8). Do not rebuild sandbox `remnawave_bot` (DB still `0110`). Named-start required for M6-T5. Do not start M7 from a next-pointer.
>
> **RC public hostname:** `panel.rookari.com` (live `/opt/remnabot1/.env` + `/opt/caddy/Caddyfile`). Do **not** put `staging-host-*` in RC env. M1-T4 (author `staging-host-*` Caddy) is **cancelled**.

**Goal:** Production-usable New-Version MVP: `/opt/remnabot1` (4.2 + ported custom) + `/opt/cabinet` + a verified immutable Remnawave 3.x revision, rehearsed on production-lineage data, cut over by DNS, rollback to frozen 3.60/2.8.1.

**Architecture:** 4.2 fork at `/opt/remnabot1`. MVP custom from `/opt/remnabot` already ported (C2C, FA, Toman, wholesale/partner, identity columns). Cabinet independent behind `/api`. Remnawave rehearsal candidate **v3.4.3** / `remnawave/backend:3.4.3` (not a permanent pin; RC sandbox `backend:3` is non-promotable). Production DB stays on the **remnabot Alembic lineage**. Cutover: freeze writers → dump → restore → pre-DNS verify → flip A records.

**Tech Stack:** Python 3.12 / aiogram, SQLAlchemy + Alembic, PostgreSQL 15 (bot; production `postgres:15-alpine` digest below) and 17.6 (Remnawave restore), Remnawave panel (rehearsal candidate, then immutable digest), Vite/React cabinet, Caddy 2.9 at `/opt/caddy`, Docker Compose, Cloudflare DNS-only.

## Global Constraints

- Production Primary IP never moves. No Floating IP. No AAAA. Cloudflare DNS-only. TTL 300.
- DNS cutover A records → `91.107.144.95`. Rollback A records → `91.107.249.43`.
- Live production path on Bot is `/opt/bot-remnawave` (not `/opt/remnabot`).
- Cabinet = `/opt/cabinet` (`k4lantar4/cabinet`). Never `/opt/cabinet1`. Never merge cabinet into remnabot1.
- remnabot1 `origin` = `k4lantar4/remnabot1`. Do not retarget origin to `k4lantar4/remnabot`.
- Last shared Alembic revision = `0087`. From `0088`, same IDs, different semantics. Production DB = remnabot-lineage `0103`. remnabot1 **live graph after M4-T3** = remnabot **`0111`** (revises grafted `0104`). Upstream `0088–0110` archived. Never apply archived upstream files onto a remnabot-lineage database.
- Restore/rehearsal volumes: **only** `rehearsal_*` / `cutover_*`.
- Remnawave two-track: rehearsal-restore (`backend:2.8.1` digest on frozen `rehearsal_rw_pg17`; **G3-passed candidate** `backend:3.4.3@sha256:4ea85b2f…84515422` on `rehearsal_rw_pg17_candidate`, PG 17.6, sub 7.2.6 unstarted). RC sandbox (`backend:3`, PG 18.4, `:latest`) is **not** promotable.
- Bot PG: pin production `postgres:15-alpine` @ `sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f` (is PostgreSQL 15.18).
- Writers freeze before dump. Pre-DNS verify before flip. Single production-token bot after old bot stopped.
- Rollback = DNS back + frozen 3.60/2.8.1. Never in-place downgrade 3.x or `0111+`.
- Secrets: fingerprints only in git/chat/plans. RC must not contain class D/E.
- G8 C2C INCOMPLETE ⇒ **MVP-VERIFIED = NO-GO**.
- `PLAN REVISION REQUIRED: <reason>` when live state contradicts this plan. Do not silently redesign.
- Session contract is binding: named-start, STOP classes, short closeout. No silent wait. No rubber-stamp `تایید` on Agent-only PASS.
- Rehearsal Remnawave must not control production nodes (E8). After a RW dump restore, `nodes` stays empty (or only an isolated dummy).

---

## Session contract

### Named-start (new chat)

A new chat may run MVP/cutover tasks only if the **user message** names a task ID (`M6-T5`, `M7-T1`, …) or says **ادامه** or **شروع M6** (or the current open milestone). `شروع M6` / `ادامه` still cannot cross a STOP class (M6-T5 is user-visible + high risk).

**Not** named-start: greeting, status question, unrelated bug, “what is next?”, or the next-pointer sitting in this file with no user verb. Default: report next pointer + STOP ahead; do not start the task.

**Skill:** `executing-plans`. Load **this file** (live plan) + the **open milestone section**. Do not load the frozen archive. Do not retarget `origin`; do not rewrite live `/opt/remnabot1/.env`; do not author `staging-host-*` working URLs. `rehearsal_bot` polling on the test token is authorized after M6-T4.

### Continue vs STOP (same chat)

**Continue without asking** when all of: next task is Agent-only; same milestone **or** remaining named-batch weight ≤ 8; next task is not a STOP class; current verification passed.

**STOP** (do not start the next task) when any of:

| Class | Examples |
|---|---|
| User-visible | Operator must tap Telegram, open `https://panel.rookari.com`, or run a query they own |
| Missing prerequisite | P2 blocks M7-T5/M8 |
| High risk | Weight 13 or 21; DNS; production token; writer freeze; M8 |
| Failure | Test/gate fail; `PLAN REVISION REQUIRED` |
| Checkpoint end | End of M6.1 after T3; MVP-VERIFIED; M7/M8 boundaries |

M6.1 = {M6-T1, M6-T2, M6-T3} **DONE**. M6.2 = {M6-T4} **DONE** (G8 PASS). Named-start for M6-T5 (user-visible + high risk). Do not auto-start M8 from a next-pointer.

### Closeout

Agent-only:

```
<task> انجام شد.
HEAD: <sha> prod-cutover — pushed|local
<one-line what changed>. rehearsal_bot روشن نشد.

اسموک کاربر: ندارد
Agent: <commands → PASS/FAIL>

بعدی: <id>
ایست: ندارد
```

STOP:

```
…
بعدی: <id>
ایست: <class> — <reason>
```

Silent wait (no HEAD, no next pointer, no STOP line) is a **contract failure**. `تایید؟` is not required on Agent-only continue. If STOP: do not say `تایید یعنی برو به …`. User-visible STOP: at most **3** items, each `مسیر` + `انتظار`. Operator replies `تایید` (all OK) or `2 FAIL: …`.

Do not keep an Open smoke table in this plan. Closed-batch evidence: `docs/superpowers/evidence/smoke-YYYY-MM-DD-<task>.md` (short).

---

## Closed milestones (bodies in archive)

| ID | Status | Evidence |
|---|---|---|
| M0-T0…T6 | DONE 2026-08-31 (T7 CANCELLED) | `2026-08-29-git-topology.md`, `2026-08-31-wip-inventory.md`, `2026-08-31-cabinet-git.md`, `2026-08-31-upstream-tracking.md`, `2026-08-31-alembic-graph.md` |
| M1 | DONE (T4 cancelled) | `2026-08-31-env-matrix.md` |
| M2-T0…T2 | DONE 2026-09-01 | `2026-09-01-m2-t0-rw-281-pin.md`, `2026-09-01-m2-t1-bot-restore-g1.md`, `2026-09-01-m2-t2-rw-restore-g2.md` |
| M3-T0, T1, ID, T2 | DONE 2026-09-01 | `2026-09-01-m3-t0-rw-candidate.md`, `2026-09-01-m3-t1-rw-candidate-g3.md`, `2026-09-01-m3-id-identity-api.md`, `2026-09-01-m3-t2-pg17.md` |
| E8 | DONE 2026-09-01 | `2026-09-01-e8-nodes-isolation.md` |
| M4-T0…T7 | DONE 2026-09-01 | `2026-09-01-m4-t0-alembic-graft.md` … `2026-09-01-m4-t7-custom-port.md` |
| M5-T1…T3 | DONE 2026-09-01 | `2026-09-01-m5-t1-rc-cabinet.md`, `2026-09-01-m5-t2-cabinet-source.md`, `2026-09-01-m5-t3-cabinet-jwt.md` |
| M6-T1 | DONE 2026-09-01 | `2026-09-01-m6-t1-fa-fallback.md` · smoke `smoke-2026-09-01-m6-t1.md` |
| M6-T2 | DONE 2026-09-01 | `2026-09-01-m6-t2-toman.md` · smoke `smoke-2026-09-01-m6-t2.md` |
| M6-T3 | DONE 2026-09-01 | `2026-09-01-m6-t3-wholesale.md` · smoke `smoke-2026-09-01-m6-t3.md` |
| M6-T4 | DONE 2026-09-02 | `2026-09-02-m6-t4-c2c-g8.md` · smoke `smoke-2026-09-02-m6-t4.md` |

Evidence root: `docs/superpowers/evidence/`. How-to bodies for closed tasks live only in the frozen archive.

---

## Six identities (do not conflate)

| # | Identity | Tree / remote | Role |
|---|---|---|---|
| 1 | Production reference | `/opt/remnabot` · `origin` = `k4lantar4/remnabot` · 3.60.0 | READ-ONLY. Never modify during RC |
| 2 | Maintained bot | `/opt/remnabot1` · `origin` = `k4lantar4/remnabot1` · 4.2.0 · branch `prod-cutover` | Working source |
| 3 | Upstream bot | `BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot` | Fetch/compare only |
| 4 | Upstream working tree | `/opt/bot` | READ-ONLY. Never compose-up, restore, or implement |
| 5 | RC runtime | `bot-v4` / `91.107.144.95` · test token · `panel.rookari.com` | Sandbox `remnabot1_postgres_data` still **`0110`** — do not rebuild against the graft. `rehearsal_bot` polling on test token after M6-T4 (G8) |
| 6 | Production runtime | `Bot` / `91.107.249.43` · `/opt/bot-remnawave` | Live until cutover; then rollback target |

**Cabinet:** `/opt/cabinet` · `k4lantar4/cabinet` / upstream `bedolaga-cabinet`. Independent. Do not merge into remnabot1. Legacy: `/opt/remnabot/cabinet` READ-ONLY.

**Rejected names:** `cabinet1`, `/opt/cabinet1`, remnabot1 `origin` = `k4lantar4/remnabot`.

**Tree classes:** APPLICATION = `/opt/remnabot1`, `/opt/cabinet`. INFRASTRUCTURE = `/opt/caddy`, `/opt/remnawave`. PRODUCTION REFERENCE = `/opt/remnabot`; `/opt/bot-remnawave` on Bot. UPSTREAM REFERENCE = `/opt/bot`. Production inspect: `ssh bot` (read-only during RC). Production modification only in explicit M8 with user authorization.

---

## Standing Alembic

**Collision:** remnabot1 upstream `0088` ≠ remnabot `0088` (`create_c2c_receipts`). Last shared identical revision = **`0087`**. remnabot `0096` is a merge `down_revision = ('0094','0095')`.

**Now (M4-T3 DONE):** remnabot1 live graph = remnabot lineage through **`0111`** (remnawave_id + boot extras; `down_revision='0104'`). G1 restore (`rehearsal_bot_pg15`) is **`0111`** with G6 backfill (`subscriptions.remnawave_id` **3170/3173** via `short_uuid`; `users.remnawave_id` stays 0, multi-tariff). `persist_identity` writes panel numeric `.id` (bigint; not uuid lookup).

**Must remain on the live graph:** C2C (`0088`, `0094`), wholesale (`0093`), partner (`0095`), merge (`0096`), serial (`0101`), entities_json (`0102`), user_disabled (`0103`), traffic clamp (`0104`), plus remnabot `0089–0092`, `0097–0100`.

**Forbidden:** apply archived remnabot1 upstream `0088–0110` (`docs/superpowers/reference/upstream-alembic-0088-0110/`) onto a remnabot-lineage `0103` database. Copy those files back into `versions/`. Commit a full `alembic revision --autogenerate` (proposes deferred 4.2 tables and would drop C2C/wholesale/`user_disabled`). `alembic upgrade` / `stamp` sandbox `remnabot1_postgres_data` (still upstream **`0110`**) with the grafted graph — restart that bot only with `SKIP_MIGRATION=true`.

Graft of remnabot `0088–0104` was authorized. “Never reuse donor revision IDs” forbids copying **upstream `/opt/bot`** migrations onto production data.

**Dumps (rehearsal input — not cutover artifacts):** `/opt/remnabot/old_3.60_remnawave_bot.sql` SHA-256 `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85` (`alembic_version=0103`). `/opt/remnawave/old(2.8.1)_remnawave.sql` SHA-256 `11935de69fc6dc318419753916ff840f950f5b4be7a27be46e2ccf2142347377`.

---

## Host / volume / node standing (E1–E5, E8)

**E1 volumes:** restore/rehearsal only onto `rehearsal_*` or `cutover_*`. **Forbidden on RC:** `remnawave-db-data`, `remnabot1_postgres_data`, `remnabot1_redis_data`, `caddy-ssl-data`, `valkey-socket`. **Forbidden on Bot:** `bot-remnawave_postgres_data`, `bot-remnawave_redis_data`, `bot-remnawave_*`, `remnawave-db-data`, `remnawave-admin_postgres_data`, `remnawave-staging_staging_postgres_data`, plus fossils in `docs/superpowers/evidence/2026-08-29-host-inventory-prod.md`.

**E2:** Live production on Bot = `/opt/bot-remnawave`. `/opt/bot-remnawave` on RC is **absent**. `/opt/remnabot` on RC is READ-ONLY 3.60 reference.

**E3:** Production Bot PG = `postgres:15-alpine` @ `sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f` (15.18). Rehearsal used that digest.

**E4 two-track:** G3 evidence only from rehearsal-restore (`2.8.1` then candidate on PG **17.6**). RC sandbox (`backend:3`, PG 18.4, `:latest`) is **not** promotable. PG 17→18 is a separate track.

**E5:** RC public hostname is `panel.rookari.com`. DNS A `staging-host-*` may exist; they are **not** operational RC. Do not put those names in RC env. Production app names stay off RC Caddy until M8.

**E8:** After any RW dump restore, `nodes` must be empty (or only an isolated dummy from **this** panel) **before** the rehearsal backend is left running. Never copy production node addresses, ports, or keys. `hosts` may keep restored public hostnames. A live Xray node is not required for remaining M6 gates. Optional dummy only if a later named batch asks: `rw-rehearsal.rookari.com` A → `91.107.144.95` → `127.0.0.1:3100`. Evidence: `docs/superpowers/evidence/2026-09-01-e8-nodes-isolation.md`.

---

## Cutover safety

### DNS (locked)

- Authoritative: Cloudflare. Production app records: A only, TTL 300, DNS-only, target `91.107.249.43` today.
- Cutover: change those A records to `91.107.144.95`.
- No AAAA. No orange-cloud proxy as part of this migration. No Primary IP / Floating IP change.
- Hostnames that **move:** `cabinet`, `hooks`, `master`, `sub`, `miniapp` (optional `pgadmin` — out of app routing scope unless later decided).
- Hostnames that **must not** be treated as production cutover: `panel`, `rw`, `config`, `staging-host-*`, `admin*`, apex `rookari.com`.

### Environment classes (A–E)

Production `.env` is the **behavioral reference**, not a file to copy blindly. Never print secret values.

**A — Must preserve (behavior):** language/currency/Toman, tariff prices and periods, product feature flags, `WEBHOOK_PATH=/webhook`, `REMNAWAVE_AUTH_TYPE=api_key`, C2C copy/limits (not the admin chat id), wholesale/partner flags, `CABINET_ENABLED`, `DEFAULT_LANGUAGE=fa`, `MULTI_TARIFF_ENABLED`, traffic packages.

**B — RC-specific override:**

| Variable | RC value shape |
|---|---|
| `BOT_TOKEN` | existing **test** token only (live `/opt/remnabot1/.env`) |
| `BOT_RUN_MODE` | `polling` (live `.env`; do not switch to webhook unless the user asks) |
| `WEBHOOK_URL` | `panel.rookari.com` (live `.env`). Never `https://hooks.rookari.com` |
| `WEBHOOK_SECRET_TOKEN` | empty while polling |
| `CABINET_URL` | `https://panel.rookari.com` |
| `WEB_API_ALLOWED_ORIGINS` | `*` (live `.env`; working RC) |
| `CABINET_ALLOWED_ORIGINS` | `*` (live `.env`) |
| `C2C_ENABLED` | `true`. Isolated P1 `C2C_ADMIN_CHAT_ID` on `.env.rehearsal` (fp `0fcbb8097f77ea8b`; ≠ production). Dummy cards. Do not copy a production admin chat id |
| Remnawave `PANEL_DOMAIN` | `rw.rookari.com` (live `/opt/remnawave/.env`) |
| Remnawave `FRONT_END_DOMAIN` | `*` (live RW env) |
| Remnawave `SUB_PUBLIC_DOMAIN` | `config.rookari.com/sub` (live RW env) |
| `IS_TELEGRAM_NOTIFICATIONS_ENABLED` | `false` unless a **non-production** RW Telegram token exists |
| `REMNAWAVE_API_URL` | live sandbox: `http://remnawave:3000`. Isolated rehearsal compose only: `http://rehearsal_rw:3000` |

**C — Generated for RC:** passwords for new PG volumes; RC `CABINET_JWT_SECRET`; RC webhook secret if webhook mode.

**D — Production-only secrets (cutover, not RC compose):** production `BOT_TOKEN`, production `WEBHOOK_SECRET_TOKEN`, production `CABINET_JWT_SECRET`, `REMNAWAVE_API_KEY`, Remnawave `JWT_*`, live Bot DB passwords (needed to dump, not to start RC), Caddy/pgAdmin prod passwords, Cloudflare token if used for DNS-01.

Store D in `.env.cutover` that is **not** referenced by RC `env_file`. Load only at the cutover start-new-bot step.

**E — Must never enter RC:** production `BOT_TOKEN` before cutover; production webhook URL while RC is running; production `C2C_ADMIN_CHAT_ID`; production payment provider API tokens/secrets; production Remnawave Telegram token.

Cabinet: `VITE_API_URL=/api` (relative) remains. `VITE_TELEGRAM_BOT_USERNAME` on RC is the **test** bot username (`mrj7_bot`).

RC compose must fail closed if `BOT_TOKEN` fingerprint equals the known production fingerprint (M1-T2).

**Two stacks (do not conflate):** live remnabot1 sandbox uses `/opt/remnabot1/.env` and `REMNAWAVE_API_URL=http://remnawave:3000` on `panel.rookari.com` (already running — do not rewrite that `.env` for cutover work; sandbox DB is still **`0110`**). Isolated rehearsal compose uses gitignored `.env.rehearsal` with the **same public URLs** and `REMNAWAVE_API_URL=http://rehearsal_rw:3000`. `rehearsal_bot` polling on the test token is authorized after M6-T4.

### Cutover Caddy (five production blocks)

| Name | Route |
|---|---|
| `cabinet.rookari.com` | `/api/*` → bot; else cabinet |
| `hooks.rookari.com` | → bot (include `/webhook` and existing payment path handles) |
| `master.rookari.com` | → remnawave `:3000` |
| `sub.rookari.com` | subscription page; preserve production root redirect if still required |
| `miniapp.rookari.com` | miniapp static + bot `/miniapp` |

Do not add `pgadmin`/`admin`/`rw`/`config`/`panel` as app routes. HTTP-01 issues after the A record points here unless M7-T6 pre-issues via DNS-01. SNI: new host must serve the exact production names.

### Telegram isolation

**RC:** existing separate test token only. Never `setWebhook` / `deleteWebhook` / `getUpdates` with the production token from RC. RC uses **polling** and `WEBHOOK_URL=panel.rookari.com` per live `/opt/remnabot1/.env`. Never `https://hooks.rookari.com`. `WEBHOOK_IP` stays unset.

**Cutover Telegram order:**

1. Stop production bot (releases the webhook consumer on `Bot`).
2. Switch application/runtime on `bot-v4` to production secrets + production webhook URL.
3. Start **one** new bot process with production token.
4. Verify `getWebhookInfo` shows `https://hooks.rookari.com/webhook`.
5. Optionally `setWebhook` to the same URL if info is stale.

Never two production-token processes at once. remnabot1 **always** `setWebhook` when `BOT_RUN_MODE=webhook` — therefore the new process must not start with the production token until step 3.

Production RW Telegram token ≠ staging RW token. RC rehearsal panel must not use the production RW token.

### C2C isolation

C2C is Telegram-admin, not an HTTP callback. Production enabled method is **only C2C**.

RC may enable C2C **only if all** of: test Telegram bot (not production token); `C2C_ADMIN_CHAT_ID` is a **test** chat, never the production admin chat; restored production `c2c_receipts` data is allowed (historical rows).

If a truly isolated test admin chat cannot be established (P1 missing): do **not** fake PASS. G8 INCOMPLETE ⇒ **MVP-VERIFIED = NO-GO**. Do not post RC receipts into the production admin chat.

P1 **SATISFIED** (M6-T4). `.env.rehearsal` has an isolated `C2C_ADMIN_CHAT_ID` (fp `0fcbb8097f77ea8b`), dummy cards, test token. Empty admin chat would fall back to notifications — do not poll that way. G8 **PASS**.

Protected columns/tables: `c2c_receipts` and related remnabot `0088`/`0094` fields. Grafted graph must not drop them.

### Rollback

Old host is a **rollback target**, not a second live application after cutover.

After cutover: old bot **stopped**; old Remnawave **stopped**; old production DBs **preserved and untouched**; x-ui/xray **remain active** (independent).

Rollback procedure:

1. Stop the new application on `bot-v4` (releases production Telegram token).
2. Restore Cloudflare A records to `91.107.249.43`.
3. Start frozen 3.60 / 2.8.1 stacks on `Bot`.
4. Verify/restore Telegram webhook to `https://hooks.rookari.com/webhook` if needed.
5. Verify cabinet, sub, panel, C2C.

Do **not** in-place downgrade Remnawave 3.x or Alembic `0111+`. TTL 300s is the DNS convergence window.

### Writer freeze + cutover sequence (order is a safety constraint)

Writers = production **bot container** (webhook consumer + scheduler) and production **Remnawave backend container**. Freeze **before** their DB is dumped. PostgreSQL-safe snapshots only (`pg_dump -Fc` or stopped-container filesystem). Never tar a running PGDATA.

High-level order:

1. RC isolation standing (test token, non-prod Caddy, new volumes).
2. Bot restore rehearsal + remnabot `0104` + `0111+` on copy.
3. Remnawave 2.8.1 restore rehearsal + candidate digest upgrade on copy.
4. `remnawave_id` backfill against rehearsed 3.x.
5. Cabinet (`/opt/cabinet`) + protected-behavior smoke on RC names.
6. If candidate gates fail: stop, revise RW target, do not cut over.
7. Maintenance: freeze writers; dump bot + RW; checksum.
8. Restore fresh dumps onto proven path; migrate; **pre-DNS verify** on `bot-v4` (`curl --resolve` / internal upstreams). Production Caddy names added on `bot-v4`.
9. Old production bot + RW stay stopped. Never two production-token processes.
10. Flip Cloudflare A records → `91.107.144.95`.
11. Start **one** new bot with production token + `https://hooks.rookari.com`.
12. Verify webhook, cabinet, sub, master, C2C, FA.
13. Leave `Bot` apps stopped, DBs intact, x-ui running.

### Verification gates G1–G13

A gate is PASS only with evidence. “Build succeeded” is not PASS.

| Gate | When | Must show |
|---|---|---|
| G1 Restore bot | After rehearsal restore | `0103` then migrated `0111`, user count, `c2c_receipts`, C2C enabled, not `0106` |
| G2 Restore RW | After rehearsal restore | 2.8.1 schema, user count, `users.uuid`, Prisma tail `20260625200530_add_external_squad_index`, 2.8.1 login on RC hostname |
| G3 RW candidate | After upgrade copy | numeric identity, reconstructible correlation, counts, joins, login, sub link, no mass revoke |
| G4 Bot 0104 | After clamp migration | alembic 0104, traffic_purchases invariant |
| G5 Bot 0111+ | After new revisions | expected tables/columns; C2C/wholesale columns still present |
| G6 Backfill | After 3.x + 0111 | sample `remnawave_id` matches panel `users.id` |
| G7 Telegram RC | Continuous | production `getWebhookInfo` still production URL; RC uses test token |
| G8 C2C | RC | isolated chat **PASS** required for MVP-VERIFIED. INCOMPLETE = **NO-GO** |
| G9 Cabinet | RC | `https://panel.rookari.com` login/API; FA strings; Toman display |
| G10 Wholesale | RC | protected pricing path |
| G11 Cutover Telegram | After start new bot | webhook URL live; single consumer |
| G12 Cutover HTTP | After DNS | cabinet/hooks/master/sub/miniapp 200/expected on new IP |
| G13 Rollback drill | Before cutover window | documented dry-run of DNS revert + old stack start **without** executing live revert |

---

## Repeatable upstream policy

Never deploy implicit `latest`, `backend:3`, or an unreviewed moving branch. Observed 4.2.0 / cabinet 1.67.0 / panel **3.4.3** are **candidate snapshots**. Promote only: Git SHA (bot, cabinet) and/or image digest (Remnawave) + Alembic head + verification evidence.

Remnawave: inspect official `remnawave/panel` releases; candidate tag **3.4.3** is tracking not pin; G3 from rehearsal-restore track only. Do not duplicate Prisma/panel migrations in the bot.

---

## Payment scope (MVP)

- **C2C: mandatory.** Isolated test admin chat (P1) required. G8 INCOMPLETE ⇒ **MVP-VERIFIED = NO-GO**.
- **Telegram Stars / CryptoBot:** disabled-but-importable if they start cleanly. No new business logic unless promoted.
- **Russian-specific providers** (YooKassa, Platega, Lava, CisPay, rest of remnabot1 enum): compatibility-only. Imports must not break startup; production credentials never enter RC.

Wholesale gating uses the **ported remnabot `price_display` path** (`partner_status` + `wholesale_discount_bps`), not the lost T2.1 `app/custom/pricing` seam.

---

## Forbidden actions (DAG edges)

1. **M4-T6 PASS (G6).** G1 restore is **`0111`**. `subscriptions.remnawave_id` **3170/3173**. Full autogenerate would drop C2C/wholesale — **do not commit that**. `rehearsal_bot` polling on the test token is authorized after M6-T4 (G8). Never `alembic upgrade` / `stamp` `remnabot1_postgres_data` (still **`0110`**) with the grafted graph; `SKIP_MIGRATION=true` if that bot must restart.
2. **Never** `docker compose up` / restore against production or legacy volumes (`remnawave-db-data`, `remnabot1_postgres_data`, `bot-remnawave_postgres_data`, `bot-remnawave_*`, admin/staging fossils). Rehearsal uses only `rehearsal_*` / `cutover_*`.
3. **Never** start the production-token bot until the old production bot is stopped (M8).
4. **Never** apply remnabot1 archived upstream `0088–0110` to a remnabot-lineage `0103` database.
5. **Never** leave production Remnawave `nodes` rows in a second live panel (E8).

The existing RC `remnabot1` compose project is the **dev sandbox**. Do not restore dumps onto it. Do not treat it as rehearsal.

---

## Prerequisites

| # | Prerequisite | Blocks | Status |
|---|---|---|---|
| P1 | Isolated C2C test admin chat (≠ production) | M6-T4, MVP-VERIFIED | **SATISFIED** 2026-09-02. fp `0fcbb8097f77ea8b` ≠ prod notifications. G8 PASS. |
| P2 | Cloudflare DNS write access | M7-T5, M8 | **UNKNOWN** — ask the user |
| P3 | Cloudflare token for DNS-01 (optional) | M7-T6 preferred path | **UNKNOWN** — HTTP-01 window if missing |
| P4 | `remnawave/backend:2.8.1` pullable | M2 (done) | **SATISFIED.** Digest `sha256:361f9bb0b183d4fcefea2f1f7163db490e2aa1ec3b4bdde016a9ab9229ce956b` |
| P5 | Read-only production RW env/compose on `Bot` | M2 (done); M7-T2 | **SATISFIED.** |
| P6 | Production bot dump | M2 (done) | **SATISFIED.** SHA-256 `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85` |

Remaining path: **STOP** M6-T5 (user-visible + high risk; G8 PASS) → M7 → M8 (21, explicit user authorization) → M9.

Weights: 1,2,3,5,8,13,21. Batches: NORMAL 8–13, HIGH-RISK 3–8, 21 standalone.

---

# M6 — Protected behavior + end-to-end MVP

M6-T1…T4 are DONE (see Closed milestones). Checkpoints **M6.1** and **M6.2** complete. Next is M6-T5 (named-start; user-visible).

### Task M6-T3: Wholesale pricing regression gate (G10)

- **ID:** M6-T3 · **WEIGHT:** 3 · **DEPENDENCIES:** M4-T7
- **STATUS:** **DONE** 2026-09-01 (`docs/superpowers/evidence/2026-09-01-m6-t3-wholesale.md`).
- **STOP after:** Checkpoint end M6.1 + next task is M6-T4 (P1).
- Lock wholesale gating on `partner_status`+`wholesale_discount_bps` via the **ported remnabot `price_display` path**, not the lost T2.1 `app/custom/pricing` seam.
- Test `tests/services/test_wholesale_pricing.py` (adapt from remnabot). Integer BPS, floor; approved partner discounted, revoked not. `PartnerStatus` has no `REVOKED`; gate uses **`REJECTED`**.
- **COMMIT:** `test(M6-T3): wholesale gate`

- [x] **Step 1:** Named gate `tests/services/test_wholesale_pricing.py` (7 tests).
- [x] **Step 2:** Ported `tests/test_wholesale_pricing.py` 11 passed; `import main` OK; `rehearsal_bot` not started; `remnawave_bot` not rebuilt this batch.

### Task M6-T4: C2C isolated RC test — HARD MVP gate

- **ID:** M6-T4 · **WEIGHT:** 5 · **RISK:** High · **DEPENDENCIES:** M4-T7, P1
- **STATUS:** **DONE** 2026-09-02 (`docs/superpowers/evidence/2026-09-02-m6-t4-c2c-g8.md`). **G8 PASS.** Checkpoint **M6.2**.
- Isolated P1 chat + test bot: receipt → approve → Toman credit + `c2c_receipts` row. Dummy cards. Never production admin chat.
- **COMMIT:** `docs(M6-T4): C2C RC PASS (isolated chat)`

### Task M6-T5: End-to-end RC MVP smoke — MVP-VERIFIED gate

- **ID:** M6-T5 · **WEIGHT:** 8 · **RISK:** High · **DEPENDENCIES:** M6-T1..T4 (**G8 PASS required**), M4-T6, Checkpoint M3-ID
- **STOP class:** User-visible + High risk. **FILES:** `docs/superpowers/evidence/2026-08-31-rc-e2e-smoke.md`.
- Rehearsal bot (test token) on the `0111`+backfilled copy talking to the **rehearsal-passed candidate digest**: subscription purchase/renew; panel-user read/update **by numeric id** (or whatever M3-ID proved); sub link on `config.rookari.com` (live RW `SUB_PUBLIC_DOMAIN`); cabinet login on `https://panel.rookari.com`; FA+Toman+wholesale; C2C (G8 PASS). Do not use `staging-host-*` as the smoke URLs. Live VPN through a node is **not** part of this gate (E8: `nodes` empty unless a later batch adds an isolated dummy).
- **FAILURE:** any protected-behavior regression, or **G8 not PASS** → **MVP-VERIFIED = NO-GO**; block cutover.
- **CHECKPOINT:** **Checkpoint MVP-VERIFIED** (requires G8 PASS).

**Batches:** M6.1={M6-T1,M6-T2,M6-T3}(9, NORMAL); M6.2={M6-T4}(5, HIGH-RISK); M6.3={M6-T5}(8, HIGH-RISK).

---

# M7 — Production cutover preparation

Do not start M7 without **MVP-VERIFIED** (G8 PASS). Record promotion identity: remnabot1 `prod-cutover` SHA, cabinet SHA, Remnawave **image digest**, Alembic head, G3/G6 evidence.

### Task M7-T1: Stage cutover Caddy blocks (repo single-source, inactive)

- **ID:** M7-T1 · **WEIGHT:** 5 · **DEPENDENCIES:** Checkpoint MVP-VERIFIED
- **FILES:** `deploy/caddy/Caddyfile.cutover`.
- Author the five blocks per this plan’s Cutover Caddy table (no `pgadmin/admin/rw/config/panel`); validate a merged copy in a scratch container. Do not serve `hooks.rookari.com` from RC until M8.
- **COMMIT:** `feat(M7-T1): staged cutover Caddy blocks` · **CHECKPOINT:** Checkpoint M7.1.

### Task M7-T2: Stage cutover secrets (class D) + arm production-token guard

- **ID:** M7-T2 · **WEIGHT:** 3 · **RISK:** High · **DEPENDENCIES:** Checkpoint MVP-VERIFIED, P5
- **FILES:** `.env.cutover` (gitignored, NOT in any compose `env_file` until cutover); matrix note.
- On production (read-only), compute `token_fingerprint(BOT_TOKEN)` → set `PRODUCTION_BOT_TOKEN_FINGERPRINT` in `.env.rehearsal` (fingerprint, not token). Place class-D secrets only in `.env.cutover`. `WEBHOOK_IP` unset.
- **COMMIT:** `docs(M7-T2): armed prod-token guard (fingerprint only)`

### Task M7-T3: Rollback drill / tabletop (G13)

- **ID:** M7-T3 · **WEIGHT:** 5 · **DEPENDENCIES:** Checkpoint MVP-VERIFIED
- **FILES:** `docs/superpowers/runbooks/rollback.md`.
- Document + dry-verify this plan’s Rollback section: stop new app → restore A to `91.107.249.43` → start frozen 3.60/2.8.1 on `Bot` → optional `setWebhook` → verify cabinet/sub/panel/C2C. Validate the frozen compose parses; confirm old 2.8.1 volume+dump untouched. Do NOT `docker compose start` on live `Bot`.
- **COMMIT:** `docs(M7-T3): rollback runbook (G13)` · **CHECKPOINT:** Checkpoint M7.2.

### Task M7-T4: Writer-freeze + fresh-dump/restore/migrate timing rehearsal

- **ID:** M7-T4 · **WEIGHT:** 8 · **RISK:** High · **DEPENDENCIES:** Checkpoint M4.5, Checkpoint M3 (GO)
- **FILES:** `docs/superpowers/evidence/2026-08-31-cutover-timing.md`; `docs/superpowers/runbooks/writer-freeze.md`.
- Define writers explicitly (bot container + scheduler; RW backend container). Rehearse: stop the (rehearsal) bot writer → `pg_dump -Fc` bot → stop the (rehearsal) RW writer → `pg_dump -Fc` RW → checksum both → restore onto `cutover_bot_pg15`/`cutover_rw_pg17` → apply remnabot `0104`+`0111` (bot), 2.8.1→**candidate digest** (RW) → backfill → time each phase.
- **COMMIT:** `docs(M7-T4): writer-freeze runbook + cutover timing`

### Task M7-T5: Cloudflare DNS write-access verification (P2)

- **ID:** M7-T5 · **WEIGHT:** 3 · **DEPENDENCIES:** Checkpoint MVP-VERIFIED
- **FILES:** `docs/superpowers/runbooks/dns-cutover.md`.
- Confirm who/what can edit `cabinet/hooks/master/sub/miniapp` A records (TTL 300, DNS-only); record record IDs + current `91.107.249.43` → target `91.107.144.95`. `panel` / `staging-host-*` must-not-move vs names that move — document both. Change nothing now. No AAAA.
- **FAILURE:** no confirmed write access → cutover blocker (P2).
- **COMMIT:** `docs(M7-T5): DNS cutover runbook + write access`

### Task M7-T6: Pre-issue production TLS certs (DNS-01) or document HTTP-01 window

- **ID:** M7-T6 · **WEIGHT:** 5 · **DEPENDENCIES:** M7-T1, P3
- **Preferred:** Caddy with Cloudflare DNS plugin on `bot-v4` and `tls { dns cloudflare <token> }` to **pre-issue** certs for the five production names **before** DNS flip (P3 token; class D).
- **Fallback (no plugin / no P3):** document that HTTP-01 issues after the A record points here; verify content pre-DNS via `curl --resolve name:443:91.107.144.95` and internal upstreams over HTTP.
- **COMMIT:** `docs(M7-T6): TLS cutover strategy`

**Batches:** M7.1={M7-T1,M7-T2}(8, HIGH-RISK); M7.2={M7-T3}(5); M7.3={M7-T4}(8, HIGH-RISK); M7.4={M7-T5}(3); M7.5={M7-T6}(5). Checkpoint **CUTOVER-READY** after all M7 + MVP-VERIFIED (with G8 PASS).

---

# M8 — Cutover (weight 21, standalone)

### Task M8-T1: Execute production cutover (writer-freeze first, pre-DNS verify)

- **ID:** M8-T1 · **WEIGHT:** 21 · **RISK:** Critical · **DEPENDENCIES:** Checkpoint CUTOVER-READY, Checkpoint M3 (GO), Checkpoint M3-ID, all M7, **explicit user authorization** (this plan does not authorize execution)
- **STOP class:** High risk. Do not auto-start from a next-pointer.
- **GOAL:** Move production application + data + hostnames to `bot-v4` with a single bot process, no lost writes, and a reversible DNS flip.
- **FILES:** live `/opt/caddy/Caddyfile` (deploy `Caddyfile.cutover`), production compose on `bot-v4` (loads `.env.cutover`), Cloudflare A records.
- **Order is a safety constraint:**
  1. **Maintenance / quiesce.** Announce; stop admitting new work.
  2. **Freeze writers:** stop the production **bot container** (webhook consumer + scheduler) and the production **Remnawave backend container** on **Bot** (`/opt/bot-remnawave`). Confirm no writer process remains. x-ui continues (out of scope).
  3. **Fresh dumps:** `pg_dump -Fc` the bot DB and the RW DB (now write-frozen) — THE cutover artifacts. SHA-256 checksum.
  4. **Restore/migrate** onto `cutover_bot_pg15`/`cutover_rw_pg17`: bot remnabot `0104`+`0111`; RW 2.8.1→**rehearsal-passed candidate digest**; run `remnawave_id` backfill; verify coverage ≥ threshold.
  5. **Pre-DNS verification — before touching DNS:** application health; DB counts/integrity (G1/G2); migration integrity (`alembic 0111`, RW candidate digest); `remnawave_id` backfill coverage (G6); internal routing via `curl --resolve {cabinet,hooks,master,sub,miniapp}.rookari.com:443:91.107.144.95` and internal upstream checks; data integrity spot-checks. Deploy `Caddyfile.cutover` to `/opt/caddy`; if M7-T6 pre-issued certs, confirm they load.
  6. **Stop remains:** old production bot + RW stay stopped. **Never two production-token processes.**
  7. **Flip Cloudflare A records** → `91.107.144.95` (TTL 300). No AAAA. Do not move Primary IP. Do not move `panel` / `staging-host-*` unless the runbook says they move.
  8. **Start ONE** new bot with the production token (`ALLOW_PRODUCTION_BOT_TOKEN=1`, `.env.cutover`) + `WEBHOOK_URL=https://hooks.rookari.com`. `WEBHOOK_IP` unset.
  9. **Post-DNS verification:** `getWebhookInfo` = `https://hooks.rookari.com/webhook` (single consumer); TLS/SNI for the five names; public HTTP 200/expected; subscription URLs fetch configs; C2C + FA. Optional `setWebhook` if stale.
  10. Leave `Bot` apps stopped, DBs intact, x-ui running.
- **VERIFICATION (G11, G12):** single webhook consumer; five names 200/expected on the new IP with valid TLS; C2C + FA verified; backfill coverage gate met.
- **FAILURE:** pre-DNS verify fails → do not flip DNS (no downtime incurred). Post-flip TLS/webhook/data failure beyond TTL → invoke M7-T3 rollback.
- **ROLLBACK:** stop new app → DNS back to `91.107.249.43` → start frozen 3.60/2.8.1 → verify. Never in-place downgrade 3.x/`0111`.
- **CHECKPOINT:** **Checkpoint CUTOVER-DONE** (standalone). Requires explicit user go-ahead.

**Batch M8** = {M8-T1} (21, standalone).

---

# M9 — Post-cutover validation / stabilization

### Task M9-T1: Full production completion-gate verification

- **ID:** M9-T1 · **WEIGHT:** 8 · **DEPENDENCIES:** Checkpoint CUTOVER-DONE
- **FILES:** `docs/superpowers/evidence/2026-08-31-postcutover.md`.
- Verify app health; DB integrity/counts; migration integrity (`alembic 0111`, RW candidate digest); Telegram single-consumer; C2C; wholesale; FA; Toman; cabinet; subscription/purchase; production routing; `remnawave_id` coverage.
- **CHECKPOINT:** Checkpoint M9.1.

### Task M9-T2: Rollback readiness + freeze old stack

- **ID:** M9-T2 · **WEIGHT:** 5 · **DEPENDENCIES:** M9-T1
- Confirm old bot/RW stopped, old DBs intact+checksummed, x-ui active; document rollback expiry.
- **CHECKPOINT:** Checkpoint M9.2.

### Task M9-T3: RC/fossil cleanup (after stable)

- **ID:** M9-T3 · **WEIGHT:** 3 · **DEPENDENCIES:** M9-T2 + stability window
- Remove `rehearsal_*` volumes and donor fossils only after stability; keep `cutover_*` (live) and frozen rollback assets.
- **FAILURE:** accidental removal of a live/rollback volume.
- **CHECKPOINT:** Checkpoint M9.3.

**Batch M9** = {M9-T1}(8), {M9-T2}(5), {M9-T3}(3).

---

# Backlog (not MVP)

Russian payment integrations; coupons; grace product; referral v2; legal consents; guest-purchase extras — unless a boot dependency is proven (then schema-only, still disabled). Do not invent `0112–0126` because 4.2 files exist.

---

## Fresh-conversation resume

Resume from:

1. **This live plan** (not the archive)
2. remnabot1 branch `prod-cutover` @ current HEAD
3. `/opt/cabinet` git
4. `/opt/remnabot` as read-only custom source
5. `docs/superpowers/evidence/*` (re-check dates)
6. `.cursor/rules/10-remnabot-migration.mdc`
7. Runtime (`docker volume ls`, `alembic current`, Cloudflare A, `getWebhookInfo`, `ssh bot`)

Do **not** look for deleted `docs/superpowers/specs/2026-08-*` or `*-errata.md` on remnabot1. Do **not** load `docs/superpowers/plans/archive/2026-08-28-production-cutover-mvp.full.md` unless reconstructing a past decision.

**Open:** M6-T5. Named-start required (user-visible + high risk). Checkpoints M0–M5, M6.1, **M6.2** complete. G8 PASS. P1 SATISFIED. P2 still UNKNOWN. `rehearsal_bot` may remain polling on the test token. Do not start M7 without MVP-VERIFIED.
