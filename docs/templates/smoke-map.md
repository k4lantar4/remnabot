# Smoke map — Earn tab redesign Jul 2026

> Branch `feat/earn-tab-redesign`; cabinet `/referral` → two-tab «کسب درآمد» (نمایندگی | دعوت); withdrawal UI removed.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `feat/earn-tab-redesign` |
| Scope | Cabinet-only Phase 1 — no backend/API changes |
| Deploy | `make smoke && make deploy-scope && make staging-rebuild` |
| Bot | `@mrj7_bot` (unchanged hot path) |
| Cabinet | staging cabinet `:3021` |

## User smoke checklist

| # | Path | Expected | Status |
|---|------|----------|--------|
| 1 | Nav (sidebar / bottom / header) | Label «کسب درآمد»; route still `/referral` | pending |
| 2 | `/referral` default tab | «نمایندگی» active; non-partner sees apply CTA at top without scroll | pending |
| 3 | Tab «دعوت» | پورسانت معرفی (`available_balance_rubles`); bot link copy/share only | pending |
| 4 | Approved partner | ✅ نماینده فعال + wholesale % + stats + «دعوت دوستان» switches tab | pending |
| 5 | Pending application | Review card on partner tab; no apply CTA | pending |
| 6 | Rejected application | Rejection card + reapply button | pending |
| 7 | Withdrawal section | **Absent** on earn page (no balance/history/request UI) | pending |
| 8 | Removed clutter | No top stats grid, no cabinet `/login?ref=` link, no 4-card terms grid | pending |

## Sign-off

- [ ] User smoke on `@mrj7_bot` + staging cabinet
- [ ] Reply **تایید** before ship

---

# Smoke map — Phase 6 numeric display units Jul 2026

> Branch `fix/amount-display-units`; Tasks 15, 17, 14, 16 — referral withdrawal, WS toasts, subscription_payment storage, admin report scale.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `fix/amount-display-units` |
| Commits | `a251f5dd` (15), `abb3eb56` (17), `f9a92371` (14), `d1131568` (16) |
| Deploy | `make staging-rebuild-both` |
| Bot | `@mrj7_bot` |
| Cabinet | staging cabinet `:3021` |

## User smoke checklist

| # | Path | Expected | Status |
|---|------|----------|--------|
| 1 | Cabinet Referral → برداشت | Available/earned show full Toman (e.g. 12,500 not 125) | pending |
| 2 | Submit withdrawal request | Stored amount 1:1 with displayed Toman | pending |
| 3 | WS balance top-up / daily debit toast | Correct تومان (not ÷100 again) | pending |
| 4 | Cabinet buy extra devices → Balance history | Amount matches charge (not 100× small) | pending |
| 5 | Admin report / stats deposit total | Order-of-magnitude matches user top-ups | pending |
| 6 | Admin stats referral earnings | Full Toman (format_balance, not ÷100) | pending |

## Sign-off

- [ ] User smoke on `@mrj7_bot` + staging cabinet
- [ ] Reply **تایید** before ship

---

# Smoke map — Subscription detail UX polish Jul 2026

> Branch `feat/subscription-detail-ux`; UX polish: renew copy dedupe, note-edit cleanup, user-disabled labels, countdown LTR, note card moved.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `feat/subscription-detail-ux` |
| Migration | `0103` (`user_disabled`) — applied on staging |
| Deploy | `cp app/localization/locales/fa.json ./locales/fa.json` + `make staging-rebuild` |
| Bot | `@mrj7_bot` |
| Cabinet | staging cabinet `:3021` |

## User smoke checklist (polish)

| # | Path | Expected | Status |
|---|------|----------|--------|
| P1 | Renew tariff (balance) | QR caption: stats + کانفیگ شما only — **no** duplicate گام بعدی / onboarding | pending |
| P2 | `sm:{id}` → ویرایش یادداشت | saves in-place; **no** extra «یادداشت ذخیره شد» message | pending |
| P3 | خاموش کردن اشتراک | badge «خاموش شده» (not معلق/موجودی ناکافی); countdown shows days LTR | pending |
| P4 | روشن کردن | enable without renew; status active again | pending |
| P5 | Cabinet `/subscriptions/:id` | note card **below** main card; countdown days left-prominent | pending |

## User smoke checklist (base feature)

| # | Path | Expected | Status |
|---|------|----------|--------|
| 1 | `menu_subscription` list | جستجو چپ + خرید سرویس جدید راست در یک ردیف | pending |
| 2 | Active sub detail `sm:{id}` | کیبورد ۲تایی؛ ویرایش یادداشت؛ خاموش کردن ردیف ۵ | pending |
| 3 | Disable → confirm | دکمه «روشن کردن» — **بدون تمدید** | pending |
| 4 | Enable | VPN برمی‌گردد؛ اعتبار حفظ | pending |
| 5 | Note edit (bot + cabinet) | FSM `/skip` پاک می‌کند؛ کابینت باکس یادداشت | pending |
| 6 | Expired / system disabled | تمدید+حذف؛ **بدون** روشن کردن | pending |

## Sign-off

- [ ] User smoke on `@mrj7_bot` + staging cabinet
- [ ] Reply **تایید** before ship

---

# Smoke map — Subscription detail UX (note + disable/enable) Jul 2026

> Branch `feat/subscription-detail-ux`; note edit, user disable/enable toggle, 2-col keyboards.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `feat/subscription-detail-ux` |
| Migration | `0103` (`user_disabled`) — applied on staging |
| Deploy | `make staging-migrate` + `make staging-rebuild` |
| Bot | `@mrj7_bot` |
| Cabinet | staging cabinet `:3021` |

## User smoke checklist

| # | Path | Expected | Status |
|---|------|----------|--------|
| 1 | `menu_subscription` list | جستجو چپ + خرید سرویس جدید راست در یک ردیف | pending |
| 2 | Active sub detail `sm:{id}` | کیبورد ۲تایی؛ ویرایش یادداشت؛ خاموش کردن ردیف ۵ | pending |
| 3 | Disable → confirm | دکمه «روشن کردن» — **بدون تمدید** | pending |
| 4 | Enable | VPN برمی‌گردد؛ اعتبار حفظ | pending |
| 5 | Note edit (bot + cabinet) | FSM `/skip` پاک می‌کند؛ کابینت باکس یادداشت | pending |
| 6 | Expired / system disabled | تمدید+حذف؛ **بدون** روشن کردن | pending |

## Sign-off

- [ ] User smoke on `@mrj7_bot` + staging cabinet
- [ ] Reply **تایید** before ship

---

# Smoke map — Post-purchase connect parity Phase 2 (Tasks 6, 9–12) Jul 2026

> Branch `fix/post-purchase-connect-parity-phase2`; unified connect chooser (reverted partner gate), first-connect checklist, broadcast forward via copy_message.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `fix/post-purchase-connect-parity-phase2` |
| Worktree | `.worktrees/post-purchase-connect-parity-phase2` |
| Commits | `2c407774a` connect revert + `00845c209` broadcast copy_message |
| Migration | `0102` (already applied on staging) |
| Deploy | `./tools/deploy-staging.sh` from worktree |
| Bot | `@mrj7_bot` |
| Cabinet | `https://staging-host-cabinet.rookari.com` |

## User smoke checklist

| # | Path | Expected | Status |
|---|------|----------|--------|
| 3 | Any user: «دریافت کانفیگ» from detail or post-purchase | Chooser first (راهنما / دریافت QR و کانفیگ), then QR on config button | pending |
| 4 | Partner and non-partner | **Same** chooser flow — no partner-only share shortcut | pending |
| 9 | Cabinet subscription detail, 0 GB used | 3-step first-connect checklist visible; hides after traffic > 0 | pending |
| 7 | Admin → broadcast → forward channel post | Preview shows copy_message with channel header; premium emoji intact on send | pending |
| 8 | Admin broadcast button toggles | «💎 خرید سرویس» toggle keeps emoji; default buttons include connect + subscription + home | pending |

## Sign-off

- [ ] User smoke on `@mrj7_bot` + staging cabinet
- [ ] Reply **تایید** before ship

---

# Smoke map — Cabinet UX polish + Phase 1–2 (Jul 2026)

> Branch `fix/cabinet-ux-polish` (includes `fix/post-purchase-cabinet-routing` Phase 1–2).

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `fix/cabinet-ux-polish` |
| Files | `ConfigDeliverySheet`, `postPurchaseRedirect`, wizards, `purchaseRoutes`, `TariffPickerGrid`, `Dashboard`, `Subscription`, `globals.css`, `cabinet/src/locales/fa.json` |
| Guard | cabinet docker build OK |
| Deploy | staging cabinet-frontend rebuilt |
| Surfaces | staging cabinet (`3021`) |

## User smoke checklist (staging cabinet)

| # | Path | Expected | Status |
|---|------|----------|--------|
| A | Post-purchase buy | `/subscriptions/:id?openConfig=1` + config sheet | pending |
| B | Config sheet QR | Soft gray `#ececec` surface, scannable | pending |
| C | Traffic slider | Thumb centered on track | pending |
| D | Dashboard → خرید اشتراک دیگر | Cards show «خرید» / «خرید اکانت جدید», not «انتخاب برای تمدید» | pending |
| E | Complete buyAnother | New subscription row (not extend) | pending |
| F | Dashboard home | Max 3 cards + accent «مشاهده همه» | pending |
| G | Nav + referral page | «نمایندگی» label | pending |
| H | Subscription detail | Renew CTA + «خرید اشتراک دیگر» row | pending |

## Sign-off

- [ ] User smoke on staging cabinet
- [ ] Reply **تایید** before ship

---

# Smoke map — Cabinet post-purchase routing (Phase 1–2) Jul 2026

> Branch `fix/post-purchase-cabinet-routing`; cabinet detail redirect + ConfigDeliverySheet + guide intro.
> Bot QR/partner/C2C parity already on `main` (PR #100).

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `fix/post-purchase-cabinet-routing` |
| Files | `postPurchaseRedirect.ts`, wizards, `SuccessNotificationModal`, `ConfigDeliverySheet.tsx`, `Subscription.tsx`, `InstallationGuide.tsx`, `cabinet/src/locales/fa.json` |
| Guard | cabinet `npm run build` |
| Deploy | `make staging-rebuild` (cabinet-frontend) |
| Surfaces | staging cabinet + `@mrj7_bot` (bot already shipped) |

## User smoke checklist (staging cabinet)

| # | Path | Expected | Status |
|---|------|----------|--------|
| 5 | Cabinet buy (classic or tariff) → success | Navigate to `/subscriptions/:id?openConfig=1`; config sheet auto-opens with copy + QR | pending |
| 6 | Guide: `/connection?sub=` or sheet «راهنمای اتصال» | Intro text above app chips; labeled QR button (not icon-only) | pending |
| 5b | Detail page CTAs | «دریافت کانفیگ» opens sheet; «راهنمای اتصال» → `/connection?sub=` | pending |
| 5c | WS success modal (if fired) | CTA goes to detail + openConfig, not list | pending |

## Sign-off

- [ ] User smoke on staging cabinet
- [ ] Reply **تایید** before ship

---

# Smoke map — Post-purchase connect parity Jul 2026

> Branch `fix/post-purchase-connect-parity`; QR+config delivery at purchase, re-fetch from subscription detail and chooser. **Merged** PR #100 → `main`.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `fix/post-purchase-connect-parity` (merged) |
| Files | `purchase_success_delivery.py`, `links.py`, `my_subscriptions.py`, `tariff_purchase.py`, `purchase.py`, `subscription_auto_purchase_service.py`, `fa.json` |
| Guard | `uv run pytest tests/handlers/test_connect_chooser.py tests/utils/test_subscription_qr.py tests/services/test_subscription_auto_purchase_service.py -q` |
| Deploy | `cp app/localization/locales/fa.json ./locales/fa.json` + `make staging-rebuild` |
| Bot | `@mrj7_bot` |

## Keys / callbacks

| Key / callback | Surface |
|----------------|---------|
| `CONNECT_CHOOSER_BTN_CONFIG` | Chooser — «دریافت QR و لینک اتصال» |
| `CONNECT_CONFIG_*` | QR delivery caption (title + hint) |
| `MY_SUB_BTN_GET_CONFIG` | Detail + post-purchase — resend QR |
| `MY_SUB_BTN_SETUP_GUIDE` | Detail + post-purchase — WebApp guide |
| `sl_config:{sub_id}` | Direct QR photo + link in chat |
| `sl_self:{sub_id}` | Install guide (WebApp) |
| `sl:{sub_id}` | Legacy chooser entry (self + config buttons) |

## User smoke checklist (`@mrj7_bot`, fa)

| # | مسیر | انتظار | Status |
|---|------|--------|--------|
| 1 | خرید با موجودی → موفق | عکس QR + کپشن کانفیگ + ۲ دکمه (دریافت QR/لینک + راهنمای اتصال) | pending |
| 2 | اشتراک من → جزئیات یک سرویس | ۲ دکمه جدا: «دریافت QR و لینک» + «راهنمای اتصال» | pending |
| 3 | زدن «راهنمای اتصال» | WebApp راهنما باز شود؛ بدون لینک مستقیم پنل | pending |
| 4 | زدن «دریافت QR و لینک» (از جزئیات یا chooser) | عکس QR جدید + لینک در `<code>` — نه صفحه «برای مشتری» | pending |
| 5 | C2C: موجودی کم → ارسال رسید | متن «سرویس پس از تایید فعال می‌شود» — **بدون QR** (هنوز اشتراک نیست) | pending |
| 6 | C2C: ادمین رسید را تایید می‌کند | **یک** پیام با QR مثل خرید با موجودی (نه «شارژ شد» جدا) | pending |
| 10 | کابینت → موجودی → تاریخچه → آخرین واریز C2C | توضیح فارسی: `واریز کارت‌به‌کارت: ...` (نه انگلیسی) | pending |

## Sign-off

- [ ] User smoke on `@mrj7_bot`
- [ ] Reply **تایید** before ship

---

# Smoke map — Bot admin RBAC parity

> Branch `fix/bot-admin-rbac-parity`; RBAC cabinet admins see Telegram admin button without `ADMIN_IDS`.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `fix/bot-admin-rbac-parity` |
| Files | `admin_access_service.py`, `auth.py`, `menu.py`, `start.py`, `decorators.py`, `cabinet/dependencies.py`, `cabinet/routes/auth.py` |
| Guard | `uv run pytest tests/services/test_admin_access.py -q` |
| Deploy | `make staging-rebuild` (bot Python) |

## User smoke checklist (`@mrj7_bot` or prod after merge)

| Step | Path | Expected | Status |
|------|------|----------|--------|
| 1 | Login as RBAC admin (e.g. `6371108688`) — `/start` or منوی اصلی | Row with **⚙️ پنل ادمین** visible | pending |
| 2 | Tap **⚙️ پنل ادمین** | Admin panel opens (not ACCESS_DENIED) | pending |
| 3 | Legacy `ADMIN_IDS` admin still sees button | Unchanged | pending |

## Sign-off

- [ ] User smoke on staging `@mrj7_bot`
- [ ] User approval (`تایید`) before ship

---

# Smoke map — Support/ticket i18n (fa)

> On `main` (uncommitted); prod bot redeploy 2026-07-01.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `main` (direct) |
| Files | `fa.json`, `tickets.py`, `admin/tickets.py`, `monitoring_service.py`, `ticket_notification.py` |
| Deploy | `docker compose build bot && docker compose up -d bot` + `cp fa.json locales/` |
| Bot | prod `@MOONVPN_BOT` |

## Keys / paths

| Key / handler | Surface |
|---------------|---------|
| `ADMIN_NOTIFY_TICKET_*` | Telegram admin group — new ticket, user reply, SLA |
| `ADMIN_TICKET_*` | Admin panel ticket detail card + block toasts |
| `CABINET_TICKET_NOTIFY_*` | Cabinet notification bell dropdown |
| `TICKET_REPLY_NOTIFICATION` | User Telegram — admin reply with preview |

## User smoke checklist

| Step | Path | Expected | Status |
|------|------|----------|--------|
| 1 | User creates ticket | Admin group: `🎫 تیکت جدید` + Persian fields + Jalali date | pending |
| 2 | User replies on ticket | Admin group: `💬 پاسخ به تیکت` | pending |
| 3 | `/admin` → تیکت‌ها → open ticket | Card labels in Persian (کاربر، عنوان، …) | pending |
| 4 | Cabinet `/admin/tickets` bell | Dropdown message in Persian | pending |
| 5 | Admin replies | User gets `TICKET_REPLY_NOTIFICATION` with preview + ticket id | pending |

## Sign-off

- [ ] User smoke on prod bot
- [ ] Reply **تایید** if OK

---

# Smoke map — Dual connect (miniapp + panel direct)

> On `main` (uncommitted); `@mrj7_bot` staging.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `main` |
| Files | `subscription_utils.py`, `links.py`, `purchase.py`, `tariff_purchase.py`, `fa.json` |
| Deploy | `make staging-rebuild` (2026-07-01) |
| Bot | `@mrj7_bot` |

## Keys / callbacks

| Key / callback | Surface |
|----------------|---------|
| `SUBSCRIPTION_CONNECT_BTN_MINIAPP_GUIDE` | Connect screen — WebApp cabinet `/connection?sub=` |
| `SUBSCRIPTION_CONNECT_BTN_PANEL_DIRECT` | Connect screen — `url` panel `subscription_url` |
| `SUBSCRIPTION_CONNECT_MINIAPP_MESSAGE` | Connect screen body (dual-option copy) |
| `MY_SUB_DETAIL_ONBOARDING` / `POST_PURCHASE_ONBOARDING` | Detail + post-purchase hints |
| `sl:{sub_id}` | Entry from detail, tariff success, purchase success |
| `MY_SUB_BTN_CONNECT_LINK` | Tariff purchase success CTA |

## User smoke checklist (`@mrj7_bot`, fa)

| Step | Path | Expected | Status |
|------|------|----------|--------|
| 1 | اشتراک من → detail → «دریافت لینک» | Two buttons: مینی‌اپ + لینک مستقیم پنل | pending |
| 2 | Tap مینی‌اپ | Stays in Telegram WebView (`/connection?sub=`) | pending |
| 3 | Tap لینک مستقیم پنل | Opens `subscription_url` in mobile browser (not cabinet) | pending |
| 4 | Buy tariff → success | «دریافت لینک» CTA above «اشتراک من» → step 1 screen | pending |
| 5 | Trial/paid purchase success (`purchase.py`) | Inline dual buttons on success message | pending |
| 6 | Detail onboarding text | Mentions both paths; no cabinet/rookari branding | pending |

## Sign-off

- [ ] User smoke on `@mrj7_bot`
- [ ] Reply **تایید** before prod deploy

---

# Smoke map — Partner broadcast targeting (admin)

> Branch `feat/admin-partner-broadcast`; مخاطب «نمایندگان» برای ارسال همگانی، نظرسنجی، و سنجاق فوری.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `feat/admin-partner-broadcast` |
| Files | `user.py`, `messages.py`, `polls.py`, `pinned_message_service.py`, `admin.py`, `fa.json`, tests |
| Guard | `uv run pytest tests/handlers/test_admin_partner_audience.py -v` |
| Deploy | `make staging-rebuild` (2026-06-26) |
| Bot | `@mrj7_bot` (staging) |

## Keys / callbacks

| Key / callback | Surface |
|----------------|---------|
| `ADMIN_BROADCAST_TARGET_PARTNERS` | Broadcast + poll target keyboard |
| `ADMIN_MSG_TARGET_PARTNERS` | History / confirm audience label |
| `broadcast_partners` | Admin → ارسال پیام → audience |
| `poll_target:{id}:partners` | Admin → نظرسنجی → send |
| `admin_pinned_broadcast_now:{id}:all` | Pinned instant — all |
| `admin_pinned_broadcast_now:{id}:partners` | Pinned instant — partners only |
| `admin_pinned_broadcast_skip:{id}` | Pinned — /start only (unchanged) |
| `ADMIN_BROADCAST_BUTTON_CONNECT` / `menu_buy` | Broadcast attach button — **خرید سرویس** (was اتصال) |
| `ADMIN_BROADCAST_BUTTON_PARTNER_APPLY` / `partner_apply_start` | Broadcast attach — **ثبت درخواست نمایندگی** |

## Broadcast button selector smoke (`@mrj7_bot`)

| Step | Path | Expected | Status |
|------|------|----------|--------|
| B1 | ارسال پیام → button step | Row shows **💎 خرید سرویس** (not اتصال) | pending |
| B2 | Same screen | Row **🤝 ثبت درخواست نمایندگی** before home | pending |
| B3 | Preview + send with both buttons | Tap خرید سرویس → `menu_buy`; tap نمایندگی → partner apply FSM | pending |
| B4 | Staging cabinet `/admin` broadcasts create | Labels: خرید سرویس + ثبت درخواست نمایندگی | pending |

## User smoke checklist (`@mrj7_bot`, fa admin)

| Step | Path | Expected | Status |
|------|------|----------|--------|
| 1 | ارتباطات → ارسال پیام → (همه یا بر اساس اشتراک) → **🤝 نمایندگان** | Count > 0 if approved partners exist; Persian label | pending |
| 2 | Confirm broadcast to partners | Only approved partners with telegram receive message | pending |
| 3 | ارتباطات → نظرسنجی → Send → **🤝 نمایندگان** | Same count as step 1 | pending |
| 4 | ارسال پیام → سنجاق → edit → **🤝 الان — نمایندگان** | Only partners pinned | pending |
| 5 | Regression: **📨 الان — همه** pinned | All active telegram users | pending |
| 6 | Regression: **⏳ فقط /start** | No instant send; /start delivery unchanged | pending |
| 7 | History → last broadcast | Target shows «نمایندگان» | pending |

## Sign-off

- [ ] User smoke on `@mrj7_bot`
- [ ] Reply **تایید** to ship

---

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

---

# Smoke map — Ledger descriptions remainder (Tasks 18–23) Jul 2026

> Branch `i18n/ledger-descriptions-remainder`; Persian `transactions.description` for classic/miniapp/wheel/admin paths.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/ledger-descriptions-remainder` |
| Keys | `CLASSIC_SUB_*`, `ADMIN_LEDGER_*`, `WHEEL_WIN_*`, `DAILY_TARIFF_RENEW_LEDGER_DESC` |
| Deploy | `cp app/localization/locales/fa.json ./locales/fa.json` + `make staging-rebuild` |
| Bot | `@mrj7_bot` |
| Cabinet | staging cabinet `:3021` |

## User smoke checklist

| # | Path | Expected |
|---|------|----------|
| 10 | C2C top-up (regression) | `واریز کارت‌به‌کارت` — unchanged |
| 11 | Cabinet tariff buy | `خرید سرویس «…»` — unchanged |
| L1 | Classic bot purchase | `اشتراک برای … روز` not `Подписка на` |
| L2 | Miniapp tariff buy | Persian ledger row |
| L3 | Wheel balance prize | `جایزه گردونه:` not `Выигрыш` |
| L4 | Admin credit balance | `شارژ توسط ادمین` in user balance history |

## Sign-off

- [ ] User smoke on `@mrj7_bot` + staging cabinet balance history
- [ ] Reply **تایید** before ship

---

# Smoke map — Monitoring notify caps (Task 24) Jul 2026

> Branch `fix/monitoring-notification-caps`; per-user daily cap + traffic lifetime cap.

| # | Path | Expected |
|---|------|----------|
| 12 | User with 2+ expired subs | ≤5 monitoring msgs in 24h (not N×subs) |
| 13 | Sub at 90%+ traffic | ≤3 traffic warnings total, then silence |
| 14 | After renew / traffic reset | traffic warnings allowed again |

Branch: `fix/monitoring-notification-caps` @ `6782a6a7b`
