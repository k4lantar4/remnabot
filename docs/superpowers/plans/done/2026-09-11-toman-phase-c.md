# Toman Phase C — one scale (Toman 1:1) everywhere in storage and backend logic

**Status:** done — Tasks 1-5 done and deployed (remnabot#61, #63, #64, #65, plus the follow-ups
#66 and #67); Task 6 (startup scale guard + `docs/deploy/phase-c-runbook.md`) in the PR that moved
this file to `plans/done/`. Revisions `0114`, `0115` and `0116` are applied on this VPS and the
cabinet was verified against them on 2026-09-12. Phase C-2 (retiring the wire x100) is not planned yet.
**Repos:** `remnabot` only. The cabinet (`frontend`) is deliberately **not** touched: this plan keeps
the HTTP contract byte-identical. The frontend change is the follow-up plan "Phase C-2" (last section).
**Upstream basis:** remnabot `origin/main` `cf47f3cf`, `upstream/main` `9fcebfd7` (2026-09-11);
frontend `origin/main` `e1016515`, `upstream/main` `57810c7d` (for C-2).
**Kind:** architectural (currency scale + data migration). Written under the `implementation-plan`
skill; execute with `plan-execution`, one PR per task.

---

## Decisions — answered by the user 2026-09-12

1. **Deploy window — approved, no constraint here.** This whole VPS is test/development and
   production runs on a separate machine, so the short read/write outage while revision `0115` runs
   (the bot migrates at start, and the cabinet API is the same container) is fine. The question is
   re-opened **only for the future production cutover**, not for this environment.
2. **Ruble-era rows — convert them, don't leave them.** There are **zero** such rows in this database
   (0 transactions, 0 c2c_receipts, 0 users before `BALANCE_TOMAN_CUTOFF_UTC = 2026-06-05T00:00:00Z`,
   queried 2026-09-11), so this is a rule the migration carries for the future production-data merge,
   not something testable against real rows here. Revision `0115` therefore keeps the conversion of
   pre-cutoff rows behind an explicit, defaulted-off switch and refuses to guess.
   **❓ Still open:** converting ruble amounts to Toman needs a **ruble→Toman rate**, which is a
   business number — the user must give it before the pre-cutoff branch can be enabled. Until then
   the switch stays off and the migration asserts that no pre-cutoff row exists (on this DB it
   passes); the rest of the plan is unaffected.
3. **`remnabot/.env` — I edit the numeric catalog keys myself** (`PRICE_*`, `TRAFFIC_*_CONFIG`) as
   part of Task 5, when the config defaults move to the Toman scale. Only those numeric keys: never a
   token, secret or credential line, and never a `*_ENABLED` flag. `system_settings` holds no
   override for any of them (queried 2026-09-11: 0 rows).

Decided in this plan, not asked: storage columns and JSON/wire field names keep their `*_kopeks` /
`*_rubles` names (a rename would fight every upstream merge); rounding of non-round legacy rows
truncates toward zero, which is what today's display already does.

---

## Goal

Every amount in the bot's database and in backend logic is stored and computed in **Toman 1:1**. The
hand-maintained `_BALANCE_SCALE_TRANSACTION_TYPES` list, `catalog_price_in_toman`, `user_can_afford`
and the two different formatters disappear, so "this hop assumed the other scale" stops being
possible. B2C and partner users alike — same paths. No user-visible number changes anywhere.

## Why now

PRs #32…#56 are almost all one bug repeated (`payment-fixer` memory, `known-scale-bugs.md`), and
12 of the open entries in `/opt/project/FINDINGS.md` are payment-kind, most of them instances of it.
Phase C removes the class instead of the instances (workspace `CLAUDE.md` → Currency).

---

## Design

### Where the two scales are today (verified 2026-09-11/12: code + read-only `remnabot-db` MCP)

The authoritative, machine-checked list is `app/utils/amount_columns.py` (Task 1): 68 money columns,
each classified as catalog x100, Toman 1:1, or a payment provider's own currency/unit. Highlights:

Already **Toman 1:1** — revision `0115` must not touch these: `users.balance_kopeks`;
`transactions.amount_kopeks` for `deposit, withdrawal, refund, failed_refund, referral_reward,
poll_reward`; `c2c_receipts.amount_kopeks` / `approved_amount_kopeks`; `referral_earnings`;
`withdrawal_requests`; `advertising_campaigns.balance_bonus_kopeks` (+ registrations);
`promocodes.balance_bonus_kopeks` (a *percent* for `PromoCodeType.DISCOUNT`);
`referral_reward_levels.referrer_fixed_kopeks` / `referee_fixed_kopeks`.

**Catalog x100** — what `0115` divides by 100: the `tariffs` price columns incl. `period_prices`
(JSON); `transactions.amount_kopeks` for `subscription_payment, gift_payment`;
**`subscription_events.amount_kopeks` for `event_type IN (purchase, renewal, activation)` only** —
this column turned out to be mixed-scale exactly like `transactions` (`balance_topup` mirrors a
deposit, `promocode_activation` and `campaign_registration` are Toman bonuses; dev DB: 114 purchase +
9 renewal + 6 activation vs 8 balance_topup rows); `server_squads` / `squads.price_kopeks`;
`subscription_servers.paid_price_kopeks`; `guest_purchases`; `subscription_conversions`;
`polls` / `poll_responses.reward_amount_kopeks`; `promo_groups.auto_assign_total_spent_kopeks` and
`users.auto_promo_group_threshold_kopeks`; `promo_offer_templates` / `discount_offers.bonus_amount_kopeks`;
the `wheel_prizes` / `wheel_spins` value columns; `referral_contest_events` /
`referral_contest_virtual_participants`; `coupon_batches.wholesale_price_kopeks`;
`payment_method_configs.min_amount_kopeks` / `max_amount_kopeks` / `quick_amounts` (JSON).

**Never touched:** every deferred gateway's payment table (`yookassa_payments` … `cispay_payments`,
`lava_subscriptions`, `platega_subscriptions`), `apple_transactions`, `cryptobot_payments.amount`
(crypto asset units) and `wheel_spins.payment_amount` (a Telegram Stars *count*, not currency).

### Migrate the data, not just the read path

A read-path-only change would keep two scales in the DB and only move the conversion — i.e. not
Phase C. So: **the data revision `0115` divides the catalog columns by 100**, split from the
structural `0114` so that no commit on `main` is ever unsafe to restart, and the backend code stops converting. Consequences that shape the tasks:

- **Rounding:** integer division truncating toward zero, the same floor `catalog_price_in_toman`
  already applies, so *every displayed number stays identical*. Dev DB has exactly one catalog row
  that isn't divisible by 100 — `transactions.id=320`, `-13` ("افزودن 2 دستگاه برای 208 روز", the
  known device-pricing rounding artifact) → becomes `0`, which is what it already displays.
- **Idempotency:** one data revision, one transaction (PostgreSQL DDL+DML is transactional), guarded
  by `alembic_version` and by the marker row in `amount_scale_state` (`scale='toman'`) that `0115`
  writes and its downgrade deletes. *Implementation note:* the marker and the rounding log live in
  their own two tables (created by `0114`) rather than in `system_settings` rows, so the
  admin-editable settings store is not polluted with synthetic keys. **The tables existing means
  nothing — only the row says the database is on the Toman scale**, which is what the Task 6 startup
  guard reads.
- **Reversible:** `downgrade()` multiplies the same columns by 100. The non-round rows are the only
  lossy ones; the upgrade stores their pre-image in `amount_scale_rounding_log`, and the downgrade
  restores each one exactly before dropping the table.
- **Pre-cutoff (ruble-era) rows:** per Decision 2 the upgrade refuses to run when rows older than
  `BALANCE_TOMAN_CUTOFF_UTC` exist unless an explicit ruble→Toman rate is configured; it never
  invents one.

### Rows written by an older container mid-deploy

There is exactly one writer: the single `bot` container (bot + cabinet API + miniapp in one process).
`docker compose restart bot` (dev compose) stops the old process before the new one starts, and the
new process runs `run_alembic_upgrade()` before it serves — so no old-code write can interleave with
the migration. The real risk is the *opposite* pair: **new DB + old image** (a rollback of the image
without the DB) or **old DB + new image** (migration skipped), both of which would silently charge or
credit 100x. Task 6 closes it: Phase C code asserts the `amount_scale` marker at startup and refuses
to serve with an explicit log line if it is missing, and the rollback runbook says "downgrade first,
then redeploy the old image". Nothing else in the workspace writes amounts to this DB.

### How bot, cabinet, miniapp and the frontend stay consistent

The bot, `app/cabinet/routes/**` and `app/webapi/routes/miniapp.py` are the same deployable and all
read the same helpers, so they change together in Tasks 3–5 — no parity gap is possible.

For the cabinet **frontend**, this plan chooses the boundary, not the big bang: the JSON contract
stays exactly as it is today (`price_kopeks` and friends on the catalog x100 scale, `amount_rubles`
display Toman), produced by one explicit serializer (`app/utils/wire_scale.py`, Task 4). So
`frontend/src/utils/catalogScale.ts` and `formatPrice` stay correct and the frontend ships **no
change at all** in this plan. Repo order therefore: `remnabot` alone, Tasks 1→6 in order; the
frontend follows later in Phase C-2, backend-first and additive as the workspace rules require.

### What replaces `_BALANCE_SCALE_TRANSACTION_TYPES`

**Nothing — it is deleted, not moved.** After `0115`, every row of `transactions.amount_kopeks` is
Toman, so the type no longer decides anything:

| Deleted | Becomes |
|---|---|
| `_BALANCE_SCALE_TRANSACTION_TYPES`, `BALANCE_SCALE_TRANSACTION_TYPES`, `is_balance_scale_transaction` | — |
| `display_transaction_amount_from_storage(amount, tx_type)` | `float(abs(amount))`, callers drop the `tx_type` argument |
| `format_transaction_amount_for_display(amount, tx_type, fb, fp)` | `settings.format_balance(abs(amount))` |
| `storage_sum_to_display_toman(raw_sum, tx_type)` | `abs(raw_sum)` |
| `crud/transaction.transaction_toman_amount()` (`CASE … // 100`) | `func.abs(Transaction.amount_kopeks)`; `transaction_toman_sum()` → plain `COALESCE(SUM(...), 0)` |
| `catalog_price_in_toman`, `display_amount_from_kopeks`, `kopeks_from_display_amount` | identity — call sites simply drop them (150 + N sites) |
| `user_can_afford(balance, price)`, `missing_toman`, `missing_toman_on_catalog_scale` | `balance >= price` / `max(0, price - balance)` (kept as one-line helpers so the AST guard test still has a name to check) |
| `settings.format_price` vs `settings.format_balance` | one formatter; `format_price` becomes an alias of `format_balance` (316 + 380 call sites keep working, and "used the wrong formatter" — F-058's whole shape — stops existing) |

The guard that replaces the hand-maintained list is a **test, not a list**: Task 1 ships
`app/utils/amount_columns.py` (every money column classified) plus a test that fails when a new
money column or a new transaction type appears unclassified — the same role `_BALANCE_SCALE…` had,
but enforced by CI instead of by memory.

### Out of scope (deliberate)

Renaming columns/fields (`*_kopeks` → `*_toman`, `*_rubles`) — it would touch 823 `price_kopeks` and
538 `_rubles` occurrences and conflict with every future upstream merge; the names stay, the docstrings
and `amount_columns.py` carry the truth. Also out: the Stars/CryptoBot **rate** work (F-050), wholesale
pricing (F-013, F-029, F-047), and enabling any payment method.

---

## Vs. upstream

- **Ours (must survive an upstream merge):** the whole Toman scale — `price_display.py`,
  `format_balance`, `toman_rates.py`, the C2C plugin, and now `amount_columns.py` + revisions `0114`/`0115`.
  Upstream is a ruble product and will keep writing `price_kopeks` as kopeks; every upstream merge
  after this must be triaged for new money columns — the Task 1 guard test is what catches it
  (a new upstream column fails CI until it is classified).
- **Reused as-is:** Alembic and `app/database/migrations.py` (`run_alembic_upgrade`), `add_user_balance` /
  `subtract_user_balance`, the pricing engine's discount math (it is scale-agnostic), the stats
  aggregation queries (they only lose their `CASE`).
- **Hot files** (`purchase.py`, `tariff_purchase.py`, `balance/main.py`, `texts.py`, `inline.py`) are
  touched only by deleting conversion calls — no restructuring, to keep the merge diff small.
- No deferred gateway is re-enabled or depended on; their payment tables are explicitly excluded from
  `0115`, and their `*_MIN/MAX_AMOUNT_KOPEKS` settings keep ruble-kopek semantics (Task 5 leaves them,
  and documents why).

---

## Tasks

Each task is one PR, mergeable on its own.

> **Invariant: every commit on `main` is restart-safe.** The bot runs `alembic upgrade head` at
> start, so a revision that rescales stored amounts must never be reachable before the code that
> reads Toman. Phase C's database work is therefore split: `0114` only creates the two bookkeeping
> tables and changes no amount (safe to apply at any time, asserted by
> `tests/database/test_0114_scale_tables.py::test_0114_changes_no_amount`), while the divide-by-100,
> the rounding log and the `toman` marker live in `0115`, which **merges together with the Task 3
> code**. Until Task 3, a restart applies `0114` only: two empty tables, no amount touched.

### Task 1 — Money-column inventory + guard test (no behavior change) — **done (remnabot#61)**

- **Repo/files:** `remnabot` — `app/utils/amount_columns.py`; test `tests/utils/test_amount_columns.py`.
- **Interfaces (consumed by Tasks 2, 3, 6):** `ColumnRef(table, column, kind='int'|'json_values',
  where=None, note='')`; `CATALOG_SCALE_COLUMNS`, `TOMAN_SCALE_COLUMNS`, `PROVIDER_CURRENCY_COLUMNS`,
  `ALL_CLASSIFIED_COLUMNS`, `scale_of()`, `looks_like_money_column()`;
  `CATALOG_SCALE_TRANSACTION_TYPES = {'subscription_payment', 'gift_payment'}`;
  `CATALOG_SCALE_SUBSCRIPTION_EVENT_TYPES = {'purchase', 'renewal', 'activation'}`.
- **Test:** every money-named column in `Base.metadata` is classified exactly once, no listed column
  is stale, the two `TransactionType` scales are disjoint and cover the enum, mixed-scale columns
  carry a row filter that matches their type set, `json_values` matches the real column type, and no
  gateway table is on the catalog scale.

### Task 2 — Alembic `0114`: the bookkeeping tables (no data change) — **done (remnabot#63, split in #64)**

- **Repo/files:** `remnabot` — `migrations/alembic/versions/0114_toman_phase_c_scale_tables.py`
  (`revision = '0114'`, `down_revision = '0113'`), test `tests/database/test_0114_scale_tables.py`;
  the data revision `0115_toman_phase_c_catalog_scale.py` and its round-trip test
  `tests/database/test_0115_catalog_scale.py` are written and tested but only become reachable with
  Task 3 (next to the other revision tests, not a new `tests/migrations/` directory).
- **Interfaces:** consumes Task 1's tuples. Creates `amount_scale_state` (`scale='toman'`, read by
  Task 6's startup guard) and `amount_scale_rounding_log`. `upgrade()` divides by 100 with the sign
  kept and the magnitude floored — what the display layer already does — per `ColumnRef.kind` and
  `ColumnRef.where`; `downgrade()` multiplies back, restores the logged pre-images and drops both
  tables. Missing tables/columns are skipped, so it runs on a partially migrated database.
  It **refuses to run** (raises, which aborts bot start) while rows older than
  `PRE_TOMAN_CUTOFF_UTC` exist, because converting them needs the ruble→Toman rate of Decision 2.
- **Test:** seeded round-trip on SQLite (upgrade → catalog ÷100 including the JSON columns, Toman and
  provider columns untouched → downgrade → byte-identical snapshot, the `-13` artifact restored from
  the log), idempotency, the marker row, the display invariant
  (`format_price(before) == format_balance(after)`), and the pre-cutoff refusal.

### Task 3 — Collapse the helpers, ship `0115`, and freeze the wire — **done (remnabot#65)**

**Re-scoped 2026-09-12, mid-execution.** Tasks 3, 4 and 5 as originally written are *not*
separable, and this is the single most important correction to this plan.

The original split assumed the HTTP contract could be frozen later, in Task 4. It cannot: `0115` —
the divide-by-100 on the stored amounts — ships with Task 3. From the moment Task 3 merges, every
response field the cabinet divides by 100 renders **100x too small** unless the backend has already
multiplied it back. The same argument applies to Task 5: an admin editor that still multiplies a
typed amount by 100 writes a 100x-too-large row into a Toman column on the first save after the
merge. So the deliverable is one PR containing three things that must land together:

1. the helper/formatter collapse (original Task 3),
2. the outbound/inbound wire boundary for every field the cabinet divides or multiplies (Task 4),
3. the admin and config inputs (Task 5).

Tasks 4 and 5 are therefore **absorbed here** and left in this document only as the field lists
they contributed.

#### How the surfaces were found (not by chasing test failures)

Two audits drive the work, because reacting to red tests gives no coverage guarantee:

- **`frontend` audit** — every argument reaching `formatPrice`, `catalogPriceInToman`,
  `userCanAfford`, `missingToman`, `KOPEKS_DIVISOR` or a literal `/ 100`, plus every request field
  built with `* 100`. Result: **25 distinct `*_kopeks` response fields** and 8 request fields.
  Of the 25, `balance_kopeks` is a false positive (it is the *undivided* first argument of
  `userCanAfford`) and `referrer_fixed_kopeks` / `referee_fixed_kopeks` are pre-existing bugs
  (those columns were already Toman, and `AdminReferralLevels.tsx` divides them anyway).
- **`amount_columns.scale_of()` audit** — the 68 classified money columns decide each backend site:
  storage (delete the hop), inbound wire, outbound wire, ruble gateway (leave), percentage (leave).

#### Done on the branch

| Area | What landed |
|---|---|
| Helpers | `catalog_price_in_toman`, `_BALANCE_SCALE_TRANSACTION_TYPES`, `display_amount_from_kopeks`, `kopeks_from_display_amount`, `missing_toman_on_catalog_scale`, `format_transaction_amount_for_display` deleted; `format_price` is an alias of `format_balance` |
| Migration | `0115` moved from `migrations/phase_c/` into the Alembic chain |
| Storage sweep | ~366 inline `// 100` / `* 100` sites; 9 `models.py` properties; the `CASE` in `crud/transaction.py` |
| Config | 17 catalog defaults in `config.py` divided by 100 |
| Wire boundary | `app/utils/wire_scale.py` plus: balance top-up limits and quick amounts, traffic packages, device prices, server/country prices, renewal options, trial price, tariff purchase options and periods, subscription daily price, tariff-switch preview, classic purchase payloads, gift config, public landing, admin landings stats, admin tariffs, admin users' tariff sheet and gifts, admin servers, admin squads, admin coupons, admin promo groups, admin payment methods, admin wheel and the user spin history |
| Admin inputs | The bot's poll-reward and pricing parsers no longer multiply a typed amount by 100 |
| Guard | `tests/utils/test_phase_c_single_scale.py` (21 tests) — AST guards for scale hops, for a factor hidden in a default argument, and a structural percentage rule (`a / b * 100` is a share, not a unit change); the money-name list was widened to `total`, `value`, `sum`, `revenue`, `payout`, `bonus`, `threshold`, `earning`, `reward`, `prize`, `spent`, `fee`, which surfaced 30 further real leftovers, all fixed |

Size so far: **~160 files**, 6 commits plus uncommitted work. This is far larger than the original
Task 3 estimate, which is why this section was rewritten before finishing.

#### How the 21 failures resolved (2026-09-12)

| # | Cause | Verdict |
|---|---|---|
| A | `render_addon_insufficient_funds()` called with the old `price_kopeks=` keyword at six sites | **Real bug this branch introduced** — a `TypeError` in the bot's addon, cart-resume and classic-purchase flows. Fixed; the values already carried Toman, only the keyword was wrong. |
| B | Stars and CryptoBot credit paths | Code was right, expectations were stale: `process_referral_topup` takes Toman 1:1 now. The legacy USD→RUB path keeps upstream's conversion but loses the kopek hop, because it credits a Toman column. |
| C | Bot admin and bot gift screens | Mostly test-side, plus **one real Task 5 gap**: `traffic_price_per_gb_kopeks` still ran the typed number through a rubles-to-kopeks parser. Now `parse_positive_toman`, normalizing through `normalize_display_amount_text` like every other typed amount. |
| D | Cabinet switch preview | Test-side: assert the wire value, as the sibling shortfall assertion already did. |
| E | "the two formatters disagree" | Premise gone; rewritten to pin that `format_price` is an alias and can no longer disagree. |
| F | Daily-charge recovery, gift purchase, referral commission | Test-side; `GiftInsufficientBalanceError` also stopped describing one side as catalog. |

Suite after the work: **6140 passed, 9 skipped, 0 failed**; `ruff format --check` and `ruff check`
clean over the whole tree. Findings deleted as subsumed: F-010, F-012, F-052, F-057, F-058.

#### Carried into deploy and Phase C-2

- ~~The numeric catalog keys in `remnabot/.env` (Decision 3)~~ — **done on deploy day.** Nine keys
  were divided by 100 in both `remnabot/.env` and `remnabot/.env.dev` (`BASE_SUBSCRIPTION_PRICE`,
  `PRICE_{14,30,60,90,180,360}_DAYS`, `PRICE_TRAFFIC_UNLIMITED`, `PRICE_PER_DEVICE`), backups beside
  them. `.env.dev` is the file `docker-compose.dev.yml` actually loads — editing only `.env` changes
  nothing the container sees. No token, secret or `*_ENABLED` flag was touched.
- ~~The first restart after this merge applies `0115`.~~ **Applied 2026-09-12**: the database was at
  `0113`, so the restart ran `0114` and `0115` together (0.84 s).
- ~~Live verification~~ **passed**: tariff 30-day `period_prices` went `1000000` → `10000` and the
  cabinet still renders «10,000 تومان»; balances (a Toman column already) were untouched; the top-up
  screen still reads «10,000 – 100,000,000 تومان» and the admin tariff editor shows the daily price
  as `10000`.
- `TopUpRequest.amount_kopeks` still caps at `le=2_000_000_000` on the wire, i.e. a single cabinet
  top-up of at most **20,000,000 Toman** (what remained of F-052 once the int32 column ceiling
  became 2.1 billion Toman). It lifts when Phase C-2 removes the ×100 from the wire.

### Task 4 — Freeze the HTTP contract with one explicit serializer — **absorbed into Task 3**

Kept for its field lists. `wire_catalog_kopeks(toman)` / `toman_from_wire_catalog(kopeks)` are the
only `* 100` left in the backend. Outbound: tariff prices and period prices, `total_price_kopeks`,
`missing_amount_kopeks`, method `min/max_amount_kopeks`, `quick_amounts`, the admin `*_kopeks`
editors. Inbound: `TopUpRequest.amount_kopeks`, `/balance/stars-invoice`, the admin tariff, server,
coupon, promo-group, payment-method and wheel-prize editors. Unchanged: `amount_rubles`,
`balance_kopeks`, `missing_amount`, the `*_toman` stats twins.

### Task 5 — Admin/bot inputs and config defaults on the Toman scale — **absorbed into Task 3**

Kept for its list: `app/config.py` catalog defaults, `payment_method_config_service.py`, the bot
admin editors that parse typed amounts ×100, and the numeric catalog keys in `remnabot/.env`
(Decision 3). The deferred gateways' `*_MIN/MAX_AMOUNT_KOPEKS` stay ruble kopeks.

### Follow-ups found after Task 3 shipped — **done (remnabot#66, frontend#22, remnabot#67)**

The admin-parity check that `CLAUDE.md` requires after a user-facing change was run against the
merged Task 3 and found four money screens 100x off. Three were regressions Task 3 itself introduced
and one was a column `0115` never saw:

| Screen | Cause | Fix |
|---|---|---|
| `/admin/payments` | the sweep in `bbba9c97` read `amount_rubles=record.amount_kopeks / 100` as a scale hop and removed the division, but the cabinet prints that field as-is | remnabot#66 — back through `toman_from_wire_catalog` |
| `/admin/users` → activity tab | the backend sent raw amounts while `src/utils/adminBalance.ts` divided by 100; only the transaction mapper had an `amount_toman` twin | remnabot#66 |
| `/admin/traffic-usage` "total spent" | same shape, one column | remnabot#66 + frontend#22 |
| tariff traffic top-up packages | `tariffs.traffic_topup_packages` was not in `CATALOG_SCALE_COLUMNS`, so `0115` skipped it — while the code shipped with `0115` reads it as Toman and **charges the stored number straight from the balance** | remnabot#67 — revision `0116` |

**The root cause is worth keeping.** `amount_columns.py` only *forces* a column to be classified when
its **name** matches `kopeks|price|amount`. `traffic_topup_packages` is a `{gb: price}` JSON map whose
name says nothing about money, so nothing made anyone decide, and it stayed on the kopek scale while
every reader moved to Toman. `0116` widens the pattern with `packages`, but a name pattern can only
ever catch the money it is told to look for: **any new JSON column that holds amounts has to be
classified by meaning, not by name.** `COLUMNS_RESCALED_AFTER_0115` is the mechanism that lets a later
revision own a column `0115` skipped, so replaying the chain on a pre-Phase-C dump still divides it
exactly once.

Found and left open by that check: **F-068** (bulk "add balance" credits 100x — pre-dates Phase C,
belongs to `payment-fixer`), **F-069**, **F-070**, **F-071** (admin money inputs still labelled in
kopeks), **F-072** (tariff custom-days / custom-traffic have no admin form at all). Smoke items are
**S-019** and **S-020**.

### Task 6 — Scale marker guard + deploy/rollback runbook

- **Repo/files:** `remnabot` — startup check reading the latest `amount_scale_state` row
  (`app/database/amount_scale_guard.py`, called from `main.py` after the migration stage, also under
  `SKIP_MIGRATION`), `docs/deploy/phase-c-runbook.md`, test `tests/database/test_amount_scale_guard.py`.
- **Fresh databases:** they are built from the models and stamped at head, so no revision writes the
  marker; `run_alembic_upgrade` declares `toman` on them (`declare_toman_scale_on_fresh_db`), or a
  brand-new install could never start.
- **Runbook:** deploy = pull + `docker compose -f docker-compose.dev.yml restart bot` (migration runs
  at start) + the verification queries. Rollback = `alembic downgrade 0114` **then** the previous
  image, never the image alone. Write it from what the 2026-09-12 deploy actually needed: take a
  `pg_dump -Fc` first, divide the numeric catalog keys in **`.env.dev`** as well as `.env` (the dev
  compose file loads the former), and recreate the container rather than restarting it when env
  values changed, because `restart` reuses the old environment.
- **Also record the head revision the runbook targets:** `0116`, not `0115` — a rollback that stops
  at `0115` leaves `traffic_topup_packages` divided while everything else is not.

---

## Cross-repo contract

None in this plan — the JSON contract is frozen inside Task 3 and the cabinet ships nothing.

**Follow-up plan (Phase C-2, after this one is deployed and stable):** remove `wire_scale.py` screen
by screen — backend adds the Toman-scale field next to the old one (additive), the cabinet switches
to it, then the old field goes. Frontend scope: `src/utils/catalogScale.ts` (deleted), `formatPrice`
→ `formatBalance`, the ~54 files that still divide by 100 (including the `*_DIVISOR` constants),
`TopUpAmount.tsx` / `TopUpMethodSelect.tsx` (F-012), `AdminPaymentMethodEdit.tsx`,
`AdminTariffCreate.tsx`, `AdminWheel.tsx`, `AdminReferralLevels.tsx`. Bot PR first, then frontend.

---

## Findings subsumed by this plan

All five were re-verified against the merged branch and **deleted from `/opt/project/FINDINGS.md`**
on 2026-09-12. The table below is kept so a later reader can see what each ID was.

| ID | How Phase C covers it |
|---|---|
| **F-052** — admin payment-method limits overflow above ~21.4M Toman | Task 5: limits become Toman 1:1 |
| **F-057** — referral-contest events stored on two scales | Task 2 + 3: both writers store Toman |
| **F-058** — admin bot "avg per referrer" divided by 100 | Task 3: the two formatters merge |
| **F-010** (partly) — wheel prize / promocode bonus scale | Task 2 + 5. **Not** the spin cost from the ruble Stars rate (that is F-050) |
| **F-012** — cabinet top-up form sends ×100 | Frozen (still correct) by Task 4; removed in Phase C-2 |

Payment-kind entries **not** subsumed: F-013, F-021, F-029, F-035, F-047, F-050, F-062.

Also subsumed from `payment-fixer` memory (`known-scale-bugs.md`, not in FINDINGS): the bot admin
"buy subscription for user" comparison, the level-scheme admin ×100 inputs, the `monitoring_service`
low-balance `÷100 ₽` display, `webapi/routes/partners.py` and `servers.py` `balance_rubles`, and the
ambiguity of `WithdrawalRequest`'s scale.

## Smoke test

Done: **S-019** (the single Toman scale after `0115` — the admin save round-trip, a real Stars or
CryptoBot top-up, and a balance purchase) and **S-020** (the admin money screens the parity check
fixed). Both are open in `/opt/project/SMOKE-TESTS.md`. What the cabinet driver could already check —
the purchase screen, the top-up limits, the admin tariff editor, the admin balances — is recorded
there as verified rather than queued.
