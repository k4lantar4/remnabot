# Tariff Mode Configuration Guide

This document maps all settings that affect `SALES_MODE=tariffs` behavior.

## Configuration Layers

| Layer | Source | Changed via | Restart needed? |
|---|---|---|---|
| 1. Architecture flags | `.env` | Server admin | Yes |
| 2. Runtime admin | DB `SystemSetting` | Cabinet admin panel → Settings | No |
| 3. Per-tariff | DB `Tariff` model | Cabinet admin panel → Tariffs | No |

**Precedence rule for tariff mode:** Layer 3 (per-tariff) wins over Layer 2/1 for that tariff's behavior.

## Architecture Flags (Layer 1 — .env only)

| Key | Description | Default |
|---|---|---|
| `SALES_MODE` | `tariffs` or `classic` | `tariffs` |
| `MULTI_TARIFF_ENABLED` | Allow multiple subscriptions per user | `False` |
| `MAX_ACTIVE_SUBSCRIPTIONS` | Max subscriptions per user (multi-tariff) | `10` |
| `TARIFF_PURCHASE_HIDE_PRICES` | Hide prices in tariff selection keyboard | `False` |

## Display / Currency (Layer 1 — .env only)

| Key | Description |
|---|---|
| `PRICE_DISPLAY_SUFFIX` | Currency suffix shown to users (` تومان`) |
| `PRICE_ROUNDING_ENABLED` | Round kopeks in display |

### Price Unit Scales

Two separate scales exist in the codebase:

- **Catalog scale** (period prices, traffic packages): `kopeks = Toman × 100`
  - `period_prices["30"] = 3_000_000` → displayed as 30,000 تومان
  - `traffic_topup_packages["10"] = 900_000` → displayed as 9,000 تومان
  - Convert to user-balance charge: `catalog_price_in_toman(x) = x // 100`

- **Balance scale** (user.balance_kopeks after 2026-06-05): `Toman 1:1`
  - `user.balance_kopeks = 90_000` → displayed as 90,000 تومان
  - Access via `display_balance_from_storage(x) = float(x)`

## Per-Tariff Settings (Layer 3 — Tariff model)

### Purchase flow

| Field | Type | Description |
|---|---|---|
| `period_prices` | JSON `{days: kopeks}` | Available subscription periods |
| `traffic_limit_gb` | int | Fixed traffic limit (0 = unlimited) |
| `custom_traffic_enabled` | bool | Show traffic selection step at purchase |
| `traffic_price_per_gb_kopeks` | int | Per-GB price (0 = packages only, no free input) |
| `min_traffic_gb` / `max_traffic_gb` | int | Range for traffic selection |
| `custom_days_enabled` | bool | Show ±day slider at purchase |
| `price_per_day_kopeks` | int | Price per day for custom days |
| `is_daily` | bool | Daily billing tariff |
| `daily_price_kopeks` | int | Daily charge amount |

### Traffic top-up (post-purchase)

| Field | Type | Description |
|---|---|---|
| `traffic_topup_enabled` | bool | Allow top-up purchases after subscription |
| `traffic_topup_packages` | JSON `{gb: kopeks}` | Available top-up packages (also used as purchase buttons when `custom_traffic_enabled=True`) |
| `max_topup_traffic_gb` | int | Max total traffic after top-up (0 = no limit) |
| `allow_traffic_topup` | bool | Whether top-up is allowed at all |

`can_topup_traffic()` (Tariff model method) returns `True` when both `traffic_topup_enabled=True` and `allow_traffic_topup=True`.

### Other per-tariff settings

| Field | Description |
|---|---|
| `allowed_squads` | Server UUIDs available for this tariff |
| `external_squad_uuid` | RemnaWave squad UUID assigned to subscriptions |
| `device_limit` / `device_price_kopeks` | Device limits and addon pricing |
| `is_trial_available` | Allow trial on this tariff |
| `show_in_gift` | Show in gift flow |
| `traffic_reset_mode` | Override global reset strategy |

## Purchase Flow Decision Tree

```
select_tariff()
├─ is_daily=True → daily confirmation screen
├─ can_purchase_custom_days() → ± slider screen
├─ can_purchase_custom_traffic() → traffic selection screen (→ period → confirm)
│   requires: custom_traffic_enabled=True AND (traffic_price_per_gb_kopeks>0 OR traffic_topup_packages non-empty)
└─ else → direct period selection (→ confirm)
```

## Global Flags That Affect Tariff Mode

These global flags can override per-tariff behavior. In tariff mode, per-tariff settings take precedence (mode isolation implemented in `app/handlers/subscription/traffic.py`).

| Global Flag | Classic mode | Tariff mode behavior |
|---|---|---|
| `TRAFFIC_TOPUP_ENABLED` | Gates all top-up | Ignored; use `tariff.can_topup_traffic()` |
| `TRAFFIC_SELECTION_MODE='fixed'` | Blocks top-up and reset | Ignored for top-up/reset/switch; per-tariff `allow_traffic_topup` gates instead |
| `TRAFFIC_PACKAGES_CONFIG` | Defines available packages | Ignored; `tariff.traffic_topup_packages` used |
| `TRAFFIC_TOPUP_PACKAGES_CONFIG` | Defines top-up packages | Ignored in tariff mode |

### Mode isolation details (`app/handlers/subscription/traffic.py`)

| Handler | Classic mode gate | Tariff mode gate |
|---|---|---|
| `handle_add_traffic` | `is_traffic_topup_enabled()` + `is_traffic_topup_blocked()` | `tariff.can_topup_traffic()` |
| `handle_reset_traffic` | `is_traffic_topup_blocked()` | `tariff.allow_traffic_topup` |
| `confirm_reset_traffic` | `is_traffic_topup_blocked()` | `tariff.allow_traffic_topup` |
| `handle_switch_traffic` | `is_traffic_topup_blocked()` | `tariff.allow_traffic_topup` |
| Cabinet GET packages | `is_traffic_topup_enabled()` | `tariff.traffic_topup_enabled` |
| Cabinet POST purchase | `is_traffic_topup_enabled()` | `tariff.traffic_topup_enabled` |

### Keyboard functions without tariff context

These keyboard builders have no tariff object available; the global flag is kept as a conservative fallback:

- `get_traffic_packages_keyboard()` — classic mode only keyboard
- `get_reset_traffic_confirm_keyboard()` — classic mode only keyboard
