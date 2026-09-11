# Remaining Russian in user-facing texts (F-009, part A: users)

**Status:** active
**Repos:** `remnabot` only. The cabinet shows the traffic top-up 402 `detail.message` verbatim
(`frontend/src/components/subscription/sheets/TrafficTopupSheet.tsx:221` via `getErrorMessage`); that is fixed
server-side, so no frontend change.
**Upstream basis:** remnabot `origin/main` `df7bd874`; `upstream/main` `bf33d125` (v4.9.1)
**Kind:** translation (run `fix-translation` / `translation-fixer`); task 2 touches a promo bonus
amount display (payment scale check, see there).
**Origin:** finding F-009 in `/opt/project/FINDINGS.md` (from remnabot#20, #26, #27, #31, #32, #35,
#40, #41). This plan covers the **user-facing** sites. Bot **admin** texts (`admin/campaigns.py`
~160 strings, withdrawal admin/risk texts ~75) stay in F-009 as the remaining part. Referral
level-scheme notifications are task 4 of `2026-09-11-promo-refund-referral-leftovers.md` (F-007),
not here.
**Order:** execute after the F-007 plan's PR has merged (both add keys to the same ten locale files).

## Goal

A Persian user never sees Russian text or `₽` on the remaining user-facing paths: the cabinet's
insufficient-balance errors, the default promo-offer broadcast/email, the withdrawal refusal
reasons, the legacy miniapp messages, and the classic bot subscription screens. B2C and partner alike.

## Design

Hard-coded Russian f-strings become `texts.t(KEY, default)` rendered in the recipient's language.
Where an equivalent key already exists, it is reused instead of adding one. Inventory (verified on
`12f5ffce`; line numbers approximate):

- Cabinet 402 `'Недостаточно средств. Не хватает {…}'`: `app/cabinet/routes/subscription_modules/traffic.py:322`
  (shown verbatim), `:637`, `renewal.py:241`, `purchase.py:848` → the existing
  `CABINET_INSUFFICIENT_BALANCE` key, exactly as `app/cabinet/routes/servers.py:207` uses it. Keep
  `code`/`missing_amount` fields unchanged (the frontend reads them).
- Promo default message `app/cabinet/routes/admin_promo_offers.py` `_build_default_promo_message`
  (~535-551) and the default button `'🎁 Получить'` (~738): one text for the whole broadcast, so
  it's rendered with `settings.DEFAULT_LANGUAGE` (per-recipient rendering would need a broadcast
  redesign, out of scope).
- Withdrawal user-facing refusal reasons: `app/services/referral_withdrawal_service.py` ~213, ~251
  (`'…через {days_left} дн.'`), ~255, shown in bot `referral.py:733/778` and cabinet `withdrawal.py:34`.
- Legacy miniapp: `app/webapi/routes/miniapp.py` trial message (~4088-4101),
  `_build_renewal_status_message` (~4539), promo payload message (~4556),
  `_build_renewal_success_message` (~4594-4606), discount line (~4625). `app/utils/formatters.py`
  ~218/244/260: `language_code in {'ru','fa'}` → Russian is **dead code** outside tests; change the
  check to `== 'ru'` (no keys).
- Classic bot screens (reachable only via old messages / stray callbacks in cabinet mode):
  `app/handlers/subscription/purchase.py` `show_subscription_info` tariff block (~376-440, incl.
  `Цена: … ₽/день`), «(за N дн.)» in `countries.py:339`, `traffic.py:879/895/896`,
  `devices.py:388/394/1591/1718-1723`, `common.py:601`, and `confirm_extend_subscription`
  (`purchase.py:1868`, returns early in tariffs mode, cheap to do anyway).

Out of scope: bot admin texts (F-009 remainder), the ~47 other Russian `detail=` strings in cabinet
routes that nobody has reported (not in F-009), transaction descriptions (F-019).

## Vs. upstream

- Ours: Persian-first i18n. Edits are text substitutions in upstream files; `purchase.py` is a hot
  file, so keep each change to the string itself (no restructuring).
- Reused as-is: `get_texts` / `texts.t`, `CABINET_INSUFFICIENT_BALANCE`, `DEVICE_CHANGE_EXTRA_COST`,
  `SUBSCRIPTION_TIME_LEFT_DAYS` / `AUTOPAY_PERIOD_VALUE`, `DAILY_SUBSCRIPTION_PAUSED`,
  `TARIFF_PURCHASE_PRICE_PER_DAY`, `NO_ACTIVE_SUBSCRIPTION`, `ACTIVATION_RENEW_SUCCESS` (check each
  one's placeholders before reuse).
- No deferred gateway touched or depended on.

**i18n rule for every task:** a new key goes into all five baked locales
`app/localization/locales/{ru,en,ua,fa,zh}.json` (ru keeps today's Russian; ua/zh may carry
English) **and** the runtime copies `locales/*.json`, kept byte-identical (`cmp`), or
`tests/test_locale_integrity.py` turns red. Persian: natural everyday wording, Latin digits,
`تومان` from the formatter rather than hard-coded. Amounts go through `settings.format_price`
(catalog) / `settings.format_balance` (wallet), never `/ 100` + `₽`.

## Tasks

### 1. Cabinet insufficient-balance errors
- **Files:** `app/cabinet/routes/subscription_modules/traffic.py`, `renewal.py`, `purchase.py`;
  test `tests/cabinet/test_insufficient_balance_messages.py` (new, or next to an existing traffic
  top-up route test).
- **Test first:** a traffic top-up with too little balance for a `fa` user returns 402 whose
  `message` has no Cyrillic and names the missing Toman amount; `code` stays `insufficient_funds`.
- **i18n:** none new (reuse `CABINET_INSUFFICIENT_BALANCE`).

### 2. Default promo-offer message
- **Files:** `app/cabinet/routes/admin_promo_offers.py`; test `tests/cabinet/test_promo_default_message.py`.
- **Scale check first:** find where a claimed offer's `bonus_amount_kopeks` is credited
  (`app/handlers/subscription/promo.py` ~328 and its callees) and render the bonus with the matching
  formatter (`format_balance` if it's credited 1:1). If other displays of the same field disagree
  (`handlers/admin/promo_offers.py:1681`, `services/promo_offer_email.py:69`, miniapp
  `_format_bonus_label`), don't fix them here: add a new `F-` entry (payment) to
  `/opt/project/FINDINGS.md` and list it in the PR body.
- **Test first:** with `DEFAULT_LANGUAGE=fa`, the default text has no Cyrillic and no `₽`, shows
  the percent and hours with Latin digits; the default button label is Persian.
- **i18n:** ~6 keys (`PROMO_OFFER_DEFAULT_TITLE`, `…_DISCOUNT_LINE`, `…_BONUS_LINE`,
  `…_VALID_LINE`, `…_CTA`, `…_BUTTON`).

### 3. Withdrawal refusal reasons shown to the user
- **Files:** `app/services/referral_withdrawal_service.py` (the user-facing reason strings only;
  admin/risk texts stay for the F-009 remainder); test next to
  `tests/services/test_withdrawal_amounts_toman.py`.
- **Test first:** each refusal reason for a `fa` user has no Cyrillic; the «in N days» reason keeps
  the number.
- **i18n:** ~3 keys.

### 4. Legacy miniapp messages and the formatter fallback
- **Files:** `app/webapi/routes/miniapp.py` (the five helpers above), `app/utils/formatters.py`;
  tests `tests/utils/test_formatters_basic.py` (update: `fa` no longer maps to Russian) and a
  miniapp message test (extend an existing one under `tests/webapi/` if present).
- **Test first:** `_build_renewal_success_message` and the trial message for `fa` contain no
  Cyrillic; the formatters return non-Russian output for `fa`.
- **i18n:** ~8 keys.

### 5. Classic bot subscription screens
- **Files:** `app/handlers/subscription/purchase.py` (`show_subscription_info` tariff block,
  `confirm_extend_subscription`), `countries.py`, `traffic.py`, `devices.py`, `common.py`; test
  `tests/handlers/test_subscription_screens_fa.py` (new).
- **Test first:** the tariff block of `show_subscription_info` for a `fa` user with a daily tariff
  has no Cyrillic and no `₽`; the «for N days» label renders via a key.
- **i18n:** ~20-25 new keys, with existing keys reused where the list above allows.

## Smoke test

After implementation: `smoke-test-checklist`. Cabinet surface: task 1 (traffic top-up with too
little balance: hard to reach because the sheet checks the balance first; the checklist says how or
marks it as test-covered only) and task 2 (admin sends a promo offer with an empty text → the user
receives Persian). Tasks 3-5: the withdrawal reasons show in the cabinet withdrawal screen only when
the feature is on; the miniapp and classic bot screens are not in the cabinet.
