# Alembic graph decision evidence

Date: 2026-08-31  
Host: RC (`bot-v4` / `91.107.144.95`)  
Task: M0-T6 · Authority: MVP plan `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`  
Branch: `prod-cutover` @ `3926dd03957adefc0cb78897be0679c03b6c3886` (at dispatch)

## Goal

Record verified Alembic collision facts and the graft strategy **before any migration file edit**. Graft execution is M4-T0; this document is evidence only.

## Verification commands (exact)

```bash
find /opt/remnabot1/migrations/alembic/versions -maxdepth 1 -name '*.py' -printf '%f\n' | sort
find /opt/remnabot/migrations/alembic/versions -maxdepth 1 -name '*.py' -printf '%f\n' | sort
cd /opt/remnabot1 && docker compose run --rm --no-deps bot alembic heads
cd /opt/remnabot && docker compose run --rm --no-deps bot alembic heads
```

Collision-range subset (0088–0110 on remnabot1; 0088–0104 on remnabot):

```bash
find /opt/remnabot1/migrations/alembic/versions -maxdepth 1 -name '008[89]*.py' -o -name '009*.py' -o -name '010*.py' -o -name '0110*.py' | xargs -I{} basename {} | sort
find /opt/remnabot/migrations/alembic/versions -maxdepth 1 \( -name '008[89]*.py' -o -name '009*.py' -o -name '010*.py' \) | xargs -I{} basename {} | sort
```

## Decision table (verified live)

```
Last shared: 0087 (0087_add_autopay_period_days_to_subscriptions.py — same filename on both trees)
remnabot1 0088 = 0088_dedupe_tariff_subscriptions.py (no-op)
remnabot  0088 = 0088_create_c2c_receipts.py
remnabot1 0103 = 0103_add_legal_consents.py
remnabot  0103 = 0103_subscription_user_disabled.py
remnabot1 0104 = 0104_remnawave_numeric_id.py
remnabot  0104 = 0104_traffic_purchase_expiry_clamp.py
remnabot1 0105.down_revision = '0104' (0105_promocode_traffic_gb.py)
remnabot1 head file = 0110_referral_user_reward_choice.py
remnabot 0096 = 0096_merge_c2c_and_partner_heads.py · down_revision = ('0094','0095')
Production DB = remnabot-lineage 0103 (live prod + dump; see host-inventory-prod / M2-T1)
remnabot1 disk head = 0110 (alembic heads)
remnabot disk head = 0104 (alembic heads)
Graft = archive remnabot1 0088–0110 + copy remnabot 0088–0104 same commit
0111+ chain from remnabot 0104
No 0111* files on either tree at M0-T6
Hazards = run_alembic_upgrade / leftover 0105–0110 / 0001 create_all / 4.2 tests
Forbidden = no remnabot1 process / no alembic upgrade / no stamp on restored volumes until M4-T0
Fallback = PLAN REVISION REQUIRED: Alembic graft failed M4-T0
```

Seed brief values vs live `find`: **all match** (no filename typos; strategy not invalidated).

## Collision detail: 0088–0110 (same revision IDs, different files)

| Rev | remnabot1 (`/opt/remnabot1`) | remnabot (`/opt/remnabot`) |
|---|---|---|
| 0088 | `0088_dedupe_tariff_subscriptions.py` (no-op) | `0088_create_c2c_receipts.py` |
| 0089 | `0089_wheel_spins_telegram_charge_id.py` | `0089_dedupe_tariff_subscriptions.py` |
| 0090 | `0090_add_quick_amounts_to_payment_method_configs.py` | `0090_wheel_spins_telegram_charge_id.py` |
| 0091 | `0091_add_info_pages_display_mode.py` | `0091_multi_account_per_user.py` |
| 0092 | `0092_backfill_vk_yandex_email_verified.py` | `0092_subscription_panel_username.py` |
| 0093 | `0093_yclid.py` | `0093_add_wholesale_discount_bps.py` |
| 0094 | `0094_payment_method_description.py` | `0094_c2c_receipt_enhancements.py` |
| 0095 | `0095_add_coupons.py` | `0095_partner_panel_fields.py` |
| 0096 | `0096_add_recurrent_payments.py` | `0096_merge_c2c_and_partner_heads.py` (merge) |
| 0097 | `0097_add_grace_access.py` | `0097_add_quick_amounts_to_payment_method_configs.py` |
| 0098 | `0098_create_cispay_payments.py` | `0098_add_info_pages_display_mode.py` |
| 0099 | `0099_add_platega_subscriptions.py` | `0099_backfill_vk_yandex_email_verified.py` |
| 0100 | `0100_platega_sub_unique_alive.py` | `0100_yclid.py` |
| 0101 | `0101_add_lava_subscriptions.py` | `0101_subscription_public_serial_seq.py` |
| 0102 | `0102_coupon_max_per_user.py` | `0102_broadcast_entities_json.py` |
| 0103 | `0103_add_legal_consents.py` | `0103_subscription_user_disabled.py` |
| 0104 | `0104_remnawave_numeric_id.py` | `0104_traffic_purchase_expiry_clamp.py` |
| 0105 | `0105_promocode_traffic_gb.py` | — (not on remnabot graph) |
| 0106 | `0106_guest_purchase_campaign.py` | — |
| 0107 | `0107_guest_purchase_idempotency.py` | — |
| 0108 | `0108_referral_reward_levels.py` | — |
| 0109 | `0109_referral_level_thresholds.py` | — |
| 0110 | `0110_referral_user_reward_choice.py` | — |

Collision begins at **0088**. Last shared revision **0087** is identical filename on both trees.

## Graft strategy (M4-T0 — not executed at M0-T6)

1. **Archive** all remnabot1 files `0088–0110` out of `migrations/alembic/versions/` into `docs/superpowers/reference/upstream-alembic-0088-0110/` (reference only).
2. **Copy** remnabot files `0088–0104` into `migrations/alembic/versions/` in the **same commit** as the archive.
3. **Verify** `alembic heads` = remnabot `0104` (`0104_traffic_purchase_expiry_clamp.py`).
4. **Chain** new MVP migrations as `0111+` from remnabot `0104`.

Do **not** create the archive directory at M0-T6.

## Explicit forbiddens (binding until M4-T0 PASS)

| Forbidden action | Reason |
|---|---|
| Apply `0104_remnawave_numeric_id.py` onto remnabot `0104` / remnabot-lineage `0103` DB | Upstream numeric-ID migration is not production lineage; would corrupt graft target |
| Leave `0105–0110` in `versions/` after graft | `0105.down_revision = '0104'` would attach upstream chain to grafted `0104` and run `0110` head |
| Start remnabot1 against `rehearsal_bot_pg15` before M4-T0 | `main.py` runs `run_alembic_upgrade()`; risks auto-upgrade/stamp on restored dump |
| `alembic upgrade` or `stamp` on restored volumes until M4-T0 | Hides mismatch; forbidden by MVP plan DAG |
| Any remnabot1 **app** process on a volume containing restored production dump until M4-T0 | Same auto-upgrade hazard; use `SKIP_MIGRATION=true` if container must touch restored DB pre-M4-T0 |

## Hazards (post-graft awareness)

- **Startup auto-upgrade:** remnabot1 `main.py` calls `run_alembic_upgrade()` before bot setup; existing DBs get `command.upgrade(..., 'head')`; “fresh” path may `create_all` + `stamp head`.
- **Leftover 0105–0110:** fatal — upstream head would remain reachable after copying remnabot `0104`.
- **`0001_initial_schema.py`:** fresh-DB path differs from production restore path.
- **4.2 tests/models:** may assume upstream `0110` graph until realigned after graft.

## M4-T0 verification gate

Pass when:

- `alembic heads` = remnabot `0104` (traffic clamp)
- No `0104_remnawave_numeric_id.py` in live `versions/`
- No `0110_*.py` in live `versions/`
- Archive directory contains the archived remnabot1 `0088–0110` files

## Fallback

If M4-T0 graft verification fails after good-faith archive+copy:

`PLAN REVISION REQUIRED: Alembic graft failed M4-T0`

Recovery path: re-ID new migrations from production `0103` only (additive `0111+`). Do not boot remnabot1 on restored data until a graph strategy passes M4-T0 gates.

## Cross-references

- Production DB `alembic_version=0103`: `docs/superpowers/evidence/2026-08-29-host-inventory-prod.md`, `docs/superpowers/evidence/2026-08-29-host-inventory-rc.md` (dump SHA `b5fc023a…`, rehearsal input)
- MVP plan §18 Alembic: `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`
