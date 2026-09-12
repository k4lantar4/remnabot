# Card-to-card receipt review in the cabinet admin

**Status:** active
**Repos:** `remnabot` first (tasks 1-2, additive API + one additive migration), then `frontend`
(tasks 3-4).
**Upstream basis:** `remnabot` origin/main `1505af7e`, upstream/main `9fcebfd7`; `frontend`
origin/main `e1016515`, upstream/main `57810c7d`.
**Order:** execute after `2026-09-12-cabinet-topup-three-methods.md` has merged in both repos — this
plan is also that plan's mandatory admin-parity deliverable (workspace `CLAUDE.md` → Admin parity).

## Goal

The owner — and any other admin the owner has granted the payments permission — reviews card-to-card
receipts in the cabinet instead of the Telegram admin group: a
dedicated admin-menu item lists every receipt with status filters (در انتظار / تأیید شده / رد شده /
منقضی / لغو شده), full-text search over the user and the receipt, and a detail view showing the
receipt image and the user's details, with approve (optionally for a different amount) and reject
(with a reason) — at least everything the bot can do today. Searching and re-reading already-decided
receipts is a first-class part of the screen, not an afterthought.

## Design

Receipts already live in one table (`c2c_receipts`) that both channels read, so the cabinet is a
second front end over the same rows and the same `C2cPaymentService`. Nothing about the bot flow
changes: a receipt submitted from the bot or the cabinet can be decided from either side, and
whichever side decides it, the Telegram group post is rewritten to its resolved form so no admin taps
a stale button.

Read side: one new router `/cabinet/admin/c2c-receipts` behind `payments:read`. List = status filter +
search + date range + pagination, ordered newest first; the search matches receipt id, user id,
telegram id, username, full name, email, and an exact amount. Stats give per-status counts so the
filter chips can show numbers. Detail adds the receipt image as a signed, expiring media URL minted
with the existing `make_media_token` (the same primitive ticket attachments use), the user block
(identity + current balance) and the decision trail.

Write side: `POST .../approve` (optional different amount) and `POST .../reject` (reason code from the
existing catalog, optional free-text comment) behind `payments:edit`, which routes through
`require_permission` and therefore writes an audit-log entry per action.

**Access is by permission, not by ownership** (user ruling, 2026-09-12): any admin holding
`payments:read` sees the screen and any admin holding `payments:edit` can approve or reject — not only
the owner. Both permissions already exist in `PermissionService.PERMISSION_REGISTRY`
(`'payments': ['read', 'edit', 'export']`) and the preset `Admin` role already carries `payments:*`,
so this plan adds no permission, no role and no widening: granting someone review rights is the owner
assigning an existing role (or a custom role with `payments:edit`) in `/admin/roles`. The audit log
records who decided each receipt, and the list screen shows it — which is what makes delegating safe.

Both endpoints delegate to the unchanged `C2cPaymentService.approve_receipt` / `reject_receipt` —
the credit, the idempotency guard on `external_id='c2c:<id>'`, the referral/cart/notification
side-effects in `finalize_approved_topup`, and the user's rejection message all stay exactly as they
are. The only refactor is mechanical: `_resolved_receipt_message` and `sync_c2c_group_admin_message`
move out of `handlers/admin.py` into a channel-agnostic `app/plugins/c2c/decision.py` so the cabinet
can produce the same resolved group post. The bot keeps importing them from there; behavior is
identical.

**Who decided it.** `C2cReceipt` only records `reviewed_by_telegram_id`, which is empty for an
email-only admin. One additive migration adds `reviewed_by_user_id` (nullable FK to `users.id`) and
`reviewed_via` (`'bot' | 'cabinet'`, nullable) so the list can name the reviewer and the channel.
Existing rows stay valid with both columns NULL; nothing reads them as required.

**Scale.** Receipt amounts are Toman 1:1; the API sends `amount_toman` (display) alongside
`amount_kopeks` (×100, for symmetry with the other cabinet payment responses) and the approve request
takes `amount_kopeks` on the cabinet scale, converted at the same single boundary the user-side plan
introduced (`config_helpers.receipt_toman_from_cabinet_amount`). No dual-scale logic is added
anywhere else; Phase C stays out of scope.

**Error cases:** a receipt decided by the other channel between load and click → 409 carrying the
current status, and the UI refreshes instead of pretending; receipt not found → 404; an approve amount
outside the C2C limits → 400; an unknown reject reason code → 400; the Telegram group edit failing
(post deleted, chat changed) is logged and never fails the decision — the money movement is already
committed at that point.

**Out of scope:** automatic receipt verification (the service seam stays ready for it), bulk
approve/reject, editing a decided receipt, and any change to the bot's admin inbox.

## Vs. upstream

- **Ours, must survive an upstream merge:** everything here — `app/plugins/c2c/**`, the new admin
  router, the new migration, and the frontend screens. The plugin pattern is respected: new code lands
  in the plugin plus one new route module registered in `app/cabinet/routes/__init__.py`; no hot file
  (`app/handlers/**`, `inline.py`, `texts.py`, `bot.py`) is edited.
- **Upstream infra reused as-is:** `require_permission` + `PermissionService` audit logging, the
  cabinet media download endpoint and its signed tokens, the admin nav/permission plumbing in
  `AdminPanel.tsx`, and the pagination/search UI conventions of `AdminPayments.tsx`. The existing
  `payment_search_service` is **not** extended — it searches gateway payment tables, and receipts are
  a different table with a different lifecycle.
- **No deferred gateway is re-enabled or depended on.**

## Tasks

### Task 1 — Backend: list, search and detail endpoints

**Repo + files:**
- `remnabot/app/plugins/c2c/crud.py` — `search_receipts(...)`, `count_receipts(...)`,
  `receipt_status_counts(db, **filters)`.
- `remnabot/app/cabinet/routes/admin_c2c_receipts.py` (new router, prefix `/admin/c2c-receipts`).
- `remnabot/app/cabinet/schemas/c2c_receipts.py` (new).
- `remnabot/app/cabinet/routes/__init__.py` — import + `include_router`, next to `admin_payments_router`.
- Test: `remnabot/tests/cabinet/test_admin_c2c_receipts_list.py`.

**Interfaces consumed:** `C2cReceipt` / `C2cReceiptStatus`, `media.make_media_token`,
`config_helpers.cabinet_amount_from_receipt_toman` and `get_card_by_index`,
`require_permission('payments:read')`.

**Interfaces produced (consumed by tasks 2-4):**
```
GET /cabinet/admin/c2c-receipts?status=&search=&date_from=&date_to=&page=&per_page=
    -> {items: [C2cReceiptAdminItem], total, page, per_page, pages}
GET /cabinet/admin/c2c-receipts/stats?search=&date_from=&date_to=
    -> {total, pending, approved, rejected, expired, cancelled}
GET /cabinet/admin/c2c-receipts/{receipt_id} -> C2cReceiptAdminDetail

C2cReceiptAdminItem:   id, status, amount_kopeks, amount_toman, approved_amount_toman|None,
                       card_label|None, receipt_type|None, has_receipt:bool,
                       created_at, processed_at|None, expires_at|None,
                       user: {id, telegram_id|None, username|None, full_name|None, email|None},
                       reviewer: {user_id|None, telegram_id|None, label|None, via|None},
                       rejection_reason_key|None, rejection_reason|None
C2cReceiptAdminDetail: C2cReceiptAdminItem + receipt_media_url|None, receipt_text|None,
                       transaction_id|None, user_balance_toman:int, card_number_masked|None
```
`status` accepts `all|pending|approved|rejected|expired|cancelled`. `search` is matched against:
receipt id (bare digits or `#123`), `users.id`, `users.telegram_id`, `users.username`,
`users.first_name`/`last_name`, `users.email` (case-insensitive `ilike`), and an exact Toman amount.
`card_number_masked` shows only the last four digits — the full PAN is configuration, not receipt data,
and has no business on this screen.

**Test (write first):** a pending, an approved and a rejected row are returned by their respective
filters and all by `all`; search by username, by telegram id and by `#<id>` each find the right row;
`stats` counts match the filtered set; the detail response carries a `receipt_media_url` whose token
verifies, and `None` when the receipt is text-only; `payments:read` is required (403 without it), and an admin holding only `payments:read` is refused by
the approve/reject routes (403) while still reading the list.

**Persian/i18n:** none (this task returns data, not prose; status labels are rendered in the frontend).

### Task 2 — Backend: approve and reject from the cabinet

**Repo + files:**
- `remnabot/migrations/alembic/versions/0114_c2c_receipt_reviewer.py` (new, additive and idempotent:
  `reviewed_by_user_id INTEGER NULL REFERENCES users(id)`, `reviewed_via VARCHAR(16) NULL`).
- `remnabot/app/database/models.py` — the two columns on `C2cReceipt`.
- `remnabot/app/plugins/c2c/decision.py` (new) — `resolved_receipt_message(db, receipt, admin_label, *,
  include_inbox_back=False)` and `sync_group_admin_message(bot, receipt, *, status_html, reply_markup,
  skip_message_id=None)`, moved verbatim from `handlers/admin.py`.
- `remnabot/app/plugins/c2c/handlers/admin.py` — import from `decision.py`, delete the local copies.
- `remnabot/app/plugins/c2c/service.py` — `approve_receipt` / `reject_receipt` gain optional
  `reviewed_by_user_id: int | None = None` and `reviewed_via: str = 'bot'` keyword arguments that are
  only persisted; no other change.
- `remnabot/app/cabinet/routes/admin_c2c_receipts.py` — the two POST routes.
- Tests: `remnabot/tests/cabinet/test_admin_c2c_receipts_actions.py`,
  `remnabot/tests/plugins/c2c/test_decision_module_shared.py`.

**Interfaces consumed:** `C2cPaymentService.approve_receipt` / `reject_receipt`,
`reject_reasons.get_reject_reason_codes()`, `decision.resolved_receipt_message` /
`sync_group_admin_message`, `bot_factory.create_bot`, `require_permission('payments:edit')`,
`config_helpers.receipt_toman_from_cabinet_amount`.

**Interfaces produced (consumed by task 4):**
```
POST /cabinet/admin/c2c-receipts/{receipt_id}/approve  {amount_kopeks?: int}      -> C2cReceiptAdminDetail
POST /cabinet/admin/c2c-receipts/{receipt_id}/reject    {reason_key: str, comment?: str} -> C2cReceiptAdminDetail
GET  /cabinet/admin/c2c-receipts/reject-reasons          -> [{code, label}]   # labels from the fa/en catalog
```
`amount_kopeks` omitted means "credit the requested amount". `reason_key` must be one of
`amt_mismatch | unclear | wrong_card | duplicate | expired | silent`; `silent` rejects without
notifying the user, exactly as in the bot. A receipt that is no longer `pending` answers 409 with
`{detail, status}`. After a successful decision the route rewrites the Telegram group post via
`sync_group_admin_message`, failures logged and swallowed. The admin label recorded is the admin's
username or `str(user.id)`, and `reviewed_via='cabinet'`.

**Test (write first):** approving credits the user's balance by the receipt's Toman amount and writes
one `deposit` transaction with `external_id='c2c:<id>'`; approving with a different `amount_kopeks`
credits the converted Toman and stores `approved_amount_kopeks`; approving twice is idempotent and the
second call answers 409; rejecting with `amt_mismatch` stores the reason key and leaves the balance
untouched; rejecting with `silent` sends no user message; an unknown reason code is 400; the
`decision.py` move keeps the bot's approve/reject path byte-identical in behavior (the existing
`tests/plugins/c2c/test_c2c_group_message_sync.py` must stay green unmodified).

**Persian/i18n:** the reject-reason labels already exist as `C2C_REJECT_REASON_*` /
`C2C_ADMIN_REJECT_BTN_*` in the locales and are reused; add only the new API error strings
(`CABINET_C2C_ADMIN_ALREADY_PROCESSED`, `CABINET_C2C_ADMIN_BAD_REASON`,
`CABINET_C2C_ADMIN_AMOUNT_OUT_OF_RANGE`) to all five baked locales plus the runtime `locales/fa.json`.

### Task 3 — Frontend: admin menu item and the receipts list screen

**Repo + files:**
- `frontend/src/api/adminC2cReceipts.ts` (new) — `list`, `stats`, `get`, `approve`, `reject`,
  `rejectReasons`; types in the same module (the admin API modules keep their own types).
- `frontend/src/pages/AdminC2cReceipts.tsx` (new).
- `frontend/src/pages/AdminPanel.tsx` — a nav item in the `analytics` section right after
  `admin.nav.payments`: `{name: 'admin.nav.c2cReceipts', icon: 'file-text', to: '/admin/c2c-receipts',
  permission: 'payments:read'}`.
- `frontend/src/App.tsx` — lazy route `/admin/c2c-receipts` (and `/admin/c2c-receipts/:receiptId` for
  task 4) inside the admin guard used by the other admin routes.
- `frontend/src/locales/fa.json` + `en.json`.
- Test: `frontend/src/pages/adminC2cReceipts.test.tsx`.

**Interfaces consumed:** task 1's three GET endpoints.

The screen follows `AdminPayments.tsx`: a debounced (300 ms) search box with a hint listing what can be
searched, status chips carrying the counts from `/stats`, a period preset + custom range, a paginated
list showing receipt `#id`, user (username / telegram id / email), amount in Toman, card label, status
badge, created and processed dates, and the reviewer. A row opens the detail (task 4). Auto-refresh
only while the filters are at their defaults, as that page does.

**Test (write first):** filter and search state map to the expected query params; the row renders
`amount_toman` with the Toman formatter (never `amount_kopeks`); an empty result renders the empty
state rather than a spinner. Visuals — verify live with `run-cabinet` as the owner.

**Persian/i18n:** `admin.nav.c2cReceipts` and `admin.c2cReceipts.*` (title, filters, status labels,
search hint, table headers, empty state) in **both** `fa.json` and `en.json`, Latin digits.

### Task 4 — Frontend: receipt detail with approve and reject

**Repo + files:** `frontend/src/pages/AdminC2cReceiptDetail.tsx` (new),
`frontend/src/locales/fa.json` + `en.json`, test
`frontend/src/pages/adminC2cReceiptDetail.test.tsx`.

**Interfaces consumed:** `GET /{id}`, `POST /{id}/approve`, `POST /{id}/reject`, `GET /reject-reasons`
(task 2).

The page shows the receipt image (from `receipt_media_url`, opening full-size on click), the receipt
text if any, the amount, the card label and masked number, the user block with the current balance,
and the decision trail. Actions, enabled only while `status === 'pending'` **and** the signed-in admin
holds `payments:edit` (an admin with only `payments:read` sees the screen read-only): «تأیید» (credits the
requested amount), «تأیید با مبلغ دیگر» (an amount field pre-filled with the requested amount,
validated against the method limits), and «رد» (a reason picker fed by `/reject-reasons`, plus an
optional comment). A 409 refetches and shows who decided it and when. After a decision the list query
is invalidated so the counts update.

**Test (write first):** the approve mutation sends no `amount_kopeks` unless the custom amount was
used; the reject mutation sends the selected `reason_key`; action buttons are disabled for a decided
receipt. Visuals — verify live with `run-cabinet` as the owner, including a real approval whose
balance change the test user's cabinet receives over the websocket.

**Persian/i18n:** `admin.c2cReceipts.detail.*` and the reason labels in `fa.json` + `en.json`.

## Cross-repo contract

`remnabot` ships first: a new router and one additive migration, no change to an existing endpoint,
field or scale, so the current frontend is unaffected. The response shapes in tasks 1-2 are the
contract; if any field name changes during implementation, grep `frontend/src/api/adminC2cReceipts.ts`
before merging. Merge the bot PR, then the frontend PR.

## Smoke test

Generate with `smoke-test-checklist` after implementation — cabinet-only, owner screens (plus one step
checking that an admin with `payments:read` only gets a read-only view) plus the
user-visible consequence of a decision (balance, toast, and the bot's rejection message for a Telegram
user). Since this plan *is* the admin-parity check for the user-side plan, `fix-admin` runs once at the
end over both.
