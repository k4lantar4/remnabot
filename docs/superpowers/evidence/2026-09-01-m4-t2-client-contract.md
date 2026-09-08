# M4-T2 — Verify remnabot1 3.x client against rehearsal 3.4.3

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M4-T2 · weight 8 · dependencies: M3-ID, M4-T1  
Panel: `rehearsal_rw` = `remnawave/backend:3.4.3@sha256:4ea85b2fc16bd3e5d367b61afc07ec219133eaa12dd7b5e898adc33c84515422`  
Commit message (this batch): `feat(M4-T2): verify remnabot1 3.x client against rehearsal contract`

## Verdict: MATCH — client unchanged

Official + M3-ID + live rehearsal 3.4.3 agree with remnabot1 `app/external/remnawave_api.py`. **No client rewrite.** Tests lock the contract so a later uuid lookup cannot land silently.

| Check | Result |
|---|---|
| Lookups that exist | `GET /api/users/{id}`, `GET /api/users/by-short-uuid/{shortUuid}`, `GET /api/users/by-username/{username}`, `POST /api/users/resolve` `{id\|shortUuid\|username}` |
| Lookups that are gone | `by-uuid`, `by-subscription-uuid`, `by-telegram-id` — **404 Cannot GET** |
| `coerce_panel_user_id` | rejects UUID strings (`RemnaWaveInvalidUserIdError`); `get_user_by_id` does not call the panel |
| Live `_make_request` paths | AST scan: **0** hits on removed 2.8 user routes (does not treat `by-short-uuid` as `by-uuid`) |
| Methods absent | no `get_user_by_uuid` / `get_user_by_subscription_uuid` / `get_user_by_telegram_id` (`find_users_by_telegram_id` uses `/api/users/stream?telegramId=`) |
| `app/external/remnawave_api.py` vs HEAD | **unchanged** (probe method added then removed to watch tests fail) |

## Tests (TDD)

File: `tests/external/test_remnawave_m4_t2_contract.py`

1. **RED:** temporary `get_user_by_uuid` + `_make_request('GET', '/api/users/by-uuid/…')` in the client. `test_live_client_make_request_paths_omit_removed_28_user_routes` and `test_client_has_no_uuid_user_lookup_methods` **FAILED** as expected.
2. **GREEN:** probe method removed. `uv run pytest tests/external/test_remnawave_m4_t2_contract.py` + related 3.0.0 cases: **27 passed**.

Also re-ran: UUID coerce, `get_user_by_id` rejects UUID before request, telegram-id uses stream filter, `resolve_user` sends exactly one identifier.

## Rehearsal probes (`127.0.0.1:3100`, proxy headers `Host`/`X-Forwarded-*` = `rw.rookari.com`)

`/health` on `:3101` = HTTP 200 `status=ok`.

| Request | HTTP | Body note |
|---|---|---|
| `GET /api/users/932` | **401** | route exists |
| `GET /api/users/by-short-uuid/placeholder` | **401** | route exists |
| `GET /api/users/by-username/placeholder` | **401** | route exists |
| `POST /api/users/resolve` `{id}` / `{shortUuid}` / `{username}` | **401** | route exists |
| `GET /api/users/by-uuid/…` | **404** | `Cannot GET` |
| `GET /api/users/by-subscription-uuid/…` | **404** | `Cannot GET` |
| `GET /api/users/by-telegram-id/1` | **404** | `Cannot GET` |
| `GET /api/users/{uuid-shaped}` | **401** | same `:userId` route, not a uuid endpoint |

Authenticated admin/API-token calls were **not** made (class D).

## Isolation

| Name | After M4-T2 |
|---|---|
| `rehearsal_bot_pg15` `alembic_version` | **`0103`** (no upgrade / stamp) |
| `rehearsal_bot` app | **absent** |
| sandbox `remnawave_bot` / `remnabot1_postgres_data` | still **`0110`**; container **not** rebuilt this batch (`Created=2026-09-01T10:26:23Z`) |
| `rehearsal_rw` | healthy 3.4.3 digest above |
| `nodes` | **0** (E8) |
| live Caddy / `panel.rookari.com` | **unchanged** |

## Not done (next batch)

**M4-T3** Alembic `0111` (`down_revision='0104'`) for `remnawave_id` + M4-T1 mapped extras. Do not poll `rehearsal_bot`. Do not `alembic upgrade` the restore until T3 lands.
