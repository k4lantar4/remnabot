---
name: fa-i18n remaining audit
overview: ممیزی کامل وضعیت فارسی‌سازی UI کاربر (ربات، کابینت، مینی‌اپ) — زنجیره fallback، اصطلاحات (دستگاه→تعداد کاربر، تعرفه→سرویس)، راهنمای onboarding، ارقام لاتین، و مسیر جداگانه ادمین/انگلیسی.
date: 2026-06-23
branch_baseline: main @ 03e1c2e8 (P1.5 merged); fix/force-default-language-when-disabled pending merge
---

# fa-i18n Remaining Audit — Implementation Plan

> **Scope:** Audit + ordered implementation phases only. No code changes in this document.
>
> **Agent workflow:** Branch from `main` per `delivery-cycle.mdc`; one concern per commit; smoke `import main` after each commit.

---

## 1. Executive summary

### Overall estimate

| Layer | Keys / files | Persian coverage | Sales-ready quality | Remaining effort |
|-------|----------------|------------------|---------------------|------------------|
| **Bot `fa.json`** (user keys) | ~1,900 user-facing keys (of 4,158 total) | **~98%** keys have Persian values; **0** Cyrillic values | **~70%** — terminology & guidance gaps | **P0–P1** copy + onboarding (~15–20 commits) |
| **Bot handlers** (non-admin, non-balance) | 986 `texts.t(..., 'Cyrillic')` fallbacks; 397 hardcoded Cyrillic lines | Keys resolve to `fa.json` when present | Fallbacks still Russian if key missing; `stars_payments.py` leaks | **P1** hardcoded sweep (~8 commits) |
| **Cabinet user UI** (`cabinet/src/locales/fa.json` user sections) | ~96 `دستگاه` strings; 26 Persian-digit literals | **~95%** Persian | Device terminology + digit policy | **P0** terminology slice + **P2** digits |
| **Miniapp API** (`miniapp.py`) | Mostly `_t(user, KEY, 'ru fallback')` | Keys in `fa.json` / `CABINET_*` | Trial message still Russian fallback L4024–4028 | **P1** parity with bot |
| **Monitoring notifications** | Branch `i18n/monitoring-notifications` (not merged) | Jalali + fa keys drafted | Awaiting user smoke | **P1** merge after smoke |
| **Admin bot + admin cabinet** | 1,715 Cyrillic fallbacks in `app/handlers/admin/**` | `fa.json` has Persian admin (P2 done) | User policy: **English priority**, not Persian | **Separate track** — English keys, not fa polish |

**Bottom line:** Structural translation is **largely done** (~95–98% key coverage). Remaining work is **copy quality, Iranian VPN sales tone, terminology migration (`دستگاه` → `تعداد کاربر`, `تعرفه` → `سرویس`), onboarding guidance, fallback chain (`fa → en → ru`), and Latin digits in cabinet** — roughly **20–25%** of total i18n effort remains for user surfaces.

### DONE vs REMAINING by surface

| Surface | DONE | REMAINING |
|---------|------|-----------|
| **Bot purchase / tariff** | `purchase.py`, `tariff_purchase.py` wired to `texts.t`; success keys Persian | Duplicate «حجم» in traffic step; vague post-purchase CTA; `تعرفه` in success strings; Cyrillic fallbacks in hot paths |
| **Bot my_subscriptions** | Detail screen Persian keys; Jalali dates; status display fix | No step-by-step «first connection» block on detail; single connect button without guidance |
| **Bot devices / traffic** | `devices.py`, `traffic.py` mostly keyed | 72+ Cyrillic fallbacks in `devices.py`; `دستگاه` terminology |
| **Bot tickets / referral / polls** | `fa.json` TICKET_* keys全部 Persian | Cyrillic fallbacks still in handler second args (upstream pattern) |
| **fa.json** | 4,158 keys; 0 Cyrillic values; 0 missing vs `ru.json` | 44 user keys English-only (platform names OK); 76 user keys still say `تعرفه`; 147 user keys say `دستگاه` |
| **Cabinet user pages** | P1 merged; `useCurrency.ts` Latin digits for amounts | 96 `دستگاه` strings; 26 Persian-digit literals in user sections; onboarding copy weak |
| **Miniapp** | API messages keyed | Russian fallbacks in trial activation; `MINIAPP_*` device labels |
| **Fallback chain** | `fix/force-default-language-when-disabled`: crash-safe `fa → ru` | User wants **`fa → en → ru`**; admin wants **English** when fa missing |
| **Admin** | P2 Persian in `fa.json` (optional) | Policy: English-first; 1,715 Cyrillic fallbacks in admin handlers |

---

## 2. Fallback chain status (fa → en → ru)

### Current implementation

**Branch:** `fix/force-default-language-when-disabled` — commits `d1df0821`, `881286bf` (awaiting user smoke).

| File | Lines | Behavior |
|------|-------|----------|
| `app/localization/loader.py` | 18–20 | `UPSTREAM_FALLBACK_LOCALE = 'ru'`; `_FALLBACK_LANGUAGE = 'ru'` |
| `app/localization/loader.py` | 54–76 | `_select_fallback_language()` — prefers `ru`, then `AVAILABLE_LANGUAGES` |
| `app/localization/texts.py` | 149–160 | `_merge_locale_fallback()` — merges missing keys from fallback locale |
| `app/localization/texts.py` | 169–176 | `Texts.__init__`: fallback order = `(DEFAULT_LANGUAGE, UPSTREAM_FALLBACK_LOCALE)` with `skip_locale=self.language` |
| `app/localization/texts.py` | 216–233 | `_get_value`: primary `fa` → `_fallback_values` → KeyError |
| `app/localization/texts.py` | 303–318 | `_get_default_rules` / privacy: falls back to `load_locale(DEFAULT_LANGUAGE)` only (not en) |
| `tests/localization/test_texts_fallback.py` | 18–49 | Asserts `fa` missing key → `ru` value |

**Effective chain today (DEFAULT_LANGUAGE=fa, user language=fa):**

```
active fa key → (no second pass, same locale) → UPSTREAM_FALLBACK_LOCALE (ru) → key name string
```

**`en` is NOT in the chain.** `en.json` exists (1,970 keys vs `ru` 1,958; 12 extra en keys) but is never merged for fa users.

### Required change for user paths

**Target chain:** `fa → en → ru` (never `fa → ru` skipping English).

| Step | File | Change |
|------|------|--------|
| 1 | `app/localization/loader.py:18–20` | Add `SECONDARY_FALLBACK_LOCALE = 'en'`; keep `UPSTREAM_FALLBACK_LOCALE = 'ru'` |
| 2 | `app/localization/texts.py:169–176` | Change loop to `for locale_code in ('en', UPSTREAM_FALLBACK_LOCALE):` when `self.language == 'fa'`; for `en` users: `en → ru`; for `ru`: no merge |
| 3 | `app/localization/texts.py:303–318` | Rules/privacy: `fa → en → ru` same pattern |
| 4 | `tests/localization/test_texts_fallback.py` | Add `fa.json` + `en.json` + `ru.json` fixture; assert `ONLY_IN_EN` resolves before `ONLY_IN_RU` |
| 5 | Optional guard | `tests/localization/test_fa_en_ru_chain.py` — static: no user P0 key resolves to Cyrillic when en has value |

### Admin / operator paths (English priority)

Admin panels use `get_texts(db_user.language)` per `fa-i18n-status.mdc`. For operators who want English:

| Approach | Files | Notes |
|----------|-------|-------|
| **A. Env default** | `.env` `DEFAULT_LANGUAGE=en` for admin-only deployments | Does not help mixed fa users |
| **B. Admin language override** | Future: force `en` in `app/handlers/admin/**` via `get_texts('en')` | Cleanest for «admin English» policy |
| **C. fa.json admin values** | Replace Persian admin strings with English literals in `en.json` only; admin handlers call `get_texts('en')` | Matches user request: «simple fix: use English where fa missing» |

**Recommended:** Phase 8 commit — `get_texts('en')` in `app/handlers/admin/__init__.py` middleware or per-handler at top (scoped slice, e.g. `admin/main.py` first). Do **not** mix with user fa copy commits.

**Cabinet admin UI:** `cabinet/src/locales/fa.json` admin.* sections — use `en.json` for admin routes or `i18n.language === 'admin' → en` in cabinet i18n init (separate PR).

---

## 3. User-facing remaining translation inventory

> **Note:** Cyrillic in `texts.t('KEY', 'Русский fallback')` is upstream-safe; users see `fa.json` when key exists. Items below are **gaps that affect fa users** (missing/wrong fa value, hardcoded Cyrillic without `texts.t`, or misleading copy).

### P0 — Purchase flow & success (user screenshots)

| File | Lines | Key / string | Current (fa) | Suggested Persian | Priority |
|------|-------|--------------|--------------|-------------------|----------|
| `app/handlers/subscription/tariff_purchase.py` | 386–397 | `TARIFF_TRAFFIC_VOLUME_BTN` + `TARIFF_TRAFFIC_STEP_HEADER` | `حجم سرویس: 📊 حجم: 1 گیگ` (duplicate) | Header: `📦 {name}\n📊 حجم: {traffic}\n👥 تعداد کاربر: {devices}` — **not** «حجم ماهانه» (volume is total for subscription period; user picks months in next step; reset is NO_RESET) | **P0** ✅ fixed |
| `app/localization/locales/fa.json` | 3852 | `TARIFF_CUSTOM_TRAFFIC_STEP_HINT` | `📊 حجم را انتخاب کنید` | `\n\n📊 <i>یکی از گزینه‌های حجم را انتخاب کنید؛ سپس مدت زمان را انتخاب می‌کنید</i>` — **not** «حجم دلخواه» only (preset package buttons + «حجم دلخواه»); **not** «بزنید» / «مدت اشتراک» | **P0** |
| `app/localization/locales/fa.json` | 3865 | `TARIFF_TRAFFIC_STEP_HEADER` | `حجم سرویس` + `دستگاه` | See above; `👥 تعداد کاربر: {devices}` | **P0** |
| `app/localization/locales/fa.json` | 3926 | `TARIFF_PURCHASE_SUCCESS` | `تعرفه`…`دستگاه`…`برای اتصال به «اشتراک» بروید` | `🎉 سرویس شما فعال شد!\n\n📦 سرویس: {name}\n📊 حجم: {traffic}\n👥 تعداد کاربر: {devices}\n📅 مدت: {period}\n💰 پرداخت: {charged}\n\n✅ گام بعدی: از منو «اشتراک من» → «🔗 دریافت لینک» را بزنید و در اپ VPN وارد کنید.` | **P0** |
| `app/localization/locales/fa.json` | 3872, 3942, 3836 | `TARIFF_DAILY_SUCCESS`, `TARIFF_RENEW_SUCCESS`, `TARIFF_CHANGE_SUCCESS` | Same pattern as purchase success | Align with `TARIFF_PURCHASE_SUCCESS` template | **P0** |
| `app/localization/locales/fa.json` | 3882 | `TARIFF_INFO_HEADER` | `تعرفه` + `دستگاه` | `📦 {name}\n📊 حجم: {traffic}\n👥 تعداد کاربر: {devices}` | **P0** |

### P0 — my_subscriptions detail & onboarding

| File | Lines | Key | Current | Suggested | Priority |
|------|-------|-----|---------|-----------|----------|
| `app/handlers/subscription/my_subscriptions.py` | 644–665 | `MY_SUB_DETAIL_*` assembly | Detail shows stats + link; one connect button | Add `MY_SUB_DETAIL_ONBOARDING` block after purchase / on first open | **P0** |
| `app/localization/locales/fa.json` | 3094 | `MY_SUB_BTN_CONNECT_LINK` | `🔗 لینک اتصال` | `🔗 دریافت لینک و راهنمای اتصال` | **P0** |
| `app/localization/locales/fa.json` | 3106 | `MY_SUB_DETAIL_DEVICES` | `📱 دستگاه‌ها` | `👥 تعداد کاربر: {devices}` | **P0** |
| `app/handlers/subscription/my_subscriptions.py` | 167–178 | `MY_SUB_DEVICES_LINE`, fallbacks L167–178 | Cyrillic fallbacks `устр.`, `Устройства` | Keys exist in fa — verify only; update fa values | **P1** |
| `app/handlers/subscription/my_subscriptions.py` | 268–320 | `_build_subscription_detail_keyboard` | Many buttons, no «راهنمای اولین اتصال» | Add button `📖 راهنمای اتصال` → `SUBSCRIPTION_CONNECT_DEVICE_MESSAGE` or Happ guide | **P0** |

### P1 — Hot-path handlers (highest Cyrillic fallback density)

| File | ~Fallback lines | Sample keys (Cyrillic in code) | fa.json status | Priority |
|------|-----------------|--------------------------------|----------------|----------|
| `app/handlers/subscription/purchase.py` | 205 | `PURCHASE_*`, `CB_*` | Mostly Persian in fa | **P1** — audit keys used in confirm/success only |
| `app/handlers/subscription/tariff_purchase.py` | 156 | `TARIFF_CUSTOM_TRAFFIC` L789 Cyrillic in fallback | fa exists | **P0** for L789 fallback text quality |
| `app/handlers/simple_subscription.py` | 143 | YooKassa flow | fa merged P1.5b | **P1** |
| `app/handlers/subscription/devices.py` | 72 | `DEVICE_*`, `CHANGE_DEVICES_*` | Persian but `دستگاه` | **P0** terminology |
| `app/handlers/subscription/traffic.py` | 37 | `TRAFFIC_*` top-up/reset | Persian keys | **P1** |
| `app/handlers/tickets.py` | 71 | `TICKET_*` | All TICKET keys Persian in fa | **P2** — fallbacks only |
| `app/handlers/subscription/my_subscriptions.py` | 52 | `MY_SUB_*` | Persian | **P0** onboarding |
| `app/handlers/menu.py` | 40 | Menu labels | Persian | **P2** |
| `app/handlers/referral.py` | 37 | `REFERRAL_*` | Persian | **P2** |
| `app/handlers/stars_payments.py` | ~20 hardcoded | L378 `Используйте меню…`, L302 description | **Not keyed** | **P1** — wrap with `texts.t` |

### P1 — fa.json user keys still using `تعرفه` (76 keys)

Partial list (full grep: `grep 'تعرفه' app/localization/locales/fa.json | grep -v ADMIN`):

| Key | Line (approx) | Suggested replacement |
|-----|---------------|----------------------|
| `TARIFF_PURCHASE_SUCCESS` | 3926 | `سرویس` |
| `TARIFF_RENEW_SUCCESS` | 3942 | `سرویس` |
| `TARIFF_DAILY_SUCCESS` | 3872 | `سرویس` |
| `TARIFF_CHANGE_SUCCESS` | 3836 | `سرویس` |
| `MAIN_MENU_TARIFF_LINE` | — | `سرویس فعال` |
| `CABINET_PURCHASE_TARIFF_SUCCESS` | 2571 | `سرویس «{name}» فعال شد` |
| `CAMPAIGN_BONUS_TARIFF` | 2595 | `سرویس` |
| `CB_*_TARIFF_*` (15 keys) | 2614–2694 | `سرویس` in user error messages |
| `MINIAPP_TARIFF_SWITCH_*` | — | `سرویس` |

**Commit:** single `i18n/fa): user-facing تعرفه → سرویس (success + errors)` — fa.json only (extends `i18n/fa-remaining` Task 7).

### P1 — fa.json English-only user keys (44)

Acceptable (platform brands): `DEVICE_GUIDE_IOS`, `HAPP_PLATFORM_*`, `PAYMENT_METHOD_STARS_NAME`, `PAYMENT_TELEGRAM_STARS`, `TOP_UP_STARS`.

Needs Persian wrapper text: `FAQ_HEADER` (L fa.json) — add Persian title; keep Latin FAQ acronym optional.

### P2 — Cabinet API (`app/cabinet/routes/**`)

| Route module | Status | Follow-up |
|--------------|--------|-----------|
| `subscription_modules/purchase.py` | Jalali + fa messages | Device terminology in response `*_label` fields |
| `devices.py` | `CABINET_DEVICES_*` keys | `دستگاه` → `تعداد کاربر` in fa.json |
| `withdrawal.py` | `/100` display (known) | Out of i18n unless parity requested |

### P2 — Miniapp (`app/webapi/routes/miniapp.py`)

| Lines | Issue | Fix |
|-------|-------|-----|
| 4024–4028 | `MINIAPP_TRIAL_ACTIVATED` fallback Russian | Ensure fa key; fallback English |
| 3942, 3977 | `refund_description` hardcoded Russian | Key or English literal |
| `_t(user, ...)` pattern | Consistent | Pass `language=user.language` on all `format_price` labels |

---

## 4. «دستگاه» → «تعداد کاربر» migration

### Terminology rules

| Context | Replace | Keep `دستگاه` |
|---------|---------|---------------|
| Subscription limit (HWID slots) | `تعداد کاربر` / `👥 تعداد کاربر: {n}` | Physical device in Happ guide («گوشی شما») |
| «Connected devices» (HWID list) | `کاربران متصل` or `اتصال‌های فعال` | — |
| Happ download / platform picker | `گوشی» / `پلتفرم` | `DEVICE_GUIDE_*` English platform names OK |
| Admin / admin-notify | **Out of scope** for user migration | Admin English track |

### Bot `fa.json` — user-facing keys (147 keys)

Full list from audit (`grep دستگاه app/localization/locales/fa.json` excluding `ADMIN_*`):

**Purchase / success / tariff (P0):**
- `TARIFF_TRAFFIC_STEP_HEADER` (3865)
- `TARIFF_PURCHASE_SUCCESS` (3926)
- `TARIFF_RENEW_SUCCESS` (3942)
- `TARIFF_DAILY_SUCCESS` (3872)
- `TARIFF_CHANGE_SUCCESS` (3836)
- `TARIFF_INFO_HEADER` (3882)
- `TARIFF_INFO_DEVICES_LINE`, `TARIFF_CUSTOM_DEVICES`, `TARIFF_PURCHASE_CONFIRM*` — lines ~3885–3920
- `PURCHASE_CART_DEVICES_LINE`, `SUBSCRIPTION_ORDER_*_DEVICES`, `SUBSCRIPTION_OVERVIEW_DEVICES_LINE`

**my_subscriptions / devices (P0):**
- `MY_SUB_BTN_DEVICES` (3098), `MY_SUB_BTN_MANAGE_DEVICES`, `MY_SUB_BTN_BUY_DEVICES`
- `MY_SUB_DETAIL_DEVICES` (3106), `MY_SUB_DEVICES_LINE`, `MY_SUB_DEVICES_COUNT_SHORT`
- `CHANGE_DEVICES_*` (2698–2705), `DEVICE_CHANGE_*` (2826–2839)
- `DEVICES_*`, `DEVICE_MANAGEMENT_*`, `DEVICE_WORD_*` (2802–2886)
- `MANAGE_DEVICES_BUTTON`, `SELECT_DEVICES`, `RESET_*_DEVICES_*`

**Cabinet API keys in fa.json (P1):**
- `CABINET_DEVICES_*` (2545–2564), `CABINET_TARIFF_SWITCH_DEVICES_RESET`

**Miniapp (P1):**
- `MINIAPP_PURCHASE_BREAKDOWN_DEVICES`, `MINIAPP_PURCHASE_DISCOUNT_DEVICES`, `MINIAPP_RENEWAL_STATUS_NOTE`

**Monitoring (user-facing, P1):**
- No user `NOTIFY_*` keys contain `دستگاه` (admin notify keys do — skip)

**Campaign / webhook (P2):**
- `CAMPAIGN_BONUS_*`, `WEBHOOK_DEVICE_*`, `AUTO_PURCHASE_DEVICES_SUCCESS`

### Bot handlers — hardcoded or fallback «устройств/Девайс» (update fa.json + fallbacks)

| File | Lines | Notes |
|------|-------|-------|
| `app/handlers/subscription/tariff_purchase.py` | 389, 393 | `دستگاه` in `TARIFF_TRAFFIC_STEP_HEADER` fallback |
| `app/handlers/subscription/devices.py` | grep `دستگاه` | 72 Cyrillic fallbacks — update fa keys first |
| `app/handlers/subscription/my_subscriptions.py` | 167–178, 648 | `MY_SUB_DETAIL_DEVICES` fallback `Устройства` |
| `app/keyboards/inline.py` | grep `DEVICE` | Device count keyboard labels (`fe607943` done — re-audit) |

### Cabinet `cabinet/src/locales/fa.json` — user sections (96 paths)

Complete paths (exclude `admin.*`):

```
successNotification.devicesAdded, .devicesPurchased.title, .totalDevices
dashboard.devicesUsed, .devicesShort, .expired.devices, .deviceLimitReached,
  .connectDevice, .devicesConnectedUnlimited
subscription.devices*, .extraDevices*, .buyDevices, .getConfig, .selectDevices,
  .perDevice, .stepDevices, .trial.devices*, .connection.selectDevice,
  .connection.yourDevice, .additionalOptions.*Device*, .revoke.*,
  .confirmDelete*, .myDevices, .noDevices, .renameDevice*, .devicesFree*,
  .perExtraDevice, .cta.activeHint
info.deviceDiscount
onboarding.steps.connectDevices.*
merge.devices, landing.devices, gift.devices*, gift.deviceCount*
```

**Suggested TSX keys mapping:**

| Current | Proposed |
|---------|----------|
| `subscription.devices` | `تعداد کاربر` |
| `subscription.stepDevices` | `تعداد کاربر` |
| `dashboard.devicesUsed` | `کاربر: {{used}} از {{total}}` |
| `subscription.myDevices` | `اتصال‌های فعال` |
| `subscription.getConfig` | `دریافت لینک اتصال` |

### Miniapp API messages

Mirror `CABINET_DEVICES_*` / `MINIAPP_*` fa.json changes; no separate Russian strings in production if keys populated.

---

## 5. Confusing / misleading Persian copy analysis

### User-reported examples

| # | Current text | Why confusing | Proposed replacement | Keys / files |
|---|--------------|---------------|----------------------|--------------|
| 1 | `📦 تانل مولتی لوکیشن` + `حجم سرویس: 📊 حجم: 1 گیگ` | «حجم» twice; emoji overload | `📦 تانل مولتی‌لوکیشن\n📊 حجم: 1 گیگابایت` — pass `{traffic}` without nested label | `TARIFF_TRAFFIC_STEP_HEADER`, `tariff_purchase.py:386–393` |
| 2 | `📱 دستگاه: 5` | «دستگاه» = hardware; VPN sellers use «کاربر» for HWID limit | `👥 تعداد کاربر: 5` | All keys in §4 |
| 3 | `📊 حجم را انتخاب کنید` (alone) | Implies only custom input; screen shows **preset GB buttons** (10/20/30 گیگ…) — tap one → period step; «حجم دلخواه» is optional | `\n\n📊 <i>یکی از گزینه‌های حجم را انتخاب کنید؛ سپس مدت زمان را انتخاب می‌کنید</i>` — say **انتخاب کنید**, not «بزنید»; **مدت زمان**, not «مدت اشتراک» | `TARIFF_CUSTOM_TRAFFIC_STEP_HINT` |
| 4 | `🎉 اشتراک با موفقیت فعال شد!` + `📦 تعرفه:` | «تعرفه» technical; inconsistent with «سرویس» branding | `سرویس` + celebration line | `TARIFF_PURCHASE_SUCCESS` |
| 5 | `برای اتصال به «اشتراک» بروید` | Which menu? «اشتراک» ≠ «اشتراک من»; no steps | See §8 `POST_PURCHASE_ONBOARDING` | `TARIFF_PURCHASE_SUCCESS`, renew/change success keys |
| 6 | `📊 ترافیک:` vs `حجم:` mixed | Iranian users expect «حجم» or «ترافیک» consistently | Pick **حجم** for limits, **مصرف** for usage | Style guide in fa.json commit 0 |
| 7 | `💰 کسر شد` | Sounds punitive | `💰 مبلغ پرداخت:` or `💰 از موجودی کسر شد:` | Success templates |
| 8 | Detail screen: one button, no copy | User lost after first purchase | Onboarding block + «دریافت لینک» CTA | `my_subscriptions.py:644–667` |
| 9 | `SUBSCRIPTION_CONNECT_DEVICE_MESSAGE_HIDDEN` «دستگاه خود را انتخاب کنید» | Implies phone model; means platform guide | `سیستم‌عامل خود را انتخاب کنید (اندروید، آیفون، ویندوز)` | fa.json 3664 |
| 10 | `LISTمیت` / formal tone inconsistent | Sales tone should be warm, short | Review top 20 purchase strings for «شما» + imperative | Copywriting pass P2 |

---

## 6. English digits audit

### Policy

User-facing strings: **Western digits 0–9 only**; comma thousands in amounts via formatters (`format_price`, `useCurrency.ts` with `fa-IR-u-nu-latn`).

### `app/localization/locales/fa.json`

| Scope | Persian digits (۰–۹) count | Action |
|-------|---------------------------|--------|
| User-facing keys | **0** | ✅ |
| Admin keys | **45** | **Skip** per admin-English policy OR fix if admin stays Persian |

### `cabinet/src/locales/fa.json` — user sections (26 hits)

| Path | Line content | Fix |
|------|--------------|-----|
| `auth.passwordTooShort` | `۸ کاراکتر` | `8 کاراکتر` |
| `dashboard.usageLast14Days` | `۱۴ روز` | `14 روز` |
| `subscription.trafficReset.MONTH_ROLLING` | `۳۰ روز` | `30 روز` |
| `subscription.connection.installApp` | `۱.` `۲.` `۳.` | `1.` `2.` `3.` |
| `subscription.tvQuickConnect.description` | `۵ رقمی` | `5 رقمی` |
| `subscription.tvQuickConnect.badCode` | `۵ رقمی` | `5 رقمی` |
| `referral.partner.stats.dailyChart` | `۳۰ روزه` | `30 روزه` |
| `referral.partner.fields.desiredCommissionPlaceholder` | `۱ تا ۱۰۰` | `1 تا 100` |
| `landing.periodLabels.d1`–`d456` | Persian digits | Latin digits (14 keys) |
| `news.admin.toolbar.heading1–3` | admin — skip | — |

**Guard:** extend `tests` or `cabinet` lint script: `rg '[۰-۹]' cabinet/src/locales/fa.json` excluding `admin.` paths → CI fail.

### Formatters / Jalali

| File | Status |
|------|--------|
| `app/utils/jalali_datetime.py` | Uses `jdatetime`; output format `DD.MM.YYYY` with Latin digits — **OK** |
| `app/localization/texts.py` `format_traffic` | L275–276 `{gb:.0f} گیگ` — Latin — **OK** |
| `cabinet/src/hooks/useCurrency.ts` | L60, L74 `fa-IR-u-nu-latn` — **OK** |
| `cabinet/src/utils/formatDate.ts` | Verify Jalali path uses Latin (P1 Jalali branch) |

### Dynamic risk

`toLocaleString('fa-IR')` **without** `u-nu-latn` → Persian digits. Grep cabinet: only `useCurrency.ts` uses fa-IR — correct.

---

## 7. Admin / English priority track (separate)

### Current state

- Admin handlers: **~1,715** `texts.t(..., Cyrillic)` calls; `fa.json` has Persian for most `ADMIN_*` keys (P2 done).
- User policy: **do not invest in Persian admin**; prefer **English** for operators.
- `en.json`: complete vs `ru.json` (0 missing); 12 extra keys.

### Simple English-first fixes

| Priority | File | Lines (sample) | Action |
|----------|------|----------------|--------|
| P0 | `app/handlers/admin/main.py` | menu callbacks | `texts = get_texts('en')` at router level |
| P1 | `app/handlers/admin/users.py` | 460 fallbacks | English fa.json not needed if `get_texts('en')` |
| P1 | `app/handlers/admin/tariffs.py` | 163 | same |
| P1 | `app/handlers/admin/backup.py` | 31–240 | Cyrillic fallbacks; `en.json` has `ADMIN_BACKUP_*` |
| P2 | `app/handlers/admin/remnawave.py` | 603 Cyrillic in stat bodies | Large strings — use `en.json` |
| P2 | `cabinet/src/locales/en.json` | admin.* | Already English — wire admin UI to `en` |
| P2 | Admin notifications | `AdminNotificationService` | **Keep Persian** per `fa-i18n-status.mdc` decision table |

### Missing en keys

`en` vs `ru`: **0 missing**. Extra 12 en keys — verify not user-facing.

### Russian still visible to admin when

1. `get_texts(user.language)` with `user.language=fa` — shows Persian admin (current).
2. Key missing in en → falls back to ru (after §2 fix, en admin should use `get_texts('en')` only).

**Branch:** `i18n/admin-english-default` — separate from user fa work.

---

## 8. Onboarding / guidance gaps

### Purchase success → connection flow

**Current path:**
1. `TARIFF_PURCHASE_SUCCESS` → vague «به اشتراک بروید»
2. User opens «اشتراک من» → detail (`my_subscriptions.py:644–667`) → optional `MY_SUB_BTN_CONNECT_LINK`
3. `links.py` / `SUBSCRIPTION_CONNECT_DEVICE_MESSAGE` — better but not auto-shown

**Gaps:**
- No numbered steps on success message
- No deep-link button in success reply (only text)
- Detail keyboard may show single action without instruction block

### Proposed new `fa.json` keys

| Key | Persian value (draft) | Handler |
|-----|----------------------|---------|
| `POST_PURCHASE_ONBOARDING` | `✅ <b>۳ گام تا اتصال:</b>\n1️⃣ منو → <b>اشتراک من</b>\n2️⃣ دکمه <b>🔗 دریافت لینک</b>\n3️⃣ لینک را در اپ VPN (مثل v2rayNG یا Streisand) وارد کنید\n\n💬 سوالی بود؟ پشتیبانی را بزنید.` | Append to `TARIFF_PURCHASE_SUCCESS` |
| `MY_SUB_DETAIL_ONBOARDING` | Short version for detail screen first line | `my_subscriptions.py` after L652 |
| `MY_SUB_DETAIL_FIRST_CONNECT` | `هنوز وصل نشده‌اید؟ دکمهٔ زیر را بزنید 👇` | When `connected_devices == 0` |
| `MY_SUB_BTN_SETUP_GUIDE` | `📖 آموزش اتصال` | New keyboard row |
| `TARIFF_PURCHASE_SUCCESS_CTA` | Replace last line of success keys | All `TARIFF_*_SUCCESS` |

### Handlers to touch (later implementation)

| Handler | Change |
|---------|--------|
| `tariff_purchase.py` | Success `edit_text` — append `POST_PURCHASE_ONBOARDING`; add inline «اشتراک من» `callback_data` |
| `purchase.py` | Classic mode success — same pattern |
| `my_subscriptions.py` | Detail template + conditional onboarding; widen connect CTA |
| `links.py` | Ensure early `callback.answer()` + platform guide |
| `simple_subscription.py` | `SIMPLE_SUB_PAYMENT_CONNECT_HINT` — align wording |
| Cabinet `subscription/connection/*` | Steps 1–3 already at `subscription.connection.*` — fix digits §6 |

### Other menus needing hand-holding

| Menu | Issue | Key / fix |
|------|-------|-----------|
| Balance top-up | C2C vs gateway — OK | — |
| Traffic top-up | Technical | `TRAFFIC_TOPUP_*` add one-line explainer |
| Device limit increase | «دستگاه» | Terminology §4 |
| Referral withdraw | Mostly done | optional |
| Happ download | Platform names English | OK |

---

## 9. Implementation phases (ordered commits)

### Branch map

| Phase | Branch | Base |
|-------|--------|------|
| 0 | `fix/force-default-language-when-disabled` | merge after user smoke |
| 1 | `i18n/fa-en-ru-fallback` | `main` |
| 2 | `i18n/fa-device-terminology-bot` | `main` |
| 3 | `i18n/fa-copy-purchase-success` | `main` |
| 4 | `i18n/fa-onboarding-my-sub` | `main` |
| 5 | `i18n/fa-traffic-step-ux` | `main` |
| 6 | `i18n/fa-tariff-to-service-json` | `main` |
| 7 | `i18n/fa-cabinet-device-terminology` | `main` |
| 8 | `i18n/fa-cabinet-latin-digits` | `main` |
| 9 | `i18n/fa-miniapp-parity` | `main` |
| 10 | `i18n/admin-english-default` | `main` (separate PR) |
| 11 | `i18n/monitoring-notifications` | existing branch — merge |

### Commit sequence (one concern each)

| # | Commit message | Files |
|---|----------------|-------|
| 1 | `fix(i18n): fa user fallback chain en before ru` | `loader.py`, `texts.py`, `tests/localization/test_texts_fallback.py` |
| 2 | `i18n(fa): rename user device limit to تعداد کاربر in fa.json (purchase)` | `fa.json` — `TARIFF_*_SUCCESS`, `TARIFF_TRAFFIC_STEP_HEADER`, `TARIFF_INFO_*` |
| 3 | `i18n(fa): purchase success onboarding copy` | `fa.json` — `POST_PURCHASE_ONBOARDING`, update `TARIFF_PURCHASE_SUCCESS` |
| 4 | `i18n(fa): fix duplicate traffic label in tariff traffic step` | `tariff_purchase.py:386–393`, `fa.json` `TARIFF_TRAFFIC_VOLUME_BTN` |
| 5 | `i18n(fa): my_subscriptions onboarding block` | `my_subscriptions.py`, `fa.json` `MY_SUB_DETAIL_ONBOARDING`, `MY_SUB_BTN_SETUP_GUIDE` |
| 6 | `i18n(fa): device terminology devices.py` | `devices.py` + `fa.json` `CHANGE_DEVICES_*`, `DEVICE_*` |
| 7 | `i18n(fa): my_subscriptions device labels` | `fa.json` `MY_SUB_DETAIL_DEVICES`, `MY_SUB_DEVICES_*` |
| 8 | `i18n(fa): user تعرفه → سرویس in fa.json` | `fa.json` only (~76 keys, user prefixes) |
| 9 | `i18n(fa): cabinet user device terminology` | `cabinet/src/locales/fa.json` subscription/dashboard/gift |
| 10 | `i18n(fa): cabinet user Latin digits` | `cabinet/src/locales/fa.json` (26 user paths) |
| 11 | `i18n(fa): miniapp trial message parity` | `miniapp.py`, `fa.json` |
| 12 | `i18n(fa): stars_payments user strings` | `stars_payments.py`, `fa.json` |
| 13 | `i18n(fa): connect flow platform wording` | `fa.json` `SUBSCRIPTION_CONNECT_*` |
| 14 | `i18n(admin): default admin handlers to English` | `admin/main.py` or middleware — **separate PR** |
| 15 | `test(i18n): guard Persian digits in user fa strings` | `tests/test_fa_digit_policy.py` |

**Parity rule:** Commits 2–3, 6–8 require bot; commits 9–11 require cabinet/miniapp per `user-surface-parity.mdc`. If single-file policy blocks, note in PR: «cabinet follow-up» or combine 9+10 per surface.

**Deploy after fa.json:** `cp app/localization/locales/fa.json ./locales/fa.json && docker compose restart bot`

---

## 10. Verification checklist

### Agent smoke (every commit)

```bash
docker compose run --rm --no-deps bot python -c "import main"
grep -r get_admin_texts app/   # must be 0
pytest tests/localization/test_texts_fallback.py -q
```

### Fallback chain

```bash
docker compose run --rm --no-deps bot python -c "
from app.localization.texts import get_texts
t = get_texts('fa')
# Key only in en — should NOT be Russian after phase 1
print(t.t('NONEXIST_TEST_KEY', 'fallback'))
"
```

### Digit guards

```bash
python3 -c "
import json,re,sys
fa=json.load(open('app/localization/locales/fa.json'))
bad=[k for k,v in fa.items() if isinstance(v,str) and re.search(r'[۰-۹]',v) and not k.startswith('ADMIN')]
sys.exit(len(bad))
"
rg '[۰-۹]' cabinet/src/locales/fa.json | rg -v 'admin\.'
```

### دستگاه migration

```bash
rg 'دستگاه' app/localization/locales/fa.json | rg -v '^  \"ADMIN_' | wc -l   # target → 0 user keys
rg 'دستگاه' cabinet/src/locales/fa.json | rg -v 'admin' | wc -l
```

### User smoke scenarios (operator)

1. **New user purchase:** `/start` → buy tariff → traffic step shows no duplicate «حجم»; «تعداد کاربر» not «دستگاه»
2. **Success message:** numbered onboarding; button to «اشتراک من»
3. **my_subscriptions detail:** onboarding visible; «دریافت لینک» works; Jalali dates
4. **Cabinet web:** subscription page — terminology + Latin digits in steps 1–2–3
5. **Miniapp trial:** Persian/English, not Russian
6. **Missing fa key test:** temporarily remove a key — user sees English, not Russian
7. **Admin panel:** English UI (after admin track)
8. **Monitoring:** expiring notification — Persian + Jalali date (after monitoring branch merge)

### Regression

- Toman amounts: `100,000 تومان` comma grouping
- Callback spinner: early `callback.answer()` in purchase/tariff flows
- C2C / partner plugins untouched in i18n commits

---

## Appendix A — Related branches (awaiting merge)

| Branch | Status |
|--------|--------|
| `fix/force-default-language-when-disabled` | fa→ru safe fallback; user smoke pending |
| `i18n/monitoring-notifications` | Done; user smoke pending |
| `i18n/fa-jalali-dates` | Done; user smoke pending |
| `i18n/fa-remaining` | Tasks 9–10 deferred (banSystem, admin.settings) |
| `i18n/p1-remainder-b` | Awaiting smoke |

## Appendix B — Tool commands used in this audit

```bash
# fa.json quality
python3 scripts/compare_locales.py  # inline audit: fa cyrillic=0, missing vs ru=0

# Handler fallbacks
rg "texts\.t\([^)]*[А-Яа-я]" app/handlers --glob '!admin/**' --glob '!balance/**' -c

# Terminology
rg -n 'دستگاه' app/localization/locales/fa.json
rg -n 'دستگاه' cabinet/src/locales/fa.json

# Digits
rg '[۰-۹]' app/localization/locales/fa.json
rg '[۰-۹]' cabinet/src/locales/fa.json
```

---

*Generated: 2026-06-23 by fa-i18n audit session. Update `fa-i18n-status.mdc` after implementation phases begin.*
