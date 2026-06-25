# fa-i18n Remaining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all remaining work from [2026-06-23-fa-i18n-remaining-audit.md](2026-06-23-fa-i18n-remaining-audit.md) and [Phase 10 admin Persian plan](../../.cursor/plans/phase_10_admin_fa_b7420966.plan.md) — Persian-first admin, user-surface polish, guards, staging smoke, then ship.

**Architecture:** One concern per commit on feature branches from `main`; bot `app/localization/locales/fa.json` and cabinet `cabinet/src/locales/fa.json` never edited in parallel; admin stays `get_texts(db_user.language)` with `fa → en → ru` fallback (already on `main`). No forced English admin.

**Tech Stack:** Python 3 / aiogram handlers, React cabinet i18next, `pytest`, Docker staging (`@mrj7_bot`, port 3021), `tools/cabinet_admin_fa_slice_b.py`.

**Branch baseline:** `i18n/admin-fa-completion` @ `7063e3fe` (Slice B done); `main` includes Phases 0–9, 11 merged.

---

## Status snapshot (2026-06-25)

### Merged on `main` (no further implementation)

| Item | Branch / note |
|------|----------------|
| Phase 0 force-default-language + safe fallback | `fix/force-default-language-when-disabled` |
| Phase 1 `fa → en → ru` | `i18n/fa-en-ru-fallback`; guard `tests/localization/test_fa_en_ru_chain.py` |
| Phases 2–7 user terminology / copy / cabinet device | PRs #73–#81 |
| Phase 8 cabinet Latin digits | `i18n/fa-cabinet-latin-digits` merged |
| Phase 9 miniapp parity | `i18n/fa-miniapp-parity` merged; user smoke تایید |
| Phase 11 monitoring notifications | `i18n/monitoring-notifications` merged |
| Phases 3–6, traffic UX, onboarding | merged (see `fa-i18n-status.mdc`) |

### Done on `i18n/admin-fa-completion` — **Slice B CLOSED** (user smoke تایید 2026-06-25)

| Commit | Slice |
|--------|-------|
| `07a7db29` | B1 — 58 cabinet admin plural + misc keys |
| `9902058a` | B2 — 148 `banSystem` keys |
| `7063e3fe` | B3 — `pinnedMessages` Persian + `tools/cabinet_admin_fa_slice_b.py` |

Cabinet admin `en_only` keys: **0**. Agent `npm run build` OK. Staging smoke **تایید**. Slices A/C/D/E **not started** (paused per operator).

### Remaining implementation (this plan)

| Track | Work |
|-------|------|
| **Phase 10** | Slices A, C, D, E (B done) |
| **Audit §9 commits 12–13, 15** | `stars_payments.py`, `SUBSCRIPTION_CONNECT_*`, optional bot digit guard |
| **Audit §4 residue** | 6 user `دستگاه` keys in bot `fa.json` (HAPP / connect — Phase 13 overlap) |
| **Ship queue** | Branches merged but operator smoke not signed off (see Task 0) |

---

## File map

| File | Responsibility |
|------|----------------|
| [app/localization/locales/fa.json](../../app/localization/locales/fa.json) | Bot user + admin strings |
| [cabinet/src/locales/fa.json](../../cabinet/src/locales/fa.json) | Cabinet user + admin strings |
| [tools/cabinet_admin_fa_slice_b.py](../../tools/cabinet_admin_fa_slice_b.py) | Reproducible cabinet admin locale patches |
| [app/handlers/admin/*.py](../../app/handlers/admin/) | Telegram admin — hardcoded Cyrillic sweep |
| [app/handlers/stars_payments.py](../../app/handlers/stars_payments.py) | Stars wheel hardcoded Russian |
| [cabinet/src/pages/Admin*.tsx](../../cabinet/src/pages/) | Cyrillic `t()` fallbacks |
| [tests/localization/test_admin_fa_coverage.py](../../tests/localization/test_admin_fa_coverage.py) | New — admin key coverage guard |
| [tests/test_cabinet_locale_integrity.py](../../tests/test_cabinet_locale_integrity.py) | Extend — admin Cyrillic `t()` fallback guard |
| [docs/templates/smoke-map.md](../../docs/templates/smoke-map.md) | User smoke checklist |

---

## Task 0: Operator gate — Slice B smoke — **DONE** (تایید 2026-06-25)

**Slice B closed; agent paused before Slice A/C/D.**

- [x] **Step 1: Staging cabinet rebuild**

```bash
cd /opt/bot-remnawave
make staging-cabinet-build
# or: docker compose -f docker-compose.staging.yml --env-file .env.staging -p remnawave-staging build cabinet-frontend && ... up -d cabinet-frontend
```

- [x] **Step 2: Smoke cabinet admin (fa user, staging URL)**

| Path | Check |
|------|-------|
| `/admin` → Ban Monitoring | Tabs/settings Persian; no English blocks |
| `/admin/pinned-messages` | Full Persian UI |
| `/admin/users` → delete/disable confirm | Persian dialogs |

- [x] **Step 3: Report** — **تایید** 2026-06-25. Agent stopped; Slices A/C/D/E deferred.

---

## Task 1: Phase 10 Slice A — seven bot `fa.json` keys

**Files:**
- Modify: [app/localization/locales/fa.json](../../app/localization/locales/fa.json)
- Test: [tests/localization/test_admin_fa_coverage.py](../../tests/localization/test_admin_fa_coverage.py) (created in Task 5; optional defer)

- [ ] **Step 1: Add keys**

```json
  "C2C_ADMIN_INBOX_BACK": "📥 صندوق ورودی",
  "PAYMENT_AURAPAY": "AuraPay",
  "PAYMENT_KASSA_AI": "Kassa AI",
  "PAYMENT_OVERPAY": "Overpay",
  "PAYMENT_PAYPEAR": "PayPear",
  "PAYMENT_ROLLYPAY": "RollyPay",
  "PAYMENT_SEVERPAY": "SeverPay"
```

Brand names for disabled providers may stay Latin; `C2C_ADMIN_INBOX_BACK` must be Persian.

- [ ] **Step 2: Agent smoke**

```bash
make smoke && make check-admin-texts
pytest tests/localization/ -q
```

Expected: `import main` OK; `get_admin_texts` grep = 0.

- [ ] **Step 3: Commit**

```bash
git add app/localization/locales/fa.json
git commit -m "$(cat <<'EOF'
i18n(fa): add 7 missing bot admin locale keys

Backfill C2C inbox back label and disabled payment provider names
so admin texts.t keys resolve from fa.json for Persian operators.
EOF
)"
```

---

## Task 2: Phase 10 Slice C — cabinet admin TSX Cyrillic fallbacks

**Files (9 files, ~55 Russian `t()` second args):**
- Modify: [cabinet/src/pages/AdminRemnawave.tsx](../../cabinet/src/pages/AdminRemnawave.tsx) (19)
- Modify: [cabinet/src/pages/AdminBroadcastCreate.tsx](../../cabinet/src/pages/AdminBroadcastCreate.tsx) (13)
- Modify: [cabinet/src/components/admin/userDetail/SubscriptionTab.tsx](../../cabinet/src/components/admin/userDetail/SubscriptionTab.tsx) (7)
- Modify: [cabinet/src/components/broadcasts/BroadcastPreview.tsx](../../cabinet/src/components/broadcasts/BroadcastPreview.tsx) (6)
- Modify: [cabinet/src/pages/AdminPartnerDetail.tsx](../../cabinet/src/pages/AdminPartnerDetail.tsx) (3)
- Modify: [cabinet/src/pages/AdminPromocodeCreate.tsx](../../cabinet/src/pages/AdminPromocodeCreate.tsx) (3)
- Modify: [cabinet/src/pages/AdminPromoOfferTemplateEdit.tsx](../../cabinet/src/pages/AdminPromoOfferTemplateEdit.tsx) (2)
- Modify: [cabinet/src/pages/AdminPaymentMethodEdit.tsx](../../cabinet/src/pages/AdminPaymentMethodEdit.tsx) (1)
- Modify: [cabinet/src/pages/AdminUserDetail.tsx](../../cabinet/src/pages/AdminUserDetail.tsx) (1)

**Strategy:** For each `t('admin.KEY', 'Русский…')`:
1. Confirm `admin.KEY` exists in `cabinet/src/locales/fa.json` with Persian value.
2. If missing → add Persian to `fa.json` in same commit.
3. Change second arg to **English** upstream-safe fallback (not Russian), e.g. `t('admin.foo', 'Foo')`.

- [ ] **Step 1: Inventory**

```bash
rg "t\\(['\"]admin\\.[^'\"]+['\"],\\s*['\"][^'\"]*[А-Яа-я]" cabinet/src -n
```

- [ ] **Step 2: Fix AdminRemnawave.tsx (largest file) — example**

Before:
```tsx
{t('admin.remnawave.nodes.title', 'Узлы')}
```

After:
```tsx
{t('admin.remnawave.nodes.title', 'Nodes')}
```

Ensure `cabinet/src/locales/fa.json` has `"title": "گره‌ها"` under `admin.remnawave.nodes`.

- [ ] **Step 3: Repeat for remaining 8 files** (one commit per 2–3 related files max)

- [ ] **Step 4: Cabinet build**

```bash
docker run --rm -v /opt/bot-remnawave/cabinet:/app -w /app node:20-alpine sh -c "npm ci && npm run build"
```

Expected: `✓ built` without i18n errors.

- [ ] **Step 5: Commit (example)**

```bash
git commit -m "i18n(fa): cabinet admin TSX fallbacks English not Russian"
```

---

## Task 3: Audit commit 13 — connect flow platform wording

**Files:**
- Modify: [app/localization/locales/fa.json](../../app/localization/locales/fa.json) only

- [ ] **Step 1: Update keys** (audit §5 item 9)

```json
  "SUBSCRIPTION_CONNECT_DEVICE_MESSAGE": "📱 <b>اتصال اشتراک</b>\n\n🔗 <b>لینک اشتراک:</b>\n<code>{subscription_url}</code>\n\n💡 <b>سیستم‌عامل خود را انتخاب کنید</b> (اندروید، آیفون، ویندوز) برای راهنمای تنظیم:",
  "SUBSCRIPTION_CONNECT_DEVICE_MESSAGE_HIDDEN": "📱 <b>اتصال اشتراک</b>\n\nℹ️ لینک از دکمه‌های زیر یا «اشتراک من» در دسترس است.\n\n💡 <b>سیستم‌عامل خود را انتخاب کنید</b> برای راهنما:"
```

- [ ] **Step 2: Verify user `دستگاه` count drops**

```bash
rg 'دستگاه' app/localization/locales/fa.json | rg -v 'ADMIN_' | wc -l
```

Expected: ≤ 4 (HAPP_* keys remain for Phase 13).

- [ ] **Step 3: Agent smoke + commit**

```bash
make smoke
git commit -m "i18n(fa): connect flow platform wording not device"
```

---

## Task 4: Audit commit 12 — stars_payments user strings

**Files:**
- Modify: [app/handlers/stars_payments.py](../../app/handlers/stars_payments.py)
- Modify: [app/localization/locales/fa.json](../../app/localization/locales/fa.json)

- [ ] **Step 1: Find hardcoded Cyrillic**

```bash
rg -n "[А-Яа-я]{4,}" app/handlers/stars_payments.py
```

- [ ] **Step 2: Wrap user-visible strings** — pattern:

```python
texts = get_texts(db_user.language)
await message.answer(
    texts.t(
        'STARS_WHEEL_UNAVAILABLE',
        '❌ Колесо удачи временно недоступно. Звезды будут возвращены.',
    ),
)
```

Add `STARS_*` keys to `fa.json` with Persian; keep Cyrillic in second `texts.t` arg.

- [ ] **Step 3: Agent smoke + commit**

```bash
make smoke
git commit -m "i18n(fa): stars_payments wheel user strings"
```

---

## Task 5: Phase 10 Slice E — guards and docs

**Files:**
- Create: [tests/localization/test_admin_fa_coverage.py](../../tests/localization/test_admin_fa_coverage.py)
- Modify: [tests/test_cabinet_locale_integrity.py](../../tests/test_cabinet_locale_integrity.py)
- Modify: [.cursor/rules/fa-i18n-status.mdc](../../.cursor/rules/fa-i18n-status.mdc)
- Modify: [docs/templates/smoke-map.md](../../docs/templates/smoke-map.md)

- [ ] **Step 1: Write failing test — bot admin keys**

```python
"""Admin texts.t keys used in code must exist in fa.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_FA = json.loads((_ROOT / "app/localization/locales/fa.json").read_text(encoding="utf-8"))
_SCAN_DIRS = [
    _ROOT / "app/handlers/admin",
    _ROOT / "app/keyboards/admin.py",
    _ROOT / "app/plugins/c2c",
]
_T_KEY = re.compile(r"""texts\.t\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]""")
_ALLOWLIST = {
    # disabled payment providers — optional Latin-only
    "PAYMENT_AURAPAY", "PAYMENT_KASSA_AI", "PAYMENT_OVERPAY",
    "PAYMENT_PAYPEAR", "PAYMENT_ROLLYPAY", "PAYMENT_SEVERPAY",
}
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def _collect_texts_t_keys() -> set[str]:
    keys: set[str] = set()
    for path in _SCAN_DIRS:
        if path.is_file():
            files = [path]
        else:
            files = list(path.rglob("*.py"))
        for f in files:
            text = f.read_text(encoding="utf-8")
            keys.update(_T_KEY.findall(text))
    return keys


def test_admin_texts_t_keys_exist_in_fa_json():
    used = _collect_texts_t_keys() - _ALLOWLIST
    missing = sorted(k for k in used if k not in _FA)
    assert not missing, f"Missing from fa.json: {missing[:20]}"


def test_admin_fa_values_have_no_cyrillic():
    admin_keys = [k for k in _FA if k.startswith(("ADMIN_", "C2C_ADMIN_"))]
    bad = [k for k in admin_keys if isinstance(_FA[k], str) and _CYRILLIC.search(_FA[k])]
    assert not bad, f"Cyrillic in fa admin values: {bad[:10]}"
```

- [ ] **Step 2: Run test (may fail until Slice A + D progress)**

```bash
pytest tests/localization/test_admin_fa_coverage.py -v
```

- [ ] **Step 3: Cabinet guard — no Cyrillic in admin `t()` fallbacks**

Add to `tests/test_cabinet_locale_integrity.py`:

```python
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_ADMIN_TSX = Path(__file__).resolve().parents[1] / "cabinet" / "src"
_T_FALLBACK = re.compile(
    r"""t\(\s*['\"](admin\.[^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]""",
)


def test_cabinet_admin_tsx_fallbacks_not_cyrillic():
  # scan Admin*.tsx and components/admin/**
  ...
```

- [ ] **Step 4: Update fa-i18n-status.mdc** — Phase 10 Slice B done; Slice A/C/D/E status.

- [ ] **Step 5: Commit**

```bash
git add tests/localization/test_admin_fa_coverage.py tests/test_cabinet_locale_integrity.py
git commit -m "test(i18n): admin fa coverage and cabinet fallback guards"
```

---

## Task 6: Phase 10 Slice D — bot admin hardcoded Cyrillic (XL)

**Files:** One [app/handlers/admin/<module>.py](../../app/handlers/admin/) + `fa.json` per commit.

**Order (P2 priority):**

| # | Module | ~hardcoded Cyrillic lines |
|---|--------|---------------------------|
| D1 | `remnawave.py` | 543 |
| D2 | `messages.py` | 283 |
| D3 | `monitoring.py` | 408 |
| D4 | `bot_configuration.py` | 297 |
| D5 | `users.py` | 431 |
| D6 | `tariffs.py` | 339 |
| D7 | `main.py` | `admin_commands_help` |
| D8+ | `campaigns`, `promocodes`, `servers`, `contests`, `referrals`, … | descending |

- [ ] **Step 1: Per module — extract hardcoded blocks**

```bash
rg -n '"""' app/handlers/admin/remnawave.py | head
rg -n "[А-Яа-я]{4,}" app/handlers/admin/remnawave.py | rg -v "texts\.t" | head -30
```

- [ ] **Step 2: For each user-visible block — wrap + fa key**

```python
# Before
await callback.message.edit_text(
    f"📊 <b>Статистика нод</b>\n\n"
    f"Онлайн: {online}\n",
    ...
)

# After
texts = get_texts(db_user.language)
body = texts.t(
    "ADMIN_RW_NODE_STATS",
    "📊 <b>Статистика нод</b>\n\nОнлайн: {online}\n",
).format(online=online)
await callback.message.edit_text(body, ...)
```

Add Persian to `fa.json`:
```json
  "ADMIN_RW_NODE_STATS": "📊 <b>آمار گره</b>\n\nآنلاین: {online}\n"
```

- [ ] **Step 3: Agent smoke after each module**

```bash
make smoke && pytest tests/localization/test_admin_fa_coverage.py -q
```

- [ ] **Step 4: Commit one module**

```bash
git commit -m "i18n(fa): admin remnawave panel Persian strings"
```

Repeat D2–D8+ until `rg "[А-Яа-я]{4,}" app/handlers/admin --glob '!**/*test*' | rg -v texts.t` is minimal (only comments/docstrings OK).

---

## Task 7: Staging deploy + smoke map (after Slice A+C or full Phase 10)

**Files:**
- Modify: [docs/templates/smoke-map.md](../../docs/templates/smoke-map.md)

- [ ] **Step 1: Deploy**

| Changed | Command |
|---------|---------|
| Bot `fa.json` + handlers | `make staging-rebuild` |
| Cabinet `fa.json` only | `make staging-cabinet-build` |
| Both | `make staging-rebuild` |

- [ ] **Step 2: Health**

```bash
make staging-health
```

- [ ] **Step 3: Fill smoke-map** — Telegram `@mrj7_bot` admin panel + staging cabinet `/admin`.

- [ ] **Step 4: User sign-off** → `CONFIRM_SHIP=1 make ship BRANCH=i18n/admin-fa-completion`

---

## Task 8: Ship queue — merged branches awaiting operator smoke (parallel track)

Not blocking Phase 10 code, but must ship before considering i18n sprint closed:

| Branch / PR | Smoke needed |
|-------------|--------------|
| `i18n/fa-cabinet-latin-digits` | Staging cabinet user pages — Latin digits |
| `i18n/fa-traffic-step-ux` | `@mrj7_bot` purchase funnel |
| `i18n/fa-onboarding-my-sub` | Detail onboarding + cabinet connection |
| `i18n/p1-remainder-b` | YooKassa keyboard labels |
| `i18n/fa-jalali-dates` | Jalali dates bot + cabinet |
| `fix/toman-balance-units` | Cabinet balance display |
| `feat/subscription-public-serial` | Partner serial smoke |

Each: operator smoke → `تایید` → `CONFIRM_SHIP=1 make ship BRANCH=…` → merge → `CONFIRM_PROD_DEPLOY=1 make prod-deploy`.

---

## Task 9: Deferred / out of scope (document only)

| Item | Reason |
|------|--------|
| Force English admin (`get_texts('en')`) | Operator policy: Persian-first |
| `en.json` backfill for fa-only bot ADMIN keys | Not needed for Persian admin |
| `AdminNotificationService` | Stays Persian by design |
| Phase 13 platform picker / HAPP `دستگاه` keys | Separate small slice |
| `withdrawal.py` `/100` display | `fix/toman-balance-units` follow-up |
| `i18n/fa-remaining` banSystem/settings bulk | Slice B covered banSystem; settings already 172/172 fa |

---

## Self-review

| Check | Result |
|-------|--------|
| Spec §9 commits 1–11 | 1, 11 merged; 2–10 merged or in Phase 10 plan; 12–13, 15 have tasks |
| Phase 10 slices A–E | B marked done; A,C,D,E have concrete steps |
| Placeholders | None — paths, commands, sample code included |
| Slice B gate | Task 0 blocks agent until operator build/smoke |
| Type/name consistency | `texts.t` / `get_texts(db_user.language)` throughout |

---

## Execution handoff

**Plan saved to** `docs/superpowers/plans/2026-06-25-fa-i18n-remaining-implementation.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task (D1, D2, …), review between tasks.
2. **Inline Execution** — same session, batch Tasks 1→2→3 after Task 0 gate.

**Current state:** **Slice B complete** @ `7063e3fe`; user smoke **تایید** 2026-06-25. Branch `i18n/admin-fa-completion` ready for PR (Slice B only) or resume Slices A/C/D/E later.
