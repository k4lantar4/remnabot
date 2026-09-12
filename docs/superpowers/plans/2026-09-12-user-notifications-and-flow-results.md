# User notifications and flow result messages — audit and fix plan

**Status:** active — **approved 2026-09-12, ready to execute** (no task started). All product
questions answered (see "Rulings"); start with task 8 (see "Execution order").
**Repos:** `remnabot` (tasks 1, 2, 3, 4, 6a, 6b, bot half of 7), then `frontend` (tasks 5, 5b,
frontend half of 7). Task 4 merges before task 5.
Each task is its own PR, mergeable on its own; follow "Execution order" (hard dependencies: 8 before
1-2, 4 before 5, bot PR before frontend PR in 7).
**Upstream basis:** `remnabot` origin/main `08194b09`, upstream/main `9fcebfd7`; `frontend`
origin/main `090e992f`.
**Audit:** notif-fixer, 2026-09-12, read-only (no sender called). Live env at audit time:
`SALES_MODE=tariffs`, `MULTI_TARIFF_ENABLED=true`, `MAIN_MENU_MODE=cabinet`, `ENABLE_NOTIFICATIONS=true`,
`AUTOPAY_WARNING_DAYS=3,1`, `TRIAL_WARNING_HOURS=2`, `REMNAWAVE_WEBHOOK_ENABLED=false`, `C2C_ENABLED`,
`TELEGRAM_STARS_ENABLED`, `CRYPTOBOT_ENABLED` on; no `system_settings` overrides for these keys;
11 users, all with Telegram (10 fa, 1 en), none email-only; two users hold 4+ active subscriptions.

## Goal

Every message a B2C user receives or sees at the end of a flow — Telegram notice from the bot,
cabinet result screen/modal, cabinet websocket toast, API error text — is in the user's language,
names the subscription it is about, shows Toman amounts on the right scale, and offers one working
next step that opens the cabinet. Partner-specific items are flagged, not designed.

## Findings (grouped by cause; severity H = live and visibly wrong, M = missing information or
confirmation, L = dormant in this env or cosmetic)

Line numbers are on the upstream basis above; grep the function name if they drift.

### A. Hardcoded Russian / missing keys in bot notices users receive today — H

| # | Where | What |
|---|---|---|
| A1 | `app/services/monitoring_service.py:1844-1857` `_send_subscription_expired_notification` | Whole text + button labels Russian |
| A2 | `monitoring_service.py:2014-2030` `_send_trial_ending_notification` | Russian text "через 2 часа", Russian buttons |
| A3 | `monitoring_service.py:2291` | Winback button "🎁 Получить скидку" |
| A4 | `monitoring_service.py:2353`, `:2403` | Appended `\n📦 Тариф: «…»` (autopay success / failed) |
| A5 | `monitoring_service.py:2409-2410`; email reasons `:549-559` | Autopay-failed buttons and email reasons Russian |
| A6 | `monitoring_service.py:1488-1494` | Legacy (`tariff_id NULL`) autopay-paused notice Russian, raw `send_message` |
| A7 | `monitoring_service.py:1951-1953` | `BTN_MY_SUBSCRIPTIONS` / `BTN_MY_SUBSCRIPTION` absent from en/fa → Russian default in every expiry reminder |
| A8 | `app/services/daily_subscription_service.py:764-771` `_notify_traffic_reset` | Russian f-string incl. `📦 Тариф:` |
| A9 | `app/services/subscription_auto_purchase_service.py:761, 1139, 2614, 3730`; defaults `:1870-1875`, `:2226-2229` | `📦 Тариф:` suffix; devices/traffic auto-purchase Russian defaults |
| A10 | `app/services/manual_topup_service.py:325-328` | Manual top-up notice Russian |
| A11 | `app/services/user_service.py:97-130` `send_topup_success_to_user`; `:162-173` | Russian (incl. "ПОДПИСКА НЕ АКТИВНА!") |
| A12 | `app/services/guest_purchase_service.py:1131-1153` `_send_telegram_gift_notification` | Gift received: Russian text + "Активировать подарок" |
| A13 | `app/services/referral_service.py:1296-1304` | Purchase-commission notice Russian f-string (others use keys) |
| A14 | `app/services/notification_delivery_service.py:702, 754-755` | Russian ban reason default, `дн. подписки … тарифа` |
| A15 | `app/handlers/admin/subscriptions.py:395-403` | Admin mass expiry reminder to users: Russian, "день(а)" |
| A16 | `app/services/payment/stars.py:531, 537` | Stars top-up keyboard labels Russian (Stars is live) |
| A17 | `app/services/promocode_service.py:497` | `…{balance_bonus_kopeks}₽` |

Dormant (deferred gateways, off): provider "Пополнение успешно!" f-strings in `payment/platega.py`,
`overpay.py`, `jupiter.py`, `severpay.py`, `paypear.py`, `aurapay.py`, `antilopay.py`, `mulenpay.py`,
`rollypay.py`, `pal24.py`, `wata.py`, `donut.py`, `freekassa.py`, `cispay.py`, `etoplatezhi.py`,
`lava.py`, `riopay.py`, `kassa_ai.py`, `heleket.py`; `yookassa.py:715`, `tribute_service.py:323`,
`recurrent_payment_service.py:390`; `ban_notification_service.py` / `BAN_MSG_*` (ban system off).
Out of scope here (gateways stay disabled, not touched).

### B. Buttons that stay bot callbacks in cabinet mode, or don't target the subscription — H

| # | Where | What |
|---|---|---|
| B1 | `monitoring_service.py:2197-2198`, `:2307-2308` | Raw `menu_support` (cabinet `/support` is mapped in `miniapp_buttons.py`) |
| B2 | `subscription_auto_purchase_service.py` 776-789, 1148-1160, 1509-1521, 1884-1896, 2239-2251, 2630-2642, 3030-3042, 3746-3758 | Raw `menu_subscription` + `back_to_menu`, never the subscription id |
| B3 | `daily_subscription_service.py:416, 421` `_notify_insufficient_balance` | Raw `menu_balance` / `menu_subscription` |
| B4 | `user_service.py:107-130, 180-187` | Raw `subscription_buy` / `subscription_extend` / `subscription_add_devices` / `menu_subscription` |
| B5 | `guest_purchase_service.py:1150-1153` | Raw `gift_activate:{id}` |
| B6 | `payment/common.py:47-50, 89-92` `build_topup_success_keyboard` | Picks the first active subscription; "extend" opens generic `/subscription`, not `/subscriptions/{id}/renew` |
| B7 | `monitoring_service.py:2521-2539` traffic warning; `:2651` low-balance | No button at all (traffic); both via raw `bot.send_message` (no blocked-user skip) |
| B8 | `monitoring_service.py:1861, 1973, 2204, 2314, 2354, 2414` | `_send_message_with_logo` without `user=` → blocked/deleted users not skipped |

### C. Wrong or misleading content in scheduled notices — M/H

| # | Sev | Where | What |
|---|---|---|---|
| C1 | H | `monitoring_service.py:1498-1503` vs `:1894-1906`; cycle order `_process_autopayments` before `_check_expiring_subscriptions` | Expiry reminder with autopay ON says "renews automatically" — it is only reached after autopay already failed for lack of balance, so the claim is false when shown |
| C2 | M | `_send_subscription_expiring_notification` | No renewal price; the user can't tell how much to top up. Price must come from the same period resolver + `pricing_engine.calculate_renewal_price` autopay uses (`:1575-1600`), so a partner's wholesale discount is included automatically |
| C3 | M | `monitoring_service.py:2156-2165` `_send_expired_day1_notification` | Quotes the tariff's shortest period; on pricing error falls back to global `PRICE_30_DAYS` (990) instead of skipping the price line |
| C4 | M | `monitoring_service.py:876` | Trial warning window hardcoded 2h; `settings.get_trial_warning_hours()` (`config.py:2318`, exposed in admin settings) has no caller |
| C5 | M | `monitoring_service.py:2521-2539` | Traffic warning doesn't name the tariff (only `Subscription.user` loaded) |
| C6 | M | `plugins/c2c/service.py:390-412` + `payment/common.py:396-487` | `send_cart_notification_after_topup` always returns False, so after a C2C approve whose saved-cart auto-purchase *succeeded* the user also gets `PAYMENT_TOPUP_CART_AUTOPURCHASE_FAILED` ("return to checkout") |
| C7 | M | `monitoring_service.py:2605-2607` | Low-balance quiet hours 22-09 **UTC** (= 01:30-12:30 Tehran); ruling Q3: Tehran 00:00-06:00 → task 8 |
| C9 | H | `monitoring_service.py:750-830` (`_check_expiring_subscriptions`), `:1230-1375` (follow-ups), `:566-612` (expired), `:2468-2560` (traffic), `daily_subscription_service._notify_daily_charge` | Every reminder is sent **per subscription**. DB 2026-09-12: user 433 (39 active, 4 expired, 3 tariffs) has 9 `expiring/3` + 4 `expiring/1` rows = 13 separate Telegram messages in two days; 7 of their subs end within 3 days (2 on 09-12, 3 on 09-15), user 97 got 4. Follow-ups (`expired_1d`, winback wave 2/3) run per expired subscription with a 30-day lookback (`:1240`) and are skipped only while another sub is active — a user whose subs have all lapsed gets 3 messages *per* subscription, and a new `discount_offers` row per subscription. → task 8 |
| C10 | M | dates in all monitoring/auto-purchase notices (`format_local_datetime`, `strftime('%d.%m.%Y')`) | Gregorian; ruling Q5: Jalali (`app/utils/jalali_datetime.format_user_datetime`, as the C2C card) |
| C8 | L | stale scale comments `monitoring_service.py:3199`, `daily_subscription_service.py:161`, `plugins/c2c/service.py:354` | Still say "catalog ×100" |

### D. Cabinet flows: the user gets no (or a silent) result — H/M

| # | Sev | Where | What |
|---|---|---|---|
| D1 | H | frontend `src/pages/RenewSubscription.tsx:60-66` | Renewal success only navigates; no confirmation, amount or new end date. Backend returns `new_end_date`, `amount_paid_kopeks` (`renewal.py:289-293`) |
| D2 | H | frontend `src/components/subscription/sheets/{DeviceTopupSheet:63, TrafficTopupSheet:62, ServerManagementSheet:79, SwitchTariffSheet:107, DeviceReductionSheet:64}.tsx` | Every add-on / switch sheet closes silently on success |
| D3 | M | backend `app/cabinet/routes/subscription_modules/*`, `subscription_renewal_service.py:604` | No cabinet action (purchase, renew, switch, trial, devices, traffic, servers, daily pause/resume, autopay, promo) sends a Telegram notice or websocket event to a Telegram user; `purchase.py:559, 1246` and `coupon.py:63` notify email-only users only. Bot-made twins do notify — ruling Q1: bot sends a Telegram confirmation for cabinet purchase/renewal/switch → task 7 |
| D4 | M | `app/services/payment/common.py:188` is the only `balance.topup` caller | Emitted only on YooKassa and C2C approve; Stars (`stars.py:544`) and CryptoBot (`cryptobot.py:700`) credits send Telegram only — the cabinet success modal never appears for them (the `TopUpResult` page polls instead) |
| D5 | M | `plugins/c2c/service.py:259-324`; `plugins/c2c/cabinet.py:63`; `service.py:285` | C2C reject: Telegram only, no websocket; cabinet learns only by polling `/c2c/current`; default reason `'Rejected by administrator'` English, returned raw |
| D6 | L | `app/cabinet/routes/websocket.py:294-589` | 15 `notify_user_*` helpers (expiring, expired, autopay.*, daily_debit, traffic_reset, referral.*, account.*, payment_received, balance_change) never called although `WebSocketNotifications.tsx` handles every one — ruling Q2: wire them for scheduled events → tasks 7 + 8 |
| D7 | L | `app/cabinet/routes/notifications.py:124-151` | `/notifications/test` and `/history` are stubs (test says "you will receive a message shortly", sends nothing) |
| D8 | H | frontend `src/components/SuccessNotificationModal.tsx:213, 222, 232, 241` | `successNotification.devicesAdded/totalDevices/trafficAdded/totalTraffic` values contain `{{count}}` but are called without params → literal placeholder; `+` in front of a renewal *price* (`:203`); "GB" hardcoded (`:234, :243`); "go to subscription" always opens the list (`:142`), `subscription_id` in the payload ignored |
| D9 | M | frontend `src/pages/Subscription.tsx:500-509` (autopay toggle), `:560-567` (daily pause/resume), `src/pages/Profile.tsx:242-247, 703-705` (prefs), `src/pages/Dashboard.tsx:144-155` / `Subscriptions.tsx:132-145` (trial), `ReferralWithdrawalRequest.tsx:33-40, 110-113`, `GiftSubscription.tsx:460-497, 822-834` | Autopay toggle and prefs save swallow errors entirely; pause/resume, trial activation, withdrawal and gift succeed silently; withdrawal drops the backend reason; gift compares against an English literal; the threshold input saves on every keystroke |
| D10 | M | frontend `src/locales/fa.json` | Missing in fa (present in en): `subscription.switchTariff.preview/.switched/.notEnoughBalance`, `subscription.pause.pausedMessage/.resumedMessage/.dailyOnly/.days_one/_few/_many`, `dashboard.expired.expiredDate_trial`; `balance.promocode.balanceAdded` rendered with `amount.toFixed(2)` (`Balance.tsx:141-170`) → "50000.00", no separator or unit |
| D11 | M | frontend `src/components/subscription/SubscriptionListCard.tsx`, `src/pages/Subscription.tsx:97, 146-200`, `SubscriptionCardActive.tsx:200-232` | No expiring-soon text (colour only at ≤3 days), no renewal price, expired list card has no renew action — with several subscriptions the user can't see which one needs attention |

### E. Cabinet API error and success texts not localized — H

`getApiErrorMessage` (`frontend/src/utils/api-error.ts:42-66`) shows a string `detail` raw, and a
`{code, message}` detail's `message` unless the code is in `CODE_MESSAGE_KEYS`.

| # | Where | What |
|---|---|---|
| E1 | `subscription_modules/renewal.py:113-177`, `purchase.py:468-673, 1216-1227` (success message `f"Тариф '{…}' успешно активирован"` Russian), `tariff_switch.py` (13, incl. `:369` 402 not localized), `devices.py` (17, reduce/delete English), `traffic.py`, `servers.py`, `daily.py` (402 code `insufficient_balance` vs `insufficient_funds` elsewhere), `autopay.py`, `multi_tariff.py`, `revoke.py`, `status.py` | ~100 hardcoded English `detail=` strings shown to fa users |
| E2 | `app/cabinet/routes/balance.py` (43; incl. Russian manual-check strings `:1717-1758`, Stars "only available through the bot" `:621`) | Top-up errors |
| E3 | `gift.py`, `promo.py:320-399`, `promocode.py:105-133`, `withdrawal.py:154,160` (Russian), `wheel.py:236-314` (Russian), `tickets.py` (6) | Other user flows |

### F. Amount scale in what the cabinet renders — H (payment-fixer)

| # | Where | What |
|---|---|---|
| F1 | `renewal.py:292`, `traffic.py:463, 764`, `servers.py:303`, `devices.py:353`, `tariff_switch.py:616, 623`, `purchase.py:1223` | Success-response `*_kopeks` amounts are Toman, not passed through `wire_catalog_kopeks` (frontend types exist in `src/api/subscription.ts:95,123,140,572,671` but nothing renders them yet — task 5 will, so this must be fixed first) |
| F2 | `balance.py:1505-1506` pending payment `amount_kopeks=record.amount_kopeks`; frontend `src/pages/TopUpResult.tsx:25` divides by 100 | Top-up result screen shows the amount 100× too small — overlaps **F-087**; resolve there, verify on this screen |
| F3 | `payment/platega.py:660`, `payment/lava.py:666` | Bare `/ 100` in websocket payloads (deferred gateways; low, but a rule breach) |

Checked and **not** a bug (don't re-investigate): websocket `subscription.renewed/devices_purchased/
traffic_purchased` send `amount_rubles = amount_kopeks` (`websocket.py:377, 396, 415`), and since
Phase C that value is Toman; the frontend reads `amount_rubles` first (`src/utils/balanceScale.ts:33`),
so the modal amount is right. Only the field names are misleading.

### G. Emails — deferred (ruling Q4: no email-only users for now)

`app/cabinet/services/email_templates.py`: 26 notification templates (balance, subscription ×4,
winback ×3, autopay ×3, daily ×2, traffic reset, ban/unban/warning, referral ×2, partner ×2,
withdrawal ×2, payment received, promo offer) have no `fa` → fall back to Russian with `₽`
defaults (e.g. `:287`). Only auth and guest/gift templates have fa. `purchase.py:1246` sends the
email with `strftime('%d.%m.%Y')` UTC dates. Existing F-033 (low-balance email/ws) and F-034
(threshold unit) stay in FINDINGS.

### Partner-relevant (flag only)

- C2 must price through `pricing_engine` with `user=` so wholesale discounts show; no new policy.
- Withdrawal create/cancel (`withdrawal.py`) gives the user no confirmation and Russian cancel errors
  (E3); partner application approve/reject and withdrawal approve/reject notify email-only users
  only (`admin_withdrawals.py:246, 297`) — a Telegram partner learns nothing. Covered by task 6 for
  text; delivery follows ruling Q1 (Telegram confirmation) where the action is a purchase/renewal/switch.

## Design

Fix in place, smallest edit per site: a locale key instead of an f-string (placeholders unchanged),
`build_miniapp_or_callback_button` / `build_subscription_extend_button(…, subscription.id)` instead of
a raw `InlineKeyboardButton`, `_send_message_with_logo(…, user=user)`. Monitoring senders whose text
is touched get a static `_build_*` returning `(text, keyboard)` so they are render-tested without a
bot. Cabinet errors become `{code, message}` with `message = texts.t(KEY)` in the user's language
(the pattern `CABINET_INSUFFICIENT_BALANCE` already uses); the frontend keeps showing `message`, so no
frontend change is needed for E. Cabinet results reuse the existing `SuccessNotificationModal`
(`showSuccessModal` in `src/store/successNotification.ts`) fed from the HTTP response, not from a
websocket event, so they don't depend on task 7's events. Nothing touches `wire_scale.py` except F1
calling it.

Out of scope: admin-chat texts (`AdminNotificationService`, F-009 part B), panel-webhook notices
(off), new notification types, winback timing/percentages, deferred gateways' texts.

## Vs. upstream

- **Ours:** Persian/Toman texts and keys, cabinet-mode buttons, multi-tariff subscription targeting,
  renewal price in reminders. All as local edits in upstream hot files (`monitoring_service.py`,
  `subscription_auto_purchase_service.py`, cabinet routes) — one key or one builder call per site, no
  restructuring, so an upstream merge conflicts line-locally at worst.
- **Reused as-is:** `miniapp_buttons.py` builders, `pricing_engine.calculate_renewal_price`,
  `SuccessNotificationModal`, `cabinet_ws_manager` helpers in `websocket.py`, `texts.t`.
- No deferred gateway is enabled or depended on; their Russian notices are left untouched.

## Tasks

Cross-cutting rule for tasks 1, 2, 3, 7, 8 (ruling Q5): every date a user notice shows goes through
`format_user_datetime` (Jalali for fa, Gregorian for other languages — the helper already decides),
never `format_local_datetime` / `strftime`. Tests assert a Jalali date for the fa user.

### Execution order

One task = one fresh conversation = one PR (plus a linked frontend PR where noted). Each starts with
`plan-execution` on this file, e.g. the phrase «تسک 8 از پلن 2026-09-12-user-notifications-and-flow-results رو اجرا کن».
Tasks with pending Persian wait for `translation-fixer` on their branch before merge.

1. **Task 8** — multi-subscription aggregation, abandonment, configurable quiet hours (bot; then
   admin-fixer parity). First, because it reshapes the senders tasks 1-2 edit.
2. **Task 1** — monitoring reminders: Russian, buttons, trial window (bot).
3. **Task 2** — expiry reminder truth + renewal price (bot).
4. **Task 3** — post-payment / auto-purchase notices, combined message (bot).
5. **Task 4** — cabinet response amount scale (bot, payment-fixer). Must merge before 5.
6. **Task 5** — cabinet result confirmations (frontend).
7. **Task 5b** — silent successes, swallowed errors, fa keys, card signals (frontend).
8. **Task 6a**, then **6b** — localize cabinet API errors (bot, two PRs).
9. **Task 7** — Telegram confirmations for cabinet actions + cabinet events (bot PR, then frontend PR).

Tasks 4, 6a and 6b touch no file tasks 1-3/8 touch and may run in parallel sessions with them.

Every bot task: worktree from `origin/main`, TDD on the rendered text/keyboard for a fa user in
tariffs mode (balance 50,000; tariff price 10,000; tariff name set; subscription id in the button
URL), new keys in all five `app/localization/locales/{en,fa,ru,ua,zh}.json` with `locales/{en,fa,ru}.json`
byte-identical, fa = English placeholder until `translation-fixer` writes Persian (PR waits for it).

### Task 1 — Monitoring reminders: Russian, buttons, trial window (A1-A7, B1, B7-B8, C4, C5, C8) · H

- **Repo + files:** `remnabot` `app/services/monitoring_service.py`; tests
  `tests/services/test_monitoring_user_notices.py` (new; grep `tests/services/test_monitoring*` first).
- **Interfaces:** produces static builders `_build_expired_notice(texts, user, subscription)`,
  `_build_trial_ending_notice(texts, subscription, hours)`, `_build_autopay_failed_notice(...)`,
  `_build_traffic_warning(texts, subscription, used, limit, percent)` → `(str, InlineKeyboardMarkup)`.
  Trial window reads `settings.get_trial_warning_hours()` for both the query and the `{hours}`
  placeholder. Tariff label via one key `NOTIFY_TARIFF_LABEL` (` «{name}»`) replacing every
  `📦 Тариф:` suffix in this file. Traffic warning query loads `Subscription.tariff`, adds a cabinet
  button to the subscription page. `menu_support` → `build_miniapp_or_callback_button(..., 'menu_support')`.
  Legacy-autopay notice → key + `_send_message_with_logo(user=user)`. Pass `user=` at the six calls in B8.
- **Test:** each builder renders fa text with tariff name, no Cyrillic, Latin digits, button URLs
  `/subscriptions/{id}/renew`, `/support`, `/balance/top-up`; trial query uses the setting (patched to 5).
- **i18n:** `SUBSCRIPTION_EXPIRED_NOTICE`, `TRIAL_ENDING_SOON` (`{hours}`, `{tariff_label}`),
  `WINBACK_CLAIM_DISCOUNT_BUTTON`, `NOTIFY_TARIFF_LABEL`, `AUTOPAY_FAILED_TOPUP_BUTTON`,
  `AUTOPAY_FAILED_SUBSCRIPTION_BUTTON`, `AUTOPAY_FAIL_REASON_*` (3), `AUTOPAY_LEGACY_PAUSED`,
  `BTN_MY_SUBSCRIPTIONS`, `BTN_MY_SUBSCRIPTION`, `TRAFFIC_WARNING_OPEN_BUTTON`. Also drop the unused
  `LOW_BALANCE_TOPUP_BUTTON` reference if one appears; fix C8 comments. → **translation-fixer**.

### Task 2 — Expiry reminder truth and price (C1, C2, C3) · H

- **Repo + files:** `remnabot` `app/services/monitoring_service.py`; test in the task-1 file.
- **Interfaces:** consumes the autopay period resolver used in `_process_autopayments` — extract it to
  `_resolve_autopay_period(subscription) -> int` (no behaviour change) and a
  `_quote_renewal_price(db, user, subscription) -> int | None` that returns `None` on pricing error.
  `SUBSCRIPTION_EXPIRING_PAID` gains `{price_line}` (empty when `None`); `SUBSCRIPTION_EXPIRED_1D`
  uses the resolver's period and omits the price line instead of `PRICE_30_DAYS`. Autopay-ON variant:
  when this sub's autopay is on and the reminder is being sent, the status reads "autopay could not
  renew — balance {balance}, needed {price}" (reuse `AUTOPAY_STATUS_*` keys; new
  `AUTOPAY_STATUS_PENDING_BALANCE`). Do not change when reminders fire.
- **Test:** fa render with price 10,000 and balance 50,000; pricing error → no price line, no 990;
  autopay-on + insufficient balance → no "renews automatically" claim; a partner user's quote equals
  `pricing_engine` with `user=` (discount applied).
- **i18n:** `SUBSCRIPTION_RENEWAL_PRICE_LINE`, `AUTOPAY_STATUS_PENDING_BALANCE`; fa value of
  `SUBSCRIPTION_EXPIRING_PAID` changes (placeholder added) → **translation-fixer**. Amounts:
  `format_price` / `format_balance` only → **payment-fixer** review not needed unless the quote differs
  from autopay's charge.

### Task 3 — Post-payment and auto-purchase notices (A8-A13, A16, A17, B2-B6, C6) · H

- **Repo + files:** `remnabot` `app/services/subscription_auto_purchase_service.py`,
  `daily_subscription_service.py`, `manual_topup_service.py`, `user_service.py`,
  `guest_purchase_service.py`, `referral_service.py` (1296-1304 only), `payment/common.py`,
  `payment/stars.py`, `promocode_service.py:497`, `plugins/c2c/service.py`; tests
  `tests/services/test_auto_purchase_notices.py`, `tests/plugins/c2c/test_approve_notice.py`.
- **Interfaces:** one helper `build_subscription_result_keyboard(texts, subscription_id | None)` in
  `app/utils/miniapp_buttons.py` → cabinet "open subscription" (`/subscriptions/{id}`) + "my
  subscriptions"; replaces the eight raw keyboards (B2), B3, B4. `build_topup_success_keyboard` takes an
  optional `subscription_id` and uses `build_subscription_extend_button` when given (B6).
  C6: `auto_purchase_saved_cart_after_topup` already returns success — make
  `send_cart_notification_after_topup` return that result (rename is not needed; keep name for its
  19 callers) and have C2C read the cart *after* the auto-purchase attempt. Gift button →
  `build_miniapp_or_callback_button` to the cabinet gift page (grep frontend routes for the gift
  activation path; if none takes an id, keep callback and record a FINDINGS entry).
  Q6 default (one combined message): when the saved-cart auto-purchase succeeds, the top-up success
  notice is not sent separately; the auto-purchase notice gains a first line
  `TOPUP_CREDITED_LINE` (`{amount}`) and ends with the remaining balance. Applies to C2C, Stars,
  CryptoBot and manual top-ups alike (all go through `send_cart_notification_after_topup`).
- **Test:** each sender renders fa, no Cyrillic, tariff named, Jalali end date; C2C approve with a
  successful cart purchase sends exactly one message (credited amount + tariff + end date + balance)
  and no `PAYMENT_TOPUP_CART_AUTOPURCHASE_FAILED`; a failed purchase still sends the top-up notice
  with the failure line.
- **i18n:** `DAILY_TRAFFIC_RESET_NOTICE`, `MANUAL_TOPUP_NOTICE`, `TOPUP_SUCCESS_NO_SUBSCRIPTION`
  (A11), `GIFT_RECEIVED_*` (3), `REFERRAL_PURCHASE_COMMISSION_NOTICE`, `STARS_TOPUP_*_BUTTON` (2),
  `PROMOCODE_BALANCE_BONUS_LINE`, devices/traffic auto-purchase default texts moved to keys. →
  **translation-fixer**. Amount display only via `format_balance` → no payment hand-off.

### Task 4 — Cabinet amount scale in responses (F1, F3; verify F2 with F-087) · H · payment-fixer

- **Repo + files:** `remnabot` `app/cabinet/routes/subscription_modules/{renewal,traffic,servers,devices,tariff_switch,purchase}.py`,
  `app/services/payment/{platega,lava}.py`; test `tests/cabinet/test_result_amount_wire_scale.py`.
- **Interfaces:** produces the contract task 5 renders: `amount_paid_kopeks`, `charged_kopeks`,
  `charged_amount`, `discount_kopeks`, `new_balance_kopeks` all on the wire catalog scale via
  `wire_catalog_kopeks` (balance fields already follow whatever `balance_kopeks` does on that route —
  keep them consistent with it). Additive keys `amount_paid_toman` / `new_end_date` /
  `subscription_id` / `tariff_name` on renew, traffic, servers, devices, switch responses where absent.
- **Test:** each endpoint's response for price 10,000 Toman returns `amount_paid_kopeks == 1_000_000`
  and `amount_paid_toman == 10_000`. F2: owned by F-087; this task only adds a regression test if F-087
  is merged, otherwise lists it as blocked.
- **i18n:** none. **Must merge before task 5.** Touches the x100 wire boundary only by calling it
  (Phase C-2 plan `2026-09-12-phase-c2-amount-scale-header.md` must be checked for conflicts first).

### Task 5 — Cabinet result confirmations (D1, D2, D8) · H · frontend

- **Repo + files:** `frontend` `src/pages/RenewSubscription.tsx`,
  `src/components/subscription/sheets/{DeviceTopupSheet,TrafficTopupSheet,ServerManagementSheet,SwitchTariffSheet,DeviceReductionSheet}.tsx`,
  `src/components/SuccessNotificationModal.tsx` (new types `tariff_switched`, `servers_changed`,
  `devices_reduced`), `src/store/successNotification.ts`; test
  `src/utils/resultModalData.test.ts` for a new `src/utils/resultModalData.ts` mapping each response
  to modal data (scale via `catalogPriceInToman`, fields from task 4).
- **Interfaces:** consumes task 4 fields; modal shows tariff name, amount, new end date / new limit,
  new balance, and a "go to subscription" button to `/subscriptions/{id}` (also for the existing
  websocket-fed types, using the payload's `subscription_id`). D8: pass `count` to the four labels,
  no `+` on prices, traffic unit from the existing traffic-unit keys.
- **Test:** mapping unit tests (logic); modal visuals verified live with `run-cabinet` as a fa user.
- **i18n:** `frontend/src/locales/{en,fa}.json` `successNotification.tariffSwitched.title`,
  `.serversChanged.title`, `.devicesReduced.title` (+ check the existing `successNotification.*` fa
  values) → **translation-fixer**. **admin-fixer:** not needed (no new user-owned data).

### Task 5b — Silent successes, swallowed errors, missing fa keys, card signals (D9, D10, D11) · M · frontend

- **Repo + files:** `frontend` `src/pages/Subscription.tsx`, `Profile.tsx`, `Dashboard.tsx`,
  `Subscriptions.tsx`, `ReferralWithdrawalRequest.tsx`, `GiftSubscription.tsx`, `Balance.tsx`,
  `src/components/subscription/SubscriptionListCard.tsx`, `src/components/dashboard/SubscriptionCardActive.tsx`;
  test `src/utils/subscriptionAttention.test.ts` for a new `subscriptionAttention(sub, now)` →
  `'expiring' | 'expired' | null` (threshold: the user's `subscription_expiry_days` pref, default 3 —
  from `notification_prefs.py`, not invented).
- **Interfaces:** consumes `GET /cabinet/notifications` for the threshold; no backend change. Errors via
  `notify.error(getApiErrorMessage(err, t('common.error')))`; success toasts use existing en keys
  (`pause.pausedMessage` etc.). Prefs number input saves on blur/debounce. Promo amount through
  `formatBalance`. Expired/expiring list card gets a "renew" link to `/subscriptions/{id}/renew`;
  renewal price on the card only if `subscriptions-list` already carries it (grep; don't add an API).
- **Test:** `subscriptionAttention` unit tests; the rest visual — verify live.
- **i18n:** the D10 keys in fa, `subscriptions.expiringSoon` (`{{days}}`), `subscriptions.renew`,
  `profile.notifications.thresholdUnit` (closes F-034) → **translation-fixer**.

### Task 6 — Localize cabinet API errors and success messages (E1-E3, D5 reason, D7 text) · H

- **Repo + files:** `remnabot` `app/cabinet/routes/subscription_modules/*.py`, `balance.py`, `gift.py`,
  `promo.py`, `promocode.py`, `withdrawal.py`, `wheel.py`, `tickets.py`, `notifications.py` (test stub
  message), `plugins/c2c/service.py:285` + `cabinet.py:63`; tests
  `tests/cabinet/test_error_details_localized.py` (parametrised: fa user → no Latin-letter-only or
  Cyrillic `message`).
- **Interfaces:** helper `cabinet_error(status, code, key, default, **fmt) -> HTTPException` in
  `app/cabinet/routes/subscription_modules/helpers.py` (or `app/cabinet/utils`), detail
  `{'code': code, 'message': texts.t(key, default).format(**fmt)}`. `daily.py` 402 code aligned to
  `insufficient_funds` (grep `frontend/src` for `insufficient_balance` first; keep both if used).
  Success `message` fields become `texts.t` too (`purchase.py:1216` Russian first). Too large for one
  conversation if done at once: split **6a** subscription modules, **6b** balance/gift/promo/withdrawal/
  wheel/tickets/notifications — two PRs.
- **Test:** as above, plus one frontend check that `getApiErrorMessage` shows the fa `message`
  (existing tests cover `{code,message}`).
- **i18n:** ~120 `CABINET_ERR_*` keys → **translation-fixer** (large batch; hand over per PR).

### Task 7 — Cabinet actions confirm in Telegram; payment and scheduled events reach the cabinet (D3, D4, D5, D6) · M · both

Rulings Q1 + Q2 (2026-09-12). Depends on task 8 for the scheduled-event payload shape.

- **Repo + files:** `remnabot`
  - Q1: new `app/services/user_action_notice.py` with
    `notify_user_subscription_result(db, user, subscription, kind: Literal['purchase','renewal','tariff_switch'], amount_toman: int, old_tariff_name: str | None = None)`
    — Telegram only when `user.telegram_id`, text/keyboard built by a static
    `build_subscription_result_notice(texts, user, subscription, kind, amount_toman, balance_toman, old_tariff_name)`
    (tariff name, Jalali end date, amount, new balance, button to `/subscriptions/{id}` via task 3's
    `build_subscription_result_keyboard`). Called after commit from `purchase.py` (tariff purchase),
    `subscription_renewal_service.finalize` for cabinet `/renew` only (autopay already has its own
    notice — pass `source` and skip `autopay`), and `tariff_switch.py`. Gated by
    `settings.is_notifications_enabled()`; failures logged, never fail the request.
  - Stars/CryptoBot credits (`payment/stars.py`, `payment/cryptobot.py`) call `notify_user_balance_topup`
    as `common.py:188` does; C2C reject gets `notify_user_c2c_rejected` in `websocket.py`
    (event `balance.c2c_rejected {receipt_id, reason}`).
  - Q2: every scheduled user notice that task 8 aggregates also emits one websocket event per
    aggregated message, using the existing helpers where the shape fits
    (`notify_user_subscription_expiring/expired`, `notify_user_autopay_*`, `notify_user_daily_debit`,
    `notify_user_traffic_reset`) and adding a `subscriptions: [{id, tariff_name, end_date, price_toman}]`
    list to their payloads (additive).
  - Tests: `tests/services/test_user_action_notice.py` (render for fa: tariff, Jalali date, amounts,
    URL), `tests/services/test_topup_ws_events.py`.
- **frontend:** `src/components/WebSocketNotifications.tsx` — handler for `balance.c2c_rejected`
  (invalidate `['c2c-current']`, toast with reason); expiring/expired/autopay/daily toasts read the
  `subscriptions` list: one subscription → tariff name + click to `/subscriptions/{id}`, several →
  "N subscriptions" + click to `/subscriptions`. Mapping in `src/utils/wsSubscriptionSummary.ts` with a
  unit test; toast visuals verified live.
- **Interfaces:** event names and `subscriptions` field above; amounts in the payload are Toman
  (`display_balance_from_storage`), as `balance.topup` already does.
- **i18n:** bot `CABINET_ACTION_PURCHASE_NOTICE`, `CABINET_ACTION_RENEWAL_NOTICE`,
  `CABINET_ACTION_TARIFF_SWITCH_NOTICE`; frontend `wsNotifications.c2c.rejectedTitle`,
  `wsNotifications.subscription.expiringMany` (`{{count}}`) → **translation-fixer**.
- Bot PR merges before the frontend PR (additive payload fields). Deferred per Q4: G (fa email
  templates), D7 `/history`. F-033/F-034 stay in FINDINGS.

### Task 8 — Reminders for many subscriptions: per-subscription targeting, abandonment cut-off, one message per user (C7, C9) · H · bot

Ruling Q2 (2026-09-12): a user or partner with many (e.g. 100) lapsed subscriptions must not be
harassed with repeated reminders; several subscriptions go into one message. **R2.1-R2.7 approved
by the user as written (2026-09-12); R2.8 approved in the configurable form below.** R2.3-R2.5 limits
are read through `NotificationSettingsService` getters whose defaults are the approved values
(overridable in `data/notification_settings.json`, like the winback waves); quiet hours are `settings`
fields exposed in the admin settings screen. No `.env` flag is flipped.

**Approved rules:**

| # | Rule | Default | Evidence / reasoning |
|---|---|---|---|
| R2.1 | Aggregation unit | One Telegram message **per user per checkpoint per cycle** (expiring 3d, expiring 1d, expired, follow-up, autopay failed, traffic, daily charge), listing every subscription that hit it. Dedup rows in `sent_notifications` stay **per subscription** (unchanged table), so a subscription is never listed twice for the same checkpoint | User 433 received 13 separate "expiring" messages in two days (9 at 3d, 4 at 1d); 7 of their subs end within 3 days, 3 on the same day |
| R2.2 | List length | Show up to **5** subscriptions (tariff name, Jalali end date, renewal price), then "+N more"; buttons: renew for a single subscription, otherwise one "my subscriptions" button (cabinet list) | Telegram keyboards past a handful of buttons are unusable; the cabinet list already shows the rest |
| R2.3 | Abandonment | A subscription expired **more than 7 days** ago is abandoned: no expired/follow-up/winback reminders for it, ever (it stays renewable in the cabinet). Replaces the 30-day lookback (`monitoring_service.py:1240`) | The last current step, winback wave 3, fires at day 5 (`trigger_days: 5`); 7 days covers it plus two cycles of slack. User 433's expired subs are from 07-30, 08-15, 08-29 and 09-10 — only 09-10 is still in scope |
| R2.4 | Follow-up series per user | Expired-1d + winback waves run for **one subscription per user**: the most recently expired one, and only while the user has no active subscription (today's skip, kept). The message names that tariff and says "and N other expired subscriptions" when more exist | Stops 3 messages × N subscriptions; one winback offer per user is what the discount is for |
| R2.5 | Winback offer frequency | At most **one winback discount offer per user per 30 days** (checked against `discount_offers` created in the last 30 days), whatever the number of subscriptions | Today a new `discount_offers` row is created per expired subscription |
| R2.6 | Expiring reminders — which subscriptions | Only subscriptions that are paid, not daily, not trial, and **not with autopay on and enough balance** for the quoted renewal (those will renew; they are listed only if autopay would fail). Keep `AUTOPAY_WARNING_DAYS` checkpoints and the user's `subscription_expiry_days` | Fixes C1 at the selection level; 3 of user 7833's 4 subs have autopay on |
| R2.7 | Traffic and daily-charge notices | Traffic warning aggregated per user per 24h (Redis key per user instead of per sub); daily charge: one message per user per daily-charge run listing each charged subscription and the final balance | Same per-subscription pattern as R2.1 |
| R2.8 | Quiet hours (configurable) | Owner-editable in the cabinet admin settings (category `NOTIFICATIONS`, tree node `notif_user`, via `system_settings_service` — the `NOTIFICATION_` prefix already maps there, `system_settings_service.py:507`): `NOTIFICATION_QUIET_HOURS_ENABLED: bool = True`, `NOTIFICATION_QUIET_HOURS_START: str = '00:00'`, `NOTIFICATION_QUIET_HOURS_END: str = '06:00'` (local time = `settings.TZ`, live `Asia/Tehran`; a window crossing midnight is allowed), `NOTIFICATION_QUIET_HOURS_TYPES: str` (comma list). **Chosen default types** (reminders and informational notices that lose nothing by waiting): `expiring`, `expired_followup` (expired-1d + winback waves), `traffic_warning`, `low_balance`, `daily_charge`. **Default exempt** (time-critical — delaying them breaks service or the offer): `expired` (access just cut), `trial_ending` (2h window would pass), `autopay_failed` (last chance before cut-off), `daily_insufficient` (subscription paused), `trial_channel_unsubscribed`. Held notices are sent in the first cycle after the window ends, not dropped. Event-driven notices (payment credited, C2C decision, cabinet actions, tickets) are never held and are not selectable | Today only low-balance has quiet hours, hardcoded 22-09 UTC (`:2605-2607`); ruling Q3 + R2.8 answer |

Partners: the same rules apply; a partner is not special-cased (no partner policy invented). If the
user wants a digest-only mode for partners with many subscriptions, that is a new question.

- **Repo + files:** `remnabot` `app/services/monitoring_service.py`,
  `app/services/daily_subscription_service.py`, `app/services/notification_settings_service.py`
  (new getters `get_expired_abandon_after_days()` = 7, `get_winback_offer_min_interval_days()` = 30,
  `get_aggregate_list_limit()` = 5, overridable by the same-named keys in
  `data/notification_settings.json`), `app/config.py` (the four `NOTIFICATION_QUIET_HOURS_*` fields
  and a parsed accessor `settings.get_quiet_hours() -> QuietHours(enabled, start: time, end: time, types: frozenset[str])`
  that ignores unknown type names and falls back to the defaults on a malformed time),
  `app/services/system_settings_service.py` (description/hint for the four keys so the admin screen
  explains them; category comes from the prefix), `.env.example` (documented, commented defaults),
  new `app/services/notification_aggregation.py`; `app/handlers/admin/messages.py:1843, 1894`
  (F-045: dedupe broadcast recipients by user — same root cause, close it here); tests
  `tests/services/test_notification_aggregation.py`, `tests/services/test_monitoring_multi_subscription.py`.
- **Interfaces (produces, used by tasks 1, 2, 7):**
  - `collect_user_batches(items: list[Subscription]) -> dict[int, list[Subscription]]` (group by user,
    order by end_date).
  - `build_expiring_digest(texts, user, subs: list[Subscription], quotes: dict[int, int | None], days: int) -> tuple[str, InlineKeyboardMarkup]`
    — single-subscription case renders exactly the task-1/2 message; several → digest.
  - `build_expired_followup(texts, user, sub, other_expired_count, kind) -> tuple[str, InlineKeyboardMarkup]`.
  - `is_abandoned(sub, now, abandon_days) -> bool`,
    `should_hold_for_quiet_hours(notice_type: str, now_utc: datetime, quiet: QuietHours) -> bool`
    (converts to `settings.TZ`; type names are the R2.8 list). Held notices need no queue: the
    dedup row is not written, so the next cycle after the window picks them up again.
  - `MonitoringService` checks call these and record one `sent_notifications` row per listed subscription.
- **Test (failing first):** user with 7 subs expiring within 3 days → one message listing 5 + "+2",
  7 dedup rows, second cycle sends nothing; sub expired 8 days ago → no follow-up; user with 4 expired
  subs and none active → one expired-1d message naming the latest and "3 others"; second winback
  within 30 days → none; 01:00 Tehran → `expiring` held, `expired` sent; 06:10 → held one sent;
  `NOTIFICATION_QUIET_HOURS_TYPES=` (empty) → nothing held; window `22:00-07:00` crosses midnight;
  `ENABLED=false` → nothing held; admin broadcast to a user with 2 expiring subs → one recipient.
- **Admin parity (mandatory, `admin-fixer` after the bot PR):** confirm the four
  `NOTIFICATION_QUIET_HOURS_*` settings appear and save under the cabinet admin settings node
  `notif_user` (`frontend/src/components/admin/constants.ts:129`), with fa labels/hints
  (`admin.settings.settingNames.*` in `frontend/src/locales/fa.json`), and decide whether
  `…_TYPES` needs a multi-select instead of a free-text comma list (frontend PR if so).
- **i18n:** `NOTIFY_DIGEST_EXPIRING` (`{count}`, `{days_text}`, `{lines}`), `NOTIFY_DIGEST_LINE`
  (`{tariff}`, `{end_date}`, `{price}`), `NOTIFY_DIGEST_MORE` (`{count}`), `NOTIFY_OTHER_EXPIRED`
  (`{count}`), `NOTIFY_DIGEST_DAILY_CHARGE` → **translation-fixer**.
- **Size:** one conversation if R2.x are confirmed as written; if the scope grows (e.g. a partner
  digest mode), stop and split.

## Hand-offs summary

| Task | Repo | translation-fixer | payment-fixer | admin-fixer |
|---|---|---|---|---|
| 8 | bot (+ frontend if admin-fixer adds a multi-select) | yes | — | **required**: quiet-hours settings visible and editable in cabinet admin settings (`notif_user`), fa labels; R2.3-R2.5 JSON limits have no cabinet screen (same as winback waves today) — admin-fixer records it as a finding if it isn't built |
| 1 | bot | yes | — | — |
| 2 | bot | yes | review C2 quote only if it differs from autopay's charge | — |
| 3 | bot | yes | — | — |
| 4 | bot | — | owner | — |
| 5 | frontend | yes | — | not needed |
| 5b | frontend | yes | — | not needed |
| 6a/6b | bot | yes (large) | — | — |
| 7 | both | yes | — | not needed (no new user preference) |

## Rulings (user, 2026-09-12)

- **Q1 — yes.** A purchase, renewal or tariff change made in the cabinet gets a Telegram confirmation
  from the bot (task 7).
- **Q2 — yes, and reshape the sending.** Scheduled events also show in the cabinet (task 7); sending
  must fit multi-subscription users: target per subscription, stop on abandoned subscriptions,
  aggregate several subscriptions into one message (task 8). **R2.1-R2.7 approved as proposed.**
- **Q3 / R2.8 — quiet hours configurable by the owner** in cabinet admin settings: the window (default
  00:00-06:00, `settings.TZ` = Asia/Tehran) and which scheduled notice types respect it (defaults
  chosen in task 8's R2.8 row). Admin-parity check by `admin-fixer` is part of task 8.
- **Q4 — no email-only users for now;** fa email templates deferred (G).
- **Q5 — Jalali dates** in notifications (cross-cutting rule above tasks).
- **Q6 — one combined message (approved default):** after a top-up that auto-completes a saved
  purchase, send one message (amount credited + subscription purchased/renewed with tariff, Jalali end
  date and remaining balance) instead of two — the top-up was only the means to the purchase (C6).
  Implemented in task 3.

No open questions remain.

## Smoke test

Generate with `smoke-test-checklist` after each task's implementation (cabinet-only; scheduler-only
notices are "covered by rendering tests").
