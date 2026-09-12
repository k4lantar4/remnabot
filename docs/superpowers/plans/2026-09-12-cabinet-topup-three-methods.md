# Cabinet top-up: three live methods (Stars, CryptoBot, card-to-card)

**Status:** active
**Repos:** `remnabot` first (tasks 1-3, backward-compatible additive API), then `frontend` (tasks 4-5).
**Upstream basis:** `remnabot` origin/main `835b4e63`, upstream/main `9fcebfd7`; `frontend`
origin/main `e1016515`, upstream/main `57810c7d`. (Re-based from `1505af7e` on 2026-09-12 when task 2
started: Toman Phase C tasks 1-3 merged in between — see "Scale" below, which was rewritten as a
result.)
**Follow-up plan:** `2026-09-12-cabinet-c2c-receipt-review.md` (admin review of the receipts this
plan starts producing from the cabinet). Execute that one after this plan's PRs are merged — it is
also the mandatory admin-parity check for this plan.

## Goal

A user tops up entirely in the cabinet: the "شارژ موجودی" button on the balance screen offers three
methods — Telegram Stars, CryptoBot and card-to-card — and card-to-card gets its own page that shows
the card to transfer to and takes the receipt (image + optional text), then shows "در انتظار بررسی"
until the owner decides. B2C and partners alike; the bot's own user-side C2C flow is left untouched
and keeps working in parallel.

## Design

**Stars and CryptoBot need no code.** Their full Toman path (fixed-rate quote, payload carrying the
Toman to credit, cabinet endpoints, webhook/manual-check crediting) already exists in
`app/utils/toman_rates.py`, `app/cabinet/routes/balance.py` (`/balance/stars-invoice`, the
`cryptobot` branch of `/balance/topup`) and the frontend (`TopUpAmount.tsx` `starsPaymentMutation`).
`TELEGRAM_STARS_ENABLED` and `CRYPTOBOT_ENABLED` are already `true` in `remnabot/.env`. Two things
block them: the fixed Toman rates are unset (`toman_rates.is_stars_toman_ready()` /
`is_cryptobot_toman_ready()` return False → `payment_method_config_service._get_method_defaults()`
reports `is_configured=False` → the method is filtered out of `/balance/payment-methods`), and the
`payment_method_configs` rows for both are `is_enabled=false`. Task 1 sets both, at the user's
explicit instruction (2026-09-12) and with placeholder rates they chose.

**Card-to-card is missing from the cabinet entirely.** The `c2c` row exists in
`payment_method_configs` (`sort_order=25`, `is_enabled=true`) but `c2c` is absent from
`_get_method_defaults()` and `DEFAULT_METHOD_ORDER`, so `get_enabled_methods_for_user()` skips it and
no cabinet surface knows the method. The whole plugin (`app/plugins/c2c/`) is bot-only today.

Cabinet C2C flow, on one dedicated page:
1. user picks «کارت به کارت» in the method list → `/balance/top-up/c2c`;
2. enters the amount (same quick-amount / limit UI as other methods) → `POST /cabinet/balance/c2c/session`
   assigns the next card from the existing Redis rotation and creates/updates the user's single
   pending `C2cReceipt`;
3. the page shows card number + holder + label + the exact amount, with copy buttons and
   `C2C_GUIDE_TEXT`;
4. the user uploads the receipt image (and may add a text note) → `POST /cabinet/balance/c2c/receipt`
   forwards it to the admin supergroup exactly as the bot does, via the unchanged
   `C2cPaymentService.submit_receipt`;
5. the page switches to a pending state that polls `GET /cabinet/balance/c2c/current` and also reacts
   to the existing `balance.topup` websocket event, so an approval lands as a live toast and balance
   bump without a reload. Rejection arrives on the next poll (and, for Telegram users, as the bot
   message the plugin already sends).

**Receipt storage reuses the ticket-attachment pipeline** (`POST /cabinet/media/upload` →
`bot.send_photo` to the staging chat → `file_id`, staging message deleted). So a cabinet receipt is a
Telegram `file_id` exactly like a bot receipt: the admin group post, the bot inbox and (next plan) the
cabinet admin page all read the same field, and nothing new has to store user images on disk.

**Scale — settled by Phase C, not by this plan (rewritten 2026-09-12).** When this plan was
written the backend still had two scales and task 2 was going to add a converting pair of helpers at
the plugin boundary. Toman Phase C tasks 1-3 (remnabot #61, #63, #64, #65, revisions 0113-0115) merged
before task 2 started and removed that premise: **the database and all backend logic are now Toman
1:1**, which is the scale C2C was already on (`C2C_MIN_AMOUNT_KOPEKS=100000` means 100,000 Toman,
`C2cReceipt.amount_kopeks` is Toman, `approve_receipt` credits it 1:1). So the plugin needs **no
conversion helpers at all** — adding them would reintroduce a 100x bug and trip the Phase C guard
`tests/utils/test_phase_c_single_scale.py::test_no_amount_is_scaled_by_100_outside_the_wire_boundary`.

The only ×100 left is the **HTTP contract**, because the cabinet frontend still divides by 100 and
still multiplies what it sends. It lives in `app/utils/wire_scale.py` (`wire_catalog_kopeks` outbound,
`toman_from_wire_catalog` inbound), the module Phase C-2 will delete. C2C therefore behaves exactly
like Stars and CryptoBot: the service layer speaks Toman, the route converts at the edge, and every
C2C response still carries both `amount_kopeks` (wire scale, consistent with the other top-up
responses) and `amount_toman` (1:1, what the frontend formats). Phase C itself stays out of scope
here.

**Error cases:** C2C disabled or no cards configured → the method is simply absent from the list, and
the endpoints answer 400 `CABINET_TOPUP_METHOD_UNAVAILABLE`; amount outside the C2C limits → 400 with
the Toman limit in the message; a pending receipt that already carries a receipt → the session
endpoint returns it as-is instead of creating a second one (the plugin allows one pending receipt per
user, and the bot relies on that); receipt TTL expiry keeps being handled by the existing
`expire_stale_c2c_receipts` sweep; admin chat unreachable → 502 and the receipt stays pending without
a receipt attached, so the user can retry.

**Out of scope:** the bot's user-side C2C handlers (the user asked for them to stay untouched — the
bot is a link shell now), automatic receipt verification (the plugin keeps the seam for it), the admin
review UI (next plan), and any change to the other 20+ gateways.

## Vs. upstream

- **Ours, must survive an upstream merge:** the whole `app/plugins/c2c/` package (fork-only), the
  Toman rate module `app/utils/toman_rates.py`, and the new cabinet adapter. Work stays inside the
  plugin plus two named integration points — one `c2c` entry in
  `payment_method_config_service._get_method_defaults()` / `DEFAULT_METHOD_ORDER`, and one
  `/balance/c2c/*` route group in `app/cabinet/routes/balance.py` that only delegates. No edit to a
  hot file (`app/handlers/balance/main.py`, `inline.py`, `texts.py`, `purchase.py`, `start.py`,
  `bot.py`) is required by this plan.
- **Upstream infra reused as-is, do not reimplement:** `PaymentMethodConfig` + its admin UI, the
  cabinet media upload/download endpoints and their signed-token scheme
  (`app/cabinet/routes/media.py`), `get_enabled_methods_for_user()`, the cabinet websocket
  (`notify_user_balance_topup` via `_send_payment_success_notification`), and
  `C2cPaymentService.submit_receipt` / `approve_receipt` / `finalize_approved_topup` — all called,
  none rewritten.
- **No deferred gateway is re-enabled or depended on.** YooKassa, Platega, Lava, CisPay,
  CloudPayments, Nalogo, Wata, ParityPay, TabPay stay disabled; their rows and code are not touched.

## Tasks

### Task 1 — Turn Stars and CryptoBot on, verify both end to end (config only, no commit) — **DONE 2026-09-12**

**Repo + files:** `remnabot/.env` (live, not in git) and the cabinet admin UI. No source change, so no
test file; the deliverable is verified behavior.

The user instructed (2026-09-12) to use placeholder rates and to enable the methods, which overrides
the standing "the user flips these personally" rule for this task only:

- `TELEGRAM_STARS_TOMAN_PER_STAR=10000`
- `CRYPTOBOT_TOMAN_PER_USDT=20000`

Both keys are absent from `.env` today; append them, then `docker compose restart` the bot
(`remnawave_bot` loads `.env` via `env_file`). Alternatively set them in the cabinet admin settings
(they are editable there — `system_settings_service` writes them and applies them in-process) — but
`.env` wins over the DB, so pick one place, not both.

Then enable the two `payment_method_configs` rows from the admin UI (`/admin/payment-methods` →
`telegram_stars`, `cryptobot` → enabled). Do not enable any other row.

**Interfaces:** none. Limits follow from the rates: Stars 10,000–100,000,000 Toman
(1..10,000 ⭐), CryptoBot 20,000–20,000,000 Toman (1..1,000 USDT).

**Test:** `run-cabinet` as a test user — both methods appear in `/balance/top-up`; the Stars page
produces an invoice link that opens in Telegram; the CryptoBot page produces an invoice URL; the
amounts shown are Toman with Latin digits. Record what each screen renders.

**Persian/i18n:** none (both names come from `TELEGRAM_STARS_DISPLAY_NAME` / `CRYPTOBOT_DISPLAY_NAME`;
if either renders Russian or a raw key on the cabinet screen, fix that key in `fa.json` + `en.json`).

**Note for the PR body and the user:** 10000 / 20000 are placeholders for testing. Real rates must be
set before this reaches production; they are one admin-settings edit, no deploy.

**Done 2026-09-12.** Both rates were written as `system_settings` rows (not `.env`, so the owner can
still change them from the cabinet admin settings), the `telegram_stars` and `cryptobot`
`payment_method_configs` rows were enabled, and the bot was restarted. Verified in the live cabinet as
test user 7830: `/balance/top-up` renders «Telegram Stars — 10,000 – 100,000,000 تومان» and «CryptoBot
— 20,000 – 20,000,000 تومان», Persian text with Latin digits, no raw keys. Card-to-card is absent, as
expected until task 2. (The 500 in that page's console is the pre-existing missing-table error tracked
by `2026-09-10-missing-upstream-tables.md`, unrelated.)

### Task 2 — `c2c` becomes a known cabinet payment method

**Repo + files:**
- `remnabot/app/services/payment_method_config_service.py` — add a `'c2c'` entry to
  `_get_method_defaults()`: `default_display_name=settings.get_c2c_display_name()`,
  `is_configured=settings.is_c2c_enabled()` (already `C2C_ENABLED and get_c2c_cards()`),
  `default_min=settings.C2C_MIN_AMOUNT_KOPEKS`, `default_max=settings.C2C_MAX_AMOUNT_KOPEKS`
  — **used as they are, no conversion**: since Phase C every `default_min`/`default_max` in this
  mapping is Toman 1:1 and `/cabinet/balance/payment-methods` puts them on the wire scale itself via
  `wire_catalog_kopeks`. `available_sub_options=None`. Insert `'c2c'` at the **front** of
  `DEFAULT_METHOD_ORDER` — card-to-card is the primary method and must be the first entry users see
  (user ruling, 2026-09-12). Code order only decides a fresh install; on this server the live row was
  already moved to `sort_order=0` on 2026-09-12 (every other row shifted up by one), so no admin step
  is needed here — just assert the order in the smoke checklist.
- Test: `remnabot/tests/cabinet/test_balance_payment_methods_c2c.py`.

**Interfaces produced (used by tasks 3-5):** none new in the plugin — the scale boundary is
`app/utils/wire_scale.py`, which already exists. `/cabinet/balance/payment-methods` gains an entry
`{"id": "c2c", "name": "کارت به کارت 💳", "min_amount_kopeks": 10000000, "max_amount_kopeks": 1000000000,
"sort_order": 0, …}` whenever C2C is configured, and it sorts ahead of Telegram Stars and CryptoBot.
(10000000 / 1000000000 are the live limits 100,000 and 10,000,000 Toman on the wire scale.)

**Test (write first):** `get_enabled_methods_for_user` includes `c2c` with the **Toman** limits when
`C2C_ENABLED=true` and cards are configured, and excludes it when `C2C_CARDS=[]`; the route serialises
those limits ×100; `DEFAULT_METHOD_ORDER[0] == 'c2c'`.

**Persian/i18n:** none in the bot (the name comes from `C2C_DISPLAY_NAME`); the cabinet-side
description key comes in task 4.

### Task 3 — Cabinet C2C endpoints (adapter in the plugin, thin routes in `balance.py`)

**Repo + files:**
- `remnabot/app/plugins/c2c/cabinet.py` (new — the cabinet adapter; the bot adapter stays in
  `handlers/user.py`, and both sit on the same service, which is the seam a future auto-verifier
  plugs into).
- `remnabot/app/cabinet/routes/balance.py` — four routes that only validate auth/amount and delegate.
- `remnabot/app/cabinet/schemas/balance.py` — the four response/request models.
- `remnabot/locales/fa.json` + `remnabot/app/localization/locales/fa.json` (byte-identical) and the
  other four baked locales for the new `CABINET_C2C_*` error keys.
- Tests: `remnabot/tests/cabinet/test_balance_c2c_routes.py`,
  `remnabot/tests/plugins/c2c/test_cabinet_adapter.py`.

**Interfaces consumed:** `app.utils.wire_scale.toman_from_wire_catalog` /
`wire_catalog_kopeks` for the request and response amounts (no plugin-local scale helper — see
"Scale" above); existing `crud.get_pending_receipt_for_user`,
`crud.create_pending_receipt`, `config_helpers.get_next_card`, `get_card_by_index`,
`C2cPaymentService.submit_receipt`, `media.make_media_token`, `bot_factory.create_bot`.

**Interfaces produced (consumed by tasks 4-5 and by the admin plan):**
```
POST /cabinet/balance/c2c/session   {amount_kopeks}                    -> C2cSessionResponse
POST /cabinet/balance/c2c/receipt   {receipt_id, media_file_id?, media_type?, text?} -> C2cReceiptStateResponse
GET  /cabinet/balance/c2c/current                                      -> C2cReceiptStateResponse | 204
POST /cabinet/balance/c2c/cancel    {receipt_id}                       -> C2cReceiptStateResponse

C2cSessionResponse:      receipt_id:int, status:str, amount_kopeks:int, amount_toman:int,
                         card_label:str, card_number:str, card_holder:str|None,
                         guide_text:str, expires_at:datetime|None
C2cReceiptStateResponse: receipt_id:int, status:str ("pending"|"approved"|"rejected"|"expired"|"cancelled"),
                         has_receipt:bool, amount_kopeks:int, amount_toman:int,
                         approved_amount_toman:int|None, rejection_reason:str|None,
                         card_label:str|None, created_at:datetime, expires_at:datetime|None,
                         processed_at:datetime|None
```
Adapter functions: `start_cabinet_receipt(db, user, amount_kopeks) -> C2cReceipt`,
`attach_cabinet_receipt(db, user, receipt_id, *, media_file_id, media_type, text) -> tuple[bool, str]`,
`current_cabinet_receipt(db, user) -> C2cReceipt | None`,
`cancel_cabinet_receipt(db, user, receipt_id) -> C2cReceipt`.

Rules the adapter must implement (all mirror the bot's `process_c2c_payment_amount`, do not invent new
ones): one pending receipt per user — if it has no receipt attached yet, update its amount and card
instead of creating a second; if it already carries a receipt, return it unchanged and let the caller
answer 409; `receipt_type` is `photo`/`document` when a `media_file_id` is given (text, if any, goes to
`receipt_text` and is shown in the admin caption) and `text` when only text is given; reject an empty
submission; refuse when `restriction_topup` is set on the user (reuse `_check_topup_allowed`); the
`create_bot()` instance is closed in a `finally`, as `media.py` does.

**Test (write first):** amount 100,000 Toman entered in the cabinet (i.e. `amount_kopeks=10_000_000`)
stores `C2cReceipt.amount_kopeks == 100_000`; below `C2C_MIN_AMOUNT_KOPEKS` → 400 naming the Toman
minimum; a second session while a receipt-less pending exists updates it and does not insert a row; a
session while a submitted pending exists returns 409; submit with a `media_file_id` calls
`submit_receipt` once with `receipt_type='photo'` and flips the state to "in review"; `current` returns
204 when the user has nothing pending; cancel only cancels a receipt-less pending one.

**Persian/i18n:** new keys in all five baked locales + the runtime `fa.json`:
`CABINET_C2C_METHOD_UNAVAILABLE`, `CABINET_C2C_AMOUNT_TOO_LOW`, `CABINET_C2C_AMOUNT_TOO_HIGH`,
`CABINET_C2C_RECEIPT_ALREADY_SUBMITTED`, `CABINET_C2C_RECEIPT_EMPTY`, `CABINET_C2C_ADMIN_UNREACHABLE`.
Persian wording must read naturally (not a mirror of the English), Latin digits only.

### Task 4 — Frontend: the dedicated card-to-card page

**Repo + files:**
- `frontend/src/api/balance.ts` — `c2cStartSession`, `c2cSubmitReceipt`, `c2cGetCurrent`, `c2cCancel`;
  types in `frontend/src/types` (`C2cSession`, `C2cReceiptState`).
- `frontend/src/pages/TopUpC2C.tsx` (new).
- `frontend/src/App.tsx` — lazy import plus a `/balance/top-up/c2c` route registered **before**
  `/balance/top-up/:methodId`, otherwise `TopUpAmount` swallows it.
- `frontend/src/locales/fa.json` + `en.json`.
- Test: `frontend/src/pages/topUpC2c.test.tsx`.

**Interfaces consumed:** the four endpoints from task 3; the `['payment-methods']` react-query key for
the `c2c` limits and quick amounts; `ticketsApi.uploadMedia(file, 'photo')` for the upload (same
`/cabinet/media/upload` endpoint, 10 MB / JPEG-PNG-GIF-WebP limits already enforced server-side);
`copyToClipboard`, `useCurrency`/`formatBalance`, `useCloseOnSuccessNotification`.

Page states: **amount** (quick amounts + free input, validated against the method's limits) →
**card** (label, number with a copy button, holder, exact amount with a copy button, `guide_text`,
countdown to `expires_at`) → **upload** (image picker with preview, optional text field, submit) →
**pending** ("رسید شما ثبت شد و در انتظار بررسی است", receipt number, amount, a cancel affordance only
while nothing is attached, a 15 s poll of `/c2c/current`). On `status === 'approved'` show success and
navigate to `/balance`; on `'rejected'` show the reason and offer a retry that starts a new session.
A pending receipt found on mount jumps straight to the right state.

**Test (write first, logic only):** the state machine picks the right step from a given
`C2cReceiptState`; amount validation maps the method's `min/max_amount_kopeks` to Toman messages;
submit sends `media_file_id` + text together. Visuals — verify live with `run-cabinet`.

**Persian/i18n:** `balance.c2c.*` (title, steps, card labels, copy confirmations, upload hints, pending
and rejected wording, errors) and `balance.paymentMethods.c2c.description` in **both** `fa.json` and
`en.json`; Latin digits in the Persian strings.

### Task 5 — Frontend: balance screen entry and pending banner

**Repo + files:** `frontend/src/pages/Balance.tsx`, `frontend/src/locales/fa.json` + `en.json`,
test `frontend/src/pages/balanceC2cBanner.test.tsx`.

**Interfaces consumed:** `balanceApi.c2cGetCurrent` (task 3/4).

The existing method grid already routes `c2c` to `/balance/top-up/c2c` once task 2 makes the method
visible — no change needed there. What this task adds: a banner at the top of the balance screen when
the user has a pending C2C receipt ("رسید کارت به کارت شما در انتظار بررسی است — شماره #{id}, {amount}")
that links back to the page, and which disappears on approval/rejection.

**Test (write first):** the banner renders only for `status === 'pending'` with a receipt attached, and
the amount is formatted from `amount_toman`.

**Persian/i18n:** `balance.c2c.pendingBanner*` in `fa.json` + `en.json`.

## Cross-repo contract

`remnabot` ships first and purely additively: a new `c2c` entry in the payment-method catalog and the
four `/cabinet/balance/c2c/*` endpoints. No existing endpoint, field or scale changes, so the current
frontend keeps working against the new bot (it will simply show one more method whose page does not
exist yet until the frontend PR lands — merge the bot PR, then the frontend PR, same day). Field names
and types the frontend depends on are frozen in task 3's interface block; if any of them changes during
implementation, grep `frontend/src/api/balance.ts` before merging.

## Smoke test

Generate with `smoke-test-checklist` after implementation (cabinet-only, user screens plus the owner
steps for enabling the two methods and reordering the method list). The admin-parity check for this
plan is the follow-up plan `2026-09-12-cabinet-c2c-receipt-review.md`: until it ships, a receipt
submitted from the cabinet is still decided from the Telegram admin group.
