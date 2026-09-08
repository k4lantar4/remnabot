> **FROZEN ARCHIVE — do not edit.** Freeze 2026-09-01. Pre-slim blob `bdb81d9692f9748a0b985980ec463dbe03e1362e` (`1383` lines).
> **Execute from:** `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md` (live plan).
> Read this file only to reconstruct a past decision or `PLAN REVISION`.
> If this file and the live plan disagree, the live plan wins for execution.
>
# Production Cutover MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL for each new chat: **superpowers:executing-plans**. One open batch only, then stop. Do **not** run the whole plan. Do **not** invoke finishing-a-development-branch until the user says the cutover work is done. Subagent-driven-development is optional *inside* a batch (fresh subagent per task), not a license to start M2–M8 in one session. Steps use checkbox (`- [ ]` / `- [x]`). Code tasks use TDD; operational tasks use evidence gates. "Container started" / "build passed" is **never** a PASS. Session contract + Open smoke below are binding.
>
> **Plan updated 2026-09-01.** **M2 DONE.** **M3 DONE.** **M4-T0 DONE.** **M4-T1 DONE** (4.2 does **not** boot cleanly on remnabot `0104` schema; MVP schema ≠ remnawave_id only). **M4-T2 DONE** (3.x client matches rehearsal 3.4.3; no rewrite). **M4-T3 DONE** (Alembic `0111` remnawave_id + extras; G1 restore is `0111`). **M4-T4 DONE** (models already match `0111`; full autogenerate is **not** empty — deferred tables + C2C/wholesale). **M4-T5 DONE** (`persist_identity` seam; panel `.id` only). **M4-T6 DONE** (G6 backfill; 3170/3173 shortUuid). **M4-T7 DONE** (C2C/FA/Toman/wholesale port; G8 not this batch). **M5-T1 DONE** (RC cabinet from `/opt/cabinet` on `panel.rookari.com`; split compose; user smoke **تایید**). **M5-T2 DONE** (canonical `/opt/cabinet`; no remnabot embed). **M5-T3 DONE** (rehearsal `CABINET_JWT_SECRET` fp `6e66e417433351da` ≠ prod `818cf61ccf8f100d`). **M6-T1 DONE** (FA fallback gate). **M6-T2 DONE** (Toman dual-scale gate). **Do not execute M6-T3 until the user confirms this batch.** M1-T4 remains cancelled.
>
> **RC public hostname revision 2026-08-31 (operator binding):** staging is **not** the operational RC. Live bot env `/opt/remnabot1/.env` and Caddy `https://panel.rookari.com` are the RC public-URL source. Do **not** put `staging-host-*` in RC env. M1-T4 as originally written (author `staging-host-*` Caddy) is **cancelled**.
>
> **This file is the single authority.** Specs/errata siblings were deleted on purpose. Binding facts from Architecture A, architecture errata, plan errata E1–E8, and the governance audit are inlined below. Executors do not need deleted files.

**Goal:** Produce a production-usable New-Version MVP: maintained bot at `/opt/remnabot1` (4.2 code + ported custom behavior) + separate cabinet at `/opt/cabinet` + a **verified immutable** Remnawave 3.x revision, rehearsed on production-lineage data, cut over by DNS, with rollback to frozen 3.60/2.8.1.

**Architecture:** Start from the clean 4.2 fork (`/opt/remnabot1`). Port only MVP-required custom behavior from `/opt/remnabot` (C2C, FA, Toman, wholesale/partner, production identity columns). Keep Cabinet as an independent application behind the API. Rehearse Remnawave 2.8.1 → a concrete 3.x **candidate** (M3-T0: official latest **v3.4.3** / `remnawave/backend:3.4.3` — **not** a permanent pin; RC sandbox `backend:3` is still non-promotable). Production DB stays on the **remnabot Alembic lineage** (`0103`/`0104`); do not apply remnabot1's upstream `0088–0110` files onto that database. Cutover freezes writers, dumps, restores, verifies pre-DNS, then flips A records.

**Tech Stack:** Python 3.12 / aiogram, SQLAlchemy + Alembic, PostgreSQL 15 (bot; production image `postgres:15-alpine` digest below) and 17.6 (Remnawave restore), Remnawave panel (rehearsal candidate, then immutable digest), Vite/React cabinet, Caddy 2.9 at `/opt/caddy`, Docker Compose, Cloudflare DNS-only.

## Global Constraints

- Production Primary IP never moves. No Floating IP. No AAAA. Cloudflare DNS-only. TTL 300.
- DNS cutover A records → `91.107.144.95`. Rollback A records → `91.107.249.43`.
- Live production path on Bot is `/opt/bot-remnawave` (not `/opt/remnabot`).
- Cabinet = `/opt/cabinet` (`k4lantar4/cabinet`). Never `/opt/cabinet1`. Never merge cabinet into remnabot1.
- remnabot1 `origin` = `k4lantar4/remnabot1`. Do not retarget origin to `k4lantar4/remnabot`.
- Last shared Alembic revision = `0087`. From `0088`, same IDs, different semantics. Production DB = remnabot-lineage `0103`. remnabot1 **live graph after M4-T0** = remnabot `0104` (traffic clamp). Upstream `0088–0110` archived. Graft before any remnabot1 app mounts a restored dump.
- Restore/rehearsal volumes: **only** `rehearsal_*` / `cutover_*`.
- Remnawave two-track: rehearsal-restore (`backend:2.8.1` digest on frozen `rehearsal_rw_pg17`; **G3-passed candidate** `backend:3.4.3@sha256:4ea85b2f…84515422` on `rehearsal_rw_pg17_candidate`, PG 17.6, sub 7.2.6 unstarted). RC sandbox (`backend:3`, PG 18.4, `:latest`) is **not** promotable.
- Bot PG: pin production `postgres:15-alpine` digest unless 15.18 compatibility is proven.
- Writers freeze before dump. Pre-DNS verify before flip. Single production-token bot after old bot stopped.
- Rollback = DNS back + frozen 3.60/2.8.1. Never in-place downgrade 3.x or `0111+`.
- Secrets: fingerprints only in git/chat/plans. RC must not contain class D/E.
- G8 C2C INCOMPLETE ⇒ **MVP-VERIFIED = NO-GO**.
- `PLAN REVISION REQUIRED: <reason>` when live state contradicts this plan. Do not silently redesign.
- Session contract (next section) is binding: one batch, numbered smoke, no silent wait.
- Rehearsal Remnawave must not control production nodes (E8). After a RW dump restore, `nodes` stays empty (or only an isolated dummy). Do not ask for a live node for M4.

---

## Session contract (binding — 2026-08-31)

Repeatable loop for **every** new chat. The user pastes this plan and says which batch to start (e.g. «شروع M2»).

**Skill:** `executing-plans`. Announce it. Load **this file**. Review critically. Execute **only the named open batch**. HIGH-RISK batch total weight **3–8**. Then stop and wait **with** the end-of-chat briefing (never a bare «تایید؟»).

**Do not:** finish all remaining milestones; create a git worktree unless a task names a path; retarget `origin`; rewrite live `/opt/remnabot1/.env`; author `staging-host-*` as working URLs; start polling `rehearsal_bot` until a later named batch needs it.

### Two-layer smoke (write into the task *before* coding if missing)

| Layer | Who | When required | Cap |
|---|---|---|---|
| **Agent** | Agent runs commands; pastes evidence | Every batch | No cap; keep short |
| **User** | Operator on `@mrj7_bot`, `https://panel.rookari.com`, or a DB query they can run | **Only if** the batch changes something they can see or query | **Max 5** numbered items |

Infra/docs/compose-only batches (typical M2–M4-T0): User smoke = **none**. List Agent smoke. Closing line: «تایید یعنی برو به `<next task ID>`» — not a Telegram checklist.

User-visible batches (bot copy, cabinet, C2C, prices, login): each User smoke row must have **path** (exact taps/URL/SQL), **expect**, **before**. Operator replies `1 OK` / `2 FAIL: …`. Do not start the next batch without those numbers.

**Where to write smoke**

- Living table: **Open smoke (this batch)** below — overwrite each session; keep ≤15 rows.
- Closed batches: append `docs/superpowers/evidence/smoke-YYYY-MM-DD-<batch>.md`. Do **not** grow this plan into a smoke log.

### End-of-chat briefing (mandatory — even when waiting)

```
## خلاصه
- چه عوض شد (فایل/رفتار)
- چرا
- قبل → بعد
- HEAD + pushed?

## اسموک من
N. سطح: بات | کابینت | DB | Agent
   مسیر / دستور: …
   انتظار: …
   قبل: …

اگر سطح کاربری ندارد: «اسموک کاربر: ندارد» + لیست Agent.

## بعد از تایید تو
<next task ID from this plan>
```

Silent wait (no before/after, no numbered list) is a **contract failure**. Update this plan in-place: task checkboxes, Open smoke `Status=pending`, wait line naming the next ID.

---

## Open smoke (this batch)

**Batch open:** M6-T2. **Wait:** user numbered OK → **M6-T3**.  
**User smoke:** none (Toman unit gate; no polling bot).  
**Last closed:** M6-T1 (`docs/superpowers/evidence/smoke-2026-09-01-m6-t1.md`).

| # | Layer | Path / command | Expect | Before | Status |
|---|---|---|---|---|---|
| 1 | Agent | `pytest tests/utils/test_price_display_toman.py` | 8 passed | remnabot had no `test_price_display_toman.py` | **PASS** |
| 2 | Agent | `pytest tests/utils/test_price_display.py` | 25 passed | M4-T7 helpers | **PASS** |
| 3 | Agent | `uv run python -c "import main"` | OK | M6-T1 | **PASS** |
| 4 | Agent | `grep -r get_admin_texts app/` | 0 | M6-T1 | **PASS** |
| 5 | Agent | `rehearsal_bot` / `remnawave_bot` | app absent; sandbox not rebuilt this batch | M6-T1 | **PASS** |

Wait after this batch: user numbered OK → **M6-T3** (wholesale pricing regression gate). Do not start polling `rehearsal_bot`. Do not rebuild `remnawave_bot`. G8 / P1 remain for M6-T4. Checkpoint M6.1 stays open until M6-T3.

---

## Re-verify 2026-08-31 (VERIFIED)

Recorded on RC (`bot-v4` / `91.107.144.95`) and via `ssh bot` (read-only). Contradicts the 2026-08-29 plan claim “No task executed.” Git snapshot below is **pre-T2–T6** (governance seed @ `a168a817`); checkpoint HEAD after closeout is `2877a28f`.

### Git

| Tree | Branch / HEAD | Notes |
|---|---|---|
| `/opt/remnabot1` | `prod-cutover` @ `a168a817cbfdbab020ed3b328c596d866dfbc2a6` (`docs: governance topology audit and pre-M0 artifacts`) | Local branch only (`refs/heads/prod-cutover`; **not** on `origin`). |
| `/opt/remnabot1` `main` | `89fa7dc584b9fb7f017c385d604614fb29692d66` (4.2.0) | **behind `origin/main` 1** (`origin/main` = `31a3e93042e528ac13f1b8aa9f4acb02001bac99` “Create python-app.yml”). Do not silently merge that CI commit into cutover work. |
| `/opt/cabinet` | `main` @ `35e5aa9e78123fdf18506a7a8a46875d268689ed` (1.67.0) | origin `k4lantar4/cabinet`; upstream `bedolaga-cabinet`; clean |
| `/opt/remnabot` | `main` @ `f36ec4ca078eea3f2647f01887ccf987823fbfd0` (3.60.0) | READ-ONLY |
| `/opt/bot` | `main` @ `89fa7dc584b9fb7f017c385d604614fb29692d66` | upstream WT; dirty `docker-compose.yml` |
| Architecture A remote | `k4lantar4/remnabot` `origin/chore/mcp-dev-tools` @ `70476c0e0a23657ce8959ffb76d0dfbebbd7e697` | **Optional historical reference only.** Facts needed to execute are inlined here. Do not follow its Alembic/cabinet paths. |

remnabot1 remotes (VERIFIED): `origin`=`k4lantar4/remnabot1.git`, `upstream`=`BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot.git`, extra `remnabot`=`k4lantar4/remnabot` (reference only).

Working tree at re-verify (do not treat as “clean”): `M .cursor/rules/10-remnabot-migration.mdc`, `M docker-compose.yml` (joins `remnawave-network`; comments out bot_network ipam), `D` four deleted spec/errata files, `?? docs/superpowers/plans/2026-08-31-plan-update-handoff.md`, `?? locales/`.

### Alembic (graft **DONE** 2026-09-01)

| Tree | Files on disk |
|---|---|
| remnabot1 live graph | remnabot `0088_create_c2c_receipts.py` … `0104_traffic_purchase_expiry_clamp.py`. `alembic heads` = **`0104`**. `0096` merge preserved. |
| remnabot | same `0088–0104` (source; SHA match) |
| Archive dir | `docs/superpowers/reference/upstream-alembic-0088-0110/` **present** (23 upstream files including `0104_remnawave_numeric_id.py` and `0110_referral_user_reward_choice.py`) |

### Dumps (rehearsal input — NOT cutover artifacts)

| File | SHA-256 |
|---|---|
| `/opt/remnabot/old_3.60_remnawave_bot.sql` | `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85` |
| `/opt/remnawave/old(2.8.1)_remnawave.sql` | `11935de69fc6dc318419753916ff840f950f5b4be7a27be46e2ccf2142347377` |

Bot dump `COPY alembic_version` = `0103`. `c2c_receipts` present. **P6 SATISFIED.**

### Artifacts (M0 checkpoint — 2026-08-31)

`docker-compose.rehearsal.yml` **absent**. `deploy/caddy/` **absent**. `rehearsal_*` / `cutover_*` volumes **absent** (expected until M1). Tag `baseline/prefork-4.2.0-89fa7dc5` **present** at `89fa7dc584b9fb7f017c385d604614fb29692d66` (M0-T4, commit `3f798500`).

### Production (`ssh bot`, 2026-08-31)

| Item | Value |
|---|---|
| Path | `/opt/bot-remnawave` **exists** |
| Bot image | `bot-remnawave-bot` |
| Bot PG | `postgres:15-alpine` digest `sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f` |
| Bot alembic | **`0103`** (live `SELECT version_num FROM alembic_version`) |
| RW | `remnawave/backend:2.8.1`, PG `postgres:17.6`, sub `remnawave/subscription-page:7.2.6` |
| C2C | enabled (env key present; value not recorded) |

Prod Caddy has `staging-host-{hooks,cabinet,miniapp,sub}.rookari.com` server blocks (no `staging-host-master`). Those names are **not** the operational RC. **E5 (revised):** RC public hostname is `panel.rookari.com`.

### RC runtime (non-promotable sandbox)

Running: `remnawave_bot`=`remnabot1-bot` (compose project `remnabot1` / `/opt/remnabot1`), `remnawave_bot_db`=`postgres:15-alpine`, `remnawave`=`backend:3`, `remnawave-db`=`postgres:18.4`, `remnawave-subscription-page`=`:latest`, `caddy`=`caddy:2.9`, `cabinet_frontend`.

RC volumes: `remnabot1_postgres_data`, `remnabot1_redis_data`, `remnawave-db-data`, `caddy-ssl-data`, `valkey-socket`. **All forbidden for restore.** This sandbox is **not** G3 evidence.

RC `/opt/caddy/Caddyfile` has **no** `staging-host-*` server blocks (unlike Bot). RC **does** serve `https://panel.rookari.com` (`/api/*` → `remnawave_bot:8080`, else cabinet). Live bot env `/opt/remnabot1/.env` uses `CABINET_URL=https://panel.rookari.com`, `WEBHOOK_URL=panel.rookari.com`, `BOT_RUN_MODE=polling`. `/opt/cabinet1` **absent**.

---

## Six identities (do not conflate)

| # | Identity | Verified tree / remote | Role |
|---|---|---|---|
| 1 | **Production reference** | `/opt/remnabot` (`origin` = `k4lantar4/remnabot`, HEAD `f36ec4ca`, CHANGELOG **3.60.0**); embedded `/opt/remnabot/cabinet` (cabinet-frontend **1.57.0**, not a separate git repo) | READ-ONLY. Inspect production code/config/history. Rollback code reference. **Never** the working source; **never** modify during RC |
| 2 | **Maintained repository (bot)** | `/opt/remnabot1` · `origin` = `https://github.com/k4lantar4/remnabot1.git` · `main` = **4.2.0** @ `89fa7dc5` · work branch `prod-cutover` @ `2877a28f` (checkpoint HEAD; governance seed `a168a817` 2026-08-31) | Final custom bot **code** authority after ports. Own Git history and release lifecycle |
| 3 | **Upstream repository (bot)** | `BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot` | Official bot upstream. Moving target. Fetch/compare only |
| 4 | **Upstream working tree (bot)** | `/opt/bot` · `origin` = official upstream · HEAD identical to remnabot1 `main` `89fa7dc5` · dirty: `docker-compose.yml` | Local read-only clone of upstream. **Not** canonical. Never `compose up`, never restore, never implement here |
| 5 | **RC runtime** | `bot-v4` / `91.107.144.95` · test Telegram token · public hostname `panel.rookari.com` (live `/opt/remnabot1/.env`) | Working RC sandbox is the **running** remnabot1 compose (`alembic` still **`0110`** on `remnabot1_postgres_data` — do not rebuild against the graft). Isolated rehearsal bot is **not** polling (M4-T1 was a probe only). Do not use `staging-host-*` as RC env URLs |
| 6 | **Production runtime (today)** | `Bot` / `91.107.249.43` · live app **`/opt/bot-remnawave`** · frozen 3.60 / 2.8.1 after cutover | Live until cutover; then rollback target |

**Cabinet (separate maintained application):**

| Identity | Verified | Role |
|---|---|---|
| Maintained cabinet repo + tree | `/opt/cabinet` · `origin` = `https://github.com/k4lantar4/cabinet.git` · `upstream` = `https://github.com/BEDOLAGA-DEV/bedolaga-cabinet.git` · HEAD `35e5aa9e` = **1.67.0** | Independent app. Talks to bot via `/api`. **Do not** merge into remnabot1 |
| Official cabinet upstream | `BEDOLAGA-DEV/bedolaga-cabinet` | Moving target |
| Legacy production cabinet | `/opt/remnabot/cabinet` (1.57.0, embedded in remnabot git) | READ-ONLY production topology |

**Remnawave runtime (not a git repo):** `/opt/remnawave` (panel compose `remnawave/backend:3` on RC sandbox) + `/opt/remnawave/subscription` (`remnawave/subscription-page:latest` on RC). Authorized infrastructure only. Production RW lives on Bot under the `/opt/bot-remnawave` stack (`backend:2.8.1`).

**Caddy:** `/opt/caddy` on RC (stock `caddy:2.9`). Production Caddy is `/opt/caddy-remnawave` on Bot. Canonical source of truth will live under remnabot1 `deploy/caddy/`.

**Rejected names:** `cabinet1`, `/opt/cabinet1`, remnabot1 `origin` = `k4lantar4/remnabot`.

---

## Claim verification

| Claim | Verdict | Evidence |
|---|---|---|
| `/opt/bot` is upstream clone | **CONFIRMED** | `origin` = official bot; HEAD = remnabot1 `main` |
| `/opt/remnabot` is remnabot origin clone | **CONFIRMED** | `origin` = `k4lantar4/remnabot`; 3.60.0; embedded `cabinet/` |
| `/opt/cabinet` is fresh upstream fork | **CONFIRMED** | origin `k4lantar4/cabinet` + upstream `bedolaga-cabinet`; HEAD = `35e5aa9e` |
| `/opt/remnabot1` is fresh upstream fork | **CONFIRMED** | origin `k4lantar4/remnabot1`; upstream official bot; `main` = 4.2.0 |
| Live prod path = `/opt/bot-remnawave` on Bot | **CONFIRMED 2026-08-31** | `ssh bot` `test -d /opt/bot-remnawave` |
| `/opt/bot-remnawave` on RC | **ABSENT** | host inventory + re-verify |
| Maintained cabinet = `k4lantar4/cabinet1` + `/opt/cabinet1` | **FALSE** | path missing; repo 404 |
| remnabot1 `origin` should be `k4lantar4/remnabot` | **FALSE** | origin is `remnabot1`; extra remote `remnabot` is reference only |
| Remnawave permanently pin 3.3.2 | **REJECTED** | Candidate / tracking snapshot. Promote only a verified digest after G3 |
| Donor/4.2 code = specification | **REJECTED** | Official panel + actual API + rehearsal + tests are authoritative |
| “No task executed” / untracked plan | **STALE as of 2026-08-31** | `prod-cutover` @ `a168a817` committed governance + 3 evidence files + this plan + rule |
| M0-T0 rule does not exist | **STALE** | `.cursor/rules/10-remnabot-migration.mdc` committed |
| Production bot PG = `postgres:15.18` | **STALE** | Production = `postgres:15-alpine` @ digest above |
| Pin Remnawave from RC sandbox `backend:3` | **FORBIDDEN** | Two-track; sandbox is non-promotable |

---

## Workspace governance

| Class | Trees | Allowed |
|---|---|---|
| **APPLICATION (maintained)** | `/opt/remnabot1`, `/opt/cabinet` | Implement, test, commit, push on migration branches |
| **AUTHORIZED INFRASTRUCTURE** | `/opt/caddy`, `/opt/remnawave` | Rehearsal/runtime orchestration only. No business logic. Caddyfile deployed from repo single-source |
| **PRODUCTION REFERENCE (protected)** | `/opt/remnabot` (incl. `/opt/remnabot/cabinet`); `/opt/bot-remnawave` on `Bot` | Read-only inspect. Never modify during RC. Production modification only in explicit M8 with user authorization |
| **UPSTREAM WORKING TREES (reference)** | `/opt/bot` only | Never compose-up, never restore, never implement |

Caddy single-source: canonical files in `/opt/remnabot1/deploy/caddy/`; live `/opt/caddy/Caddyfile` is a deploy of that file; every Caddy task ends with a SHA-256 drift check.

Machine-readable copy: `.cursor/rules/10-remnabot-migration.mdc` (**M0-T0 DONE**). After this plan update, that rule must point at **this plan** as single authority (not deleted specs).

---

## Locked errata vs Architecture A (binding — inlined)

Architecture A (`70476c0e`, 737 lines on remnabot remote `origin/chore/mcp-dev-tools`) was written when remnabot1 was assumed to be the custom 3.60 tree. Live trees invert that. **Do not recover the spec into remnabot1** (M0-T7 CANCELLED). Cutover-safety facts are inlined in this plan. Alembic/cabinet/prod-path in Architecture A body are **stale**.

| Stale Architecture A claim | Binding replacement |
|---|---|
| `/opt/cabinet1`; remnabot1 keeps custom `0001–0104` | Cabinet = **`/opt/cabinet`**. remnabot1 is **4.2** (`0001` plus upstream `0088–0110` on disk today). Custom Alembic `0088–0104` is **grafted from `/opt/remnabot`**. |
| Do **not** copy donor Alembic `0088–0110` into remnabot1 | That non-goal assumed remnabot1 already held production lineage. After inversion: **archive remnabot1 `0088–0110`** and **copy remnabot `0088–0104`**. “Donor” meant `/opt/bot`; do not copy `/opt/bot` files. |
| Production `0103` is remnabot1-lineage `subscription_user_disabled` | Production `0103` is remnabot-lineage `subscription_user_disabled`. remnabot1 `0103` is `add_legal_consents`. Same ID, different file. |
| Five identities; `/opt/cabinet` is a donor | Six identities in this plan. `/opt/cabinet` is **maintained**. `/opt/bot` is the only bot upstream working tree. |
| Pin Remnawave **3.3.2** | **Candidate**, not pin. M3-T0 selected **3.4.3** (`remnawave/backend:3.4.3`). Promote only a verified image digest after G3. |
| “Cabinet1” in cutover step 5 | `/opt/cabinet` |
| Dump name `old(3.60)_remnawave_bot.sql` | Live path: `/opt/remnabot/old_3.60_remnawave_bot.sql` |
| Production app path implied `/opt/remnabot` on Bot | Live production on Bot: **`/opt/bot-remnawave`**. RC reference clone: `/opt/remnabot`. |
| “Never reuse donor revision IDs” forbids all copies | Grafting remnabot `0088–0104` is **authorized**. The forbid applies to copying **upstream `/opt/bot`** migrations onto production data. |

**Alembic + cabinet path + cutover authority = this plan.**

---

## Plan errata E1–E8 (inlined; sibling file deleted)

### E1. Host-scoped volume forbidden lists

**Rule:** restore/rehearsal only onto volumes named `rehearsal_*` or `cutover_*`.

**RC (verified 2026-08-31):** `remnawave-db-data`, `remnabot1_postgres_data`, `remnabot1_redis_data`, `caddy-ssl-data`, `valkey-socket` — forbidden. No `bot_postgres_data` on this host.

**Bot (verified 2026-08-31):** never touch `bot-remnawave_postgres_data`, `bot-remnawave_redis_data`, `bot-remnawave_*`, `remnawave-db-data`, `remnawave-admin_postgres_data`, `remnawave-staging_staging_postgres_data`, or the feature-branch `*_postgres_data` fossils listed in `docs/superpowers/evidence/2026-08-29-host-inventory-prod.md` (re-verify that list before any Bot-side volume operation).

### E2. Production application path

| Host | Path | Role |
|---|---|---|
| Bot (`91.107.249.43`) | `/opt/bot-remnawave` | **Live** production compose + `.env` |
| RC | `/opt/remnabot` | READ-ONLY 3.60 reference clone |
| RC | `/opt/bot-remnawave` | **Absent** |

P5 read-only production env/compose: inspect **`/opt/bot-remnawave`** on Bot via `ssh bot`.

### E3. Bot PostgreSQL image

Production Bot runs **`postgres:15-alpine`** @ `sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f` (2026-08-31).

Rehearsal must either:

- pin **that same digest**, or
- document and test `postgres:15.18` compatibility before cutover.

`15.18` in earlier plan text is **aspirational**, not verified. Do not treat 15.18 as production-equivalent merely because it is a newer 15.x tag.

**Re-verify 2026-09-01 (M2-T1):** the pinned production digest **is** PostgreSQL 15.18 (`psql (PostgreSQL) 15.18` inside `rehearsal_bot_db`). Rehearsal used that digest; dump header is also 15.18. No separate `:15.18` tag was introduced.

### E4. Remnawave two-track model

| Track | Stack | Promotable? |
|---|---|---|
| Rehearsal-restore | `backend:2.8.1` digest on frozen `rehearsal_rw_pg17`; **G3-passed** `3.4.3@sha256:4ea85b2f…84515422` on `rehearsal_rw_pg17_candidate`, PG **17.6** | Candidate yes; production pin only at cutover |
| RC dev sandbox | `backend:3`, PG **18.4**, `subscription-page:latest` | **No** — exploratory only |

M3-T1/G3 evidence must come from the rehearsal-restore track, not the live RC sandbox. PG 17→18 is a **separate** track; do not combine with 2.8→3.x in one window.

### E5. RC public hostname is `panel.rookari.com` (not `staging-host-*`)

**VERIFIED 2026-08-31:** Bot `/opt/caddy-remnawave/Caddyfile` has `staging-host-{hooks,cabinet,miniapp,sub}` server blocks. RC `/opt/caddy/Caddyfile` has **no** those blocks. RC **does** serve `https://panel.rookari.com` (`/api/*` → `remnawave_bot:8080`, else cabinet).

**Operator binding:** staging is not the operational RC. Live bot env `/opt/remnabot1/.env` is the RC public-URL source (`CABINET_URL=https://panel.rookari.com`, `WEBHOOK_URL=panel.rookari.com`, polling). The running remnabot1 container is the working RC.

DNS A records named `staging-host-*` currently resolve to RC (`91.107.144.95`) but have no RC Caddy site. Do **not** put those names in RC env. Do **not** HTTP-01 them. Do **not** duplicate Bot’s staging blocks. Do not delete those Cloudflare records in M1 (P2 UNKNOWN).

M1-T4 as originally written (**author `staging-host-*` on RC**) is **cancelled**. Leave live RC Caddy unchanged in M1. Public RC name remains `panel.rookari.com`. Production application names stay off RC Caddy until M8.

### E6. Governance artifacts (Checkpoint M0 complete)

Governance started on `prod-cutover` @ `a168a817` (2026-08-29): rule `10-remnabot-migration.mdc`; evidence `2026-08-29-git-topology.md`, `2026-08-29-host-inventory-rc.md`, `2026-08-29-host-inventory-prod.md`; this plan. M0 evidence T2–T6 + checkpoint closeout through `2877a28f` (2026-08-31). Spec/errata files were committed then **deleted from the working tree** and must stay deleted. Rule filename is `10-remnabot-migration.mdc` (not gitignored `10-remnabot.mdc`). Rule alignment finished in `0c5fa2d1` / closeout `2877a28f`.

### E7. Alembic fallback trigger

If M4-T0 graft verification fails after good-faith archive+copy: `PLAN REVISION REQUIRED: Alembic graft failed M4-T0`. Fallback = re-ID from production `0103` only (additive `0111+`). Do not boot remnabot1 on restored data until a graph strategy passes M4-T0 gates.

### E8. Rehearsal must not control production nodes (2026-09-01)

**Incident:** Restoring the production Remnawave dump into `rehearsal_rw` copied live `nodes` rows. The 3.4.3 panel **actively** connects to `nodes.address` (node agent) and pushes config (`NodeHealthCheckTask` restarts nodes on boot; `StartAllNodesByProfile`; plugin sync). Two panels with the same node rows dual-control production agents and can take nodes down. M2-T2’s note that node errors mean “unreachable / not a G2 failure” was incomplete — the copy was reachable enough to interfere.

**Operator mitigation (accepted):** emptied `nodes`. VERIFIED 2026-09-01: `nodes=0`, `hosts_to_nodes=0`, `config_profile_inbounds_to_nodes=0`; `users=3181`; `hosts=50` (subscription YAML public hostnames — not the control plane); panel still healthy. Evidence: `docs/superpowers/evidence/2026-09-01-e8-nodes-isolation.md`.

**Binding:**
- After any RW dump restore, `nodes` must be empty (or contain only an isolated dummy created in this panel) **before** the rehearsal backend is left running.
- Never copy production node addresses, ports, or keys into a second live panel.
- `hosts` may keep restored public hostnames; emptying `hosts` is **not** required for dual-control stop.
- A live Xray node is **not** required for M4 (Alembic/client/`0111`/backfill) or for panel HTTP API purchase/renew/identity. G3 already proved `/api/sub/{shortUuid}` YAML without node connectivity.
- Optional isolated dummy node is deferred. Do not create DNS or attach a node unless a later named batch asks. If asked: new record **`rw-rehearsal.rookari.com`** A → `91.107.144.95`, Caddy → `127.0.0.1:3100`, new node + key from **this** panel only. Rehearsal panel is **not** published on `rw.rookari.com` (`PANEL_DOMAIN` is the SPA Host header only; bind is `127.0.0.1:3100` / `:3101`).

---

## Cutover safety (inlined; was Architecture A §§2.3, 8–14)

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
| `C2C_ENABLED` | `true` (live `.env`). `C2C_ADMIN_CHAT_ID` empty. Do not copy a production admin chat id |
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

**Two stacks (do not conflate):** live remnabot1 sandbox uses `/opt/remnabot1/.env` and `REMNAWAVE_API_URL=http://remnawave:3000` on `panel.rookari.com` (already running — do not rewrite that `.env` for cutover work; sandbox DB is still **`0110`**). Isolated rehearsal compose uses gitignored `.env.rehearsal` with the **same public URLs** and `REMNAWAVE_API_URL=http://rehearsal_rw:3000` (do not start polling `rehearsal_bot` until a later named batch).

### Cutover Caddy (five production blocks)

| Name | Route |
|---|---|
| `cabinet.rookari.com` | `/api/*` → bot; else cabinet |
| `hooks.rookari.com` | → bot (include `/webhook` and existing payment path handles) |
| `master.rookari.com` | → remnawave `:3000` |
| `sub.rookari.com` | subscription page; preserve production root redirect if still required |
| `miniapp.rookari.com` | miniapp static + bot `/miniapp` |

Do not add `pgadmin`/`admin`/`rw`/`config`/`panel` as app routes. HTTP-01 issues after the A record points here unless M7-T6 pre-issues via DNS-01. Staging Caddy lacks the Cloudflare plugin (VERIFIED historically). SNI: new host must serve the exact production names.

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

**Operator binding 2026-08-31:** live `/opt/remnabot1/.env` has `C2C_ENABLED=true` and empty `C2C_ADMIN_CHAT_ID`. Match that in RC env. Empty admin chat is **not** G8 PASS.

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
2. Bot restore rehearsal + remnabot `0104` + planned `0111+` on copy.
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
| G1 Restore bot | After rehearsal restore | `0103`, user count, `c2c_receipts`, C2C enabled, not `0106` |
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

**UPSTREAM TRACKING** (may move daily):

```
fetch official remotes
→ record new HEAD SHA / tag
→ diff against last recorded tracking SHA
→ classify: ignore / integrate-now / defer
```

**PRODUCTION PROMOTION** (immutable only):

```
choose a commit SHA (bot, cabinet) and/or image digest (Remnawave)
→ integrate on a branch
→ test (unit + RC rehearsal gates)
→ record: Git SHA, tag if any, image digest, Alembic head, verification evidence
→ only then deploy that revision
```

Never deploy implicit `latest`, `backend:3`, or an unreviewed moving branch. The 4.2.0 / cabinet 1.67.0 / panel **3.4.3** (M3-T0) observed are **candidate snapshots**.

**Remnawave specifically:**

1. Inspect `remnawave/panel` releases/tags (M0 seed 2026-08-29 **v3.3.2**; M3-T0 execution **v3.4.3**).
2. Identify the currently relevant stable/recommended 3.x **candidate** (**`CANDIDATE_TAG=3.4.3`** — tracking, not pin).
3. Inspect official migration/API notes 2.8.1 → candidate (not only 4.2 bot comments).
4. Rehearse that **immutable** image digest against a copy of production RW data **on the rehearsal-restore track**.
5. Promote only the candidate that passes G3 + M3-ID.

Do **not** duplicate Prisma/panel migrations in the bot. Bot Alembic only owns the **bot** database.

---

## Alembic strategy (inverted — critical)

**VERIFIED collision 2026-08-31:** remnabot1 `0088` = `dedupe_tariff_subscriptions` (no-op); remnabot `0088` = `create_c2c_receipts`. Same IDs, different semantics from `0088` onward. Last shared identical revision remains **`0087`**. remnabot `0096` is a **merge** `down_revision = ('0094','0095')`.

**Production bot DB** is remnabot-lineage **`0103`** (custom; live + dump). remnabot1 HEAD files are upstream **`0110`**. No `0111*` files exist on either tree.

**Therefore:** never `alembic upgrade` remnabot1's current `0088–0110` onto a restored production DB. Never `stamp` to hide the mismatch.

**Required graph for remnabot1 (the maintained code tree):**

1. **Graft** remnabot custom files `0088–0104` into remnabot1 `migrations/alembic/versions/` (those IDs already exist as different files — **replace** the upstream files in `versions/`).
2. Archive **all** remnabot1 `0088–0110` as **reference only** under `docs/superpowers/reference/upstream-alembic-0088-0110/` in the **same commit** as the graft. Leaving `0105–0110` in `versions/` is fatal: remnabot1 `0105.down_revision = '0104'`, so after replacing `0104` with remnabot traffic-clamp, leftover `0105–0110` would still run and `alembic heads` would be `0110`.
3. New additive revisions **`0111+`** chain from remnabot **`0104`**, inspector-guarded, for 4.2 schema the **running 4.2 code** actually needs after unused features stay disabled. `0111` is a **new file / new ID**. Never reuse remnabot1’s `0104` or `0105–0110` IDs on the live graph.
4. `remnawave_id` is already in remnabot1 **models** and in the **to-be-archived** upstream `0104_remnawave_numeric_id.py`. It is **absent** from remnabot models/production schema (dump has no `remnawave_id`). **M3-ID filled the live `0111` semantics:** store panel `users.id` (bigint, former 2.8.1 `t_id`; **not** a hash of dropped `uuid`). Users: nullable BIGINT + **full** unique `ix_users_remnawave_id`. Subscriptions: nullable BIGINT + **partial** unique `WHERE remnawave_id IS NOT NULL`. Non-unique index on existing `remnawave_short_uuid` (exact match key). Inspector-guard `grace_access_sessions`. **uuid lookup is gone** (official + rehearsal 404 on `by-uuid` / `by-subscription-uuid`). Models must match (no inline `unique=True` on Subscription).

**Graft is lineage-correct and not a drop-in.** File-swap alone is unsafe until these hazards are gated:

| Hazard | Evidence | Gate |
|---|---|---|
| Startup auto-upgrade | remnabot1 `main.py` calls `run_alembic_upgrade()` before `setup_bot()`. On existing DBs: `command.upgrade(..., 'head')`. On “fresh”: `create_all` + **`stamp head`**. `SKIP_MIGRATION` exists (`os.getenv('SKIP_MIGRATION','false')`) but is not a rehearsal default. | **M4-T0 PASS / M4-T1 recorded.** Do not poll `rehearsal_bot` until `0111` (and extras) exist. Set `SKIP_MIGRATION=true` if sandbox `remnawave_bot` must restart (DB still `0110`). |
| Leftover `0105–0110` | `0105.down_revision = '0104'` (VERIFIED 2026-08-31) | Archive **0088–0110** in the same commit as the remnabot copy. M4-T0 fails if `0104_remnawave_numeric_id.py` or `0110_*.py` remain in `versions/`. |
| `0001` = `Base.metadata.create_all` | `0001_initial_schema.py` creates **current** 4.2 models (remnawave_id, grace, coupons, legal consents, **no C2C**) then later revisions apply. Production restore skips `0001`; empty/CI volumes do not. | M4-T1 records this. Tests/CI against empty DBs are expected inconsistent until M4-T4/T7. Do not use empty-volume `create_all` as a production path. |
| 4.2 tests/models vs grafted graph | Models already declare `users.remnawave_id` unique; tests import grace/legal/coupons; `tests/database/test_migration_chain.py` assumes the 4.2 chain. | Graft commit will desync models vs live graph until M4-T1/T3/T4/T7. Do not claim green 4.2 tests at M4-T0. List known breakages in M4-T0 evidence. |

**Code vs schema:** remnabot1 already contains the 4.2 Remnawave client (`get_user_by_id`, `get_all_users_stream`, `resolve_user`, no `get_user_by_uuid`) and `scripts/backfill_remnawave_ids.py` / `app/services/remnawave_identity_backfill.py`. Treat these as **reference implementations**. Verify against official panel + rehearsal (M3-ID) before trusting them.

**Custom remnabot revisions that must remain on the live graph after graft:** C2C (`0088`, `0094`), wholesale (`0093`), partner (`0095`), merge (`0096`), serial (`0101`), entities_json (`0102`), user_disabled (`0103`), traffic clamp (`0104`). Plus remnabot files `0089–0092`, `0097–0100` that sit on that lineage.

---

## Technical-debt / refactoring policy

Target: **clean production-compatible MVP** + **minimal risk-reducing refactoring** + **clean upstream boundaries** + **future mergeability**.

Refactor **now** only if it directly reduces: migration risk, duplicated compatibility logic, custom/upstream coupling, configuration fragmentation, testability, or future merge conflicts.

| Area | Decision | Why |
|---|---|---|
| remnabot1 4.2 Remnawave client | **KEEP + verify** (do not rewrite) | Already 3.x-shaped; verify on rehearsal; adapt only where official API differs |
| remnabot1 Alembic `0088–0110` as live graph | **REFACTOR NOW** (graft remnabot lineage) | Applying them to production data is unsafe |
| C2C / FA / Toman / wholesale from remnabot | **PORT NOW** (MVP) | Protected production behavior; remnabot1 has no C2C plugin and no `PaymentMethod.C2C` |
| Russian payment business logic | **DEFER** | Not an MVP product requirement |
| Unused 4.2 schema (coupons, grace **table**, cispay, …) | **DEFER** (M4-T1 proved) | Do not invent those **tables**. Mapped **columns** on existing User/Subscription/Tariff/promocodes/payment_method_configs **are** MVP schema-only. |
| FA/Toman extraction into `app.custom.*` | **DEFER** unless it unblocks mergeability | Prefer tests + keep working remnabot code paths |
| T2.1 wholesale seam (old uncommitted WIP) | **LOST with remnabot1 tree replace** | Recover from remnabot inline `price_display` / remnabot git; do not invent a housekeeping commit |

---

## Payment scope (MVP)

- **C2C: mandatory.** Port from `/opt/remnabot/app/plugins/c2c` + `PaymentMethod.C2C` + `c2c_receipts`. Isolated test admin chat (P1) required. G8 INCOMPLETE ⇒ **MVP-VERIFIED = NO-GO**.
- **Telegram Stars / CryptoBot:** already in remnabot1 `PaymentMethod`. May stay as **disabled-but-importable** paths if they start cleanly. Do not implement new business logic unless explicitly promoted.
- **Russian-specific providers** (YooKassa, Platega, Lava, CisPay, and the rest of the remnabot1 enum): **compatibility-only**. Imports must not break startup; paths stay disabled; production credentials never enter RC; no full integration “because upstream has them.”

---

## Forbidden actions (DAG edges)

1. **M4-T6 PASS (G6).** G1 restore is **`0111`**. `subscriptions.remnawave_id` **3170/3173** via `short_uuid`; 0 join mismatches. `users.remnawave_id` stays 0 (multi-tariff). `grace_access_sessions` still absent. Full `alembic revision --autogenerate` still proposes deferred 4.2 tables and would drop C2C/wholesale/`user_disabled` — **do not commit that**. Do **not** start polling `rehearsal_bot` until a later named batch. Never `alembic upgrade` / `stamp` the sandbox volume `remnabot1_postgres_data` (still upstream **`0110`**) with the grafted graph; restart that bot only with `SKIP_MIGRATION=true`.
2. **Never** `docker compose up` / restore against production or legacy volumes (`remnawave-db-data`, `remnabot1_postgres_data`, `bot-remnawave_postgres_data`, `bot-remnawave_*`, admin/staging fossils). Rehearsal uses only `rehearsal_*` / `cutover_*`.
3. **Never** start the production-token bot until the old production bot is stopped (M8).
4. **Never** apply remnabot1 live-graph `0088–0110` to a remnabot-lineage `0103` database.
5. **Never** leave production Remnawave `nodes` rows in a second live panel (E8). Rehearsal `nodes` stays empty unless an isolated dummy is explicitly added.

The existing RC `remnabot1` compose project (running `remnabot1-bot` against `remnabot1_postgres_data`) is the **dev sandbox**. Do not restore dumps onto it. Do not treat it as rehearsal.

---

## File map (create vs modify)

| Path | Responsibility | When |
|---|---|---|
| `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md` | This plan — single authority | this update |
| `.cursor/rules/10-remnabot-migration.mdc` | Machine-readable topology/Alembic/forbidden DAG | M0-T0 DONE; keep aligned with this plan |
| `docs/superpowers/evidence/2026-08-29-*.md` | Snapshots; append re-verify dates | M0-T1 DONE; T3/T5/T6 DONE (`2026-08-31-cabinet-git.md`, `2026-08-31-upstream-tracking.md`, `2026-08-31-alembic-graph.md`; T2 `2026-08-31-wip-inventory.md`) |
| `docs/superpowers/evidence/smoke-YYYY-MM-DD-<batch>.md` | Closed-batch smoke archive (not this plan) | each batch closeout |
| `docker-compose.rehearsal.yml` | Isolated rehearsal stack | M1-T1 |
| `deploy/remnawave/docker-compose.rehearsal.yml` | Rehearsal RW 2.8.1 then candidate | M1-T1 / M2 / M3 |
| `deploy/caddy/Caddyfile` | Canonical Caddy if/when repo single-source is used. **M1-T4 staging-host authoring cancelled.** Live RC Caddy stays `/opt/caddy/Caddyfile` (`panel.rookari.com`) | M1-T4 CANCELLED; M7-T1 still owns cutover blocks |
| `deploy/caddy/Caddyfile.cutover` | Staged production blocks | M7-T1 |
| `app/custom/safety/token_guard.py` | Fail-closed production-token guard | M1-T2 |
| `tests/custom/test_token_guard.py` | Guard unit tests | M1-T2 |
| `main.py` | Call guard **before** `run_alembic_upgrade()` / `setup_bot()` | M1-T2 |
| `.env.rehearsal` | RC env (gitignored; class D/E absent) | M1-T3 |
| `docs/superpowers/reference/upstream-alembic-0088-0110/` | Archived remnabot1 `0088–0110` | M4-T0 |
| `migrations/alembic/versions/0088–0104` | Grafted remnabot lineage | M4-T0 |
| `migrations/alembic/versions/0111_*.py` | New remnawave_id (after M3-ID) | M4-T3 |
| `/opt/cabinet` compose | RC cabinet on `remnawave-network` | M5 |
| `docs/superpowers/runbooks/{rollback,writer-freeze,dns-cutover,tls-cutover}.md` | Cutover runbooks | M7 |

---

## Pre-execution prerequisites

| # | Prerequisite | Blocks | Status 2026-08-31 |
|---|---|---|---|
| P1 | Isolated C2C test admin chat (≠ production) | M6-T4, MVP-VERIFIED | **UNKNOWN** — ask the user; do not guess |
| P2 | Cloudflare DNS write access | M7-T5, M8 | **UNKNOWN** — ask the user |
| P3 | Cloudflare token for DNS-01 (optional) | M7-T6 preferred path | **UNKNOWN** — HTTP-01 window documented if missing |
| P4 | `remnawave/backend:2.8.1` pullable | M2-T0 | **SATISFIED 2026-09-01.** Digest `sha256:361f9bb0b183d4fcefea2f1f7163db490e2aa1ec3b4bdde016a9ab9229ce956b` (matches live Bot). Evidence `docs/superpowers/evidence/2026-09-01-m2-t0-rw-281-pin.md`. |
| P5 | Read-only production RW env/compose on `Bot` | M2-T0 | **SATISFIED 2026-09-01.** Compose `/opt/remnawave/docker-compose.yml` (`backend:2.8.1` tag-only). Key names recorded. Secrets not copied. |
| **P6** | **Production bot dump** | M2-T1 | **SATISFIED 2026-08-31.** SHA-256 `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85`. `alembic_version=0103`. Not a cutover artifact. Not inside remnabot1 git. RW dump SHA `11935de69fc6dc318419753916ff840f950f5b4be7a27be46e2ccf2142347377`. |

---

## Parallel DAG

```
M0 complete (T0–T6 evidence + tag on prod-cutover)
  M1 complete (T4 cancelled)
  USER GATE: «شروع M2» → M2-T0 only (session contract)
  ├─ M2-T0 pin RW 2.8.1 runtime
  ├─ M2-T1 bot restore postgres-only (needs P6, M1.1)     ──┐
  ├─ M2-T2 RW restore                                         │
  │      └─ M3-T1 3.x candidate rehearsal GO/NO-GO            │
  │            └─ M3-ID official+runtime identity/API proof     │
  └─ M4-T0 graft Alembic (needs M0-T6; independent of M3) ──┘
        HARD JOIN: M4-T0 verified BEFORE any remnabot1 app mounts rehearsal_bot_pg15
        └─ M4-T1 … T7
M5 cabinet (/opt/cabinet, API only)
M6 gates (C2C hard) → MVP-VERIFIED
M7 prep → M8 cutover (21) → M9
```

**Hard rule:** identity proof (M3-ID) before trusting backfill/client. Graft verified before remnabot1 app starts on restored data. Writer freeze before final dumps. Official panel + rehearsal override 4.2 comments. G3 evidence from rehearsal-restore track only.

Weights: 1,2,3,5,8,13,21. Batches: NORMAL 8–13, HIGH-RISK 3–8, 21 standalone.

---

# M0 — Governance, topology, upstream baseline

**Status 2026-09-01:** **M0–M3 complete.** **M4-T0 PASS.** **M4-T1 DONE.** **M4-T2 DONE.** **M4-T3 DONE** (G1 `0111`). **M4-T4 DONE**. **M4-T5 DONE**. **M4-T6 DONE** (G6). **M4-T7 DONE** (C2C/FA/Toman/wholesale). **M5-T1 DONE** (user smoke **تایید**). **M5-T2 DONE**. **M5-T3 DONE**. **M6-T1 DONE** (FA fallback gate). **M6-T2 DONE** (Toman dual-scale gate). M1-T4 cancelled. Do not execute M6-T3 until the user confirms. Session contract applies.

### Task M0-T0: Codify workspace governance — DONE

- **ID:** M0-T0 · **WEIGHT:** 2 · **RISK:** Low · **STATUS:** **DONE** 2026-08-29 (commit `a168a817`); re-verified 2026-08-31
- **FILES:** `.cursor/rules/10-remnabot-migration.mdc` (exists; names `/opt/cabinet`, remnabot1 origin, four forbidden actions, Alembic graft)
- **Do not recreate** the rule. **Do not** use filename `10-remnabot.mdc`.

- [x] Rule exists and names `/opt/cabinet` (not cabinet1)
- [x] Align rule “Read first” with this plan as single authority (no deleted-spec paths) — done 2026-08-31 in this plan-update

### Task M0-T1: Record Git topology — DONE (append re-verify)

- **ID:** M0-T1 · **WEIGHT:** 2 · **RISK:** Low · **STATUS:** **DONE** 2026-08-29; re-verify appended 2026-08-31
- **FILES:** `docs/superpowers/evidence/2026-08-29-git-topology.md`
- **Do not recreate.** Append dated re-verify (this update). Future executors re-check remotes/HEADs before M4/M8.

- [x] Evidence file committed with six-identity table
- [x] Append 2026-08-31 re-verify SHAs (this plan-update)

**Branch strategy (bot):** `prod-cutover` already exists from `89fa7dc5`. Leave `main` free to track upstream. Never force-push. Never overwrite `origin/main`. M0 commits are done. Branch is **not** on `origin` yet — first push is `git push -u origin prod-cutover` when the user/plan permits.

### Task M0-T2: WIP inventory after tree replace — DONE

- **ID:** M0-T2 · **WEIGHT:** 2 · **RISK:** Low · **DEPENDENCIES:** M0-T1 · **STATUS:** **DONE** 2026-08-31 (commit `f10ebd75`)
- **GOAL:** State what WIP survived. **Do not** commit `.cursor` churn or invent T2.1. **Do not** commit `locales/` unless an explicit product decision says so.
- **FILES:** Create `docs/superpowers/evidence/2026-08-31-wip-inventory.md`

- [x] **Step 1: Write evidence** — `docs/superpowers/evidence/2026-08-31-wip-inventory.md` (commit `f10ebd75`)
- [x] **Step 2: Verify** no `app/` files staged for M0
- [x] **Step 3: Commit** `docs(M0-T2): WIP inventory after remnabot1 re-fork`

### Task M0-T3: Cabinet Git reconciliation (non-destructive — no `git init`) — DONE

- **ID:** M0-T3 · **WEIGHT:** 3 · **RISK:** Medium · **DEPENDENCIES:** M0-T1 · **STATUS:** **DONE** 2026-08-31 (commit `8b70bd75`)
- **GOAL:** Confirm `/opt/cabinet` already is the maintained fork.
- **FILES:** `docs/superpowers/evidence/2026-08-31-cabinet-git.md`

- [x] **Step 1: Re-inspect** (read-only) — remotes `k4lantar4/cabinet` + `bedolaga-cabinet`; HEAD `35e5aa9e`; 0/0 both; `/opt/cabinet1` ABSENT
- [x] **Step 2: Write evidence** — `docs/superpowers/evidence/2026-08-31-cabinet-git.md`
- [x] **Step 3:** No `git init`; no `cabinet1`; no force-push
- [x] **Step 4:** Remotes match six-identity table
- [x] **Step 5: Commit** `docs(M0-T3): cabinet git reconciliation` (`8b70bd75`). Cabinet repo unchanged.

### Task M0-T4: Baseline tags + dump inventory — DONE

- **ID:** M0-T4 · **WEIGHT:** 3 · **RISK:** Medium · **STATUS:** **DONE** 2026-08-31 (commit `3f798500` + tag `baseline/prefork-4.2.0-89fa7dc5`)
- **FILES:** append to `docs/superpowers/evidence/2026-08-29-host-inventory-rc.md`; create tag.

- [x] SHA-256 bot dump `b5fc023a…c093cb85` (re-verified 2026-08-31)
- [x] SHA-256 RW dump `11935de6…42347377` (re-verified 2026-08-31)
- [x] Dump `alembic_version=0103`
- [x] **Step: Tag** `baseline/prefork-4.2.0-89fa7dc5` → `89fa7dc584b9fb7f017c385d604614fb29692d66` (verified)
- [x] **Commit** `docs(M0-T4): record baseline tag 89fa7dc5` (`3f798500`). Dumps remain **REHEARSAL INPUT — NOT cutover artifacts** (not in git).

### Task M0-T5: Establish upstream tracking baseline — DONE

- **ID:** M0-T5 · **WEIGHT:** 3 · **RISK:** Low · **STATUS:** **DONE** 2026-08-31 (commit `3926dd03`)
- **FILES:** `docs/superpowers/evidence/2026-08-31-upstream-tracking.md`

- [x] **Step 1: Record** — `docs/superpowers/evidence/2026-08-31-upstream-tracking.md`. Seed values VERIFIED 2026-08-31:

| Ref | SHA |
|---|---|
| remnabot1 `main` | `89fa7dc584b9fb7f017c385d604614fb29692d66` |
| remnabot1 `origin/main` | `31a3e93042e528ac13f1b8aa9f4acb02001bac99` (1 ahead: `python-app.yml`) |
| remnabot1 `prod-cutover` (2026-08-31 seed) | `a168a817cbfdbab020ed3b328c596d866dfbc2a6` |
| remnabot1 `prod-cutover` (current, post T2–T6 closeout) | `2877a28fad3d47d8a3dcb34659983aaef7952388` |
| `/opt/bot` HEAD | `89fa7dc584b9fb7f017c385d604614fb29692d66` |
| cabinet `main`/`origin`/`upstream` | `35e5aa9e78123fdf18506a7a8a46875d268689ed` |
| remnabot reference | `f36ec4ca078eea3f2647f01887ccf987823fbfd0` |
| remnawave/panel latest (2026-08-29) | **v3.3.2** — re-check at execution |
| RC compose promotion policy | `:3` / `:latest` = **violation** for promotion |

- [x] **Step 2:** `origin/main` +1 (`python-app.yml`) classified **defer** (CI file, not a bot release)
- [x] **Step 3:** Remotes match six-identity table
- [x] **Step 4: Commit** `docs(M0-T5): upstream tracking baseline` (`3926dd03`)

### Task M0-T6: Alembic graph decision evidence (before any migration file edit) — DONE

- **ID:** M0-T6 · **WEIGHT:** 5 · **RISK:** High · **STATUS:** **DONE** 2026-08-31 (commit `9aa0d69a`)
- **FILES:** `docs/superpowers/evidence/2026-08-31-alembic-graph.md`

- [x] **Step 1: Write the table** — `docs/superpowers/evidence/2026-08-31-alembic-graph.md`. Includes:

```
Last shared: 0087
remnabot1 0088 = 0088_dedupe_tariff_subscriptions.py (no-op)
remnabot  0088 = 0088_create_c2c_receipts.py
remnabot1 0103 = 0103_add_legal_consents.py
remnabot  0103 = 0103_subscription_user_disabled.py
remnabot1 0104 = 0104_remnawave_numeric_id.py
remnabot  0104 = 0104_traffic_purchase_expiry_clamp.py
remnabot1 0105.down_revision = '0104'
remnabot1 head file = 0110_referral_user_reward_choice.py
Graft = archive remnabot1 0088–0110 + copy remnabot 0088–0104 same commit
0111+ from remnabot 0104
Hazards = run_alembic_upgrade / leftover 0105–0110 / 0001 create_all / 4.2 tests
Forbidden = no remnabot1 process / no alembic upgrade / no stamp on restored volumes until M4-T0
Fallback = PLAN REVISION REQUIRED: Alembic graft failed M4-T0
```

- [x] **Step 2: Verify** document forbids wrong `0104`, leftover `0105–0110`, and remnabot1 against `rehearsal_bot_pg15` before M4-T0
- [x] **Step 3: Commit** `docs(M0-T6): alembic graft strategy` (`9aa0d69a`)

### Task M0-T7: Recover Architecture A spec — CANCELLED

- **ID:** M0-T7 · **STATUS:** **CANCELLED** 2026-08-31
- **Replacement:** Cutover-safety / DNS / Telegram / C2C / rollback / gates / env classes are inlined in this plan (§Cutover safety). Do **not** copy `docs/superpowers/specs/2026-08-28-production-cutover-architecture-design.md` (or any `*-errata.md`) back into remnabot1.
- Optional historical blob remains on `k4lantar4/remnabot` `origin/chore/mcp-dev-tools` @ `70476c0e`. Executors do not need it.

**Checkpoint M0 complete** (2026-08-31): T2–T6 evidence files committed; tag `baseline/prefork-4.2.0-89fa7dc5` present; this plan is the only authority document. **M1 since completed.** Do not re-run T2–T6.

---

# M1 — RC isolation + infrastructure foundation

**Blocked** until the user explicitly starts M1. Cabinet source is `/opt/cabinet`. Caddy is repo single-source. Remnawave image in this milestone is **not** pinned to 3.3.2 — M2-T0 pins 2.8.1 for restore; M3-T1 pulls the candidate digest.

The running `remnabot1` compose stack is **not** this rehearsal stack. M1 creates a **new** compose project `rehearsal`.

### Task M1-T1: Dedicated `rehearsal` compose with NEW isolated volumes

- **ID:** M1-T1 · **WEIGHT:** 5 · **RISK:** Medium · **DEPENDENCIES:** Checkpoint M0
- **GOAL:** RC rehearsal stack that cannot touch existing volumes/containers. Definable without starting the remnabot1 **app** against a restored DB.
- **FILES:** Create `docker-compose.rehearsal.yml` (repo) + `deploy/remnawave/docker-compose.rehearsal.yml`. remnabot1 has **no** `deploy/` yet.

- [ ] **Step 1: Author compose** project `rehearsal`:
  - `rehearsal_bot_db`: image **`postgres:15-alpine@sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f`** (E3; re-check digest at execution with `ssh bot docker image inspect`). Volume **`rehearsal_bot_pg15`**, bind `127.0.0.1:6061:5432`. Do **not** default to `15.18` unless a written compatibility proof exists.
  - `rehearsal_bot_redis`; `rehearsal_bot` (build `/opt/remnabot1`, `env_file: .env.rehearsal`, `127.0.0.1:8081:8080`) — **defined but not started** (M4-T1 probe only). If the service is ever created: `SKIP_MIGRATION=true` until `0111` lands.
  - `rehearsal_rw`: image from M2-T0 (`remnawave/backend:2.8.1` digest) until M3-T1 replaces it with the candidate digest. Do not use `:3` or `:latest`.
  - `rehearsal_rw_db` (`postgres:17.6`, volume **`rehearsal_rw_pg17`**, `127.0.0.1`); `rehearsal_rw_redis`; `rehearsal_sub` image `remnawave/subscription-page:7.2.6` until M3.
  - `cabinet_frontend` built from **`/opt/cabinet`** (not cabinet1, not `/opt/remnabot/cabinet`).
  - Explicit `name:` on every volume so Docker does not prefix-collide with `remnabot1_*` / `remnawave-db-data`.

- [ ] **Step 2: Verify**

```bash
docker compose -p rehearsal -f docker-compose.rehearsal.yml config
docker compose -p rehearsal -f docker-compose.rehearsal.yml config | grep -E 'remnawave-db-data|remnabot1_postgres|bot-remnawave'
```

Expected: config renders; grep empty. After a volume create, `docker volume ls` shows only new `rehearsal_*` names. **Do not** `compose up` `rehearsal_bot` as the M1.1 pass condition.

- **FAILURE CONDITION:** any volume resolves to an existing non-rehearsal volume.
- **RECOVERY:** `docker compose -p rehearsal down` (never `-v` on a wrong volume); delete only `rehearsal_*` volumes.
- [ ] **Step 3: Commit** `feat(M1-T1): isolated rehearsal compose` · **CHECKPOINT:** Checkpoint M1.1.

### Task M1-T2: BOT_TOKEN production-fingerprint fail-closed guard (TDD)

- **ID:** M1-T2 · **WEIGHT:** 3 · **RISK:** Medium · **DEPENDENCIES:** Checkpoint M0
- **GOAL:** RC refuses to start if `BOT_TOKEN` matches the production fingerprint, unless an explicit cutover override is set.
- **FILES:** Create `app/custom/__init__.py`, `app/custom/safety/__init__.py`, `app/custom/safety/token_guard.py`; Test `tests/custom/test_token_guard.py`; call in `main.py` **before** `run_alembic_upgrade()` / `setup_bot()`. remnabot1 has **no** `app/custom` today.
- **Interfaces — Produces:** `token_fingerprint(token: str) -> str` (first 16 hex of sha256); `assert_not_production_token(bot_token: str, prod_fingerprint: str | None, allow_override: bool) -> None` (raises `RuntimeError` on match unless override).

- [ ] **Step 1: Write the failing tests** `tests/custom/test_token_guard.py`

```python
import hashlib

import pytest

from app.custom.safety.token_guard import (
    assert_not_production_token,
    token_fingerprint,
)


def test_token_fingerprint_is_first_16_hex_of_sha256() -> None:
    token = 'test-token'
    expected = hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]
    assert token_fingerprint(token) == expected


def test_assert_refuses_matching_fingerprint() -> None:
    token = 'prod-like'
    fp = token_fingerprint(token)
    with pytest.raises(RuntimeError, match='production BOT_TOKEN'):
        assert_not_production_token(token, fp, allow_override=False)


def test_assert_allows_override() -> None:
    token = 'prod-like'
    fp = token_fingerprint(token)
    assert_not_production_token(token, fp, allow_override=True)


def test_assert_passes_distinct_token() -> None:
    fp = token_fingerprint('production')
    assert_not_production_token('rehearsal', fp, allow_override=False)


def test_assert_passes_when_fingerprint_unset() -> None:
    assert_not_production_token('anything', None, allow_override=False)
    assert_not_production_token('anything', '', allow_override=False)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/custom/test_token_guard.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.custom'` (or import error for `token_guard`).

- [ ] **Step 3: Minimal implementation** `app/custom/safety/token_guard.py`

```python
from __future__ import annotations

import hashlib


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]


def assert_not_production_token(
    bot_token: str,
    prod_fingerprint: str | None,
    allow_override: bool,
) -> None:
    if not prod_fingerprint:
        return
    if allow_override:
        return
    if token_fingerprint(bot_token) == prod_fingerprint:
        raise RuntimeError(
            'Refusing to start: BOT_TOKEN matches PRODUCTION_BOT_TOKEN_FINGERPRINT'
        )
```

Empty `app/custom/__init__.py` and `app/custom/safety/__init__.py`. In `main.py`, immediately after imports / before `run_alembic_upgrade()`:

```python
from app.custom.safety.token_guard import assert_not_production_token

assert_not_production_token(
    os.getenv('BOT_TOKEN', ''),
    os.getenv('PRODUCTION_BOT_TOKEN_FINGERPRINT'),
    os.getenv('ALLOW_PRODUCTION_BOT_TOKEN', 'false').lower() in ('1', 'true', 'yes'),
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/custom/test_token_guard.py -v
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit** `feat(M1-T2): fail-closed production token guard` · **CHECKPOINT:** Checkpoint M1.2.

### Task M1-T3: RC environment reconciliation matrix + `.env.rehearsal`

- **ID:** M1-T3 · **WEIGHT:** 5 · **RISK:** Medium · **DEPENDENCIES:** M1-T1
- **GOAL:** A/B/C/D/E classification; RC env with no class D/E secrets.
- **FILES:** `docs/superpowers/evidence/2026-08-31-env-matrix.md`; `.env.rehearsal` (gitignored).

- [ ] Classify important keys using **this plan’s Environment classes (A–E)**. RC public URLs from live `/opt/remnabot1/.env`: test token, `WEBHOOK_URL=panel.rookari.com`, `BOT_RUN_MODE=polling`, `CABINET_URL=https://panel.rookari.com`, `WEB_API_ALLOWED_ORIGINS=*`, `C2C_ENABLED=true` with empty `C2C_ADMIN_CHAT_ID`. Isolated rehearsal compose: `REMNAWAVE_API_URL=http://rehearsal_rw:3000`. Live sandbox keeps `http://remnawave:3000`. Generated RC secrets. Class D absent. Report key names + fingerprints only. **Do not use `staging-host-*` in env.**
- [ ] **Verify:** no class D/E key present; matrix classifies each important key.
- [ ] **Commit** matrix doc only (never the env file) · **CHECKPOINT:** Checkpoint M1.2.

### Task M1-T4: RC Caddy — **CANCELLED** (do not author `staging-host-*`)

- **ID:** M1-T4 · **WEIGHT:** 5 · **RISK:** Medium · **DEPENDENCIES:** M1-T1, M0-T0
- **STATUS:** **CANCELLED as written (2026-08-31 operator binding).** Staging is not the operational RC. Live Caddy already serves `https://panel.rookari.com`. Do **not** add `staging-host-*` server blocks. Do **not** HTTP-01 those names. Do **not** copy live `/opt/caddy/Caddyfile` into `deploy/caddy/` in M1. Do **not** add production names (`cabinet.rookari.com`, `hooks.rookari.com`, …) to RC Caddy until M8.
- **GOAL (revised):** Leave live RC Caddy unchanged. Public RC hostname remains `panel.rookari.com`.
- **FILES:** none for M1. Cutover production blocks remain M7-T1 (`deploy/caddy/Caddyfile.cutover`).
- **CHECKPOINT:** Checkpoint M1.3 is **not** opened by this task. Next Caddy work waits for explicit user start (M7 or a later named task).

### Task M1-T5: RC network/port hardening

- **ID:** M1-T5 · **WEIGHT:** 3 · **RISK:** Low · **DEPENDENCIES:** M1-T1
- **FILES:** `docker-compose.rehearsal.yml`, `.env.rehearsal`.

- [ ] Bind rehearsal DBs to `127.0.0.1`; no `0.0.0.0:6060`; `WEB_API_ALLOWED_ORIGINS=*` matching live `/opt/remnabot1/.env` (not `staging-host-cabinet`).
- [ ] **Verify:** `ss -ltnp | grep -E ':6061|:8081'` shows `127.0.0.1` only (once those ports exist).
- [ ] **Commit** `chore(M1-T5): harden RC ports/CORS` · **CHECKPOINT:** Checkpoint M1.1.

**Batches:** M1.1={M1-T1,M1-T5}(8, NORMAL); M1.2={M1-T2,M1-T3}(8, NORMAL); M1.3={M1-T4} **cancelled** (do not author `staging-host-*` Caddy). Checkpoints leave RC isolation improved; production untouched (G7 holds). Public RC hostname = `panel.rookari.com`.

---

# M2 — DB restoration rehearsals

Infra-heavy. Default **User smoke: none**. Each task must list Agent smoke in Open smoke before running. Do not start `rehearsal_bot`. Session contract: one task/batch then briefing.

### M2-T0: Pin Remnawave **2.8.1** restore runtime (not a 3.x pin)

- **WEIGHT:** 5 · **DEPENDENCIES:** M1.1, P4, P5 · **STATUS:** **DONE** 2026-09-01
- Pull `remnawave/backend:2.8.1`; record **digest**. Derive compose/env from `/opt/bot-remnawave` / `/opt/remnawave` on Bot (read-only). Boot reports 2.8.1. This pins the **pre-upgrade verify** image only. Do not use the RC sandbox `backend:3` image for this track.
- **FILES:** `deploy/remnawave/docker-compose.rehearsal.yml`; evidence `docs/superpowers/evidence/2026-09-01-m2-t0-rw-281-pin.md`; gitignored `.env.rehearsal-rw` (`METRICS_*` class C).

- [x] Production RepoDigest recorded (`ssh bot`): `sha256:361f9bb0b183d4fcefea2f1f7163db490e2aa1ec3b4bdde016a9ab9229ce956b`
- [x] Pull by that digest on RC (P4 PASS); local Id matches; `__RW_METADATA_VERSION=2.8.1`
- [x] Pin `rehearsal_rw` (and companion PG 17.6 / sub 7.2.6) to production digests
- [x] `compose config` grep empty for live volume names
- [x] Boot `rehearsal_rw` reports `Remnawave Backend v2.8.1`; `/health` 200. Blocker: missing `METRICS_USER`/`METRICS_PASS` — generated class C (not production)
- [x] Sandbox `backend:3` + `remnawave-db-data` untouched; `rehearsal_bot` not started
- [x] Empty Prisma-seeded `rehearsal_rw_pg17` wiped after proof (M2-T2 restore target stays empty)
- [x] Evidence committed

### M2-T1: Restore bot dump (G1) — postgres only

- **WEIGHT:** 8 · **DEPENDENCIES:** M1.1, P6 (satisfied) · **STATUS:** **DONE** 2026-09-01 · **G1: PASS**
- Restore `/opt/remnabot/old_3.60_remnawave_bot.sql` into `rehearsal_bot_pg15` with **only** `rehearsal_bot_db` (and redis if needed) running. G1: `alembic_version=0103`, user count, `c2c_receipts`, `c2c` enabled, not `0106`.
- **FORBIDDEN:** poll `rehearsal_bot` / `alembic upgrade` / `stamp` against this volume until `0111` (+ M4-T1 extras) exists. **FORBIDDEN:** restore onto `remnabot1_postgres_data`.
- **FILES:** evidence `docs/superpowers/evidence/2026-09-01-m2-t1-bot-restore-g1.md`

- [x] Dump SHA-256 matches P6
- [x] `up -d rehearsal_bot_db` only; mount `rehearsal_bot_pg15`; bind `127.0.0.1:6061`
- [x] Restore with `psql -v ON_ERROR_STOP=1` (exit 0)
- [x] G1: `0103`; users 7828; `c2c_receipts` 1186; no `0106`; `C2C_ENABLED=true`
- [x] `rehearsal_bot` not started; sandbox `remnabot1_postgres_data` untouched
- [x] Evidence committed

### M2-T2: Restore RW 2.8.1 dump (G2)

- **WEIGHT:** 8 · **DEPENDENCIES:** M2-T0 · **STATUS:** **DONE** 2026-09-01 · **G2: PASS**
- Restore `/opt/remnawave/old(2.8.1)_remnawave.sql` into `rehearsal_rw_pg17`. G2: user count, `users.uuid`, Prisma tail `20260625200530_add_external_squad_index`, 2.8.1 login on RC hostname.
- **FORBIDDEN:** restore onto `remnawave-db-data`.
- **FILES:** evidence `docs/superpowers/evidence/2026-09-01-m2-t2-rw-restore-g2.md`

- [x] Dump SHA-256 matches P6
- [x] Restore into `rehearsal_rw_pg17` (created local `postgres` role for dump owners; no `--remove-orphans`)
- [x] G2 schema: users 3181 all `uuid`; Prisma tail `20260625200530_add_external_squad_index`
- [x] Boot pinned 2.8.1; `/health` 200; login SPA 200 via `X-Forwarded-Proto: https` on `127.0.0.1:3100` (live Caddy unchanged; no class-D login)
- [x] Sandbox `remnawave-db-data` / `backend:3` untouched; `rehearsal_bot` absent
- [x] Evidence committed
- **Correction 2026-09-01 (E8):** restored `nodes` were **not** safely unreachable; they dual-controlled production. Operator emptied `nodes`. Do not restore that table into a live second panel again.

---

# M3 — Remnawave candidate rehearsal + identity proof

### M3-T0: Choose the 3.x **candidate** from official panel (tracking, not pin)

- **WEIGHT:** 3 · **DEPENDENCIES:** M0-T5 · **STATUS:** **DONE** 2026-09-01
- Inspect `https://github.com/remnawave/panel/releases` (2026-08-29 seed **v3.3.2**). Record tag + recommended docker tag. If a newer 3.x exists at execution time, **that** is the candidate unless notes say otherwise. Output: `CANDIDATE_TAG`, to be pulled as digest in M3-T1.
- **FILES:** evidence `docs/superpowers/evidence/2026-09-01-m3-t0-rw-candidate.md`

- [x] Latest stable panel release = **v3.4.3** (not draft/prerelease; published 2026-08-31T20:14:25Z)
- [x] Recommended docker tag = `remnawave/backend:3.4.3` (not `:latest`, not `:3`)
- [x] Notes do not reject 3.4.3 (auth-bypass fix over 3.4.2)
- [x] `CANDIDATE_TAG=3.4.3` recorded; Hub index digest observed; **image not pulled**
- [x] Isolation: `rehearsal_rw` still 2.8.1 digest; sandbox `backend:3` untouched; `rehearsal_bot` absent
- [x] Evidence committed

### M3-T1: Upgrade copy 2.8.1 → **candidate** (G3) GO/NO-GO

- **WEIGHT:** 13 · **DEPENDENCIES:** M2-T2, M3-T0 · **STATUS:** **DONE** 2026-09-01 · **G3: PASS**
- Snapshot via `pg_dump -Fc` (not live PGDATA tar). Pull `remnawave/backend:<tag>` and record **digest**. Prisma runs on the copy. G3: numeric identity, reconstructible correlation (`shortUuid` or proven mapping), counts, joins, login, sub link, no mass revoke. Failure → `PLAN REVISION REQUIRED` (pick another 3.x). Success promotes **that digest** to “rehearsal-passed candidate,” still not production until cutover records it.
- Evidence **must** come from `rehearsal_*` volumes, not the RC `backend:3` / PG 18.4 sandbox (E4).
- **FILES:** evidence `docs/superpowers/evidence/2026-09-01-m3-t1-rw-candidate-g3.md`

- [x] `pg_dump -Fc` after freeze; SHA-256 `e87a3aeb…a98940d8`
- [x] Restore into `rehearsal_rw_pg17_candidate`; G2 `rehearsal_rw_pg17` unmounted
- [x] Pull/pin `remnawave/backend:3.4.3@sha256:4ea85b2fc16bd3e5d367b61afc07ec219133eaa12dd7b5e898adc33c84515422`
- [x] Prisma on copy; boot `v3.4.3`; `/health` 200
- [x] G3: `users.id` bigint; `uuid` dropped; `short_uuid` 3181 unique; revoked 205; join orphans 0; login SPA; `/api/sub/{shortUuid}` YAML 200
- [x] Isolation: sandbox `backend:3` + `rehearsal_bot` absent
- [x] Evidence committed

### M3-ID: Prove identity/API on the **actual** candidate + official docs

- **WEIGHT:** 8 · **DEPENDENCIES:** M3-T1 GO · **STATUS:** **DONE** 2026-09-01
- Official panel migration/API + runtime: uuid dropped?, `shortUuid` retained?, mapping table?, which lookups work, correlation to bot `remnawave_short_uuid`, whether backfill is required, exact deterministic algorithm. **4.2 backfill is reference, not proof.** Adapt remnabot1 client only where evidence differs. Low shortUuid coverage → `PLAN REVISION REQUIRED`.
- **FILES:** evidence `docs/superpowers/evidence/2026-09-01-m3-id-identity-api.md`

- [x] Official Prisma: `t_id`→`id` rename; `DROP COLUMN uuid`; no mapping table
- [x] Official API: resolve `{id|shortUuid|username}`; by-id / by-short-uuid / by-username; **no** by-uuid
- [x] Runtime schema matches; unauth 401 vs 404 probes
- [x] Bot ∩ panel shortUuid **3170/3172 = 99.94%** (not low)
- [x] Backfill required (no `remnawave_id`); exact key `remnawave_short_uuid`; 4.2 script keys **agree** — client **not** changed
- [x] Evidence committed

### M3-T2: PG 17 vs 18

- **WEIGHT:** 5 · **DEPENDENCIES:** M3-T1 GO · **STATUS:** **DONE** 2026-09-01 · **STAY ON 17.6**
- Stay on 17 if the candidate runs; PG 18 is a separate track. Do not combine PG 17→18 with 2.8→3.x.
- **FILES:** evidence `docs/superpowers/evidence/2026-09-01-m3-t2-pg17.md`

- [x] Candidate `SHOW server_version` = **17.6** on M2-T0 digest
- [x] `rehearsal_rw` 3.4.3 healthy; `/health` 200; users 3181
- [x] Sandbox remains PG **18.4** / `remnawave-db-data` (not used for G3)
- [x] No compose retarget to `postgres:18.4`
- [x] Evidence committed

---

# M4 — Bot compatibility (port custom → 4.2; verify client)

### M4-T0: Graft remnabot Alembic lineage into remnabot1

- **WEIGHT:** 8 · **DEPENDENCIES:** M0-T6 · **STATUS:** **DONE** 2026-09-01 · **PASS**
- Archive **all** remnabot1 `0088–0110` out of `versions/` into `docs/superpowers/reference/upstream-alembic-0088-0110/`. Copy remnabot `0088–0104` into `versions/` **in the same commit**. Confirm `alembic heads` = remnabot `0104` (traffic clamp). Record known test/model/`0001` breakages. Do not run against production. Do not start remnabot1 against `rehearsal_bot_pg15` until this verification PASSES.
- **VERIFICATION:** `alembic heads` is remnabot `0104`; no file `0104_remnawave_numeric_id.py` or `0110_*.py` on the live graph; archive directory contains the 4.2 files.
- **FAILURE:** `PLAN REVISION REQUIRED: Alembic graft failed M4-T0` (E7).
- **COMMIT:** `feat(M4-T0): graft remnabot alembic 0088-0104; archive upstream 0088-0110`
- **FILES:** evidence `docs/superpowers/evidence/2026-09-01-m4-t0-alembic-graft.md`

- [x] Archive 23 upstream `0088–0110` files (incl. `0104_remnawave_numeric_id.py`, `0110_*.py`)
- [x] Copy 17 remnabot `0088–0104` files (SHA match); `0087` identical
- [x] `alembic heads` = remnabot `0104` traffic clamp; `test_migration_chain.py` 3 passed
- [x] Recorded model/`0001`/sandbox-`0110` breakages; no upgrade on restore; `rehearsal_bot` absent
- [x] Evidence committed

### M4-T1: Schema + boot + code-dependency diff

- **WEIGHT:** 8 · **DEPENDENCIES:** M4-T0, M2-T1 · **STATUS:** **DONE** 2026-09-01
- Inputs: remnabot 0104 schema (restored), remnabot1 4.2 models/imports, remnabot custom models, official RW contract (M3-ID if available).
- Question: **does remnabot1 4.2 boot against remnabot 0104 schema with unused payments disabled?** Every missing table/column that crashes import/startup becomes MVP schema. Every omitted upstream table gets a reason: not-MVP / already-local / not-required-by-imported-code / deferred.
- **Do not** claim “MVP = remnawave_id only” until this runs.
- **ANSWER:** **NO.** Evidence `docs/superpowers/evidence/2026-09-01-m4-t1-schema-boot-diff.md`. `select(User)` / `select(Subscription)` fail. Unused **payment tables** are not required. Mapped **columns** on existing `users`/`subscriptions`/`tariffs`/`promocodes`/`payment_method_configs` are. `c2c_receipts` is already in DB (M4-T7 models). `grace_access_sessions` query is non-fatal — defer table.

- [x] Diff remnabot1 models vs `rehearsal_bot_pg15` (0103 ≅ 0104 columns)
- [x] Classify omitted 4.2 tables
- [x] Boot-stage probe with SKIP_MIGRATION; no polling `rehearsal_bot`; no sandbox rebuild
- [x] Evidence committed

### M4-T2: Verify/adapt Remnawave client (do not rewrite from scratch)

- **WEIGHT:** 8 · **DEPENDENCIES:** M3-ID, M4-T1 · **STATUS:** **DONE** 2026-09-01
- Start from remnabot1’s existing 3.x client. Compare to official+rehearsal evidence. Change only mismatches. Tests: no live path calls removed 2.8 routes; `coerce_panel_user_id` rejects UUIDs.
- **COMMIT:** `feat(M4-T2): verify remnabot1 3.x client against rehearsal contract`
- **FILES:** evidence `docs/superpowers/evidence/2026-09-01-m4-t2-client-contract.md`; tests `tests/external/test_remnawave_m4_t2_contract.py`

- [x] Compare remnabot1 3.x client to M3-ID + rehearsal 3.4.3
- [x] No mismatches — `app/external/remnawave_api.py` unchanged
- [x] Tests: AST lock on removed 2.8 routes; `coerce_panel_user_id` rejects UUIDs (RED then GREEN)
- [x] Rehearsal probes 401/404 match M3-ID; `rehearsal_bot` absent; restore still `0103`
- [x] Evidence committed

### M4-T3: Alembic `0111` remnawave_id (semantics from M3-ID, not 4.2 comments)

- **WEIGHT:** 8 · **DEPENDENCIES:** M4-T1, M3-ID · **STATUS:** **DONE** 2026-09-01
- `down_revision='0104'` (grafted remnabot). **Decision: same `0111`, no `0112`.** Users: nullable BIGINT + **full** unique `ix_users_remnawave_id`. Subscriptions: nullable BIGINT + **partial** unique `uq_subscriptions_remnawave_id WHERE remnawave_id IS NOT NULL`. Non-unique index on existing `remnawave_short_uuid`. Inspector-guard `grace_access_sessions` (absent on remnabot schema). Protect custom columns (`c2c_receipts.approved_amount_kopeks`, `wholesale_discount_bps`, `user_disabled`, …).
- **M4-T1 extras (schema-only, same `0111`):** `users.referral_days_subscription_id`, `users.referral_reward_preference`; `subscriptions.grace_candidate_at/reason/suppressed_until`; `payment_method_configs.description`; `tariffs.lava_product_id`; `promocodes.traffic_gb` Integer NOT NULL `server_default='0'`. Do **not** create cispay/platega/lava/coupon/legal/grace **tables**.
- TDD + G5 clone round-trip + G1 upgrade to `0111`. Evidence: `docs/superpowers/evidence/2026-09-01-m4-t3-alembic-0111.md`.
- **COMMIT:** `feat(M4-T3): alembic 0111 remnawave_id and boot extras`

- [x] `0111` revises grafted `0104`; single head
- [x] Inspector-guarded extras; no deferred payment/product tables
- [x] Clone `0103→0104→0111→0104→0111`; G1 restore `0111`
- [x] C2C / wholesale / `user_disabled` kept; sandbox still `0110`; `rehearsal_bot` absent

### M4-T4: Models match `0111` (no drift)

- **WEIGHT:** 3 · **DEPENDENCIES:** M4-T3 · **STATUS:** **DONE** 2026-09-01
- remnabot1 4.2 already maps identity onto the grafted graph: User `unique=True,index=True` → `ix_users_remnawave_id`; Subscription plain column + `__table_args__` partial `uq_subscriptions_remnawave_id`. **No model edit.**
- **Autogenerate:** scoped to 0111-owned columns/indexes = **no diff**. Full `compare_metadata` vs G1 is **not** empty (9 deferred `create_table` + would drop `c2c_receipts` / wholesale / `user_disabled`). Do **not** commit a full autogenerate revision. Evidence: `docs/superpowers/evidence/2026-09-01-m4-t4-models-match-0111.md`.
- **COMMIT:** `test(M4-T4): lock models to 0111 remnawave_id mapping`

- [x] User `remnawave_id` unique+index BIGINT matches `0111`
- [x] Subscription plain `remnawave_id` + partial unique matches `0111`
- [x] 0111 extras mapped; TDD RED then GREEN
- [x] Scoped autogenerate 0 owned ops; full autogenerate not applied

### M4-T5: `persist_identity` seam (panel `.id`, not uuid lookup)

- **WEIGHT:** 5 · **DEPENDENCIES:** M4-T4 · **STATUS:** **DONE** 2026-09-01
- Thin adapter `app/custom/identity/persist.py`. Two write paths: `User.remnawave_id` and `Subscription.remnawave_id`. Reads panel ``.id`` only (via `coerce_panel_user_id`). **No** `resolve_remnawave_id(uuid=...)` — M3-ID uuid lookup is gone. Wired in `subscription_service` create/update and shortUuid adopt/bind. Evidence: `docs/superpowers/evidence/2026-09-01-m4-t5-persist-identity.md`.
- **COMMIT:** `feat(M4-T5): persist_identity seam for numeric panel id`

- [x] `persist_identity` User path from panel `.id`
- [x] `persist_identity` Subscription path from panel `.id`
- [x] UUID rejected; no uuid lookup helper
- [x] TDD RED then GREEN; `rehearsal_bot` absent; sandbox still `0110`

### M4-T6: Backfill (stable-key; verify remnabot1 script)

- **WEIGHT:** 13 · **DEPENDENCIES:** M4-T5, M3-ID · **STATUS:** **DONE** 2026-09-01
- Use remnabot1 `remnawave_identity_backfill` **only if** M3-ID match keys match the script. Otherwise rewrite the match order. Dry-run default, `--apply`, coverage report, idempotent, non-destructive. Low coverage blocks cutover. The 4.2 module also imports `GraceAccessSessionModel` — do not treat that import as a reason to create grace tables unless M4-T1 proved a boot dependency. Evidence: `docs/superpowers/evidence/2026-09-01-m4-t6-backfill.md`.
- **COMMIT:** `feat(M4-T6): stable-key remnawave_id backfill (G6)`

- [x] M3-ID keys MATCH script (`short_uuid` exact first); no rewrite
- [x] Dry-run default non-destructive (`with_id` stayed 0)
- [x] `--apply` 3170/3173; G6 3170 matches, 0 mismatches
- [x] Idempotent re-apply `applied=0`; grace table not created
- [x] `rehearsal_bot` absent; sandbox still `0110`

### M4-T7: Port MVP custom behavior from `/opt/remnabot`

- **WEIGHT:** 13 · **DEPENDENCIES:** M4-T0 (schema lineage), M4-T1 · **STATUS:** **DONE** 2026-09-01
- Port **only**: C2C plugin + `PaymentMethod.C2C`; FA fallback/default language behavior; Toman dual-scale; wholesale/partner pricing (`wholesale_discount_bps` / `partner_status`) from remnabot `app/utils/price_display.py` (not a lost T2.1 seam). Keep seams small. Tests from remnabot `tests/plugins/c2c` and pricing tests. Do not port unused payments. Do not merge cabinet. Evidence: `docs/superpowers/evidence/2026-09-01-m4-t7-custom-port.md`.
- **COMMIT:** `feat(M4-T7): port C2C, FA fallback, Toman, wholesale`

- [x] C2C plugin + `PaymentMethod.C2C` + `C2cReceipt` mapped to existing `c2c_receipts` (no new Alembic)
- [x] FA default language + fa→en→ru missing-key chain
- [x] Toman dual-scale (`format_price` / `format_balance`; balance 1:1)
- [x] Wholesale via remnabot `price_display` + `PricingEngine` wholesale-first (no `app/custom/pricing`)
- [x] Agent tests 152 passed, 3 skipped; `import main` OK; `rehearsal_bot` not polled; sandbox still `0110`
- [ ] G8 isolated C2C chat — **M6-T4** (P1 still UNKNOWN; empty `C2C_ADMIN_CHAT_ID` falls back to notifications chat)

**Batches:** M4.0={T0}(8); M4.1={T1}(8); M4.2={T2}(8); M4.3={T3}(8); M4.4={T4,T5}(8); M4.5={T6}(13); M4.6={T7}(13).

---

# M5 — Cabinet (separate repo `/opt/cabinet`)

### Task M5-T1: RC cabinet from `/opt/cabinet`

- **ID:** M5-T1 · **WEIGHT:** 5 · **RISK:** Medium · **DEPENDENCIES:** Checkpoint M1.2, Checkpoint M0-CAB (M1.3 Caddy cancelled)
- **STATUS:** **DONE** 2026-09-01 (cabinet `95d49d8b`; remnabot1 evidence `docs/superpowers/evidence/2026-09-01-m5-t1-rc-cabinet.md`). User smoke **تایید**.
- **GOAL:** Serve cabinet on `https://panel.rookari.com` with `/api`→bot (already how live RC Caddy works). Isolated rehearsal cabinet, if used, must not invent `staging-host-cabinet`.
- **FILES:** `/opt/cabinet` compose (join `remnawave-network` **or the rehearsal network named in M1-T1** — do not assume the sandbox `remnawave-network` is the rehearsal network).
- **EXACT IMPLEMENTATION:** keep relative `VITE_API_URL=/api`; test bot username `mrj7_bot`. Live Caddy already routes `/api/*`→`remnawave_bot:8080`. Do not wait for cancelled M1-T4 staging-host blocks.
- **VERIFICATION (G9):** `https://panel.rookari.com` loads; login/API works; FA strings; Toman `تومان`.
- **COMMIT:** cabinet repo `feat(M5-T1): RC split compose + network` on `prod-cutover` if custom commits start · **CHECKPOINT:** Checkpoint M5.

- [x] **Step 1:** Restore upstream `docker-compose.yml`; add `docker-compose.rc.yml` (`remnawave-network` only) and `docker-compose.rehearsal.yml` (`rehearsal_net` only, not started).
- [x] **Step 2:** Recreate `cabinet_frontend` with RC overlay; do not rebuild `remnawave_bot`; do not start `rehearsal_bot`.
- [x] **Step 3:** Agent G9 probes PASS. User Telegram login **تایید** 2026-09-01.
- [x] **Step 4: Commit** cabinet `feat(M5-T1): RC split compose + network` (`95d49d8b`) on `prod-cutover`; pushed `origin/prod-cutover`.

### Task M5-T2: Single cabinet source of truth

- **ID:** M5-T2 · **WEIGHT:** 3 · **RISK:** Low · **DEPENDENCIES:** M5-T1
- **STATUS:** **DONE** 2026-09-01 (`docs/superpowers/evidence/2026-09-01-m5-t2-cabinet-source.md`).
- Canonical: `/opt/cabinet`. `/opt/remnabot/cabinet` is legacy production embed — do not deploy it. remnabot1 must not grow an embedded `cabinet/`.
- **VERIFICATION:** rehearsal compose does not mount `/opt/remnabot/cabinet` or an embedded remnabot1 cabinet.

- [x] **Step 1:** Confirm `/opt/cabinet` present; `/opt/cabinet1` and `/opt/remnabot1/cabinet` absent; remnabot1 `git ls-files cabinet/` empty.
- [x] **Step 2:** Rehearsal compose `context: /opt/cabinet`; rendered config has no legacy embed path. Live `cabinet_frontend` working_dir `/opt/cabinet`.
- [x] **Step 3:** Comment-pin the constraint in `docker-compose.rehearsal.yml`. Do not start `rehearsal_bot`. Do not rebuild `remnawave_bot`.

### Task M5-T3: RC JWT (class C)

- **ID:** M5-T3 · **WEIGHT:** 2 · **RISK:** Medium · **DEPENDENCIES:** M1-T3
- **STATUS:** **DONE** 2026-09-01 (`docs/superpowers/evidence/2026-09-01-m5-t3-cabinet-jwt.md`).
- `.env.rehearsal` (`CABINET_JWT_SECRET`=generated). Fingerprint ≠ production. Production JWT must not validate on RC. No secret in git.

- [x] **Step 1:** Re-fingerprint rehearsal `6e66e417433351da` vs production `818cf61ccf8f100d` (`ssh bot`, read-only).
- [x] **Step 2:** Prod-signed HS256 dummy fails on rehearsal secret (`InvalidSignatureError`). Rehearsal self-decode OK.
- [x] **Step 3:** `.env.rehearsal` / `.env` / `.env.cutover` gitignored; no tracked secret values. Live sandbox `.env` not rewritten. `rehearsal_bot` not started; `remnawave_bot` not rebuilt.

**Batch M5** = {M5-T1,M5-T2,M5-T3} (10, NORMAL).

---

# M6 — Protected behavior + end-to-end MVP

### Task M6-T1: FA fallback regression gate (G9-strings)

- **ID:** M6-T1 · **WEIGHT:** 3 · **DEPENDENCIES:** M4-T7
- **STATUS:** **DONE** 2026-09-01 (`docs/superpowers/evidence/2026-09-01-m6-t1-fa-fallback.md`).
- Test `tests/localization/test_fa_fallback.py` (remnabot had no file of that name; gate authored here). Assert Persian for known keys; missing FA key → en → ru; English digits where required (formatters + ported C2C strings).
- **COMMIT:** `test(M6-T1): FA fallback gate` · **CHECKPOINT:** Checkpoint M6.1 (opens; closes after M6-T2 + M6-T3).

- [x] **Step 1:** Named gate `tests/localization/test_fa_fallback.py` (4 tests).
- [x] **Step 2:** Known FA keys Persian; missing key fa→en→ru; English digits on `format_price`/`format_balance` and C2C keys.
- [x] **Step 3:** `tests/localization` 15 passed, 1 skipped (`test_fa_en_ru_chain`). `import main` OK. `rehearsal_bot` not started. `remnawave_bot` not rebuilt this batch.

### Task M6-T2: Toman dual-scale regression gate

- **ID:** M6-T2 · **WEIGHT:** 3 · **DEPENDENCIES:** M4-T7
- **STATUS:** **DONE** 2026-09-01 (`docs/superpowers/evidence/2026-09-01-m6-t2-toman.md`).
- Test `tests/utils/test_price_display_toman.py` (remnabot had no file of that name; gate authored here). Cover display helpers used after the remnabot port (`تومان`, fa-IR grouping). Dual-scale: catalog kopeks÷100 vs balance Toman 1:1; `BALANCE_TOMAN_CUTOFF_UTC`.
- **COMMIT:** `test(M6-T2): Toman gate`

- [x] **Step 1:** Named gate `tests/utils/test_price_display_toman.py` (8 tests).
- [x] **Step 2:** TDD RED then GREEN on `calculate_missing_amount` mixed-scale (990550 → 550).
- [x] **Step 3:** `test_price_display.py` 25 passed; `import main` OK; `rehearsal_bot` not started; `remnawave_bot` not rebuilt this batch.

### Task M6-T3: Wholesale pricing regression gate (G10)

- **ID:** M6-T3 · **WEIGHT:** 3 · **DEPENDENCIES:** M4-T7
- Lock wholesale gating on `partner_status`+`wholesale_discount_bps` via the **ported remnabot `price_display` path**, not the lost T2.1 `app/custom/pricing` seam.
- Test `tests/services/test_wholesale_pricing.py` (adapt from remnabot). Integer BPS, floor; approved partner discounted, revoked not.
- **COMMIT:** `test(M6-T3): wholesale gate`

### Task M6-T4: C2C isolated RC test — HARD MVP gate

- **ID:** M6-T4 · **WEIGHT:** 5 · **RISK:** High · **DEPENDENCIES:** M4-T7, P1
- With the isolated test chat (P1) and test bot: submit a receipt; approve in the test chat; confirm balance credit (Toman scale) + `c2c_receipts` row. Restored historical rows allowed. Never post to the production admin chat.
- **VERIFICATION (G8):** receipt→approve→balance flow verified in the isolated chat.
- **FAILURE:** P1 unavailable, or any RC receipt reaches the production admin chat → **G8 INCOMPLETE ⇒ MVP-VERIFIED = NO-GO**.
- **COMMIT:** `docs(M6-T4): C2C RC PASS (isolated chat)` · **CHECKPOINT:** Checkpoint M6.2.

### Task M6-T5: End-to-end RC MVP smoke — MVP-VERIFIED gate

- **ID:** M6-T5 · **WEIGHT:** 8 · **RISK:** High · **DEPENDENCIES:** M6-T1..T4 (**G8 PASS required**), M4-T6, Checkpoint M3-ID
- **FILES:** `docs/superpowers/evidence/2026-08-31-rc-e2e-smoke.md`.
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

Russian payment integrations; coupons; grace product; referral v2; legal consents; guest-purchase extras — unless M4-T1 proves a boot dependency (then schema-only, still disabled). Do not invent `0112–0126` because 4.2 files exist.

---

## Fresh-conversation resume

Resume from:

1. **This plan** (`docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`)
2. remnabot1 branch `prod-cutover` @ current HEAD
3. `/opt/cabinet` git
4. `/opt/remnabot` as read-only custom source
5. `docs/superpowers/evidence/*` (re-check dates) and **Open smoke (this batch)** in this plan
6. `.cursor/rules/10-remnabot-migration.mdc`
7. Runtime (`docker volume ls`, `alembic current`, Cloudflare A, `getWebhookInfo`, `ssh bot`)

Do **not** look for deleted `docs/superpowers/specs/2026-08-*` or `*-errata.md` on remnabot1. Architecture A on remnabot remote is optional history only.

**Do not execute M6-T3 until the user confirms this batch.** Checkpoints M0–M3, **M4-T0**–**M4-T7**, **M5-T1**–**M5-T3**, **M6-T1**, and **M6-T2** are complete. Follow Session contract (one batch + Open smoke). Do not start polling `rehearsal_bot`. G8 remains M6-T4. Checkpoint M6.1 stays open until M6-T3.

---

## Self-review (2026-08-31)

1. Spec coverage: topology inversion, Alembic graft, two-track RW, bot PG digest, volume forbid lists, cutover safety (DNS/Telegram/C2C/rollback/gates/env A–E), E1–E8, M0 honest status, M1+ user gate — each has a section or task.
2. Placeholder scan: no TBD / “implement later” / “similar to Task N”. Deleted-spec recovery task cancelled with an inlined replacement.
3. Type consistency: graft archive path, `0111` `down_revision='0104'`, volume names `rehearsal_*`/`cutover_*`, identities 1–6, cabinet `/opt/cabinet` — used the same way in later milestones.
4. No required path to `specs/2026-08-*` or `*-errata.md`.
5. M0 checkpoint complete: T0–T6 DONE (T2 `f10ebd75`, T3 `8b70bd75`, T4 `3f798500` + tag, T5 `3926dd03`, T6 `9aa0d69a`); T7 CANCELLED.
6. User gate now: numbered OK on M6-T2 → **M6-T3**. Session contract. Do not start polling `rehearsal_bot`. Do not rebuild sandbox `remnawave_bot` (DB still `0110`). G8 / P1 remain for M6-T4.

---

## Execution handoff

Plan updated and saved to `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`.

**Done:** M0–M3, E8, **M4-T0 PASS**, **M4-T1**, **M4-T2**, **M4-T3**, **M4-T4**, **M4-T5**, **M4-T6** (G6 backfill 3170/3173), **M4-T7** (C2C/FA/Toman/wholesale port), **M5-T1** (RC cabinet split compose @ cabinet `95d49d8b`, user smoke **تایید**), **M5-T2** (canonical `/opt/cabinet`), **M5-T3** (rehearsal JWT fp `6e66e417433351da` ≠ prod), **M6-T1** (FA fallback gate), **M6-T2** (Toman dual-scale gate + `calculate_missing_amount` mixed-scale fix) 2026-09-01.

**Not started:** M6-T3..T5, DNS, cutover. M1-T4 cancelled.

**Next after user numbered OK:** **M6-T3** (wholesale pricing regression gate). User smoke: none this batch. Do not start polling `rehearsal_bot`. Do not rebuild sandbox `remnawave_bot`. G8 is M6-T4 (needs P1 isolated chat + dedicated `C2C_ADMIN_CHAT_ID`).

P1 (C2C test chat) and P2 (Cloudflare DNS write) still UNKNOWN — they block M6 / M7, not M2. Do not guess chat IDs.

**New-chat skill:** executing-plans + Session contract (one batch). Optional SDD *inside* the batch. Never finish the whole plan in one session.
