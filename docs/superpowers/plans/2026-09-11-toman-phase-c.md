# Toman Phase C — one scale (Toman 1:1) everywhere in storage and backend logic

**Status:** active — design approved by the user on 2026-09-12; execution started (Task 1, Task 2).
**Repos:** `remnabot` only. The cabinet (`frontend`) is deliberately **not** touched: this plan keeps
the HTTP contract byte-identical. The frontend change is the follow-up plan "Phase C-2" (last section).
**Upstream basis:** remnabot `origin/main` `cf47f3cf`, `upstream/main` `9fcebfd7` (2026-09-11);
frontend `origin/main` `e1016515`, `upstream/main` `57810c7d` (for C-2).
**Kind:** architectural (currency scale + data migration). Written under the `implementation-plan`
skill; execute with `plan-execution`, one PR per task.

---

## Decisions — answered by the user 2026-09-12

1. **Deploy window — approved, no constraint here.** This whole VPS is test/development and
   production runs on a separate machine, so the short read/write outage while revision `0113` runs
   (the bot migrates at start, and the cabinet API is the same container) is fine. The question is
   re-opened **only for the future production cutover**, not for this environment.
2. **Ruble-era rows — convert them, don't leave them.** There are **zero** such rows in this database
   (0 transactions, 0 c2c_receipts, 0 users before `BALANCE_TOMAN_CUTOFF_UTC = 2026-06-05T00:00:00Z`,
   queried 2026-09-11), so this is a rule the migration carries for the future production-data merge,
   not something testable against real rows here. Revision `0113` therefore keeps the conversion of
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

Already **Toman 1:1** — revision `0113` must not touch these: `users.balance_kopeks`;
`transactions.amount_kopeks` for `deposit, withdrawal, refund, failed_refund, referral_reward,
poll_reward`; `c2c_receipts.amount_kopeks` / `approved_amount_kopeks`; `referral_earnings`;
`withdrawal_requests`; `advertising_campaigns.balance_bonus_kopeks` (+ registrations);
`promocodes.balance_bonus_kopeks` (a *percent* for `PromoCodeType.DISCOUNT`);
`referral_reward_levels.referrer_fixed_kopeks` / `referee_fixed_kopeks`.

**Catalog x100** — what `0113` divides by 100: the `tariffs` price columns incl. `period_prices`
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
Phase C. So: **one Alembic revision (`0113`, `down_revision = '0112'`, the current head) divides the
catalog columns by 100**, and the backend code stops converting. Consequences that shape the tasks:

- **Rounding:** integer division truncating toward zero, the same floor `catalog_price_in_toman`
  already applies, so *every displayed number stays identical*. Dev DB has exactly one catalog row
  that isn't divisible by 100 — `transactions.id=320`, `-13` ("افزودن 2 دستگاه برای 208 روز", the
  known device-pricing rounding artifact) → becomes `0`, which is what it already displays.
- **Idempotency:** one revision, one transaction (PostgreSQL DDL+DML is transactional), guarded by
  `alembic_version` and by the marker table `amount_scale_state` (one row, `scale='toman'`) the
  revision creates and the downgrade drops. *Implementation note (Task 2):* the marker and the log
  live in their own two tables rather than in `system_settings` rows, so the admin-editable settings
  store is not polluted with synthetic keys and the downgrade can simply drop them.
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

**Nothing — it is deleted, not moved.** After `0113`, every row of `transactions.amount_kopeks` is
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
  `format_balance`, `toman_rates.py`, the C2C plugin, and now `amount_columns.py` + revision `0113`.
  Upstream is a ruble product and will keep writing `price_kopeks` as kopeks; every upstream merge
  after this must be triaged for new money columns — the Task 1 guard test is what catches it
  (a new upstream column fails CI until it is classified).
- **Reused as-is:** Alembic and `app/database/migrations.py` (`run_alembic_upgrade`), `add_user_balance` /
  `subtract_user_balance`, the pricing engine's discount math (it is scale-agnostic), the stats
  aggregation queries (they only lose their `CASE`).
- **Hot files** (`purchase.py`, `tariff_purchase.py`, `balance/main.py`, `texts.py`, `inline.py`) are
  touched only by deleting conversion calls — no restructuring, to keep the merge diff small.
- No deferred gateway is re-enabled or depended on; their payment tables are explicitly excluded from
  `0113`, and their `*_MIN/MAX_AMOUNT_KOPEKS` settings keep ruble-kopek semantics (Task 5 leaves them,
  and documents why).

---

## Tasks

Each task is one PR, mergeable on its own. Tasks 1–2 are inert (no behavior change); behavior changes
only when Task 3 merges, which is why Tasks 2 and 3 must deploy together — note it in both PR bodies.

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

### Task 2 — Alembic revision `0113`: divide the catalog columns by 100 — **done (this PR)**

- **Repo/files:** `remnabot` — `migrations/alembic/versions/0113_toman_phase_c_catalog_scale.py`
  (`revision = '0113'`, `down_revision = '0112'`); test `tests/database/test_0113_catalog_scale.py`
  (next to the other revision tests, not a new `tests/migrations/` directory).
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

### Task 3 — Collapse the helpers and the two formatters

- **Repo/files:** `remnabot` — `app/utils/price_display.py`, `app/config.py`,
  `app/database/crud/transaction.py`, then the ~150 `catalog_price_in_toman` call sites and the
  `user_can_afford` / `missing_toman` callers across `app/handlers/**`, `app/services/**`,
  `app/cabinet/routes/**`, `app/webapi/routes/miniapp.py`, `app/plugins/c2c/**` (C2C should come out
  unchanged except imports — it is the reference for "correct"). Also fix the `referral_contest_events`
  restore writer (F-057) so both writers are Toman. 37 test files reference the helpers.
- **Test first:** balance 150,000 vs tariff 200,000 → refused, 50,000 shortfall; balance 250,000 →
  exactly 200,000 debited, row `-200000`, history «200,000 تومان»; deposit 50,000 → «50,000 تومان».
  Extend the AST guard to fail on any `// 100` / `* 100` near an amount outside `wire_scale.py`.

### Task 4 — Freeze the HTTP contract with one explicit serializer

- **Repo/files:** `remnabot` — new `app/utils/wire_scale.py`, applied in `app/cabinet/routes/**` and
  `app/webapi/routes/miniapp.py`; tests `tests/cabinet/test_wire_scale_contract.py`,
  `tests/test_miniapp_payments.py`.
- **Interfaces:** `wire_catalog_kopeks(toman)` / `toman_from_wire_catalog(kopeks)` — the only `* 100`
  left in the codebase. Outbound: tariff `price_kopeks` and period prices, `total_price_kopeks`,
  `missing_amount_kopeks`, method `min/max_amount_kopeks`, `quick_amounts`, admin `*_kopeks` editors.
  Inbound: `TopUpRequest.amount_kopeks`, `/balance/stars-invoice`, the admin tariff/limit editors.
  Unchanged: `amount_rubles`, `balance_kopeks`, `missing_amount`, the `*_toman` stats twins.
- **Test first:** golden-JSON contract tests recorded from `origin/main` before the migration.

### Task 5 — Admin/bot inputs and config defaults on the Toman scale

- **Repo/files:** `remnabot` — `app/config.py` catalog defaults, `payment_method_config_service.py`,
  the bot admin editors that parse typed amounts ×100, and the numeric catalog keys in
  `remnabot/.env` (Decision 3). The deferred gateways' `*_MIN/MAX_AMOUNT_KOPEKS` stay ruble kopeks.
- **Test first:** per editor, type 50,000 → stored 50,000 → «50,000 تومان»; 1,000,000 persists in the
  payment-method limit editor (no int32 overflow — F-052).

### Task 6 — Scale marker guard + deploy/rollback runbook

- **Repo/files:** `remnabot` — startup check reading `system_settings['amount_scale']`,
  `docs/deploy/phase-c-runbook.md`, test `tests/database/test_amount_scale_guard.py`.
- **Runbook:** deploy = pull + `docker compose -f docker-compose.dev.yml restart bot` (migration runs
  at start) + the verification queries. Rollback = `alembic downgrade 0112` **then** the previous
  image, never the image alone.

---

## Cross-repo contract

None in this plan — the JSON contract is frozen by Task 4 and the cabinet ships nothing.

**Follow-up plan (Phase C-2, after this one is deployed and stable):** remove `wire_scale.py` screen
by screen — backend adds the Toman-scale field next to the old one (additive), the cabinet switches
to it, then the old field goes. Frontend scope: `src/utils/catalogScale.ts` (deleted), `formatPrice`
→ `formatBalance`, the ~54 files that still divide by 100 (including the `*_DIVISOR` constants),
`TopUpAmount.tsx` / `TopUpMethodSelect.tsx` (F-012), `AdminPaymentMethodEdit.tsx`,
`AdminTariffCreate.tsx`, `AdminWheel.tsx`, `AdminReferralLevels.tsx`. Bot PR first, then frontend.

---

## Findings subsumed by this plan

Do not fix these separately — re-check them after Task 3/5 merges and delete the entries in that PR
(re-read `/opt/project/FINDINGS.md` first; another session edits it concurrently).

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

Generate with the `smoke-test-checklist` skill **after Task 3 and after Task 5** (the two tasks a user
can see), not now — with the exact Toman numbers expected on each cabinet screen, and a before/after
comparison of a tariff price, the wallet balance, a purchase and the balance history.
