# Rookari Migration v2 — Revised Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Migrate active VPN subscribers (~761 matched to 3x-ui) plus bot-joined users without service (~5,893) into bot-remnawave, preserving **remaining time** and **remaining traffic** as of backup anchor `2026-02-28 08:00 UTC`, with `MULTI_TARIFF_ENABLED=true` (one subscription per tariff, squads merged within tier).

**Architecture:** Standalone CLI in `tools/migration/` runs in isolated worktree. Phase 0 snapshots all at-risk data to disk. ETL produces three cohorts: `subscribers`, `campaign_users`, `partners`. Time/traffic math uses backup anchor, not raw `expiryTime`. Panel sync sets `trafficLimitBytes = remaining_bytes` and `traffic_used_gb = 0`. No changes to miniapp or cabinet for vmess — ops-only grace period on old 3x-ui panels.

**Tech Stack:** Python 3.13, sqlite3, JSON, SQLAlchemy async, pytest, Remnawave API via `app/external/remnawave_api.py`, `SubscriptionService`.

**Base plan:** Extends [2026-06-07-rookari-migration.md](./2026-06-07-rookari-migration.md).

---

## Key design decisions (locked)

| Topic | Decision |
|-------|----------|
| Execution | Subagent-Driven (A), one task per subagent with review |
| Backup anchor | `2026-02-28T08:00:00Z` (from `old_bot/bcp/2026-02-28_08-00/`) |
| Multi-sub | `MULTI_TARIFF_ENABLED=true`; group by `(telegram_id, tariff_id)`; merge `connected_squads` within group |
| Time formula | `remaining = expiry_at_backup - anchor`; `new_end_date = migration_run_time + remaining` |
| Traffic formula | `remaining_bytes = max(0, total - up - down)`; `traffic_limit_gb = ceil(remaining_bytes/1GiB)`; `traffic_used_gb = 0` |
| No-service users | All active `fl_user` without active `config_stat` → user row only, no subscription (~5,893) |
| vmess direct users | **Skip upstream changes**; ops grace period only |
| Small server merge | Servers 11, 17, 40, 46 → squad `merged-small` (unchanged) |

---

## Cohort definitions

### Cohort A — Subscribers (~761–1,538 depending on 3x-ui join strictness)

- Active in 3x-ui backup (`enable=1`, expiry > anchor OR unlimited)
- Joined to `config_stat` by `remark = email`
- Joined to `fl_user` by `userid = telegram_id`, `status=1`
- Output: 1..N `MigrationSubscription` per user (N = distinct active tariff_ids, max 2: پایه + پریمیوم)

### Cohort B — Campaign users (~5,893)

- Active `fl_user` NOT in Cohort A
- Load: `users` row only (`telegram_id`, name, username, wallet, `language=fa`)
- No `subscriptions`, no Remnawave panel user
- Preserve `sent` field in audit manifest for future broadcast segmentation

### Cohort C — Partners (subset of A + B)

- From `fl_sellers` (246 rows): set `partner_status=approved`, `referral_commission_percent=percent`

---

## CLI usage

```bash
python -m tools.migration.run backup          # Task 0
python -m tools.migration.run extract         # cohorts JSON
python -m tools.migration.run load            # dry-run
python -m tools.migration.run load --execute  # requires MIGRATION_BACKUP_DIR
python -m tools.migration.run sync --execute
python -m tools.migration.run validate
```

**Gate:** `load --execute` refuses to run unless `MIGRATION_BACKUP_DIR` points to a directory with valid `SHA256SUMS`.

**Config before load:**

```env
MULTI_TARIFF_ENABLED=true
MAX_ACTIVE_SUBSCRIPTIONS=10
SALES_MODE=tariffs
```

---

## Operational runbook (production cutover)

### T-7 days

- Staging dry-run full pipeline
- Provision Remnawave squads + nodes per topology table
- Set `MULTI_TARIFF_ENABLED=true` in staging, verify miniapp shows multiple subs

### T-1 day

- Fresh 3x-ui backup if live drift > 24h
- Re-run `extract` on fresh backup; diff count vs staging

### T-0 (maintenance window, ~2–4 hours)

1. Old bot → maintenance message
2. `python -m tools.migration.run backup`
3. `load --execute` + `sync --execute`
4. `validate` — abort if any check fails
5. Spot-check 10 users: wallet, end_date, subscription URL HTTP 200
6. Enable new bot
7. Broadcast (Persian): new subscription link required; old vmess works for grace period

### T+1 to T+30

- Monitor `remnawave_retry_queue`
- Keep old panels read-only for grace period
- Campaign segment: export `campaign_users.json` → Telegram broadcast API / external CRM

### Rollback

- Restore PostgreSQL from `pg_remnawave_bot.sql.gz`
- Re-enable old bot
- Old panels still have original clients (unchanged backup)

---

## Requirement 6 — vmess direct users (audit conclusion)

**Finding:** Old DB has no reliable field for "used subscription link vs pasted vmess URI". Cannot audit retroactively.

**Without upstream debt (recommended):**

- Do NOT add vmess fields to bot or bedolaga-cabinet
- **Ops-only grace window (14–30 days):**
  - Keep old 3x-ui panels running read-only (no new sales)
  - Nginx on old domains (`s3.rookari.com`, etc.) proxies to frozen panels
  - Telegram broadcast: import new Remnawave subscription URL
  - Old vmess UUIDs keep working until panel shutdown

**Skip:** Custom reverse-proxy in bot, vmess display in cabinet, UUID preservation via API (not supported in Remnawave `create_user`).

---

## Server topology

| Old server IDs | New squad key |
|----------------|---------------|
| 11, 17, 40, 46 | `merged-small` |
| 14 | `s3` |
| 18 | `s4` |
| 19 | `s5` |
| 22 | `s5-alt` |
| 24 | `s10` |
| 30 | `s8` |
| 57 | `s100` |
| 37, 56 | skip |

| Old `server_info.vip` | `tariff_id` |
|-----------------------|-------------|
| `1` | `3` (پایه) |
| `20` | `2` (پریمیوم) |
