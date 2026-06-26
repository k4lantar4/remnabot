# Smoke map — Main menu UX (low-risk)

> Branch `i18n/main-menu-ux-low-risk`; balance in caption, cabinet+wallet paired row, referrals WebApp; awaiting user smoke.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/main-menu-ux-low-risk` |
| Commits | `8b9d163c` fa labels, `25ed64df` caption balance, `3216fbc2` keyboard reorder |
| Files | `fa.json`, `menu.py`, `inline.py`, tests |
| Deploy | `make staging-rebuild` |
| Bot | `@mrj7_bot` (staging) |
| Guard | `uv run pytest tests/handlers/test_main_menu_text.py tests/keyboards/test_main_menu_keyboard_layout.py -v` |

## What changed

- Caption shows `💰 موجودی: …` via `MAIN_MENU_BALANCE_LINE` (not first keyboard row)
- Cabinet + wallet paired below buy / my subscriptions
- Referrals opens cabinet `/referral` WebApp (`🤝 همکاری و دعوت`)
- `menu_info` removed from main menu

## User smoke checklist (`@mrj7_bot`, fa user)

| # | Action | Expected |
|---|--------|----------|
| 1 | `/start` → main menu | Caption shows `💰 موجودی: …` |
| 2 | First action row | NOT balance-only row |
| 3 | Row with `📱 پنل کاربری` + `💳 شارژ موجودی` | Below buy / my subs |
| 4 | Tap `💳 شارژ موجودی` | Balance / top-up flow |
| 5 | Tap `📱 پنل کاربری` | Cabinet mini-app opens |
| 6 | Tap `🤝 همکاری و دعوت` | Cabinet `/referral` with partner CTA |
| 7 | No `ℹ️ اطلاعات` on main menu | `menu_info` absent |
| 8 | Active sub → `اشتراک‌های من` → detail → connect | Unchanged per-sub flow |

## Sign-off

- [ ] User smoke on `@mrj7_bot`
- [ ] Reply **تایید** → `CONFIRM_SHIP=1 make ship BRANCH=i18n/main-menu-ux-low-risk`

---

# Smoke map — Phase 11 admin reports + statistics fix

> Branch `i18n/admin-reports-fa`; reports Persian + stats `*_BODY` keys + delivery resilience; awaiting user smoke.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-reports-fa` |
| Files | `fa.json`, `reporting_service.py`, `reports.py`, `statistics.py`, `config.py`, tests |
| Deploy | `make staging-rebuild` |
| Bot | `@mrj7_bot` (staging) |
| Guard | `uv run pytest tests/test_admin_statistics_i18n.py tests/test_admin_reporting_i18n.py -v` |

## What changed (2026-06-26 fix)

- Reports: preview always in DM; topic delivery best-effort with topic retry + `ADMIN_NOTIFICATIONS_TOPIC_ID` fallback
- Stats: `ADMIN_STATS_*_BODY` keys separate from keyboard labels — summary/users/revenue/referrals show full numbers
- `ADMIN_REPORT_TOPIC_FAILED` Persian toast if topic post fails after preview

## User smoke checklist (`@mrj7_bot`, fa admin)

| Step | Path | Expected |
|------|------|----------|
| 1 | Admin → گزارش‌ها → دیروز | Persian report in chat; no Russian alert (topic fail → Persian warning + preview visible) |
| 2 | Admin reports topic | Report posted if topic configured |
| 3 | Admin → آمار → خلاصه کلی | Full Persian stats with numbers, not label-only |
| 4 | آمار → کاربران / درآمدها / دعوت | Full panel bodies with data |

## Sign-off

- [ ] User smoke on `@mrj7_bot`
- [ ] Reply **تایید** → `CONFIRM_SHIP=1 make ship BRANCH=i18n/admin-reports-fa`

---

# Smoke map — Phase 11 admin reports Persian (initial)

# Smoke map — Phase 10 Slice C gaps (cabinet admin)

> Branch `i18n/admin-fa-slice-c-gaps`; multiline Cyrillic `admin.*` fallbacks + missing fa keys; awaiting user smoke.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-fa-slice-c-gaps` |
| Files | `cabinet/src/locales/fa.json` + 3 `Admin*.tsx` |
| Deploy | `make staging-cabinet-build` |
| Cabinet URL | staging cabinet (`3021` / `staging-host-cabinet`) |
| Guard | `rg -U "t\\(['\\\"]admin\\." cabinet/src` Cyrillic fallbacks = **0** |

## What changed

- Added `admin.promocodes.form.noTrialTariffHint`, `tariffOption`, `admin.promoOffers.form.selectSquadHint` to cabinet `fa.json`
- Replaced hardcoded `устр.` in promocode tariff dropdown with `tariffOption` i18n (`کاربر` label)
- 3 multiline Cyrillic `t('admin.*', …)` fallbacks → English upstream-safe defaults

## User smoke checklist (staging cabinet, fa admin)

| Step | Path | Expected |
|------|------|----------|
| 1 | `/admin/promocodes/create` → type «اشتراک آزمایشی» | Tariff dropdown: `GB، N کاربر`; empty-tariff hint Persian |
| 2 | `/admin/promo-offers/templates/:id/edit` → test squads | Warning when no server selected is Persian |
| 3 | `/admin/payment-methods/:id/edit` | «Open URL directly» hint stays Persian |
| 4 | Regression | `/admin/remnawave`, `/admin/broadcasts/create` unchanged |

## Sign-off

- [x] User smoke on staging cabinet (**تایید** 2026-06-26)
- [x] Shipped PR [#91](https://github.com/k4lantar4/remnabot/pull/91) → `main` @ `31276b98`; prod cabinet deploy

---

# Smoke map — Admin Persian gaps (smoke follow-up)

> Branch `i18n/admin-fa-slice-d` (uncommitted hotfix); re-smoke items 1, 2, 5.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-fa-slice-d` |
| Commits | `0edd37ec` monitoring language · `7308d380` broadcast-by-tariff · `a46fbc7f` bot config |
| Hotfix (local) | `monitoring.py` — `db_user: User` not `data: dict` (crash fix) · `fa.json` `ADMIN_SETTINGS_APP_CONFIG` |
| Bot | `@mrj7_bot` (staging) |
| Deploy | `make staging-rebuild` (2026-06-25, post hotfix) |

## Fixes in this batch

| Issue | Root cause | Fix |
|-------|------------|-----|
| **admin_monitoring does not open** | D3.1 used `data: dict` param — aiogram injects `db_user`, not `data` | Handlers use `db_user: User`; FSM uses `state.get_data()` |
| Force check / monitoring menu Russian | `from_user.language_code` | D3.1 `_admin_language(db_user)` |
| `broadcast_by_tariff` button Russian | Missing key | `ADMIN_BROADCAST_TARGET_BY_TARIFF` — **تایید** |
| `admin_bot_config` Russian | D4 deferred | Localized — **تایید** |
| **`admin_remna_config` button label Russian** | `ADMIN_SETTINGS_APP_CONFIG` missing in fa.json | Added Persian label in settings submenu keyboard |

## User smoke checklist (`@mrj7_bot`, fa admin)

| Step | Path | Expected | Status |
|------|------|----------|--------|
| 1 | Monitoring → force check | Persian result | re-test |
| 2 | Monitoring main menu | Opens + Persian status/stats | re-test |
| 3 | Messages → by sub → **بر اساس سرویس** | Persian button + tariff list | **تایید** |
| 4 | Settings → bot config | Persian dashboard | **تایید** |
| 5 | Settings submenu → **پیکربندی اپلیکیشن‌ها** (`admin_remna_config`) | Persian button label (+ screen from D4) | re-test |
| 6 | FAQ / privacy / offer admin menus | Persian chrome (P2) | optional |

## Sign-off

- [ ] User smoke on `@mrj7_bot`
- [ ] Reply **تایید** to ship or continue D5+

---

# Smoke map — Phase 10 Slice D: bot admin remnawave / broadcast / monitoring

> Branch `i18n/admin-fa-slice-d` @ `5e0e9bc7`; 3 commits (D1–D3); awaiting user smoke.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-fa-slice-d` |
| Commits | `f6a77f5f` remnawave · `e2fe9912` broadcast FSM · `5e0e9bc7` monitoring |
| Files | `app/handlers/admin/remnawave.py`, `messages.py`, `monitoring.py`, `app/localization/locales/fa.json` (+452 keys) |
| Deploy | `make staging-rebuild` + `cp app/localization/locales/fa.json ./locales/fa.json` |
| Bot | `@mrj7_bot` (staging) |
| Locale | `fa` admin (`get_texts(db_user.language)`) |

## fa.json key delta

| Commit | Keys | +new |
|--------|------|------|
| D1 remnawave | 4430 | +252 |
| D2 broadcast | 4500 | +70 |
| D3 monitoring | 4652 | +152 |

## User smoke checklist (staging Telegram, fa admin)

### D1 — Remnawave panel

| Step | Path | Expected |
|------|------|----------|
| System stats | Admin → Remnawave → system stats | Persian labels; Jalali dates where shown |
| Nodes list | Nodes management → node detail | Persian status/connect labels |
| Node stats | Node statistics view | Persian traffic/uptime copy |
| Squads | Squad list → detail | Persian (some FSM bodies may still Cyrillic — known gap) |
| Sync | Sync options / recommendations | Persian menu; sync result bodies may mix |

### D2 — Broadcast FSM

| Step | Path | Expected |
|------|------|----------|
| Menu | Admin → Messages / broadcasts | Persian menu |
| Pinned | Pinned message menu + edit flow | Persian |
| Target picker | By subscription / criteria / history | Persian buttons + history lines |
| Create flow | Message → media → buttons → preview → send | Persian prompts; preview keyboard Persian |
| Progress | Confirm send | Persian progress + result |

### D3 — Monitoring

| Step | Path | Expected |
|------|------|----------|
| Main menu | Admin → Monitoring | Persian status + 24h stats |
| Notify settings | Settings → user notifications | Persian toggles + test buttons |
| Test preview | Send test notification previews | Persian admin chrome; user template from fa.json |
| Traffic settings | Traffic monitoring settings | Persian toggles/thresholds |
| Force check | Force subscription check | Persian result |
| Traffic delta | Manual traffic check | Persian result |
| Logs | Monitoring logs paginated | Persian headers/stats |
| NaloGO | Statistics → receipt queue (if enabled) | Persian labels (partial — reconcile log regex unchanged) |

## Sign-off

- [ ] User smoke on `@mrj7_bot` (**تایید**)
- [ ] Ship PR → merge → prod deploy

## Known gaps (Slice D)

- `remnawave.py`: ~154 `count_hardcoded` lines (squad edit FSM + sync result f-strings) — Cyrillic in `texts.t` fallbacks excluded from metric
- `messages.py`: ~33 lines (multi-line `texts.t` fallback continuations)
- `monitoring.py`: ~112 lines (fallback continuations, logger, YooKassa log parse regex, duplicate nalogo stats block)

---

# Smoke map — Phase 10 Slice C: cabinet admin TSX fallbacks

> Branch `i18n/admin-fa-completion` @ `97d4ee81`; 9 TSX files + remnawave `fa.json` keys; awaiting user smoke.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-fa-completion` |
| Commits | `f58f93de` remnawave · `f318bd13` broadcasts · `ce02c928` user detail · `97d4ee81` partner/promo/payment |
| Files | 9 cabinet admin TSX + `cabinet/src/locales/fa.json` (16 `admin.remnawave.overview` keys) |
| Deploy | `make staging-cabinet-build` |
| Cabinet URL | staging cabinet (`3021` / `staging-host-cabinet`) |
| Guard | `rg "t\\(['\\\"]admin\\." cabinet/src` Cyrillic fallbacks = **0** |

## What changed

- 55 Cyrillic `t('admin.*', '…')` fallbacks → English upstream-safe defaults
- 16 new Persian keys under `admin.remnawave.overview` (active24h, panel health, top consumers, etc.)
- fa admin users still see Persian from `fa.json`; missing keys no longer fall back to Russian

## User smoke checklist (staging cabinet, fa admin)

| Step | Path | Expected |
|------|------|----------|
| Remnawave overview | `/admin/remnawave` → Overview | Persian labels; no Cyrillic |
| Broadcast create | `/admin/broadcasts/create` | Category/button labels Persian; preview modal Persian |
| User subscription | `/admin/users/:id` → Subscription tab | Create/back/device rename Persian |
| Partner detail | `/admin/partners/:id` → campaigns | Registrations/referrals/earnings Persian |
| Promocode create | `/admin/promocodes/create` | Tariff picker Persian |
| Regression | Ban monitoring, pinned messages (Slice B) | Unchanged |

## Sign-off

- [x] User smoke on staging cabinet (**تایید** 2026-06-25; post-fix `c53ff63e` redeployed)
- [ ] Ship with Slice A + remaining Phase 10 slices

### Smoke fixes (`c53ff63e`)

| Issue | Fix |
|-------|-----|
| Broadcast buttons Russian (img 1) | UI uses `admin.broadcasts.btn*` from fa.json, not API `default_text` |
| Filter dropdown Russian (img 2) | `admin.broadcasts.audienceFilters.*` keys; tariff **names** still from DB (e.g. Стандартный) |
| `categoryDesc` Cyrillic | fa key + English fallback |
| `Текущий трафик` / live traffic | `admin.remnawave.traffic.realtimeTitle` in fa.json |
| Subscription dates Persian digits (img 3) | `formatUserDateTime` in admin user detail |
| Promocode dates Persian digits (img 4) | `formatUserDate` in AdminPromocodes |

---

# Smoke map — Phase 10 Slice A: bot admin locale keys (CLOSED)

> Branch `i18n/admin-fa-completion` @ `96133025`; bot `fa.json` only; user smoke **تایید** 2026-06-25.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-fa-completion` |
| Commit | `96133025` — 7 missing `texts.t` keys (C2C inbox back + disabled payment providers) |
| Files | `app/localization/locales/fa.json` |
| Deploy | `make staging-rebuild` (bot image + locale copy) |
| Bot | `@mrj7_bot` (staging) |
| Locale | `fa` admin (`get_texts(db_user.language)`) |

## What changed

- `C2C_ADMIN_INBOX_BACK` → `📥 صندوق ورودی` (was inline default only)
- `PAYMENT_AURAPAY`, `PAYMENT_KASSA_AI`, `PAYMENT_OVERPAY`, `PAYMENT_PAYPEAR`, `PAYMENT_ROLLYPAY`, `PAYMENT_SEVERPAY` → Latin brand labels with `💳` prefix (disabled providers; admin config test buttons)

## User smoke checklist (staging Telegram, fa admin)

| Step | Path | Expected |
|------|------|----------|
| C2C inbox back | Admin panel → C2C inbox → open receipt → tap back | Button `📥 صندوق ورودی` |
| Regression | Cabinet `/admin` (Slice B) | Still Persian — unchanged |
| Regression | User main menu | Still Persian — unchanged |

Payment provider test buttons: optional (providers disabled in `.env`).

## Sign-off

- [x] User smoke on `@mrj7_bot` (**تایید** 2026-06-25)
- [ ] Ship with remaining Phase 10 slices or standalone PR

---

# Smoke map — Phase 10 Slice B: cabinet admin Persian (CLOSED)

> Branch `i18n/admin-fa-completion`; cabinet `fa.json` only; user smoke **تایید** 2026-06-25.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/admin-fa-completion` |
| Commits | `07a7db29` plural/misc (58 keys) · `9902058a` banSystem (148) · `7063e3fe` pinnedMessages + patch tool |
| Files | `cabinet/src/locales/fa.json`, `tools/cabinet_admin_fa_slice_b.py` |
| Deploy | `make staging-cabinet-build` |
| Cabinet URL | staging cabinet (`3021` / `staging-host-cabinet`) |
| Locale | `fa` (admin routes use global i18n; no force-en) |

## What changed

- Cabinet admin `en_only` paths: **206 → 0** (plural `_one`, banSystem, user confirm dialogs, news combobox).
- `banSystem.*` — dashboard, agents, settings, punishments, user detail (Persian).
- `admin.pinnedMessages.*` — was full English leak; now Persian.
- `admin.settings` — already 172/172 Persian (no commit needed).

## User smoke checklist (staging cabinet, fa admin)

| Step | Path | Expected |
|------|------|----------|
| Ban monitoring | `/admin` → نظارت بر مسدودسازی | Tabs/settings Persian |
| Pinned messages | `/admin/pinned-messages` | Create/edit UI Persian |
| User actions | `/admin/users` → delete/disable confirm | Persian dialogs |
| Regression | `/subscription` (user) | Unchanged Persian user UI |

## Sign-off

- [x] User smoke on staging cabinet (**تایید** 2026-06-25)
- [ ] PR → merge → prod deploy (when Phase 10 scope agreed)

---

# Smoke map — Cabinet subscription sheets currency (تومان)

> Branch `fix/cabinet-subscription-sheets-currency`; staging cabinet rebuild only.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `fix/cabinet-subscription-sheets-currency` |
| Commit | `8a65e958` — `useCurrency` in traffic/device/server sheets |
| Files | `TrafficTopupSheet.tsx`, `DeviceTopupSheet.tsx`, `ServerManagementSheet.tsx` |
| Staging | `make staging-cabinet-build` (cabinet only — no bot rebuild) |
| Cabinet URL | `https://staging-host-cabinet.rookari.com` (port `3021`) |
| Bot | `@mrj7_bot` (login via Telegram if needed) |

## What changed

- Subscription page «گزینه‌های اضافی» sheets no longer hardcode `₽`.
- Prices use `useCurrency`: `30,000 تومان` for `fa` (comma-grouped Latin digits).
- Fixes double `₽ ₽` on discounted traffic cards in RTL/mobile.

## User smoke checklist (staging cabinet, fa locale)

| Step | Path | Expected |
|------|------|----------|
| Traffic topup | `/subscriptions/:id` → **خرید ترافیک بیشتر** | Package prices show `N تومان`, not `₽` |
| Discount card | Same, package with `-50%` badge | Strikethrough + final price both `تومان`; no double ruble |
| Device topup | **افزودن کاربر بیشتر** (if enabled) | Per-device / total prices in `تومان` |
| Server management | **مدیریت سرورها** (classic mode, if shown) | Country add-on prices in `تومان` |
| Balance prompt | Select package above balance | Insufficient-balance line consistent `تومان` |

**Regression:** `ru` locale still shows ruble amounts; tariff purchase wizard unchanged.

## Sign-off

- [ ] User smoke on staging cabinet (`تایید`)
- [ ] PR → merge → prod deploy (after approval)

---

# Smoke map — Cabinet partner checkout (یادداشت + نام دلخواه)

> Branch `feat/cabinet-partner-checkout`; staging bot + cabinet rebuild.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `feat/cabinet-partner-checkout` |
| Scope | Partner-only fields on `/subscription/purchase` confirm (cabinet + miniapp WebView) |
| API | `POST /cabinet/subscription/purchase-tariff` + `GET /cabinet/referral/partner/status` (`panel_brand_prefix`) |
| Staging | `make staging-rebuild` + `make staging-health` |
| Cabinet URL | staging cabinet (`3021` / `staging-host-cabinet`) |
| Bot | `@mrj7_bot` (partner account) |

## User smoke checklist (approved partner, fa)

| Step | Path | Expected |
|------|------|----------|
| Open purchase | Cabinet/miniapp → خرید سرویس → انتخاب سرویس → تأیید | بلوک «یادداشت خرید» + «نام دلخواه» visible |
| Non-partner | Same with retail account | No partner block |
| Prefill brand | Partner with saved prefix | نام دلخواه input prefilled |
| Set note + brand | Enter note + `mobile_x` → خرید | Panel username `mobile_x_{serial}`; note in description |
| Renew path | Renew existing sub | Purchase works; username unchanged on panel |

## Sign-off

- [ ] User smoke on staging (`تایید`)
- [ ] PR → merge → prod deploy (after approval)
