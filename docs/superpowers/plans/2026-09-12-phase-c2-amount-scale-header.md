# Toman Phase C-2 — retire the x100 cabinet wire scale behind an `X-Amount-Scale` header

**Status:** active — design approved by the user 2026-09-12 (option "scale header", chosen over
`*_toman` twin fields and over a one-shot flip). Task 1 done (PR #81, with this plan); next: Task 2.
**Repos:** `remnabot` Tasks 1-2 (merged and deployed first), then `frontend` Tasks 3-7, then Task 8
(`remnabot` PR, then `frontend` PR).
**Upstream basis:** remnabot `origin/main` `08194b09`, `upstream/main` `9fcebfd7`; frontend
`origin/main` `090e992f`, `upstream/main` `57810c7d` (2026-09-12).
**Kind:** architectural (cross-repo interface change, currency). Predecessor:
`plans/done/2026-09-11-toman-phase-c.md` (DB + backend on Toman 1:1; this is its "Phase C-2").
**Branching:** unlike the default one-branch-per-plan, **every task is its own branch and PR off
`main`** — the header makes each surface independently shippable, and one PR for ~150 frontend
sites would be unreviewable.

---

## Goal

The cabinet and its API speak one money unit: every amount on the wire is Toman 1:1, so the
cabinet's `÷100` / `×100` hops, `catalogScale.ts` and the `formatPrice`/`formatBalance` split
disappear, and "this field is on the other scale" stops being a possible bug on the frontend too.
B2C and partner screens alike. **No number a user or admin sees changes.**

## Design

### Where the x100 lives today (inventory 2026-09-12)

- **Backend:** 180 calls to `app/utils/wire_scale.py` (`wire_catalog_kopeks` out,
  `toman_from_wire_catalog` in): 150 in `app/cabinet/routes/**`, 21 in
  `app/services/subscription_purchase_service.py` and `payment_verification_service.py`, 9 in
  `app/webapi/routes/miniapp.py`. ≈68 cabinet endpoints, ≈111 response fields, 19 request fields.
  Pinned by `tests/utils/test_wire_scale.py`, `tests/cabinet/test_wire_scale_admin_editors.py`,
  `test_wire_scale_subscription.py`, `test_wire_scale_public_and_landing.py`,
  `test_admin_money_wire_scale.py`, `test_landing_payment_method_limit_scale.py`,
  `test_balance_payment_methods_c2c.py`.
- **Frontend:** `src/utils/catalogScale.ts` (20 call sites), `formatPrice` in `src/utils/format.ts`
  (divides by 100; ≈70 calls), 29 literal hops (`/ 100`, `* 100`, `CHART_COMMON.KOPEKS_DIVISOR`),
  ~8 local `formatAmount(kopeks / 100)` helpers, and `InsufficientBalancePrompt`'s default `÷100`.

### The approach

Field names stay (`*_kopeks` everywhere — renaming fights both upstreams). What changes is the
**unit**, negotiated per request:

1. **Request header `X-Amount-Scale: toman`.** A pure ASGI middleware on the web API app reads it
   into a `ContextVar` in `wire_scale.py`. When it is `toman`, `wire_catalog_kopeks` and
   `toman_from_wire_catalog` are the identity; when absent (or anything else) they keep today's x100.
   Because every x100 hop already goes through those two functions, **all 180 call sites switch at
   once without being edited**, and the miniapp and the Telegram bot (no header) are unaffected.
2. **Response header `X-Amount-Scale: toman | catalog_x100`** on every response, plus
   `Vary: X-Amount-Scale`. The cabinet checks it (below), so a mismatched pair — new cabinet, old
   bot — fails loudly instead of rendering 100x. This mirrors the Phase C startup guard.
3. **Cabinet opt-in per endpoint.** `frontend/src/api/amountScale.ts` holds an allowlist of API
   paths already converted; the `apiClient` request interceptor adds the header only for those, and
   the response interceptor rejects a listed path whose response does not echo `toman`
   (`AmountScaleMismatchError`, surfaced like a network error, never rendered). Each frontend task
   adds its paths and removes the `÷100`/`×100` of **every consumer of those responses** in the same
   PR.
4. **Retire (Task 8).** Once every cabinet money path is listed, the bot's default for cabinet routes
   becomes Toman and the header becomes a no-op; the contextvar path, `catalogScale.ts`,
   `formatPrice`'s division and the allowlist are deleted.

### Rules the tasks rely on

- **A path is converted with all its readers.** Before listing a path, grep `frontend/src` for
  every field its response returns; a screen that reads `GET /cabinet/subscription` (e.g.
  `daily_price_kopeks`) converts in the task that lists that path, even if its "home" is another
  group. This is the only way a frontend task can break a screen; the plan assigns shared paths
  explicitly (Tasks 4-5).
- **Inbound bounds are on the wire scale today.** `app/cabinet/schemas/balance.py:70`
  (`ge=1000`) and `:89` (`ge=100`) encode "10 rubles"/"1 ruble" in x100 units; under `toman` they
  would demand 1,000 / 100 Toman. Task 1 makes them scale-neutral (`ge=1`; the per-method min/max
  check in `routes/balance.py:259-261` already enforces the real limit). `ge=0` bounds are neutral.
- **Server-side caches must not store a wire-scaled body.** The only response cache in cabinet
  routes, `subscription_modules/traffic.py:811`, holds traffic usage from Remnawave and no amount
  (checked 2026-09-12), so nothing needs keying by scale. A new cache over a money response must
  include `current_wire_scale()` in its key until Task 8.
- **Not every `*_kopeks` field is x100.** `balance_kopeks`, `amount_rubles`, `*_toman`,
  `withdrawal_min_amount_kopeks`, `referrer_fixed_kopeks`, `balance_bonus_kopeks`, the websocket
  `amount_kopeks` are already Toman and never pass `wire_scale`; the header does not touch them and
  no task edits their readers except to delete a wrong fallback (Task 8).
- **Miniapp stays x100.** `app/webapi/routes/miniapp.py` serves a separate static Telegram WebApp
  that is in neither checkout; it sends no header, so nothing changes for it. Task 8 makes its 9
  call sites explicit (`miniapp_wire_kopeks`) instead of deleting them.

### Out of scope

Renaming fields; the `tomanOrLegacy` / `activityAmountToman` stats twins (already Toman, a separate
cleanup); the deferred Russian gateways' own ruble fields (`sbpInfo`, `lavaInfo` in
`Subscription.tsx` stay as they are); Stars/CryptoBot rates (F-050); wholesale pricing.

### Interaction with other plans

`2026-09-12-cabinet-c2c-receipt-review.md` (active, not started; see F-086) adds admin receipt
endpoints with an x100 `amount_kopeks` and names helpers that do not exist on `main`. If it runs
after Task 1, its endpoints must use `wire_scale` and its screen should be born on the allowlist; if
before, its paths join Task 3.

---

## Vs. upstream

- **Ours:** the Toman scale end to end — `wire_scale.py`, the middleware, `amountScale.ts`, and the
  removal of every `÷100`. Upstream (both repos) is a ruble product and keeps kopeks; field names
  stay theirs, so an upstream merge conflicts only on the *arithmetic* lines, and the Phase C AST
  guard (`tests/utils/test_phase_c_single_scale.py`) plus the frontend guard test of Task 8 catch a
  merged-in `/ 100`.
- **Reused as-is:** upstream's `apiClient` interceptors (one more header, like the CSRF one),
  FastAPI/Starlette middleware and CORS setup, every route and schema.
- **Gateways:** no deferred gateway is enabled, touched or depended on; `*_ENABLED` flags untouched.

---

## Tasks

### Task 1 — Scale header on the bot (remnabot)

- **Files:** `app/utils/wire_scale.py` (ContextVar `_WIRE_SCALE`, constants `AMOUNT_SCALE_HEADER =
  'X-Amount-Scale'`, `TOMAN_WIRE = 'toman'`, `CATALOG_WIRE = 'catalog_x100'`, `current_wire_scale()`,
  both helpers honour it); `app/webapi/middleware.py` (`AmountScaleMiddleware`, **pure ASGI**, not
  `BaseHTTPMiddleware`, so the contextvar is set in the request's own context; resets it after the
  response; sets response `X-Amount-Scale` + `Vary`); `app/webapi/app.py` (register it; add
  `X-Amount-Scale` to `allow_headers` in both CORS branches and `expose_headers`);
  `app/cabinet/schemas/balance.py:70, :89` (bounds → `ge=1`).
- **Produces:** header contract above; `current_wire_scale() -> Literal['toman', 'catalog_x100']`.
- **Test first:** `tests/utils/test_wire_scale.py` (identity under `toman`, x100 otherwise, reset);
  new `tests/webapi/test_amount_scale_header.py` — a real cabinet route (`GET
  /cabinet/balance/payment-methods`) returns Toman with the header and x100 without; an inbound
  request (`POST /cabinet/balance/c2c/session`) is read on the right scale both ways; the response
  echoes the scale; two interleaved requests with different headers don't leak into each other.
  Existing wire-scale suites stay green unchanged (they send no header).
- **i18n:** none.

### Task 2 — Pending payments carry Toman inside the bot (remnabot)

- **Files:** `app/services/payment_verification_service.py:539, :1160, :1545` (store Toman in
  `PendingPayment.amount_kopeks`); `app/cabinet/routes/balance.py:1506` and
  `app/cabinet/routes/admin_payments.py:311` (apply `wire_catalog_kopeks` to `amount_kopeks` at the
  route, `amount_rubles` = Toman); `app/handlers/admin/payments.py:346, :377, :802` (format Toman);
  `app/services/payment_search_service.py:299` (check its consumer).
- **Why:** the service is shared with the Telegram admin bot, which has no request and thus no
  header — the scale must be applied at the HTTP route only. Fixes **F-087** and **F-088** (delete
  both from `/opt/project/FINDINGS.md` in this PR).
- **Test first:** user and admin pending-payment responses (with and without header) and the bot
  handler's formatted line for a 50,000 Toman Stars deposit.
- **i18n:** none.

### Task 3 — Cabinet opt-in mechanism + top-up and payment methods (frontend)

- **Files:** new `src/api/amountScale.ts` (`TOMAN_SCALE_PATHS`, `isTomanScalePath(url)`,
  `AmountScaleMismatchError`); `src/api/client.ts` (request header + response check). Screens:
  `pages/TopUpAmount.tsx` (:306-307, :369-370, :380), `TopUpMethodSelect.tsx:87-88`,
  `Balance.tsx:358-359`, `TopUpResult.tsx:25`, `TopUpC2C.tsx:219-220`, `utils/c2cTopUp.ts:58-63`,
  `pages/AdminPaymentMethodEdit.tsx` (:264-332, :560, :572),
  `components/admin/SortableSelectedMethodCard.tsx:22, :26`, the admin payments list.
- **Paths listed:** `/cabinet/balance/payment-methods`, `/cabinet/balance/c2c/*`,
  `/cabinet/balance/stars-invoice`, `/cabinet/balance/topup`, `/cabinet/balance/pending-payments*`,
  `/cabinet/admin/payment-methods*`, `/cabinet/admin/payments*`.
- **Consumes:** Task 1 deployed (and Task 2 for the pending-payment paths).
- **Test first:** `src/api/amountScale.test.ts` (header only on listed paths; mismatch rejects);
  update `c2cTopUp.test.ts`, `sortableSelectedMethodCard.test.tsx`; new test for the top-up request
  amount (no `×100`). Screens: verify live with `run-cabinet` — same Toman numbers before/after.
- **i18n:** the mismatch error message — key in `en.json` and `fa.json` (natural Persian, e.g. «نسخه‌ی
  سرور با این صفحه هماهنگ نیست؛ صفحه را دوباره بارگذاری کنید»).

### Task 4 — Purchase, renewal and the subscription card (frontend)

- **Paths listed:** `/cabinet/subscription` (info; `daily_price_kopeks`), `/cabinet/subscription/
  purchase-options`, `/purchase-preview`, `/purchase`, `/purchase-tariff`, `/renewal-options`,
  `/trial`.
- **Files:** `components/subscription/purchase/TariffPurchaseForm.tsx`, `ClassicPurchaseWizard`,
  `TariffPickerGrid`, `QuickPurchase`, `pages/RenewSubscription.tsx`, `pages/Subscription.tsx`
  (:232 and its local formatter; not the SBP/Lava lines), `components/dashboard/TrialOfferCard.tsx`,
  `SubscriptionCardExpired.tsx`, `components/InsufficientBalancePrompt.tsx` (callers
  `Subscription.tsx:1716`, `ClassicPurchaseWizard.tsx:543`), `hooks/usePromoDiscount.ts:47, :54`,
  `utils/pricing.ts`; every other reader of these responses found by grep (`SwitchTariffSheet` reads
  `/subscription` too — convert its `daily_price` read here).
- **Test first:** `pricing.test.ts`, `dailyPrice.test.ts`, `bestValuePeriod.test.tsx`,
  `subscriptionCardExpiredRenew.test.tsx` move to Toman inputs; `usePromoDiscount` percent math on
  Toman. Visual: `run-cabinet` purchase, renewal and trial screens.
- **i18n:** none expected.

### Task 5 — Subscription add-ons, gift and the public landing (frontend)

- **Paths listed:** `/cabinet/subscription/devices/price`, `/devices/purchase`,
  `/traffic-packages`, `/countries`, `/tariff/switch/preview`, `/cabinet/gift/config`,
  `/cabinet/landing/*`, `/cabinet/wheel/history`.
- **Files:** `components/subscription/sheets/DeviceTopupSheet.tsx`, `TrafficTopupSheet.tsx` (its
  local `formatPrice` at :47), `ServerManagementSheet.tsx`, `SwitchTariffSheet.tsx` (+
  `InsufficientBalancePrompt` caller :246), `pages/GiftSubscription.tsx`, the public landing page, the
  wheel history view.
- **Test first:** a unit test per sheet price helper that remains; otherwise visual via
  `run-cabinet`.
- **i18n:** none expected.

### Task 6 — Admin catalog editors (frontend)

- **Paths listed:** `/cabinet/admin/tariffs*`, `/cabinet/admin/servers*`,
  `/cabinet/admin/remnawave/squads*`, `/cabinet/admin/users/*/available-tariffs`,
  `/cabinet/admin/users/*/gifts`, `/cabinet/admin/promo-groups*`, `/cabinet/admin/coupons*`.
- **Files:** `pages/AdminTariffCreate.tsx` (period prices, daily, device, traffic packages — read
  and save), `AdminTariffs.tsx:122`, `AdminServerEdit.tsx:215/221`, `AdminRemnawaveSquadDetail.tsx:156`,
  `components/admin/userDetail/GiftsTab.tsx:123`, `AdminPromoGroups.tsx:150`,
  `AdminPromoGroupCreate.tsx:54/124`, `AdminCouponCreate.tsx:79`, `AdminCouponDetail`, `AdminCoupons`,
  the admin buy-for-user tariff picker.
- **Test first:** `adminTariffFreePeriod.test.tsx` updated; new save round-trip test for
  `AdminTariffCreate` (typed 30000 → request `30000`). Visual: `run-cabinet` as owner.
- **i18n:** none expected.

### Task 7 — Admin wheel and landings (frontend)

- **Paths listed:** `/cabinet/admin/wheel/*`, `/cabinet/admin/landings*`.
- **Files:** `pages/AdminWheel.tsx` (9 helper calls, stats), `AdminLandingEditor.tsx` (:978 percent
  on Toman), `AdminLandingStats.tsx` (:183-260); delete `CHART_COMMON.KOPEKS_DIVISOR`
  (`constants/charts.ts:2`) and its dead re-exports in `constants/salesStats.ts:9`,
  `constants/partner.ts:10`.
- **Test first:** new `AdminWheel` prize save round-trip; visual `run-cabinet`.
- **i18n:** none expected.

### Task 8 — Retire the x100 (remnabot PR, then frontend PR)

- **remnabot:** `AmountScaleMiddleware` defaults cabinet paths to `toman` (header ignored);
  miniapp's 9 call sites and the shared `subscription_purchase_service` payloads used by miniapp get
  an explicit `miniapp_wire_kopeks` at `app/webapi/routes/miniapp.py`; delete the contextvar branch
  and the cabinet uses of `wire_catalog_kopeks` / `toman_from_wire_catalog` (call sites become plain
  values); the wire-scale suites assert Toman; `test_phase_c_single_scale.py` allows `* 100` only in
  the miniapp helper.
- **frontend:** delete `src/utils/catalogScale.ts` (+ test), make `formatPrice` an alias of
  `formatBalance` (or replace its calls), delete `amountScale.ts` and the interceptor hooks, drop the
  `amount_kopeks / 100` fallback in `WebSocketNotifications.tsx:306`; add
  `src/utils/noWireDivision.test.ts` — fails on a new `/ 100` or `* 100` next to a money name
  (percent math excluded), the frontend twin of the Phase C AST guard.
- **Order:** bot PR merged and deployed first (the cabinet still sends the header, now a no-op),
  then the frontend PR. Moves this plan to `plans/done/`.
- **i18n:** delete the Task 3 mismatch key from both locales.

---

## Cross-repo contract

| Step | Bot sends | Cabinet expects |
|---|---|---|
| Tasks 1-2 deployed | x100 without header, Toman with `X-Amount-Scale: toman`; echoes scale | unchanged (sends no header) |
| Tasks 3-7, each | same | listed paths: header + Toman + echo check; unlisted: x100 |
| Task 8 bot | Toman on all cabinet paths; echoes `toman` | all paths listed — no-op |
| Task 8 frontend | same | Toman everywhere, no header |

Every step is backward-compatible with the one before it; rollback of any frontend task is a plain
revert.

## Smoke test

Generate with `smoke-test-checklist` after each frontend task (what `run-cabinet` could not judge:
a real top-up, a real purchase charge, an admin save round-trip). Not now.
