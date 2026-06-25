# Smoke map — Partner sequential username (global public serial)

> Branch `feat/subscription-public-serial`; staging deployed after Alembic `0101` + `make staging-rebuild`.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `feat/subscription-public-serial` |
| Tip (pre-docs) | `8b868572` — brand settings from photo referral menu |
| Key commits | `4a901bfd` PG sequence START 1000; `ac604cee` decimal serial allocator; `70ea755a` brand button at confirm; `5168012e` serial in list/search; `8b868572` referral menu brand settings |
| Migration | `0101_subscription_public_serial_seq` |
| Staging | `make staging-migrate` + `make staging-rebuild` + `make staging-health` |
| Bot | `@mrj7_bot` (staging Telegram) |
| Plan | `docs/superpowers/plans/2026-06-24-partner-sequential-username.md` |

## What changed

- Global PostgreSQL sequence allocates decimal public serial (`1000`, `1001`, …) into `subscriptions.remnawave_short_id`.
- Multi-tariff panel username: `{brand_or_template}_{serial}` (e.g. `mobile_x_1000`).
- Partner checkout: brand-name button + preview on confirm (no toggle); prefix stored on `users.panel_brand_prefix`.
- My subscriptions: partners see `#serial` and can search by serial.
- Renewals: panel username unchanged.

## User smoke checklist (staging @mrj7_bot)

| Step | Telegram @mrj7_bot | Expected |
|------|---------------------|----------|
| Partner confirm | Buy tariff → confirm screen | «نام دلخواه: هنوز انتخاب نشده» + button |
| Set brand | Tap 🏷 → `mobile_x` | Preview shows `mobile_x`; DB `users.panel_brand_prefix` |
| First buy | Confirm | Panel username `mobile_x_1000` (or next serial) |
| Second buy | Confirm without changing brand | `mobile_x_1001` |
| Search | My subscriptions → search `1001` | Finds subscription |
| Renewal | Renew existing | Username unchanged in panel |
| Referral menu | Referrals → 🏷 نام برند | Brand settings opens (photo menu fix) |

**Regression:** default purchase (non-partner) still works; existing hex serial rows unchanged; Toman/Jalali/device terminology unaffected.

## Sign-off

- [ ] User smoke on `@mrj7_bot` (partner account with brand prefix)
- [ ] PR → merge → prod deploy (after `تایید`)
