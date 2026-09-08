# M3-ID — Identity/API proof on G3 candidate 3.4.3

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M3-ID · weight 8 · dependencies: M3-T1 GO  
Panel digest: `remnawave/backend:3.4.3@sha256:4ea85b2fc16bd3e5d367b61afc07ec219133eaa12dd7b5e898adc33c84515422`  
Sources: official `remnawave/backend@3.4.3` Prisma/OpenAPI **and** runtime on `rehearsal_rw_pg17_candidate` + G1 `rehearsal_bot_pg15`. **Not** RC sandbox `backend:3`. **Not** 4.2 comments as proof.

## Verdict

| Question | Answer |
|---|---|
| `users.uuid` dropped? | **YES** — Prisma `20260720132335_drop_user_uuid` (`DROP COLUMN uuid`). Runtime: column absent. |
| Mapping table uuid→id? | **NO** — no such table. Numeric id is a **rename** of 2.8.1 `t_id`. |
| `shortUuid` retained? | **YES** — unique `users.short_uuid`; 3181/3181 nonempty. |
| Lookups that exist | `GET /api/users/{id}`, `GET /api/users/by-short-uuid/{shortUuid}`, `GET /api/users/by-username/{username}`, `POST /api/users/resolve` with **exactly one of** `{id, shortUuid, username}` |
| Lookups that are gone | `GET /api/users/by-uuid/…` **404 Cannot GET**; `GET /api/users/by-subscription-uuid/…` **404**; `GET /api/users/by-telegram-id/…` **404** |
| Bot correlation key | `subscriptions.remnawave_short_uuid` = panel `users.short_uuid` (**exact**) |
| Backfill required? | **YES** — bot dump has **no** `remnawave_id`; users.remnawave_uuid count **0**; identity lives on subscriptions |
| Deterministic algorithm | `users.id` := former `t_id` (Prisma `20260720124815_rename_column`). **Not** a hash of uuid. Bot never stored `t_id`, so backfill cannot recover id from `remnawave_uuid`. |
| 4.2 backfill match keys vs evidence | **MATCH** — exact key is `shortUuid`; do not call uuid routes; `coerce_panel_user_id` must reject UUIDs (`numberParamSchema = z.coerce.number().positive()`) |
| Low shortUuid coverage? | **NO** — 3170/3172 distinct bot shortUuids present on panel (**99.94%**). Not `PLAN REVISION REQUIRED`. |
| Client code this batch | **unchanged** — official+runtime agree with remnabot1 4.2 client |

Authenticated admin/API-token calls were **not** made (class D). Route existence is 401 vs 404 with proxy headers. Public `GET /api/sub/{shortUuid}` already proven in G3.

## Official Prisma (backend tag 3.4.3)

`prisma/migrations/20260720124815_rename_column/migration.sql`:

```
ALTER TABLE "users" RENAME COLUMN "t_id" TO "id";
ALTER SEQUENCE "users_t_id_seq" RENAME TO "users_id_seq";
```

`prisma/migrations/20260720132335_drop_user_uuid/migration.sql`:

```
DROP INDEX "users_uuid_key";
ALTER TABLE "users" DROP COLUMN "uuid";
```

Warning in that file: “All the data in the column will be lost.” There is **no** copy into a mapping table.

Earlier `20260407151134_repalce_uuid_with_user_id` only rewired child FKs (`hwid_user_devices.user_uuid` → `user_id` via join on `users.uuid = h.user_uuid` **before** the drop). After G3 those child FKs already point at numeric `users.id`.

## Official API (backend tag 3.4.3)

`libs/contract/api/controllers/users.ts` `USERS_ROUTES`:

- `GET_BY_ID: (userId) => userId`
- `GET_BY.SHORT_UUID`
- `GET_BY.USERNAME`
- `RESOLVE: 'resolve'`
- **no** `BY_UUID` / `BY_SUBSCRIPTION_UUID` / `BY_TELEGRAM_ID`

`ResolveUserCommand`: body exactly one of `id` | `shortUuid` | `username`; response `{id, username, shortUuid}`.

`GetUserByIdCommand.RequestParamSchema.userId` = `numberParamSchema` = `z.coerce.number().positive()` (`libs/contract/models/path-params.schema.ts`). A leftover panel **uuid string** on `{userId}` is validation failure after auth, not a uuid lookup.

## Runtime (rehearsal candidate)

| Check | Result |
|---|---|
| `users.id` | bigint PK, sequence `users_id_seq` |
| `users.uuid` / `users.t_id` | **absent** |
| `users.short_uuid` | text unique, 3181 |
| uuid mapping table | **none** |
| Remaining uuid columns on `users` | `vless_uuid` (protocol), `external_squad_uuid` (squad FK) — **not** panel user identity |
| `GET /api/users/932` | **401** (route exists) |
| `GET /api/users/by-short-uuid/placeholder` | **401** |
| `GET /api/users/by-username/placeholder` | **401** |
| `POST /api/users/resolve` `{id}` / `{shortUuid}` / `{username}` | **401** |
| `GET /api/users/by-uuid/…` | **404 Cannot GET** |
| `GET /api/users/by-subscription-uuid/…` | **404 Cannot GET** |
| `GET /api/users/by-telegram-id/1` | **404 Cannot GET** |
| `GET /api/users/{uuid-shaped}` | **401** (same `:userId` route, not a uuid endpoint) |

Unauthenticated `/api/users/*` needs `X-Forwarded-Proto` + `X-Forwarded-Host` + `X-Forwarded-For` (same proxy middleware as G3). Empty reply without them is **not** a missing route.

## Bot dump correlation (G1 `rehearsal_bot_pg15`, alembic still **0103**)

| Metric | Count |
|---|---|
| `subscriptions` | 3173 |
| nonempty `remnawave_short_uuid` | 3173 |
| nonempty `subscriptions.remnawave_uuid` | 3173 (historical panel uuid; **unusable** for 3.4.3 lookup) |
| uuid-only rows (short empty, uuid set) | **0** |
| `users.remnawave_uuid` nonempty | **0** |
| `remnawave_id` column | **absent** (0 columns) |
| distinct bot shortUuids | 3172 (1 duplicate value) |
| panel shortUuids | 3181 |
| intersection | **3170** |
| bot missing in panel | **2** (0.06% — backfill unresolved, not a coverage NO-GO) |
| panel missing in bot | 11 |

**0111 semantics (from this evidence, not 4.2 comments):** store panel `users.id` (bigint, former `t_id`) as bot `remnawave_id`. Match/backfill order: **`remnawave_short_uuid` exact first**. Do not implement uuid lookup. Do not treat `vless_uuid` as panel identity. DDL still landed in M4-T3 after graft.

4.2 `remnawave_identity_backfill._match_subscription` exact-first `short_uuid` **agrees**. Telegram/username/email remain fallbacks only when shortUuid is empty (production dump has **no** such rows). Do not rewrite the script this batch.

## Isolation

sandbox `backend:3` still running; `rehearsal_bot` absent; bot alembic **0103** (no upgrade/stamp).

## Next

M3-T2: stay on PG 17 (candidate already runs on 17.6). Then M4-T0 graft remains independently unblocked.
