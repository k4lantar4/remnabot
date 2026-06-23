# Smoke map — Phase 2 (bot device terminology)

> Agent: filled for Phase 2 commits on `i18n/fa-device-terminology-bot` (2026-06-23).
> User: verify on staging before ship approval.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/fa-device-terminology-bot` |
| Commits | 4 (TARIFF_*, DEVICE_*, MY_SUB_*, SUBSCRIPTION_*) |
| Staging bot | `@mrj7_bot` |
| Staging cabinet | `https://staging-host-cabinet.rookari.com` |
| Deploy | `make staging-rebuild` (done) |

## Phase 2 — what changed

Bot `fa.json` only: user-facing «دستگاه» → «تعداد کاربر» (HWID limits) or «اتصال» (connected sessions / management).

**Not in this smoke:** cabinet web device labels (Phase 7), miniapp keys (Phase 9), platform picker strings (Phase 13), purchase onboarding copy (Phase 3).

**Parity note:** Cabinet UI may still show «دستگاه» until Phase 7.

## Changes → where to smoke

| # | What to verify | Expected behavior | Telegram path |
|---|----------------|-------------------|---------------|
| 1 | Tariff traffic step | `👥 تعداد کاربر: N` not `📱 دستگاه` | Buy tariff → traffic step |
| 2 | Purchase confirm | Device line says `تعداد کاربر` | Confirm purchase screen |
| 3 | Purchase success | Device line says `تعداد کاربر` | Complete purchase |
| 4 | My subscriptions list | Short count `{n} کاربر` | «اشتراک من» |
| 5 | Subscription detail | `👥 تعداد کاربر: N` | Tap subscription → detail |
| 6 | Device menu buttons | `افزایش تعداد کاربر`, `مدیریت اتصال‌ها` | Detail → device buttons |
| 7 | Change user count flow | Prompts use `کاربر` not `دستگاه` | Change limit → confirm |
| 8 | Manage connections | `اتصال‌های فعال`, `مدیریت اتصال‌ها` | If HWIDs connected |

## Agent verification (done)

```bash
uv run pytest tests/localization/test_texts_fallback.py tests/localization/test_fa_en_ru_chain.py -q  # 7 passed, 1 skipped
make smoke
make staging-rebuild && make staging-health
grep -r get_admin_texts app/  # 0
# user keys with دستگاه: 29 (deferred CABINET_*/MINIAPP_*/HAPP_*/connect flow)
```

## User smoke sign-off

- [ ] Staging Telegram: paths 1–8 verified on `@mrj7_bot`
- [ ] No «دستگاه» in purchase / my_sub / device-change flows
- [ ] User approves → `CONFIRM_SHIP=1 make ship BRANCH=i18n/fa-device-terminology-bot`

## After merge to main

```bash
git checkout main && git pull remnabot main
CONFIRM_PROD_DEPLOY=1 make prod-deploy
cp app/localization/locales/fa.json ./locales/fa.json
docker compose build bot && docker compose up -d bot
```
