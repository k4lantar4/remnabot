# fa-i18n P2 — Admin Surfaces (Bot + Cabinet Admin) — Outline

> **Status:** Outline only. Expand before execution after P1 user surfaces plan is merged.

**Goal:** Localize remaining ~3,300 hardcoded Russian strings in Admin Telegram handlers and ~225 in cabinet admin routes for admins with `language=fa`.

**Architecture:** Same `get_texts(db_user.language).t('KEY', 'ru fallback')` — admin **is** localized via user language per project rules (not `get_admin_texts`). One `app/handlers/admin/<file>.py` per commit + `fa.json`. Prefix keys with `ADMIN_`.

**Priority order (from audit):**

1. `app/handlers/admin/remnawave.py` (~551 hardcoded; node/traffic/system detail blocks)
2. `app/handlers/admin/messages.py` (~204; broadcast create/history/criteria FSM)
3. `app/handlers/admin/monitoring.py` (~317)
4. `app/handlers/admin/bot_configuration.py` (~306)
5. `app/handlers/admin/users.py` (~257)
6. `app/handlers/admin/payments.py` (+ 13 missing `fa` keys: `ADMIN_PAYMENTS_CHECK_ALL`, etc.)
7. `app/keyboards/admin.py` (~290 button labels)
8. Cabinet admin: `admin_email_templates.py`, `admin_payments.py`, `admin_broadcasts.py`, `admin_promo_offers.py`

**Verification:** Same agent smoke; admin user smoke in Telegram admin panel.

**Depends on:** `2026-06-06-fa-i18n-p1-user-surfaces.md` merged and `fa-i18n-status.mdc` updated.
