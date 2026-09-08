# M6-T3 — Wholesale pricing regression gate (G10)

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M6-T3 · weight 3 · batch M6.1 (this task closes the checkpoint) · dependencies: M4-T7  
Commit message (this batch): `test(M6-T3): wholesale gate`

## Verdict: PASS (named unit gate)

`tests/services/test_wholesale_pricing.py` locks production wholesale behavior ported in M4-T7:

- Gating on `partner_status` + `wholesale_discount_bps` via `calculate_user_price` / `PricingEngine` (not `app.custom.pricing`)
- Integer BPS with floor division (`subtotal * (10000 - bps) // 10000`)
- Approved partner discounted; non-approved not

`PartnerStatus` has **no** `REVOKED` member. The gate treats **`REJECTED`** as the production revoke, plus `PENDING` / `NONE`.

remnabot already has `tests/test_wholesale_pricing.py` (identical copy at remnabot1 root, M4-T7). This named file is the M6-T3 path from the live plan.

**G8 / polling / cabinet UI are not this batch.** User smoke: none.

## Tests

```text
MULTI_TARIFF_ENABLED=false uv run pytest tests/services/test_wholesale_pricing.py tests/test_wholesale_pricing.py -v
```

**18 passed** (7 named-gate + 11 ported remnabot).

| Test | Result |
|---|---|
| `test_approved_partner_discounted_integer_bps_floor` | PASS (`9999` @ `3333` bps → `6666`) |
| `test_approved_partner_25_percent` | PASS (`10000` → `7500`) |
| `test_rejected_partner_not_discounted_even_with_bps` | PASS |
| `test_pending_and_none_not_discounted` | PASS |
| `test_price_display_approved_bypasses_retail_promo` | PASS (25% wholesale, not 50% promo) |
| `test_price_display_rejected_uses_retail_not_wholesale` | PASS (50% promo, not 25% wholesale) |
| `test_no_custom_pricing_seam` | PASS (`app.custom.pricing` absent) |

`uv run python -c "import main"` — **OK**. `grep -r get_admin_texts app/` — **0**.

No production-code change. M4-T7 already implemented the ported path.

## Isolation

Live `/opt/remnabot1/.env` was **not** rewritten. No polling. No compose rebuild.

| Name | After M6-T3 |
|---|---|
| `rehearsal_bot` app | **absent** |
| sandbox `remnawave_bot` | Created `2026-09-01T17:01:39Z`; **not rebuilt this batch** |
| live Caddy / `panel.rookari.com` | **unchanged** |
