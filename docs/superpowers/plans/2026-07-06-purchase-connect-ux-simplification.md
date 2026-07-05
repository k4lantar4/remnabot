# Purchase & Connect UX Simplification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. One concern per commit. Agent smoke after each commit; staging deploy at end of sprint.

**Goal:** Reduce beginner/partner drop-off from purchase to first connection — without new subsystems, without touching upstream hot paths beyond thin wiring.

**Architecture:** Reuse existing connect helpers (`get_display_subscription_link`, `build_miniapp_subscription_connect_keyboard`, cart/autopurchase). Add a **two-step connect chooser** (self vs share-for-customer). Inline subscription link on purchase success. Align C2C/autopurchase copy with “service delivered”. All user strings via `fa.json` + `texts.t()`.

**Tech stack:** aiogram handlers, Redis cart/intent, C2C plugin, existing RemnaWave link utils.

**Branch:** `fix/purchase-connect-ux` from `main`

---

## Out of scope (no tech debt)

| Do NOT | Why |
|--------|-----|
| Refactor `purchase.py` / merge with `tariff_purchase` | Upstream merge risk |
| Remove `simple_subscription` handlers | Dead path OK; env/doc only |
| New plugin or parallel payment flow | C2C + autopurchase already exist |
| Auto-purchase without `topup_intent` guard | Accidental charge on generic topup |
| FX / provider webhook changes | Currency layer 3 |
| Cabinet Connection page rewrite | Bot-first sprint; cabinet unchanged unless parity key added later |
| Per-tariff vmess/vless extraction | Separate P2; not this plan |
| Force `AUTO_PURCHASE` without env verify | Ops confirms `.env` first |

---

## Ops preflight (no code — Task 0)

- [ ] Confirm runtime: `AUTO_PURCHASE_AFTER_TOPUP_ENABLED=true` (`.env.example` yes; code default `False`).
- [ ] Confirm `TARIFF_PURCHASE_HIDE_PRICES=false` in prod/staging (audit doc currently `True` — hides prices in list; high abandon risk). **Separate ops change**, not mixed with handler commits.
- [ ] Staging smoke baseline on `@mrj7_bot` before first commit (record in `docs/templates/smoke-map.md`).

---

## File map

| File | Role |
|------|------|
| `app/handlers/subscription/links.py` | Connect chooser + self/share screens |
| `app/handlers/subscription/my_subscriptions.py` | `sl:` delegation unchanged; chooser lives in `links.py` |
| `app/handlers/subscription/tariff_purchase.py` | Success message + keyboard entry |
| `app/services/subscription_auto_purchase_service.py` | Post-C2C autopurchase user message keyboard |
| `app/services/payment/common.py` | Conditional topup success copy when cart intent |
| `app/plugins/c2c/service.py` | Optional: suppress duplicate topup notify if autopurchase succeeded in same turn |
| `app/localization/locales/fa.json` | All new/changed user strings |
| `tests/handlers/test_connect_chooser.py` | Static/callback routing guards (new) |
| `tests/services/test_autopurchase_connect_keyboard.py` | Keyboard parity guard (new, small) |

**No new modules** unless `links.py` exceeds ~80 lines added — then extract **one** helper `app/handlers/subscription/connect_ui.py` (keyboard builders only), imported by `links.py` + `tariff_purchase.py` + `subscription_auto_purchase_service.py`. Prefer inline in `links.py` first.

---

## Callback contract (stable, minimal)

| Callback | Action |
|----------|--------|
| `sl:{sub_id}` | **Chooser** — two buttons only |
| `sl_self:{sub_id}` | Self: WebApp install guide only (single primary button) |
| `sl_share:{sub_id}` | Partner/customer: `<code>link</code>` + forward template text |
| `sm:{sub_id}` | Back to subscription detail (existing) |

Register in `purchase.py` router: `F.data.startswith('sl_self:')`, `F.data.startswith('sl_share:')` — or single handler with prefix parse in `links.py` (prefer **one handler** `handle_subscription_link` extended in `my_subscriptions.py` to route `sl_self`/`sl_share`).

---

## Phase 1 — Connect chooser (partner + end-user)

### Commit 1 — `fa.json` keys only

**Files:** `app/localization/locales/fa.json`

Add keys (Persian, Latin digits, no Cyrillic):

| Key | Purpose |
|-----|---------|
| `CONNECT_CHOOSER_TITLE` | 2-line: «چطور وصل می‌شوید؟» |
| `CONNECT_CHOOSER_BTN_SELF` | `📱 راهنمای نصب (خودم)` |
| `CONNECT_CHOOSER_BTN_SHARE` | `📋 لینk برای مشتری / فروش` |
| `CONNECT_SHARE_TITLE` | «لینk سرویس — برای فرستادن به مشتری» |
| `CONNECT_SHARE_LINK_BLOCK` | `<code>{link}</code>` wrapper line |
| `CONNECT_SHARE_NOT_BOT_HINT` | یک خط: «این آدرس ربات/کانال شما **نیست** — لینk VPN است» |
| `CONNECT_SHARE_FORWARD_TEMPLATE` | متن آماده forward (با `{link}`) |
| `CONNECT_SELF_TITLE` | «راهنمای نصب داخل تلگرام» — ۱ خط |

Shorten (replace long bodies):

- `SUBSCRIPTION_CONNECT_MINIAPP_MESSAGE` → ۱–۲ خط (remove dual-path essay)
- `POST_PURCHASE_ONBOARDING` → «دکمهٔ دریافت لینk → خودم یا برای مشتری»
- `MY_SUB_DETAIL_ONBOARDING` → همان ۲ خط chooser hint (no miniapp vs panel essay)

Rename button labels (values only):

- `SUBSCRIPTION_CONNECT_BTN_MINIAPP_GUIDE` → `📱 راهنمای نصب (داخل تلگرام)`
- `SUBSCRIPTION_CONNECT_BTN_PANEL_DIRECT` → hidden on chooser screens; only on share screen as optional `🔗 تست لینk در مرورگر` if needed

**Audit:** `rg '[А-Яа-я]' app/localization/locales/fa.json` on changed keys = 0.

---

### Commit 2 — `links.py` chooser flow

**Files:** `app/handlers/subscription/links.py`, `app/handlers/subscription/my_subscriptions.py` (router if needed)

**Behavior:**

1. `handle_connect_subscription` when data is `sl:{id}` (after sub resolve): **edit to chooser** — no link, no dual buttons.
2. `sl_self:{id}`: call existing `build_miniapp_subscription_connect_keyboard` but **only cabinet guide row** (hide panel URL row on self path). Message = `CONNECT_SELF_TITLE`.
3. `sl_share:{id}`: message = title + `CONNECT_SHARE_LINK_BLOCK` + hint + forward template. Keyboard: `[🔗 تست در مرورگر url=link]` (optional) + `[BACK → sm:{id}]`.
4. Multi-sub picker (`subscription_connect` with >1 sub): unchanged → still picks sub → then chooser.

**Reuse:** `get_display_subscription_link`, `build_miniapp_subscription_connect_keyboard` — trim rows in self path via param `include_panel_url: bool = False` (single optional arg; default True for backward compat elsewhere).

**Audit:**

- `make smoke`
- Manual: `@mrj7_bot` → اشتراک من → دریافت لینk → chooser → each branch

---

## Phase 2 — Purchase success delivers link

### Commit 3 — `tariff_purchase.py` success body

**Files:** `app/handlers/subscription/tariff_purchase.py`, `fa.json` if `TARIFF_PURCHASE_SUCCESS` shortened

**Behavior:**

- After successful purchase (all sites calling `_with_post_purchase_onboarding` + `_tariff_purchase_success_keyboard`):
  - Append **one line** when link exists: `CONNECT_SHARE_LINK_BLOCK` or dedicated `TARIFF_PURCHASE_SUCCESS_LINK` with `<code>{link}</code>`.
  - Remove stacked `POST_PURCHASE_ONBOARDING` when link present **or** replace with 1-line chooser hint (Commit 1 keys).
- Success keyboard: primary button text → `CONNECT_CHOOSER_BTN_SELF` or keep `MY_SUB_BTN_CONNECT_LINK` pointing to `sl:{id}` (chooser entry).

**Do not** duplicate link in both body and onboarding.

**Audit:** grep success paths still call same helpers (`rg '_tariff_purchase_success_keyboard' app/handlers/subscription/tariff_purchase.py`).

---

### Commit 4 — Autopurchase keyboard parity

**Files:** `app/services/subscription_auto_purchase_service.py`

**Behavior:**

- Replace inline keyboard in user notify block (~3214–3253) with same entry as purchase success: button → `sl:{subscription.id}` or import shared builder from `links.py` if extracted.
- Message: use shortened `AUTO_PURCHASE_SUBSCRIPTION_SUCCESS` + optional link line (fa.json Commit 1).

**Audit:** `tests/services/test_subscription_auto_purchase_service.py` — extend or add test asserting keyboard contains `sl:` callback when subscription id known.

---

## Phase 3 — C2C / topup messaging

### Commit 5 — Conditional topup copy

**Files:** `app/services/payment/common.py`, `fa.json`

Add keys:

- `PAYMENT_TOPUP_SUCCESS_WITH_CART` — «پرداخت تأیید شد — در حال فعال‌سازی سرویس…» (not “only balance”)
- `C2C_RECEIPT_SUBMITTED_WITH_CART` — «رسید ثبت شد — پس از تأیید، **سرویس** فعال می‌شود»

**Behavior in `_send_payment_success_notification`:**

- If `await user_cart_service.has_topup_intent(user.id)` → use `PAYMENT_TOPUP_SUCCESS_WITH_CART`.
- Else keep `PAYMENT_TOPUP_SUCCESS`.

**Behavior in C2C receipt submit** (`plugins/c2c/handlers/user.py`): if cart exists → `C2C_RECEIPT_SUBMITTED_WITH_CART`.

**Audit:** existing C2C tests still pass; add unit test for message key selection (mock `has_topup_intent`).

---

### Commit 6 — Suppress double notification (optional, small)

**Files:** `app/plugins/c2c/service.py`, `app/services/payment/common.py`

**Behavior:**

- In `finalize_approved_topup`: call `send_cart_notification_after_topup` **first**; if returns autopurchase success (change return type to `bool` or check side channel), **skip** `_send_payment_success_notification` OR send merged single message key `PAYMENT_SERVICE_DELIVERED_SUCCESS` (fa.json).

**Risk control:** only skip generic topup when autopurchase **succeeded**; on failure still send topup + `return_to_saved_cart` keyboard (existing).

**Audit:** `tests/plugins/c2c/test_c2c_finalize_topup_notify.py` — update for merged path.

---

## Phase 4 — Tests & guards

### Commit 7 — Static tests

**Files:** `tests/handlers/test_connect_chooser.py`

- [ ] New fa keys exist in fa.json
- [ ] `SUBSCRIPTION_CONNECT_MINIAPP_MESSAGE` fa value ≤ N chars / no «مینی‌اپ» + «لینk مستقیم پنل» both in same string
- [ ] Callback prefixes `sl_self:`, `sl_share:` registered (import router or grep guard)

**Files:** optional `tests/localization/test_purchase_connect_fa.py`

- [ ] `CONNECT_SHARE_NOT_BOT_HINT` present
- [ ] No Cyrillic in new keys

**Run:** `uv run pytest tests/handlers/test_connect_chooser.py tests/plugins/c2c/ -q`

---

## Phase 5 — Deploy & user smoke

- [ ] `cp app/localization/locales/fa.json ./locales/fa.json`
- [ ] `make staging-rebuild && make staging-health`
- [ ] Update `docs/templates/smoke-map.md` — section **Purchase-Connect UX Jul 2026**

### User smoke checklist (`@mrj7_bot`)

| # | Path | Pass |
|---|------|------|
| 1 | Buy service (balance) → success shows copyable link + chooser button | |
| 2 | اشتراک من → دریافت لینk → chooser (2 buttons only) | |
| 3 | «خودم» → only WebApp guide, no panel URL button | |
| 4 | «مشتری» → link in `<code>`, forward template, NOT bot URL | |
| 5 | C2C from insufficient checkout → receipt text mentions service | |
| 6 | C2C approve → one clear message (not balance-only + separate if autopurchase ok) | |
| 7 | Partner rep: can copy link from share screen without reading detail onboarding | |

---

## Commit sequence summary

| # | Scope | Message example |
|---|--------|-----------------|
| 1 | fa.json connect + shorten copy | `i18n(fa): connect chooser keys and shorten connect onboarding` |
| 2 | links.py chooser | `fix(connect): self vs share chooser for subscription link` |
| 3 | tariff_purchase success link | `fix(purchase): inline subscription link on tariff success` |
| 4 | autopurchase keyboard | `fix(autopurchase): connect chooser keyboard after C2C topup` |
| 5 | topup conditional copy | `fix(payment): cart-aware topup and C2C receipt messages` |
| 6 | merge C2C notify (optional) | `fix(c2c): single user message when autopurchase succeeds` |
| 7 | tests | `test: connect chooser and purchase-connect fa guards` |

---

## Rollback

- One commit revert per slice.
- Env `TARIFF_PURCHASE_HIDE_PRICES` independent — revert via `.env` only.

---

## Success metrics (informal)

- Support tickets «لینk نیومد / کدوم لینk» down after 1 week prod smoke.
- Partner can complete share flow in ≤3 taps from «اشتراک من».

---

## Related docs

- Prior UX audit: conversation Jul 2026 (Phase A/B)
- `docs/ops/env-subscription-keys-audit.md` — hide prices, autopurchase flags
- `.cursor/rules/localization-upstream.mdc` — one handler + fa.json per commit
- `.cursor/rules/telegram-callback-ux.mdc` — `callback.answer()` early in new handlers
