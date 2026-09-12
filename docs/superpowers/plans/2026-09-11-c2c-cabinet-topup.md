# C2C (card-to-card) wallet top-up in the cabinet — Implementation Plan

- **Status:** approved 2026-09-12 (design rulings folded in below); implementation not started.
- **Repos:** `remnabot` first (Tasks 1-4, additive API), then `frontend` (Tasks 5-7). One PR per repo, linked.
- **Upstream basis:** remnabot `origin/main` d83ded23 (upstream `main` 9fcebfd7 = v4.10.0, merge-base 89fa7dc5);
  frontend `origin/main` 91009e94 (upstream merge-base 5ade78f5).
- **Rebase required before Task 1:** the branch was cut at d83ded23; `origin/main` has since moved to
  97b1e469 (grace-access migration `0113`, Toman Phase C catalog-scale migration `0114`, remnabot#63).
  Rebase onto `origin/main` first, then re-check `alembic heads` — this plan's migration is renumbered to
  **`0115`** because 0113 and 0114 are both taken. The Phase C session has confirmed it will take 0116+
  and will not reuse 0115 even if 0114 is reverted, so this number is final — do not renumber again.
- **Phase C coupling — do not restart the bot container:** as of 2026-09-12 `origin/main` is not
  restart-safe (revision `0114` divides catalog prices by 100 while the reading code is only adapted in
  Phase C Task 3, which is unwritten). Another session is moving that data step into a later revision.
  Until it reports the all-clear: do not pull `/opt/project/remnabot` to `main` and do not restart or
  rebuild the bot container. This plan needs neither — C2C amounts ride the balance scale (Toman 1:1),
  which Phase C does not touch.
- **Branches/worktrees:** remnabot `feat/c2c-cabinet-topup` (`.claude/worktrees/c2c-cabinet-topup`),
  frontend `feat/c2c-cabinet-topup` (create it when Task 5 starts).

## Goal

A cabinet user (B2C and partners alike) opens **Balance → Top up → Card to card**, types an amount, sees
which card to pay, then sends the receipt as an **image or text** (chosen at send time) and follows its
review status. The owner reviews the receipt in a new cabinet admin page, reachable by direct URL
(`/admin/c2c-receipts/:id`, linked from the Telegram admin post), or keeps using the Telegram buttons as
today. Stars and CryptoBot keep their existing cabinet flows (see Design → out of scope).

## Design

**Today.** C2C lives only in the bot (`app/plugins/c2c/`): table `c2c_receipts`, one pending receipt per
user (partial unique index), card rotation from env `C2C_CARDS`, receipts posted to the admin group with
approve / custom-amount / reject-reason buttons, and crediting as `DEPOSIT` + `PaymentMethod.C2C` with
external id `c2c:{id}` (idempotent). The flow logic is embedded in aiogram handlers
(`handlers/user.py` `process_c2c_payment_amount`), and `C2cPaymentService` requires a Telegram reviewer id.
The cabinet has no C2C endpoint, and `_get_method_defaults()` has no `c2c` entry, so the existing DB row
`payment_method_configs.c2c` (enabled, sort 25) is filtered out as "not configured".

**Shape: one channel-agnostic C2C core, thin channel adapters.** All inside the plugin:

```
app/plugins/c2c/
  flow.py          NEW  start_topup(): every check + receipt create/reuse, returns result or C2cFlowError
  review.py        NEW  ReviewActor + approve/reject entry used by bot buttons, cabinet admin, later auto-verify
  admin_sync.py    NEW  (moved from handlers/admin.py) resolved-message builder + group-post sync
  verification.py  NEW  ReceiptVerifier protocol + registry; default = manual only (seam for auto-verify)
  service.py       submit_receipt accepts a file_id OR uploaded bytes; reviewer may be a cabinet user
  cabinet/         NEW  schemas.py, user_routes.py, admin_routes.py, deps.py (owner guard)
  handlers/        unchanged behaviour; call flow.py / review.py instead of inline logic
```

- **Data model (migration `0115_c2c_receipt_source_reviewer`):** add `c2c_receipts.source` (`'bot' |
  'cabinet'`, NOT NULL, server default `'bot'`) and `reviewed_by_user_id` (FK `users.id`, nullable). The
  `reviewed_by_telegram_id` column stays and is filled when the actor has one. `amount_kopeks` keeps its
  name (it already holds Toman 1:1). No change to any upstream table.
- **User flow (cabinet):** `POST /cabinet/c2c/receipts {amount_toman}` → `flow.start_topup` (restriction,
  enabled, admin chat, reviewable-pending → 409, min/max, `get_next_card()`, lazy expiry, reuse the
  awaiting-receipt row or create one) → the response carries the card (label, number, holder), amount,
  `expires_at`. **Re-starting while a receipt is still awaiting its image (user ruling 2026-09-12):** the
  existing row is reused, its `amount_kopeks` and `expires_at` are updated to the new request, and the
  **card already shown to the user is kept** (`card_index` / `card_label` unchanged, no rotation) — the
  user must never be told to pay one card and then be shown another mid-flow. `get_next_card()` rotation
  happens only when a genuinely new row is created. A receipt that already carries a submitted receipt is
  not reusable and yields 409 `c2c.review_pending` instead.
  The user copies the card number, pays, then `POST /cabinet/c2c/receipts/{id}/submit`
  (multipart: `receipt_type=photo` + `file`, or `receipt_type=text` + `text`). The server sends the
  **bytes straight to the admin group** (confirmed by the user 2026-09-12: Telegram is the only store for
  the image — we keep no copy of our own, accepting that a submit fails with 502 `c2c.notify_failed` if
  Telegram is unreachable and that deleting the admin-group message loses the image for disputes)
  (no `/media/upload` staging, so the user never supplies a
  `file_id`) and stores the `file_id` Telegram returns, so the cabinet admin can show the image through
  the existing signed `/cabinet/media/{file_id}?token=` proxy. The status is read from
  `GET /cabinet/c2c/receipts/current` (polled) plus the existing `balance.topup` websocket event.
- **Review (both channels):** `review.approve(db, receipt_id, actor, amount_toman=None)` /
  `review.reject(db, receipt_id, actor, reason_key)` wrap the existing service calls, then run the same
  side effects for every channel: sync the Telegram group post (resolved state + reviewer label), Telegram
  message to the user (existing), plus a websocket event (`balance.topup` via the existing success path on
  approval; a new `c2c.receipt_rejected` on rejection). Row lock + `c2c:{id}` external id already make a
  simultaneous Telegram and cabinet approval safe; the loser gets "already processed" → HTTP 409.
- **Review access (user ruling 2026-09-12):** the admin API uses a new dependency `require_c2c_reviewer`,
  which passes for `is_user_admin_by_env(user)` (ADMIN_IDS / ADMIN_EMAILS — the workspace "Superadmin")
  **or** for any user holding the existing RBAC permission `payments:edit`. Rationale: such a user can
  already approve and reject the same receipt with the Telegram admin-group buttons, so restricting the
  cabinet would make it strictly less capable than Telegram for the same person. No new RBAC permission is
  defined and no role's permission set changes — `payments:edit` is reused as-is. The frontend page sits
  behind that same `payments:edit` permission, so the guard matches on both sides; the 403 code stays
  `c2c.owner_only` for anyone without it. Every review records its actor (`reviewed_by_user_id`, plus
  `reviewed_by_telegram_id` when the actor has one), so a non-owner reviewer is always attributable.
- **Direct link:** every admin-group receipt post gets a URL button «باز کردن در پنل» →
  `{CABINET_URL}/admin/c2c-receipts/{id}` when `CABINET_URL` is configured (it is:
  `https://panel.rookari.com`). The Telegram buttons keep working.
- **Methods list:** add `c2c` to `_get_method_defaults()` (`is_configured = settings.is_c2c_enabled() and
  bool(settings.get_c2c_admin_chat_id())`, name `settings.get_c2c_display_name()`, limits = C2C Toman
  limits put on the method-list ×100 scale like Stars/CryptoBot) and at the **front** of
  `DEFAULT_METHOD_ORDER` (affects fresh DBs only; this DB's row keeps sort 25, which the owner changes in
  the existing admin payment-methods page). No row is flipped by code.
- **Auto-verification seam:** `verification.py` defines `ReceiptVerifier.verify(receipt) ->
  VerificationVerdict(decision='approve'|'reject'|'manual', amount_toman=None, reason_key=None)` and a
  registry; `submit` runs the registered verifiers after the admin post and, on a non-manual verdict,
  calls `review.approve/reject` with `ReviewActor(kind='auto', label=<verifier name>)`. Today the registry
  is empty → always manual. A future SMS/bank-API verifier is a new module that registers itself; nothing
  else changes.
- **Currency:** the new C2C API speaks **Toman 1:1** (`amount_toman`, `min_toman`, …) — Phase C direction,
  no ×100 anywhere in it. The only ×100 value is the methods-list entry, which follows the existing
  convention of that endpoint (F-012) and is only used by the Balance grid label; the C2C page reads its
  limits from `/cabinet/c2c/config`. `_BALANCE_SCALE_TRANSACTION_TYPES` is untouched (C2C credits
  `deposit`, already there — still present and still in use on `origin/main` at
  `app/utils/price_display.py:40`, consumed by `crud/transaction.py` and `handlers/balance/main.py`).
  Phase C Task 1 (remnabot#61, merged) added `app/utils/amount_columns.py` alongside it — a
  classification of money *columns* guarded by `tests/utils/test_amount_columns.py`, which reflects
  `Base.metadata` and fails on any unclassified column matching `looks_like_money_column`. Both C2C money
  columns are already classified there as **Toman 1:1** (`TOMAN_SCALE_COLUMNS`: `c2c_receipts.amount_kopeks`,
  `c2c_receipts.approved_amount_kopeks`), independently confirming this plan's scale assumption. The two
  columns migration 0115 adds (`source`, `reviewed_by_user_id`) are not money columns, so the guard does
  not apply — but read `amount_columns.py` rather than the older list when in doubt after the rebase.
- **Wire scale / F-012 (confirmed by the Phase C session 2026-09-12):** Phase C deliberately *freezes* the
  HTTP contract — its Task 4 funnels the remaining ×100 into one serializer (`wire_scale.py`) so responses
  keep their present shape and the cabinet needs no change. Collapsing the wire scale is a separate later
  plan ("C-2"), which subsumes F-012. So the methods-list entry here must follow the endpoint's existing
  ×100 convention, as planned: matching its neighbours is correct, and pre-empting a scale that is not
  being changed yet would leave an inconsistent value to migrate.
- **Errors:** API errors return `{"detail": {"code": "c2c.<code>", "message": <en fallback>}}`; the
  frontend localizes by code. Codes: `c2c.unavailable` (503), `c2c.restricted` (403, + reason),
  `c2c.review_pending` (409), `c2c.amount_too_low` / `c2c.amount_too_high` (400, + min/max),
  `c2c.not_found` (404), `c2c.not_awaiting_receipt` (409), `c2c.bad_file` (400), `c2c.empty_text` (400),
  `c2c.already_processed` (409), `c2c.owner_only` (403), `c2c.notify_failed` (502),
  `c2c.use_dedicated_flow` (400, from `/cabinet/balance/topup` when `payment_method='c2c'`).
- **Out of scope:** building the auto-verifier itself; PDF/document receipts from the cabinet (the bot
  still accepts them, and the admin page displays them); managing cards in the cabinet (they stay in env
  `C2C_CARDS`); the legacy miniapp (`app/webapi/routes/miniapp.py`); Stars and CryptoBot — their cabinet
  flows already exist (`/balance/stars-invoice` + `openInvoice`, `/balance/topup` → CryptoBot link) and
  appear in the same method grid once the user enables them (currently blocked, see the chat hand-off);
  F-012 (the generic ×100 form) — C2C bypasses it through its own route.

## Vs. upstream

- **Ours (must survive merges):** everything C2C — all new code lives in `app/plugins/c2c/**` (bot) and
  `src/**/c2c*` / `src/pages/*C2c*` (frontend), plus migration 0115.
- **Upstream touch points (named, minimal):** `app/cabinet/routes/__init__.py` (+2 `include_router`
  lines), `app/services/payment_method_config_service.py` (+1 defaults entry, +1 order entry),
  `app/cabinet/routes/balance.py` (`/topup` with `payment_method='c2c'` → 400 `c2c.use_dedicated_flow`
  instead of falling through); frontend `src/App.tsx` (+3 routes), `src/pages/AdminPanel.tsx` (+1 nav
  item), `src/constants/paymentMethods.ts` + `src/components/PaymentMethodIcon.tsx` (+1 entry each).
- **Reused as-is:** `/cabinet/media/{file_id}` signed proxy + `make_media_token`, the media upload
  validation constants in `app/cabinet/routes/media.py`, `notify_user_balance_topup` / websocket manager,
  `is_user_admin_by_env`, `get_enabled_methods_for_user` filters, `copyToClipboard`, `useCurrency`,
  `useCloseOnSuccessNotification`, the withdrawals admin list/detail pattern.
- **Deferred gateways:** none touched, none re-enabled or depended on.

## Tasks

### Task 1 — `flow.py`: channel-agnostic start of a C2C top-up (remnabot)

- **Files:** create `app/plugins/c2c/flow.py`; modify `app/plugins/c2c/handlers/user.py`
  (`process_c2c_payment_amount` delegates to `flow.start_topup`; start handler checks reuse
  `flow.check_can_start`). Test: `tests/plugins/c2c/test_flow.py`; existing `tests/plugins/c2c/*` must stay green.
- **Interfaces (produces):**
  - `class C2cFlowError(StrEnum)`: `UNAVAILABLE, RESTRICTED, REVIEW_PENDING, AMOUNT_TOO_LOW, AMOUNT_TOO_HIGH`.
  - `@dataclass C2cStartResult`: `receipt: C2cReceipt | None`, `card: dict | None`, `error: C2cFlowError | None`,
    `pending: C2cReceipt | None` (set with `REVIEW_PENDING`).
  - `async check_can_start(db, user) -> C2cFlowError | None` (restriction, enabled, admin chat, reviewable pending).
  - `async start_topup(db, user, amount_toman: int, *, source: str = 'bot') -> C2cStartResult` — flushes, does
    not commit; the caller commits.
  - `def c2c_limits_toman() -> tuple[int, int]` (from `C2C_MIN/MAX_AMOUNT_KOPEKS`, already Toman).
- **Concurrency:** one pending receipt per user is enforced by the partial unique index
  `uq_c2c_receipts_user_pending` (migration 0088), which is **not** declared in `C2cReceipt.__table_args__`
  — the ORM does not know about it. A simultaneous double-start therefore surfaces as a raw
  `IntegrityError` on flush, not as a failed read-then-write check. `start_topup` must catch that
  `IntegrityError`, roll back, re-read the now-committed row and return it (reuse path), or map it to 409
  `c2c.review_pending`; it must never escape as a 500. Task 2 also adds the index to `__table_args__` so
  the model matches the database.
- **Test first:** each error code; reuse of an awaiting-receipt row updates amount and expiry but **keeps
  the card**; a genuinely new row rotates the card; a new row gets `source`; `REVIEW_PENDING` when a
  reviewable receipt exists; a simulated `IntegrityError` on insert resolves to the reuse path, not a 500.
  Bot handler tests unchanged and green.
- **i18n:** none (bot texts unchanged).

### Task 2 — Model, submission with uploaded bytes, `review.py`, `admin_sync.py`, verifier seam (remnabot)

- **Files:** `app/database/models.py` (`C2cReceipt.source`, `reviewed_by_user_id`); create
  `migrations/alembic/versions/0115_c2c_receipt_source_reviewer.py` (down_revision = current head, check
  `alembic heads`); `app/plugins/c2c/service.py`; create `app/plugins/c2c/review.py`,
  `app/plugins/c2c/admin_sync.py` (move `sync_c2c_group_admin_message` + `_resolved_receipt_message` out of
  `handlers/admin.py`, which then imports them), `app/plugins/c2c/verification.py`;
  `app/plugins/c2c/keyboards.py` + `admin_messages.py` (cabinet URL button, «از پنل» source line);
  `app/cabinet/routes/websocket.py` (+`notify_user_c2c_receipt_rejected`). Tests:
  `tests/plugins/c2c/test_review.py`, `test_submit_upload.py`, `test_verification.py`, extend `test_keyboards*`.
- **Interfaces:**
  - `C2cPaymentService.submit_receipt(..., receipt_media: str | BufferedInputFile | None, ...)` — replaces
    `receipt_file_id`; returns `(ok, message, admin_message_id)` as today and stores the `file_id` taken from
    the admin message (`photo[-1].file_id` / `document.file_id`).
  - `approve_receipt(db, receipt_id, admin_telegram_id: int | None, *, reviewed_by_user_id: int | None = None,
    credited_amount_kopeks=None)`; `reject_receipt` gets the same.
  - `@dataclass(frozen=True) ReviewActor`: `kind: Literal['telegram','cabinet','auto']`, `label: str`,
    `telegram_id: int | None = None`, `user_id: int | None = None`.
  - `review.approve(db, bot, receipt_id, actor, *, amount_toman: int | None = None) -> ReviewOutcome` and
    `review.reject(db, bot, receipt_id, actor, *, reason_key: str) -> ReviewOutcome`;
    `ReviewOutcome(ok: bool, code: Literal['approved','rejected','already_processed','not_found','failed','out_of_range'], receipt)`.
    Both sync the group post via `admin_sync`; reject also calls the websocket notifier.
  - `verification.VerificationVerdict`, `ReceiptVerifier` (Protocol, `name: str`, `async verify(db, receipt)`),
    `register_verifier(v)`, `async run_verifiers(db, bot, receipt) -> VerificationVerdict` (empty registry → manual).
  - `keyboards.get_c2c_admin_review_keyboard(receipt_id, amount_label, *, cabinet_url: str | None)` — URL row
    `{cabinet_url}/admin/c2c-receipts/{id}` when set.
  - `notify_user_c2c_receipt_rejected(user_id, receipt_id, reason_key)` → ws `{'type': 'c2c.receipt_rejected', ...}`.
- **Test first:** an uploaded photo is sent as `BufferedInputFile` and the returned `file_id` is persisted;
  cabinet actor fills `reviewed_by_user_id` and leaves the telegram id null; `review.approve` twice →
  second `already_processed`, balance credited once; custom amount outside the limits → `out_of_range`;
  reject emits the ws event and respects `silent`; a registered fake verifier with `approve` credits via
  `ReviewActor(kind='auto')`; keyboard has the URL button only when `CABINET_URL` is set.
- **Migration check:** `alembic upgrade head` then `downgrade -1` on the dev DB.
- **i18n (bot, all five baked locales + runtime twins, byte-identical):** `C2C_ADMIN_OPEN_IN_CABINET_BTN`
  (fa «باز کردن در پنل»), `C2C_ADMIN_SOURCE_CABINET` (fa «ارسال از پنل وب»).

### Task 3 — Cabinet user API `/cabinet/c2c` (remnabot)

- **Files:** create `app/plugins/c2c/cabinet/__init__.py`, `schemas.py`, `user_routes.py`; modify
  `app/cabinet/routes/__init__.py` (include the router), `app/cabinet/routes/balance.py` (`/topup` c2c guard).
  Test: `tests/plugins/c2c/test_cabinet_user_routes.py`.
- **Interfaces (produces, consumed by Task 5):**
  - `GET /cabinet/c2c/config` → `{enabled: bool, min_toman: int, max_toman: int, receipt_ttl_hours: int,
    guide_text: str | null, max_file_mb: int}`.
  - `GET /cabinet/c2c/receipts/current` → `C2cReceiptOut | null` (pending only, after lazy expiry).
  - `GET /cabinet/c2c/receipts?limit=10` → `C2cReceiptOut[]` (the user's latest, any status).
  - `POST /cabinet/c2c/receipts` `{amount_toman: int}` → `C2cReceiptOut` (201).
  - `POST /cabinet/c2c/receipts/{id}/submit` multipart `receipt_type` (`photo`|`text`), `file?`, `text?` → `C2cReceiptOut`.
  - `C2cReceiptOut`: `id, status ('pending'|'approved'|'rejected'|'expired'|'cancelled'), stage
    ('awaiting_receipt'|'under_review'|null), amount_toman, approved_amount_toman|null, card {label, number,
    holder}|null (only while awaiting_receipt), receipt_type|null, rejection_reason_key|null, created_at,
    expires_at|null, processed_at|null`.
- **Rules:** file validation reuses `media.py` constants (image types jpeg/png/webp, size limit, blocked
  types); text trimmed, 1-2000 chars; submit on someone else's receipt → 404; the router returns 404 for all
  endpoints except `config` when C2C is unavailable; `source='cabinet'`.
- **Test first:** each endpoint's happy path and every error code from Design → Errors; no ×100 anywhere
  (amount 150000 in → `amount_kopeks == 150000` stored, credited 150000).
- **i18n:** none server-side (codes); the English `message` fallbacks are not user-facing in the cabinet.

### Task 4 — Cabinet admin API `/cabinet/admin/c2c` + methods-list entry (remnabot)

- **Files:** create `app/plugins/c2c/cabinet/deps.py`, `admin_routes.py`; modify
  `app/cabinet/routes/__init__.py`, `app/services/payment_method_config_service.py`. Tests:
  `tests/plugins/c2c/test_cabinet_admin_routes.py`, `tests/services/test_payment_method_c2c_entry.py`.
- **Interfaces (produces, consumed by Task 7):**
  - `require_c2c_reviewer` dependency → 403 `c2c.owner_only` for anyone who is neither
    `is_user_admin_by_env` nor a holder of RBAC `payments:edit`.
  - `GET /cabinet/admin/c2c/receipts?status=review|pending|approved|rejected|expired|cancelled|all&page=1&per_page=20`
    → `{items: C2cAdminReceiptListItem[], total, page, per_page, counts: {review, approved, rejected, expired, cancelled}}`
    (`review` = reviewable pending, the default).
  - `C2cAdminReceiptListItem`: `id, status, stage, source, amount_toman, approved_amount_toman, receipt_type,
    created_at, processed_at, user {id, telegram_id, username, full_name}`.
  - `GET /cabinet/admin/c2c/receipts/{id}` → list item + `receipt_text, receipt_media_url|null (signed),
    card_label, card_index, reviewer_label|null, rejection_reason_key, transaction_id, user_balance_toman,
    min_toman, max_toman`.
  - `POST /cabinet/admin/c2c/receipts/{id}/approve` `{amount_toman?: int}` and
    `POST …/{id}/reject` `{reason_key: 'amt_mismatch'|'unclear'|'wrong_card'|'duplicate'|'expired'|'silent'}`
    → the detail object; `already_processed` → 409, `out_of_range` → 400.
  - Methods list: `c2c` entry as in Design → Methods list.
- **Test first:** non-owner RBAC admin → 403; approve from the cabinet syncs the group post (bot mocked) and
  credits once; reject with an unknown key → 422; `c2c` shows in `get_enabled_methods_for_user` only when
  `is_c2c_enabled()` and an admin chat exist, limits = Toman ×100.
- **i18n:** none. **Then:** full suite + `ruff format --check . && ruff check .` in the worktree, PR, merge
  (bot before frontend).

### Task 5 — Frontend API clients + flow logic (frontend)

- **Files:** create `src/api/c2c.ts`, `src/api/adminC2c.ts`, `src/types/c2c.ts`, `src/utils/c2cFlow.ts`.
  Test: `src/utils/c2cFlow.test.ts`, `src/api/c2c.test.ts` (error-code mapping).
- **Interfaces (produces):** `c2cApi.{getConfig, getCurrent, getHistory, start(amountToman), submitPhoto(id, file),
  submitText(id, text)}`; `adminC2cApi.{list(params), get(id), approve(id, amountToman?), reject(id, reasonKey)}`;
  `c2cStep(current: C2cReceipt | null): 'amount' | 'pay' | 'review'`; `validateC2cAmount(raw: string,
  cfg) -> {ok: true, amountToman} | {ok: false, error: 'invalid'|'too_low'|'too_high'}` (accepts Persian/Arabic
  digits and thousands separators, integer Toman); `c2cErrorKey(err) -> i18n key` from `detail.code`.
- **Test first:** step selection for every status/stage; amount parsing (`'۱۵۰٬۰۰۰'` → 150000), bounds;
  error-code → key mapping with an unknown-code fallback. Never ×100.
- **i18n:** none in this task.

### Task 6 — User C2C top-up page + Balance integration (frontend)

- **Files:** create `src/pages/TopUpC2c.tsx`, `src/components/c2c/C2cAmountStep.tsx`, `C2cCardDetails.tsx`,
  `C2cReceiptForm.tsx`, `C2cReviewStatus.tsx`, `C2cPendingBanner.tsx`; modify `src/App.tsx`
  (`/balance/top-up/c2c` inside `ProtectedRoute` + `LazyPage`, declared before `:methodId`),
  `src/pages/Balance.tsx` (banner when `getCurrent` has a receipt under review),
  `src/constants/paymentMethods.ts`, `src/components/PaymentMethodIcon.tsx`, locales.
- **Behaviour:** step from `c2cStep`; amount step with quick amounts derived from `min/max_toman`; pay step
  shows card number (grouped 4×4, copy via `copyToClipboard`), holder, exact amount, time left, guide text;
  receipt form has a two-option toggle «تصویر رسید» / «متن رسید» — image picker with preview (jpeg/png/webp,
  `max_file_mb`) or textarea; review step polls `getCurrent` every 15 s, closes with the existing success
  modal on `balance.topup` (`useCloseOnSuccessNotification`), shows the localized reject reason with
  «تلاش دوباره» on rejection. Biome webview guards apply (no `window.open`/`alert`/`navigator.clipboard`).
- **Test:** visual — verify live on panel.rookari.com (logic is covered in Task 5).
- **i18n (en, fa, ru — ru may carry English; zh if `locales.test.ts` requires it):** `balance.paymentMethods.c2c.{name,description}`,
  `balance.c2c.*` (steps, labels, copy, toggle, errors per code, reject reasons, banner). Persian written
  idiomatically, Latin digits.

### Task 7 — Admin C2C receipts pages (frontend)

- **Files:** create `src/pages/AdminC2cReceipts.tsx`, `src/pages/AdminC2cReceiptDetail.tsx`; modify
  `src/App.tsx` (`/admin/c2c-receipts`, `/admin/c2c-receipts/:id`, both `PermissionRoute permission="payments:edit"`),
  `src/pages/AdminPanel.tsx` (nav item `admin.nav.c2cReceipts` in the payments group, `payments:edit`), locales.
- **Behaviour:** list with status tabs + counts (default «در انتظار بررسی»), rows → detail; detail shows the
  image (tap to enlarge) or text, user link to `/admin/users/:id`, amount, card label, source, timestamps;
  actions while under review: «تأیید», «تأیید با مبلغ دیگر» (number input within `min/max_toman`), «رد» with
  the reason list — which the API serves from `get_reject_reason_codes()` (`app/plugins/c2c/reject_reasons.py`)
  rather than the page hardcoding today's six, so the cabinet and the Telegram buttons cannot drift apart
  when a reason is added; 409 → refetch and show "already processed by …"; 403 `c2c.owner_only` → explanatory empty
  state. The list uses `AdminBackButton to="/admin"` (nav-coverage test). Pattern: `AdminWithdrawals*`.
- **Test:** `adminNavCoverage.test.ts` stays green; the rest is visual — verify live, including opening
  the Telegram post's link while logged out (log in, then land on the receipt).
- **i18n (en, fa, ru):** `admin.nav.c2cReceipts`, `admin.c2cReceipts.*`.
- **Then:** `npm run test`, `npm run type-check`, `npx biome check .` vs baseline; `fix-admin` parity check;
  `smoke-test-checklist`; PR; merge after the bot PR.

## Cross-repo contract

New endpoints only (Tasks 3-4); nothing existing changes shape except `/cabinet/balance/payment-methods`
gaining a `c2c` item (same `PaymentMethod` shape, ×100 limits as every other item) and `/topup` refusing
`c2c` with 400. The bot PR ships and merges first; an old frontend just shows a C2C tile that routes to
the generic form, which the new 400 turns into an error rather than a 100x-off request.

## Smoke test

Generate with `smoke-test-checklist` after Task 7 (cabinet only): user C2C with image, user C2C with text,
approve from the cabinet page, approve from Telegram → cabinet page shows resolved, custom-amount approval,
reject with reason, second receipt while one is under review, non-owner admin blocked.
