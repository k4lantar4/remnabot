# Traffic units and traffic add-on texts in the user's language (F-036, F-037, F-040, F-041)

- **Status:** active
- **Repos:** remnabot only (no endpoint/field changes; `frontend/src/api` needs nothing — the
  cabinet already prints `detail` / `description` strings as received)
- **Upstream basis:** remnabot `origin/main` 0b5ec3ff (upstream `v4.10.0`, 9fcebfd7)
- **Branch / worktree:** `fix/traffic-units-i18n` · `remnabot/.claude/worktrees/traffic-units-i18n`
- **PR:** one PR, `fix(F-036, F-037, F-040, F-041): traffic units and add-on texts in the user's language`

## Goal

B2C and partners alike: a fa user never sees «ГБ / ТБ / безлимит», «Докупка N ГБ трафика» or an
empty «📱 دستگاه‌ها:  / 2» line — in the bot's tariff screens, the miniapp tariff cards, and the
cabinet's traffic add-on (balance history + errors). ru output stays byte-for-byte what it is today.

## Design

Traffic amounts become locale keys read in the user's language; nothing about prices, scales or
flows changes.

- **One formatter.** `Texts.format_traffic` changes from a `@staticmethod` to an instance method
  that reads three new keys through `self.t`. Every app caller already uses the `texts.` receiver
  (34 calls), so they need no edit. The bare `app.utils.formatting.format_traffic` (hard-coded
  «Безлимит» / «ГБ», 26 calls in `tariff_purchase.py` and `admin/tariffs.py`) gets no more callers:
  those sites switch to `texts.format_traffic`. The function stays in `formatting.py` untouched
  (upstream file, keeping the diff small). Side effect, accepted: those screens now show ≥1024 GB
  as TB («2.0 ترابایت») and unlimited as «∞ (نامحدود)», like the rest of the bot.
- **Removing a template line independent of language.** When device selection is off, the device
  line is found by its placeholder, not by the Russian literal.
- **Miniapp** reuses the cabinet's existing keys `CABINET_TARIFF_TRAFFIC_GB` /
  `CABINET_TARIFF_TRAFFIC_UNLIMITED` (see `app/cabinet/routes/subscription_modules/purchase.py:235-237`)
  and `TRAFFIC_UNLIMITED_SHORT`.
- **Transaction descriptions** for traffic add-ons are localized **at write time** in
  `user.language`. Precedent: `app/cabinet/routes/balance.py:303,432` (Stars/CryptoBot invoice
  descriptions). The general "store a key or localize at render time" question for *all*
  transaction types is F-019, still open; this plan doesn't settle it, it only stops writing new
  Russian rows for traffic.

Out of scope (don't touch): F-038 (classic bot traffic screens `handlers/subscription/traffic.py`,
`common.py` `format_traffic_display`, `keyboards/inline.py:2649,2717` «₽»);
`admin_notification_service._format_traffic` (admin chat, Russian by design); the other Russian
strings in `admin/tariffs.py` (F-009 admin part); the cabinet devices add-on (F-053);
`formatters.format_traffic_usage` (already language-aware).

## Vs. upstream

- **Ours:** fa wording and the language-aware formatter. `texts.py`, `purchase.py` and
  `tariff_purchase.py` are hot files, so keep the edits there to swapping calls in place. The one
  new helper goes into a fork-owned file (`app/utils/template_lines.py`), not into a hot file.
- **Reused as-is:** `Texts.t` / `get_texts`, the locale loader, the existing cabinet traffic keys,
  `subtract_user_balance`.
- **Gateways:** none touched, and no deferred gateway is enabled or depended on.

## Global rules for every task

- New key → all five baked locales `app/localization/locales/{ru,en,ua,fa,zh}.json` **and** the
  runtime copies `locales/{ru,en,fa}.json`, byte-identical (`cmp`). ru carries today's Russian
  literal exactly; ua gets Ukrainian; zh may carry the English text.
  `tests/test_locale_integrity.py` enforces identical key sets and that every
  `texts.t(key, 'default')` key exists.
- Every `texts.t(KEY, default)` default = the current Russian literal, so a missing key never
  regresses ru.
- fa: Latin digits; «گیگ» for GB (the wording already used in 20+ fa keys), «ترابایت» for TB,
  «نامحدود» for unlimited. Write natural Persian, not a word-for-word copy of the English.
- Tests: `uv run python -m pytest`, run in the worktree. Lint: `ruff format --check .` and
  `ruff check .`.

## Tasks

### 1. `Texts.format_traffic` in the user's language (F-036, part 1)

- **Files:** `app/localization/texts.py:260-272`; all 8 locale files; test
  `tests/localization/test_format_traffic_i18n.py` (new); update
  `tests/test_device_limit_display.py:26` (it calls `Texts.format_traffic(0, …)` on the class →
  `get_texts('ru').format_traffic(0, is_limit=True)`).
- **Interfaces — produces:** `Texts.format_traffic(self, gb: float, is_limit: bool = True) -> str`
  (same name, arguments and rules: `0` + `is_limit` → unlimited, `0` + not a limit → zero amount,
  `>= 1024` → TB with one decimal, else GB with no decimals). New keys:
  - `TRAFFIC_AMOUNT_GB` — ru `{value} ГБ` · en `{value} GB` · fa `{value} گیگ` · ua `{value} ГБ` · zh `{value} GB`
  - `TRAFFIC_AMOUNT_TB` — ru `{value} ТБ` · en `{value} TB` · fa `{value} ترابایت` · ua `{value} ТБ` · zh `{value} TB`
  - `TRAFFIC_LIMIT_UNLIMITED` — ru `∞ (безлимит)` · en `∞ (unlimited)` · fa `∞ (نامحدود)` · ua `∞ (безліміт)` · zh `∞ (unlimited)`
  `{value}` is the already-formatted number (`f'{gb:.0f}'` / `f'{gb / 1024:.1f}'`).
- **Test first:** fa `50 → '50 گیگ'`, `2048 → '2.0 ترابایت'`, `(0, True) → '∞ (نامحدود)'`,
  `(0, False) → '0 گیگ'`; ru returns exactly today's strings (`'50 ГБ'`, `'2.0 ТБ'`,
  `'∞ (безлимит)'`, `'0 ГБ'`); en `'50 GB'`.
- **Commit:** `fix(F-036): format traffic amounts in the user's language`

### 2. Move the bare `format_traffic` callers to `texts.format_traffic` (F-036, part 2)

- **Files:** `app/handlers/subscription/tariff_purchase.py` (import line 34; calls at 498, 744,
  951, 1517, 1692, 2201, 2513, 2788, 2887, 3178, 3548, 3711, 4024, 4319, 4746-4747, 5337, 5459 —
  `texts` is already in scope in every enclosing function); `app/handlers/admin/tariffs.py`
  (import line 32; calls at 789, 827, 867, 903, 941, 1166 have `texts` in scope;
  `format_tariff_info` (def 275, call 280) has only `language` → `get_texts(language)`;
  `process_tariff_prices` (def 962, call 985) has no `texts` → `get_texts(db_user.language)`).
  Take `format_traffic` out of both `from app.utils.formatting import …` lines. Line numbers are
  from 0b5ec3ff; re-find them with `git grep -n 'format_traffic(' app/handlers`.
- **Interfaces — consumes:** `Texts.format_traffic` from Task 1.
- **Test first:** `tests/handlers/test_tariff_traffic_label_i18n.py` (new) —
  `format_tariff_info_for_user(tariff, language='fa')` (tariff_purchase.py:490) with
  `traffic_limit_gb=50` contains `50 گیگ` and no `ГБ`; with `0` it contains `نامحدود`. Check
  `tests/handlers/test_admin_tariff_custom_traffic*.py` still pass (they may pin «ГБ» for ru — ru
  must be unchanged).
- **Commit:** `fix(F-036): tariff screens use the language-aware traffic formatter`

### 3. Drop the device line in any language (F-037)

- **Files:** `app/utils/template_lines.py` (new) + `tests/utils/test_template_lines.py` (new);
  `app/handlers/subscription/purchase.py:505-509` (`show_subscription_info`, placeholder
  `{devices_used}`) and `:3002-3006` (settings overview, same placeholder).
- **Interfaces — produces:** `strip_template_line(template: str, placeholder: str) -> str` —
  removes every line that contains `placeholder`, together with its newline; returns the template
  unchanged when there is no such line.
- **Test first:** unit cases (middle line, last line, absent placeholder); and the real fa
  templates: `strip_template_line(get_texts('fa').t('SUBSCRIPTION_OVERVIEW_TEMPLATE'), '{devices_used}')`
  contains no `دستگاه‌ها`, and the same for `SUBSCRIPTION_DAILY_OVERVIEW_TEMPLATE` and
  `SUBSCRIPTION_SETTINGS_OVERVIEW`; the result still `.format()`s with the other placeholders.
- **i18n:** none.
- **Commit:** `fix(F-037): hide the device line in every language when device selection is off`

### 4. Miniapp traffic labels (F-040)

- **Files:** `app/webapi/routes/miniapp.py` — `_format_traffic_limit_label` (6328) and
  `_format_limit_label` (538) gain `language: str`; callers at 3688-3690 (`_get_current_tariff_model`;
  the non-tariffs branch `f'{…} ГБ'` uses the same helper), 6444 (`_build_tariff_model`), 6492
  (`_build_current_tariff_model`) pass `(user.language if user else None) or settings.DEFAULT_LANGUAGE`
  (`user` defaults to `None` there); 3478 (`get_subscription_details`) passes the resolved DB
  user's language. Test `tests/webapi/test_miniapp_traffic_labels.py` (new).
- **Interfaces — consumes:** existing keys `CABINET_TARIFF_TRAFFIC_GB` (`{traffic}`),
  `CABINET_TARIFF_TRAFFIC_UNLIMITED`, `TRAFFIC_UNLIMITED_SHORT`. **Produces:**
  `_format_traffic_limit_label(traffic_gb: int, language: str) -> str`,
  `_format_limit_label(limit: int | None, language: str) -> str`.
- **Test first:** fa `50 → '50 گیگ'`, `0 → '♾️ نامحدود'` (tariff label) / `'نامحدود'` (limit
  label); ru keeps `'50 ГБ'` / `'♾️ Безлимит'`; en `_format_limit_label(None, 'en') == 'Unlimited'`
  (today's value).
- **i18n:** no new keys.
- **Commit:** `fix(F-040): miniapp traffic labels in the user's language`

### 5. Traffic add-on descriptions and errors (F-041)

- **Files:** `app/cabinet/routes/subscription_modules/traffic.py` — `purchase_traffic` (def 152:
  cart `description` 305, transaction description 334-336) and `save_traffic_cart` (def 456: every
  Russian `detail=` at ~469-525 and cart `description` 557); `app/webapi/routes/miniapp.py`
  `purchase_traffic_topup_endpoint` (7379-7381 description, 7437 `message`);
  `app/services/subscription_auto_purchase_service.py:2098` (description for a traffic cart bought
  after a top-up — `user` is in scope). Use `texts = get_texts(user.language)` once per function
  (already imported in traffic.py). Check the rest of `purchase_traffic` for Russian `detail=` too,
  and include any it has.
- **Interfaces — produces (new keys, all 8 files):**
  - `TRAFFIC_TOPUP_DESCRIPTION` — ru `Докупка {gb} ГБ трафика` · en `Extra traffic: {gb} GB` · fa `خرید {gb} گیگ ترافیک اضافه`
  - `TRAFFIC_TOPUP_DESCRIPTION_DISCOUNT` — ru `Докупка {gb} ГБ трафика (скидка {percent}%)` · en `Extra traffic: {gb} GB ({percent}% off)` · fa `خرید {gb} گیگ ترافیک اضافه ({percent}% تخفیف)`
  - `TRAFFIC_TOPUP_ADDED` — ru `Добавлено {gb} ГБ трафика` · en `{gb} GB of traffic added` · fa `{gb} گیگ ترافیک اضافه شد`
  - `CABINET_TRAFFIC_SUBSCRIPTION_INACTIVE` — ru `Ваша подписка неактивна` · en `Your subscription is not active` · fa `اشتراک فعال نیست`
  - `CABINET_TRAFFIC_TOPUP_TRIAL` — ru `Докупка трафика недоступна на пробном периоде` · en `Extra traffic isn't available during the trial` · fa `در دوره‌ی آزمایشی خرید ترافیک اضافه ممکن نیست`
  - `CABINET_TRAFFIC_ALREADY_UNLIMITED` — ru `У вас уже безлимитный трафик` · en `Your traffic is already unlimited` · fa `ترافیک این اشتراک نامحدود است`
  - `CABINET_TRAFFIC_TARIFF_NOT_FOUND` — ru `Тариф не найден` · en `Tariff not found` · fa `تعرفه پیدا نشد`
  - `CABINET_TRAFFIC_TOPUP_TARIFF_DISABLED` — ru `Докупка трафика недоступна на вашем тарифе` · en `Your tariff doesn't allow extra traffic` · fa `این تعرفه امکان خرید ترافیک اضافه ندارد`
  - `CABINET_TRAFFIC_PACKAGE_UNAVAILABLE` — ru `Пакет трафика {gb} ГБ недоступен` · en `The {gb} GB traffic package isn't available` · fa `بسته‌ی {gb} گیگ در دسترس نیست`
  - `CABINET_TRAFFIC_TOPUP_DISABLED` — ru `Докупка трафика отключена` · en `Extra traffic purchases are turned off` · fa `خرید ترافیک اضافه فعلاً غیرفعال است`
  - `CABINET_TRAFFIC_PACKAGE_INVALID` — ru `Недоступный пакет трафика` · en `This traffic package isn't available` · fa `این بسته‌ی ترافیک در دسترس نیست`
  ua: Ukrainian; zh: English. fa is impersonal (neither «تو» nor «شما»), like the existing cabinet
  errors (`CABINET_INSUFFICIENT_BALANCE`: «موجودی کافی نیست. کسری: {amount}»).
- **Test first:** `tests/cabinet/test_traffic_topup_i18n.py` (new; copy the fixture style from
  `tests/cabinet/test_traffic_packages_discount.py`) — fa user on a trial subscription →
  `save_traffic_cart` raises with the fa `detail`; fa user buying 10 GB → `subtract_user_balance`
  gets `خرید 10 گیگ ترافیک اضافه`; ru user gets exactly today's Russian description.
- **Commit:** `fix(F-041): traffic add-on descriptions and errors in the user's language`

## Finish

Full suite (no new failures vs. the `origin/main` baseline), ruff, `cmp` of the three runtime/baked
locale pairs, rebuild/restart the dev bot, then the `smoke-test-checklist` (cabinet: buy extra
traffic as a fa user → balance history row; tariff cards). Text-only change → `fix-admin` parity
check skipped. `git mv` this plan to `plans/done/` with `Status: done` in the final commit; after
merge, delete F-036, F-037, F-040 and F-041 from `/opt/project/FINDINGS.md` (`git ws commit`).
