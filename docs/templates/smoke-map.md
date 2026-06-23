# Smoke map — Phase 2 (bot device terminology) — CLOSED

> Merged PR #73 @ `a1375f5b`; prod deploy + user تایید 2026-06-24.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-device-terminology-bot` (merged, deleted) |
| Merge | `a1375f5b` on `main` |
| Prod | deployed 2026-06-24 |
| Hotfix | PR #74 `show_main_menu` NameError (`9fa5cef5`) |

## Phase 2 — what changed

Bot `fa.json` only: «دستگاه» → «تعداد کاربر» / «اتصال». User keys 147 → 29 (deferred CABINET/MINIAPP/HAPP/connect).

## User smoke sign-off

- [x] Production Telegram: purchase, my_sub, device-change flows — تایید 2026-06-24
- [x] Back to menu (PR #74 hotfix)

## Next phase

Phase 3: `i18n/fa-copy-purchase-success` — onboarding copy in success messages. See `docs/superpowers/plans/2026-06-23-fa-i18n-remaining-audit.md` §9.
