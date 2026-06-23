# Smoke map (fill before user staging smoke)

> Agent: update this file at end of each sprint / before `deploy-staging.sh`.
> User: follow paths in Telegram / cabinet to verify copy and UX.

## Branch & deploy

| Item | Value |
|------|--------|
| Branch | `i18n/…` |
| Staging bot | `@…` (from `.env.staging` `BOT_USERNAME`) |
| Staging cabinet | `CABINET_URL` |
| Deploy | `./tools/deploy-staging.sh` (same server as prod) |

## Changes → where to smoke

| # | Key / file | User-visible text / behavior | Telegram / UI path |
|---|------------|------------------------------|-------------------|
| 1 | `TARIFF_TRAFFIC_STEP_HEADER` / `tariff_purchase.py` | Header at volume step | منو → خرید سرویس → تعرفه → **مرحله انتخاب حجم** (دکمه‌های ۱۰/۲۰ گیگ…) |
| 2 | `TARIFF_CUSTOM_TRAFFIC_STEP_HINT` | Hint under header | همان صفحه — متن راهنما زیر خلاصه |
| 3 | `TARIFF_PERIOD_AFTER_TRAFFIC` | After picking GB | کلیک روی یک حجم → **مرحله انتخاب مدت زمان** |
| 4 | `TARIFF_PURCHASE_SUCCESS` | Post-payment message | تکمیل خرید → پیام موفقیت |
| 5 | `MY_SUB_*` | Subscription detail | منو → **اشتراک من** → یک اشتراک → جزئیات + دکمه‌ها |
| 6 | `cabinet/.../fa.json` | Cabinet strings | `CABINET_URL` → همان صفحات |

## Callback / button checklist

| Callback / button | Handler | Expected after change |
|-------------------|---------|------------------------|
| `tariff_traffic_ct:*` | `tariff_purchase.py` | انتخاب حجم → رفتن به دوره |
| `tariff_period_ct:*` | `tariff_purchase.py` | انتخاب مدت → تأیید/پرداخت |
| `my_subscriptions` | `my_subscriptions.py` | لیست اشتراک‌ها فارسی |
| `sub_connect:*` | `my_subscriptions.py` | لینک / راهنما |

## User smoke sign-off

- [ ] Staging Telegram: paths above verified
- [ ] Staging cabinet (if touched): pages verified
- [ ] No Cyrillic / wrong «دستگاه» / duplicate «حجم»
- [ ] User approves → `CONFIRM_SHIP=1 ./tools/ship-after-smoke.sh <branch>`

## After merge to main (production stack, same server)

```bash
git checkout main && git pull
CONFIRM_PROD_DEPLOY=1 ./tools/deploy-production.sh
```

Production smoke (short): `/start` → buy path → اشتراک من — same paths as above on live bot.
