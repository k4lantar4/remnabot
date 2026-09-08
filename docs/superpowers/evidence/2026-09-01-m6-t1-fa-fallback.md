# M6-T1 — FA fallback regression gate (G9-strings)

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Task: M6-T1 · weight 3 · batch M6.1 (this task only) · dependencies: M4-T7  
Commit message (this batch): `test(M6-T1): FA fallback gate`

## Verdict: PASS (named unit gate)

`tests/localization/test_fa_fallback.py` locks production FA behavior ported in M4-T7:

- Known FA keys resolve to Persian (not Cyrillic)
- Missing FA key → `en` → `ru`
- English digits (0-9) where required: `format_price` / `format_balance` and ported `C2C_*` / `PAYMENT_C2C` strings

remnabot (`/opt/remnabot`) has **no** `tests/localization/test_fa_fallback.py`. Closest files (`test_texts_fallback.py`, `test_fa_en_ru_chain.py`, `test_user_language.py`) were already in remnabot1 from M4-T7. This gate is the named M6-T1 file.

**G8 / polling / cabinet UI are not this batch.** User smoke: none.

## Tests

Command:

```text
MULTI_TARIFF_ENABLED=false uv run pytest tests/localization/test_fa_fallback.py -v
```

**4 passed.**

| Test | Result |
|---|---|
| `test_known_fa_keys_resolve_to_persian` | PASS (`MAIN_MENU`, `PAYMENT_C2C`, `C2C_ENTER_AMOUNT`, `WELCOME_FALLBACK`) |
| `test_missing_fa_key_falls_back_en_then_ru` | PASS (tmp locales; en wins over ru) |
| `test_format_price_and_balance_use_english_digits` | PASS (`تومان`, ASCII digits, comma grouping, no `۰-۹`) |
| `test_ported_c2c_fa_keys_use_english_digits` | PASS |

Suite:

```text
MULTI_TARIFF_ENABLED=false uv run pytest tests/localization -v
```

**15 passed, 1 skipped.** Skip: `test_en_keys_resolve_before_ru_for_fa_users` — no shared en+ru keys missing from live `fa.json` (same skip as M4-T7). The named gate does **not** skip; it uses isolated tmp locales.

`uv run python -c "import main"` — **OK**. `grep -r get_admin_texts app/` — **0**.

## Scope note (English digits)

Gate covers formatters + ported C2C keys. Live `fa.json` still has Persian digits in some non-C2C strings (`PERIOD_*`, `TRAFFIC_*`, several `ADMIN_*`). That is **not** this gate. Dual-scale Toman is **M6-T2**.

## Isolation

Live `/opt/remnabot1/.env` was **not** rewritten. No polling. No compose rebuild.

| Name | After M6-T1 |
|---|---|
| `rehearsal_bot` app | **absent** (not polled) |
| `rehearsal_bot_db` | Up (untouched) |
| sandbox `remnawave_bot` | id `3a8fbdb915d3…`; **not rebuilt this batch** |
| G1 `rehearsal_bot_pg15` | untouched this batch |
| live Caddy / `panel.rookari.com` | **unchanged** |
