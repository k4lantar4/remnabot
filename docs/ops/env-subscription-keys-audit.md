# Subscription `.env` key audit

Generated: `2026-06-09 18:59 UTC` via `tools/audit_env_subscription_keys.py`.
Env source: `/app/.env` (falls back to process environment when file missing).
Sales mode: `tariffs`.

## Summary

- Total subscription keys scanned: **61**
- Present in `.env` / environment: **46**
- Env-locked (`ENV_OVERRIDE_KEYS`): **46**
- Recommendations: KEEP_ENV=49, REMOVE_FOR_UI=1, USE_TARIFFS_ADMIN=11

## Key table

| Key | In `.env` | Env locked | Runtime value | Recommendation |
| --- | --- | --- | --- | --- |
| `AUTOPAY_WARNING_DAYS` | yes | yes | `'3,1'` | KEEP_ENV |
| `AVAILABLE_RENEWAL_PERIODS` | yes | yes | `'30,90,180'` | KEEP_ENV |
| `AVAILABLE_SUBSCRIPTION_PERIODS` | yes | yes | `'30,90,180'` | KEEP_ENV |
| `BASE_PROMO_GROUP_PERIOD_DISCOUNTS` | yes | yes | `'60:10,90:20,180:40,360:70'` | KEEP_ENV |
| `BASE_PROMO_GROUP_PERIOD_DISCOUNTS_ENABLED` | yes | yes | `False` | KEEP_ENV |
| `BASE_SUBSCRIPTION_PRICE` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `DEFAULT_DEVICE_LIMIT` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `DEFAULT_TRAFFIC_LIMIT_GB` | yes | yes | `1` | KEEP_ENV |
| `DEFAULT_TRAFFIC_RESET_STRATEGY` | yes | yes | `'MONTH'` | KEEP_ENV |
| `DEVICES_SELECTION_DISABLED_AMOUNT` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `DEVICES_SELECTION_ENABLED` | yes | yes | `True` | USE_TARIFFS_ADMIN |
| `FIXED_TRAFFIC_LIMIT_GB` | yes | yes | `100` | KEEP_ENV |
| `MAX_ACTIVE_SUBSCRIPTIONS` | yes | yes | `50` | KEEP_ENV |
| `MULTI_TARIFF_ENABLED` | yes | yes | `True` | KEEP_ENV |
| `PAID_SUBSCRIPTION_USER_TAG` | no | no | `None` | KEEP_ENV |
| `PRICE_14_DAYS` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `PRICE_180_DAYS` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `PRICE_30_DAYS` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `PRICE_360_DAYS` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `PRICE_60_DAYS` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `PRICE_90_DAYS` | yes | yes | `0` | USE_TARIFFS_ADMIN |
| `PRICE_DISPLAY_SUFFIX` | no | no | `' تومان'` | KEEP_ENV |
| `PRICE_PER_DEVICE` | yes | yes | `100000` | USE_TARIFFS_ADMIN |
| `PRICE_ROUNDING_ENABLED` | yes | yes | `True` | KEEP_ENV |
| `PRICE_TRAFFIC_1000GB` | no | no | `19500` | KEEP_ENV |
| `PRICE_TRAFFIC_100GB` | no | no | `15000` | KEEP_ENV |
| `PRICE_TRAFFIC_10GB` | no | no | `3500` | KEEP_ENV |
| `PRICE_TRAFFIC_250GB` | no | no | `17000` | KEEP_ENV |
| `PRICE_TRAFFIC_25GB` | no | no | `7000` | KEEP_ENV |
| `PRICE_TRAFFIC_500GB` | no | no | `19000` | KEEP_ENV |
| `PRICE_TRAFFIC_50GB` | no | no | `11000` | KEEP_ENV |
| `PRICE_TRAFFIC_5GB` | no | no | `2000` | KEEP_ENV |
| `PRICE_TRAFFIC_UNLIMITED` | yes | yes | `10000000` | KEEP_ENV |
| `RESET_TRAFFIC_ON_PAYMENT` | yes | yes | `True` | KEEP_ENV |
| `RESET_TRAFFIC_ON_TARIFF_SWITCH` | no | no | `True` | KEEP_ENV |
| `SALES_MODE` | yes | yes | `'tariffs'` | KEEP_ENV |
| `SIMPLE_SUBSCRIPTION_DEVICE_LIMIT` | yes | yes | `0` | REMOVE_FOR_UI |
| `SIMPLE_SUBSCRIPTION_ENABLED` | yes | yes | `True` | KEEP_ENV |
| `SIMPLE_SUBSCRIPTION_PERIOD_DAYS` | yes | yes | `30` | KEEP_ENV |
| `SIMPLE_SUBSCRIPTION_SQUAD_UUID` | no | no | `None` | KEEP_ENV |
| `SIMPLE_SUBSCRIPTION_TRAFFIC_GB` | yes | yes | `0` | KEEP_ENV |
| `TARIFF_PURCHASE_HIDE_PRICES` | yes | yes | `True` | KEEP_ENV |
| `TARIFF_SWITCH_DOWNGRADE_ENABLED` | yes | yes | `False` | KEEP_ENV |
| `TARIFF_SWITCH_UPGRADE_ENABLED` | yes | yes | `True` | KEEP_ENV |
| `TRAFFIC_PACKAGES_CONFIG` | yes | yes | `'5:5000000:false,10:10000000:false,25:25000000:false,50:50000000:true,100:100...` | KEEP_ENV |
| `TRAFFIC_RESET_BASE_PRICE` | yes | yes | `0` | KEEP_ENV |
| `TRAFFIC_RESET_PRICE_MODE` | yes | yes | `'traffic_with_purchased'` | KEEP_ENV |
| `TRAFFIC_SELECTION_MODE` | yes | yes | `'selectable'` | KEEP_ENV |
| `TRAFFIC_THRESHOLD_GB_PER_DAY` | no | no | `10.0` | KEEP_ENV |
| `TRAFFIC_TOPUP_ENABLED` | yes | yes | `True` | KEEP_ENV |
| `TRAFFIC_TOPUP_PACKAGES_CONFIG` | yes | yes | `''` | KEEP_ENV |
| `TRIAL_ACTIVATION_PRICE` | yes | yes | `0` | KEEP_ENV |
| `TRIAL_ADD_REMAINING_DAYS_TO_PAID` | yes | yes | `False` | KEEP_ENV |
| `TRIAL_DEVICE_LIMIT` | yes | yes | `5` | KEEP_ENV |
| `TRIAL_DISABLED_FOR` | no | no | `'none'` | KEEP_ENV |
| `TRIAL_DURATION_DAYS` | yes | yes | `3` | KEEP_ENV |
| `TRIAL_PAYMENT_ENABLED` | yes | yes | `False` | KEEP_ENV |
| `TRIAL_TARIFF_ID` | yes | yes | `0` | KEEP_ENV |
| `TRIAL_TRAFFIC_LIMIT_GB` | yes | yes | `1` | KEEP_ENV |
| `TRIAL_USER_TAG` | no | no | `None` | KEEP_ENV |
| `TRIAL_WARNING_HOURS` | yes | yes | `2` | KEEP_ENV |

## Priority remediation

1. **Tariffs admin (immediate):** Cabinet → Admin → Tariffs — set `device_limit` and `period_prices` per tariff (پایه / پریمیوم). This fixes device counts and prices while `SALES_MODE=tariffs` regardless of classic `PRICE_*` env keys.
2. **Comment-out for UI control:** Remove these keys from `.env` and restart the bot so `system_settings` / cabinet can apply DB overrides:
   - `SIMPLE_SUBSCRIPTION_DEVICE_LIMIT`
3. **Show prices in bot tariff lists:** Set `TARIFF_PURCHASE_HIDE_PRICES=false` in cabinet/bot settings (keep in `.env` only if you want it fixed at deploy time).
4. **Legacy subscriptions:** Existing `subscriptions.device_limit=1` rows are not controlled by these env keys — use bulk tariff switch / admin tools (out of scope for this audit).

### Env-locked keys — prefer tariffs admin

While `SALES_MODE=tariffs`, these locked keys are superseded by the tariffs table:
- `BASE_SUBSCRIPTION_PRICE`
- `DEFAULT_DEVICE_LIMIT`
- `DEVICES_SELECTION_DISABLED_AMOUNT`
- `DEVICES_SELECTION_ENABLED`
- `PRICE_14_DAYS`
- `PRICE_180_DAYS`
- `PRICE_30_DAYS`
- `PRICE_360_DAYS`
- `PRICE_60_DAYS`
- `PRICE_90_DAYS`
- `PRICE_PER_DEVICE`

## Recommendation legend

| Value | Meaning |
| --- | --- |
| `KEEP_ENV` | Should remain in `.env` for this deployment |
| `REMOVE_FOR_UI` | Remove from `.env` to allow cabinet/bot `system_settings` edits |
| `USE_TARIFFS_ADMIN` | With `SALES_MODE=tariffs`, edit in Admin → Tariffs, not system settings |

## Currency scale (Toman fork)

Two intentional integer scales coexist in this deployment:

| Surface | Storage field names | Integer meaning | Display helper | Example |
| --- | --- | --- | --- | --- |
| Balance, C2C min/max, ledger deposits | `balance_kopeks`, `C2C_*_KOPEKS` | **Toman 1:1** | `format_balance` | `C2C_MIN_AMOUNT_KOPEKS=100000` → 100,000 تومان |
| Catalog (period, traffic packages, subscription charges) | `*_kopeks`, `PRICE_*_DAYS` | **Catalog kopeks** (display Toman × 100) | `format_price` (÷100) | `100_000_000` kopeks → 1,000,000 تومان traffic |

**Period env:** `PRICE_30_DAYS=20000` displays as 200 تومان (not 20,000). For ~20,000 Toman/month use `PRICE_30_DAYS=2000000` or set `period_prices` per tariff in admin.

**Traffic packages:** `traffic_topup_packages` in DB uses catalog kopeks (`gb × 1_000_000` for 10k Toman/GB). Seed: `python -m tools.tariff_traffic_packages_seed --execute --i-understand`.


```bash
docker compose run --rm --no-deps bot python tools/audit_env_subscription_keys.py \
  --write docs/ops/env-subscription-keys-audit.md
```
