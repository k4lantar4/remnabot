# M4-T1 — Schema + boot + code-dependency diff

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M4-T1 · weight 8  
Restored bot DB: `rehearsal_bot_pg15` · `alembic_version=0103` · users **7828**  
Code graph: remnabot `0104` (traffic clamp is data-only; **column schema = 0103**)

## Verdict

**remnabot1 4.2 does not boot cleanly against remnabot 0104 schema**, even with unused payments disabled (`TELEGRAM_STARS`/`YOOKASSA`/`PLATEGA`/`LAVA`/`CISPAY`/… = false, `GRACE_ACCESS_MODE` default false).

**MVP ≠ remnawave_id only.** `users.remnawave_id` / `subscriptions.remnawave_id` are required (M4-T3) but **not sufficient**: SQLAlchemy SELECTs every mapped column on `User` / `Subscription` / `Tariff` / `promocodes` / `payment_method_configs`.

Did **not** start `rehearsal_bot` polling. Did **not** `alembic upgrade` / `stamp`. Did **not** rebuild sandbox `remnawave_bot` (still `0110`). Probe inserted then **deleted** `web_api_tokens.id=2`.

## Counts (VERIFIED)

| Set | Count |
|---|---|
| DB tables | 107 (incl. `alembic_version`, `c2c_receipts`) |
| remnabot1 models | 114 |
| remnabot models | 106 |

## 4.2 model tables absent from restored DB

| Table | Classification |
|---|---|
| `cispay_payments` | **not-MVP** — payment disabled |
| `platega_subscriptions` | **not-MVP** — payment disabled |
| `lava_subscriptions` | **not-MVP** — payment disabled |
| `recurrent_payments` | **not-MVP** — payment disabled |
| `coupon_batches`, `coupons` | **deferred** — unused 4.2 product |
| `legal_consents` | **deferred** — cabinet email/legal extras off |
| `referral_reward_levels` | **deferred** as product — but see User columns below |
| `grace_access_sessions` | **deferred table.** `grace_access_runtime.start()` queries it even when mode=false; exception is **non-fatal** (main.py warning). Prefer inspector-guard in code (already in M4-T3 notes). Do **not** create this table just because 4.2 has the file. |

## DB tables remnabot1 models lack

| Table | Classification |
|---|---|
| `c2c_receipts` | **already-local** on restored schema. Missing from remnabot1 models/`PaymentMethod`. **M4-T7 code port**, not a new Alembic table. |
| `alembic_version` | n/a |

## Mapped columns missing on existing tables (ORM-breaking)

| Table | Missing mapped columns | Classification |
|---|---|---|
| `users` | `remnawave_id`, `referral_days_subscription_id`, `referral_reward_preference` | **MVP schema-only.** Any `select(User)` fails (`remnawave_id` is the first error; others follow). Referral v2 **product** stays deferred. |
| `subscriptions` | `remnawave_id`, `grace_candidate_at`, `grace_candidate_reason`, `grace_suppressed_until` | **MVP schema-only.** Any `select(Subscription)` fails. Grace **product** stays deferred (`GRACE_ACCESS_MODE=false`). |
| `payment_method_configs` | `description` | **MVP schema-only.** `ensure_payment_method_configs` INSERT at startup (caught as warning). |
| `tariffs` | `lava_product_id` | **MVP schema-only** (nullable). Tariff ORM is core; Lava **product** stays disabled. |
| `promocodes` | `traffic_gb` | **MVP schema-only** (nullable). Promocode table exists and is imported. |
| `guest_purchases` | `campaign_slug`, `idempotency_key` | **deferred** — guest-purchase extras; not on this boot path |
| `referral_earnings` | `days_granted`, `level`, `reward_type`, `tariff_id` | **deferred** as product columns unless a later hot path SELECTs the 4.2 mapper |

## DB columns remnabot1 does not map (keep; port in M4-T7)

| Table | Unmapped production columns |
|---|---|
| `users` | `wholesale_discount_bps`, `business_role`, `panel_brand_prefix` |
| `subscriptions` | `user_disabled`, `account_sequence`, `panel_username`, `purchase_note` |
| `broadcast_history`, `pinned_messages` | `entities_json` |

## Boot stages (SKIP_MIGRATION, rehearsal DSN, no `setup_bot`)

| Stage | Result |
|---|---|
| `sync_postgres_sequences` | ok |
| `ensure_default_web_api_token` | ok (row inserted then deleted) |
| `bootstrap_superadmins` | swallows `users.remnawave_id` missing; continues |
| `ensure_tariffs_synced` | ok (did not hit full Tariff mapper in this probe) |
| `ensure_payment_method_configs` | **FAIL** `payment_method_configs.description` |
| `select(User)` | **FAIL** `users.remnawave_id` |
| `select(Subscription)` | **FAIL** `subscriptions.grace_candidate_reason` (mapper lists all grace_* + `remnawave_id`) |
| `grace_access_runtime.start()` | **FAIL** missing `grace_access_sessions` — non-fatal in `main.py` |

`AuthMiddleware` / any user message will hit `select(User)` → not a usable bot until MVP schema-only columns exist.

## Follow-on (not this batch)

- **M4-T3 `0111`:** remnawave_id semantics from M3-ID **plus** inspector-guarded extras listed as MVP schema-only above (or a tight `0112` if 0111 should stay identity-only — decide in M4-T3, do not invent payment tables).
- **M4-T2:** client vs rehearsal panel (independent of this ORM gap).
- **M4-T7:** C2C model + `PaymentMethod.C2C` + wholesale/`user_disabled` mappings.
- Do **not** `alembic upgrade` the restore to `0104` in M4-T2 (clamp is G4 / later). Do **not** start polling `rehearsal_bot` until a named batch needs it.
