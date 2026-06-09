# fa-i18n — Remaining Work (Jun 9 2026 audit)

> **Status:** Superseded for execution by `2026-06-09-fa-i18n-execution.md` (bite-sized tasks). This file remains the audit outline.
> **Living status:** `.cursor/rules/fa-i18n-status.mdc`
> **Audit date:** 2026-06-09 · workspace `/opt/bot-remnawave`

## Executive summary

| Layer | Key coverage | User-visible quality |
|-------|-------------|----------------------|
| Bot `fa.json` | 100% vs `ru` (4047 keys) | ~99% — production-ready |
| Miniapp API | 100% MINIAPP_* | Complete |
| Cabinet user UI | 82.5% (1521/1843) | **Main gap** — 322 keys fall back to Russian |
| Cabinet admin UI | 81.0% (2509/3099) | 590 keys missing |
| Jalali dates | Done on branch `i18n/fa-jalali-dates` | Pending merge |
| Copywriting (native Persian) | Not started | Awkward calques remain |

**User-facing experience estimate: ~90–93%** (translation coverage + copy quality).

---

## Priority order (user-defined)

### P1 — User interface (what end-users see)

**Goal:** Zero Russian fallback on hot paths for `language=fa`.

#### P1-A — Cabinet `fa.json` (158 high-impact user keys)

Exclude `banSystem` (admin-operated) from first slice; focus:

| Namespace | Missing | Impact |
|-----------|---------|--------|
| `subscription.*` | 75 | Trial banner, switch tariff/traffic, pause, device plurals, insufficient balance |
| `gift.*` | 16 | Gift status labels |
| `dashboard.*` | 12 | Zone labels, days remaining, traffic usage |
| `notifications.*` | 9 | Relative timestamps (days/hours ago) |
| `resetPassword.*` | 7 | Email reset flow |
| `balance.paymentMethods.*` | 16 | Method descriptions (tooltips) |
| `support.*` | 2 | Profile hints |
| `landing.*` | 6 | Plural period labels |
| `wheel.*` / `promo.*` / `news.*` | 9 | Secondary surfaces |

**Files:** `cabinet/src/locales/fa.json` (+ `npm run build` for cabinet).

**Note:** `subscription.insufficientBalance` in `ru.json` still uses `₽` — FA translation must use تومان via existing formatter patterns.

#### P1-B — Bot code leaks (restriction fallback)

~40 files still hardcode `'Действие ограничено администратором'` instead of `texts.t('USER_RESTRICTION_DEFAULT_REASON', ...)`.

| Fixed | Remaining |
|-------|-----------|
| `app/handlers/balance/main.py` | `app/plugins/c2c/handlers/user.py` (×2), `c2c/integration.py`, all other `app/handlers/balance/*.py` |

Edge-case path only (when `restriction_reason` is null).

#### P1-C — Pending merges (unblock production)

| Branch | Content | Gate |
|--------|---------|------|
| `i18n/p1-remainder-b` | YooKassa button keys + restriction fix | User smoke + PR |
| `i18n/fa-jalali-dates` | Jalali calendar P1 | User smoke + PR |
| `chore/merge-cabinet-1.57` | bot 3.60 + cabinet 1.57 | User smoke + approval |

---

### P2 — Admin surfaces + bot/group notifications

**Goal:** Persian for admins with `language=fa` and admin notification group.

#### P2-A — Bot admin (mostly done in fa.json)

- `ADMIN_*` keys: **2339/2397** have Persian text (97.6%)
- ~1480 lines in `app/handlers/admin/**` still carry Cyrillic **fallbacks** in `texts.t()` — safe when fa.json populated; risky for new upstream keys
- Large FSM bodies in `remnawave.py`, `messages.py` broadcast flows may still surface Cyrillic if key missing

**Plan reference:** `docs/superpowers/plans/2026-06-06-fa-i18n-p2-admin-bot.md`

#### P2-B — Admin group notifications

- **291** `*NOTIFY*` keys in `fa.json`; **0 Cyrillic**; **26** emoji/placeholder-only (language-neutral)
- `AdminNotificationService` uses `get_texts(user.language)` — **decision: Persian** ✅

#### P2-C — Cabinet admin (590 keys)

| Namespace | Missing |
|-----------|---------|
| `admin.settings.*` | ~485 |
| `admin.tariffs.*` | 15 |
| `admin.auditLog.*` | 12 |
| `admin.promoOffers.*` | 12 |
| `banSystem.*` | 148 (also has user-visible ban messages) |

#### P2-D — Email templates

Separate plan: `docs/superpowers/plans/2026-06-06-fa-i18n-cabinet-email.md` (referenced in P1 plan).

---

### P3 — Copywriting / native Persian terminology

**Goal:** Replace calques and unclear labels with familiar Iranian UX language. **Locale-only commits** (fa.json + cabinet fa.json) — no handler logic unless label source is hardcoded.

#### Confirmed awkward terms (audit)

| Current | Occurrences | Proposed | Keys / surfaces |
|---------|-------------|----------|-----------------|
| خرید ساده / خرید ساده اشتراک | 5 bot keys | **خرید سرویس** | `MENU_SIMPLE_SUBSCRIPTION`, `SIMPLE_SUBSCRIPTION_TITLE`, `CB_SIMPLE_SUB_UNAVAILABLE`, `SIMPLE_SUB_CONFIRM_*`, `SIMPLE_SUB_PAYMENT_STARS_DESCRIPTION` |
| اشتراک ساده | 1 cabinet | **خرید سرویس** | `admin.settings.subs_simple` (or user nav if exposed) |
| صدور مجدد (button, no context) | 7+ keys | **صدور مجدد لینک** or **تغییر لینک و قطع دستگاه‌ها** | `MY_SUB_BTN_REISSUE`, `SUBSCRIPTION_REVOKE_*`, `subscription.revoke.*` in cabinet |
| خرید اکانت جدید | 1 | **خرید سرویس جدید** | `MY_SUB_BTN_BUY_ANOTHER` |
| تعرفه | 159 (many admin) | **سرویس** or **پلن** for **user-facing only**; keep «تعرفه» in admin infra if preferred | User keys: `TARIFF_*`, `CHANGE_TARIFF_*`, cabinet `subscription.switchTariff.*` |
| نود | 6 (admin) | **سرور** | `ADMIN_RW_*`, `ADMIN_MAINTENANCE_PANEL_NODES` |
| اکانت | 2 | **حساب** | `MY_SUB_BTN_BUY_ANOTHER`, `SUSPICIOUS_DISPLAY_NAME_BLOCKED` |

#### `sr:5611` clarification

`sr:{sub_id}` is **internal Telegram `callback_data`** — not shown to users. The visible button is `MY_SUB_BTN_REISSUE` = «🔄 صدور مجدد». Users may still find the label unclear because it does not explain *what* is reissued (link vs subscription). P3 copywriting addresses the **label**, not callback prefix.

Subscription list label `{tariff} #{seq}` (e.g. «استاندارد #3») is intentional sequencing — review separately if `#seq` feels technical.

#### P3 execution slices

1. **Slice 3a — Simple subscription rename** (5 bot keys + 1 cabinet) — single commit
2. **Slice 3b — Revoke/reissue labels** (bot + cabinet revoke namespace) — single commit
3. **Slice 3c — User-facing «تعرفه» → «سرویس/پلن»** — grep-scoped, user keys only (~40–60 keys, not all 159)
4. **Slice 3d — Admin «نود» → «سرور»** — 6 keys, admin-only

---

### P4 — Edge cases & polish

| Item | Notes |
|------|-------|
| `ADMIN_RW_NODE_NOT_FOUND` | `'❌ نода یافت نشد'` — mixed transliteration; fix to fully Persian |
| `PAYMENT_METHOD_YOO_MONEY` | Brand name — keep |
| Disabled providers (CryptoBot, Heleket, WATA, Stars) | Skip per `.env` decision |
| `app/cabinet/routes/withdrawal.py` | Optional language-parity |
| Persian digit shaping (۱۸ vs 18) | Out of scope for Jalali P1 |
| `banSystem` 148 keys | User-visible ban messages — treat as P1 if ban feature enabled |

---

## Phase map (historical → remaining)

| Phase | Scope | Status |
|-------|-------|--------|
| P0 | Locale parity, callback/menu hardcodes | ✅ Done |
| P1 | User surfaces bot + cabinet + miniapp | ✅ Merged to main |
| P1.5 / P1.5b | Tariff purchase remainder, YooKassa buttons | ✅ Done; branch awaiting PR |
| P2 (bot admin) | Admin handlers + fa.json | ✅ ~97.6% keys; fallbacks remain in code |
| Jalali P1 | User-facing dates | ✅ Branch done; awaiting merge |
| **P1-remain** | Cabinet 322 user keys | 🔲 **Next execution** |
| **P2-remain** | Cabinet admin 590 + notify polish | 🔲 Queued |
| **P3-copy** | Native terminology | 🔲 Queued |
| **P4-edge** | Restriction fallbacks, transliteration fixes | 🔲 Queued |
| Email i18n | Templates | 🔲 Separate plan |

---

## Verification (each slice)

```bash
# Bot
docker compose run --rm --no-deps bot python -c "import main"
cp app/localization/locales/fa.json ./locales/fa.json
docker compose restart bot

# Cabinet keys parity check
python3 -c "
import json
from pathlib import Path
def flat(d,p=''):
  for k,v in d.items():
    key=f'{p}.{k}' if p else k
    if isinstance(v,dict): yield from flat(v,key)
    else: yield key
ru=set(flat(json.loads(Path('cabinet/src/locales/ru.json').read_text())))
fa=set(flat(json.loads(Path('cabinet/src/locales/fa.json').read_text())))
print('cabinet missing', len(ru-fa))
"

# Cabinet build
cd cabinet && npm run build

# Admin texts guard
grep -r get_admin_texts app/  # must be 0
```

---

## Suggested execution order (for Plan mode)

1. Merge pending branches (Jalali, P1.5b) after smoke
2. **P1-A** cabinet subscription namespace (75 keys) — highest user impact
3. **P3-a + P3-b** copywriting quick wins (خرید سرویس, revoke labels)
4. **P1-A** remainder (gift, dashboard, notifications)
5. **P4** restriction fallback sweep (one commit across balance + c2c)
6. **P2-C** cabinet admin (if admin users use fa)
7. **P3-c** تعرفه → سرویس user-facing sweep
8. Email templates (separate track)
