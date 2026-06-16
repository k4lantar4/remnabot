"""Audit subscription-related `.env` keys for tariffs/C2C deployments.

Usage:
    python tools/audit_env_subscription_keys.py
    python tools/audit_env_subscription_keys.py --write docs/ops/env-subscription-keys-audit.md

Reads keys from the Settings model (subscription category matcher), classifies each
against host `.env` (repo root) and `ENV_OVERRIDE_KEYS` / runtime `settings`.
When run inside Docker, `.env` is loaded from the mounted repo root if present;
otherwise only `os.environ` is used for `in_env` detection.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import ENV_OVERRIDE_KEYS, Settings, settings  # noqa: E402


TARIFFS_MODE_PRICE_KEYS = {
    'PRICE_14_DAYS',
    'PRICE_30_DAYS',
    'PRICE_60_DAYS',
    'PRICE_90_DAYS',
    'PRICE_180_DAYS',
    'PRICE_360_DAYS',
    'BASE_SUBSCRIPTION_PRICE',
}
REMOVE_FOR_UI_KEYS = {
    'DEFAULT_DEVICE_LIMIT',
    'SIMPLE_SUBSCRIPTION_DEVICE_LIMIT',
    *TARIFFS_MODE_PRICE_KEYS,
}
KEEP_ENV_KEYS = {
    'SALES_MODE',
    'MULTI_TARIFF_ENABLED',
    'TARIFF_PURCHASE_HIDE_PRICES',
    'TARIFF_SWITCH_UPGRADE_ENABLED',
    'TARIFF_SWITCH_DOWNGRADE_ENABLED',
}
USE_TARIFFS_ADMIN_KEYS = {
    'DEFAULT_DEVICE_LIMIT',
    'MAX_DEVICES_LIMIT',
    'PRICE_PER_DEVICE',
    'DEVICES_SELECTION_ENABLED',
    'DEVICES_SELECTION_DISABLED_AMOUNT',
    *TARIFFS_MODE_PRICE_KEYS,
}

SUBSCRIPTION_PREFIXES = (
    'SALES_',
    'TARIFF_',
    'MULTI_TARIFF',
    'PRICE_',
    'DEFAULT_DEVICE',
    'DEVICES_',
    'SIMPLE_SUBSCRIPTION',
    'TRIAL_',
    'BASE_SUBSCRIPTION',
    'AUTOPAY_',
    'AVAILABLE_SUBSCRIPTION',
    'AVAILABLE_RENEWAL',
    'DEFAULT_TRAFFIC',
    'RESET_TRAFFIC',
    'TRAFFIC_SELECTION',
    'FIXED_TRAFFIC',
    'TRAFFIC_PACKAGES',
    'PRICE_TRAFFIC',
    'PAID_SUBSCRIPTION',
    'MAX_ACTIVE_SUBSCRIPTIONS',
    'BASE_PROMO_GROUP',
)

TRAFFIC_MONITORING_PREFIXES = (
    'TRAFFIC_MONITORING',
    'TRAFFIC_MONITORED',
    'TRAFFIC_SNAPSHOT',
    'TRAFFIC_FAST_',
    'TRAFFIC_DAILY_',
    'TRAFFIC_IGNORED',
    'TRAFFIC_EXCLUDED',
    'TRAFFIC_NOTIFICATION',
    'TRAFFIC_CHECK_',
)

PAYMENT_GATEWAY_PREFIXES = (
    'YOOKASSA_',
    'TRIBUTE_',
    'CRYPTOBOT_',
    'HELEKET_',
    'MULENPAY_',
    'PAL24_',
    'WATA_',
    'CLOUDPAYMENTS_',
    'FREEKASSA_',
    'KASSA_AI_',
    'RIOPAY_',
    'SEVERPAY_',
    'PAYPEAR_',
    'ROLLYPAY_',
    'OVERPAY_',
    'AURAPAY_',
    'ANTILOPAY_',
    'ETOPLATEZHI_',
    'JUPITER_',
    'DONUT_',
    'LAVA_',
    'PLATEGA_',
    'TELEGRAM_STARS',
)

SECRET_PATTERN = re.compile(r'(SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE)', re.IGNORECASE)


def is_subscription_setting_key(key: str) -> bool:
    upper = key.upper()
    if any(upper.startswith(prefix) for prefix in PAYMENT_GATEWAY_PREFIXES):
        return False
    if any(upper.startswith(prefix) for prefix in SUBSCRIPTION_PREFIXES):
        return True
    if upper.startswith('TRAFFIC_'):
        return not any(upper.startswith(prefix) for prefix in TRAFFIC_MONITORING_PREFIXES)
    return False


def load_dotenv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        result[key] = value
    return result


def mask_secret(key: str, value: object) -> str:
    text = repr(value) if value is not None else 'None'
    if SECRET_PATTERN.search(key):
        return '***masked***'
    if len(text) > 80:
        return text[:77] + '...'
    return text


def get_recommendation(key: str, sales_mode: str) -> str:
    if key in KEEP_ENV_KEYS:
        return 'KEEP_ENV'
    if sales_mode == 'tariffs' and key in USE_TARIFFS_ADMIN_KEYS:
        return 'USE_TARIFFS_ADMIN'
    if key in REMOVE_FOR_UI_KEYS:
        return 'REMOVE_FOR_UI'
    return 'KEEP_ENV'


def collect_subscription_keys() -> list[str]:
    keys = [name for name in Settings.model_fields if is_subscription_setting_key(name)]
    return sorted(keys)


def build_audit_rows(env_values: dict[str, str]) -> list[dict[str, object]]:
    sales_mode = str(getattr(settings, 'SALES_MODE', 'tariffs') or 'tariffs')
    rows: list[dict[str, object]] = []
    for key in collect_subscription_keys():
        in_env = key in env_values or key in os.environ
        env_locked = key in ENV_OVERRIDE_KEYS
        runtime_value = getattr(settings, key, None)
        rows.append(
            {
                'key': key,
                'in_env': in_env,
                'env_locked': env_locked,
                'runtime_value': mask_secret(key, runtime_value),
                'recommendation': get_recommendation(key, sales_mode),
            }
        )
    return rows


def render_markdown(rows: list[dict[str, object]], env_path: Path) -> str:
    generated = datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')
    counts = Counter(row['recommendation'] for row in rows)
    locked_count = sum(1 for row in rows if row['env_locked'])
    in_env_count = sum(1 for row in rows if row['in_env'])

    lines = [
        '# Subscription `.env` key audit',
        '',
        f'Generated: `{generated}` via `tools/audit_env_subscription_keys.py`.',
        f'Env source: `{env_path}` (falls back to process environment when file missing).',
        f'Sales mode: `{getattr(settings, "SALES_MODE", "tariffs")}`.',
        '',
        '## Summary',
        '',
        f'- Total subscription keys scanned: **{len(rows)}**',
        f'- Present in `.env` / environment: **{in_env_count}**',
        f'- Env-locked (`ENV_OVERRIDE_KEYS`): **{locked_count}**',
        f'- Recommendations: KEEP_ENV={counts.get("KEEP_ENV", 0)}, '
        f'REMOVE_FOR_UI={counts.get("REMOVE_FOR_UI", 0)}, '
        f'USE_TARIFFS_ADMIN={counts.get("USE_TARIFFS_ADMIN", 0)}',
        '',
        '## Key table',
        '',
        '| Key | In `.env` | Env locked | Runtime value | Recommendation |',
        '| --- | --- | --- | --- | --- |',
    ]

    for row in rows:
        lines.append(
            '| `{key}` | {in_env} | {env_locked} | `{runtime_value}` | {recommendation} |'.format(
                key=row['key'],
                in_env='yes' if row['in_env'] else 'no',
                env_locked='yes' if row['env_locked'] else 'no',
                runtime_value=row['runtime_value'],
                recommendation=row['recommendation'],
            )
        )

    remove_keys = sorted(row['key'] for row in rows if row['recommendation'] == 'REMOVE_FOR_UI' and row['in_env'])
    tariffs_keys = sorted(
        row['key'] for row in rows if row['recommendation'] == 'USE_TARIFFS_ADMIN' and row['env_locked']
    )

    lines.extend(
        [
            '',
            '## Priority remediation',
            '',
            '1. **Tariffs admin (immediate):** Cabinet → Admin → Tariffs — set `device_limit` and '
            '`period_prices` per tariff (پایه / پریمیوم). This fixes device counts and prices while '
            '`SALES_MODE=tariffs` regardless of classic `PRICE_*` env keys.',
            '2. **Comment-out for UI control:** Remove these keys from `.env` and restart the bot '
            'so `system_settings` / cabinet can apply DB overrides:',
        ]
    )
    if remove_keys:
        for key in remove_keys:
            lines.append(f'   - `{key}`')
    else:
        lines.append('   - _(none currently set in `.env`)_')

    lines.extend(
        [
            '3. **Show prices in bot tariff lists:** Set `TARIFF_PURCHASE_HIDE_PRICES=false` in '
            'cabinet/bot settings (keep in `.env` only if you want it fixed at deploy time).',
            '4. **Legacy subscriptions:** Existing `subscriptions.device_limit=1` rows are not controlled '
            'by these env keys — use bulk tariff switch / admin tools (out of scope for this audit).',
        ]
    )

    if tariffs_keys:
        lines.extend(
            [
                '',
                '### Env-locked keys — prefer tariffs admin',
                '',
                'While `SALES_MODE=tariffs`, these locked keys are superseded by the tariffs table:',
            ]
        )
        for key in tariffs_keys:
            lines.append(f'- `{key}`')

    lines.extend(
        [
            '',
            '## Recommendation legend',
            '',
            '| Value | Meaning |',
            '| --- | --- |',
            '| `KEEP_ENV` | Should remain in `.env` for this deployment |',
            '| `REMOVE_FOR_UI` | Remove from `.env` to allow cabinet/bot `system_settings` edits |',
            '| `USE_TARIFFS_ADMIN` | With `SALES_MODE=tariffs`, edit in Admin → Tariffs, not system settings |',
            '',
            '## Regenerate',
            '',
            '```bash',
            'docker compose run --rm --no-deps bot python tools/audit_env_subscription_keys.py \\',
            '  --write docs/ops/env-subscription-keys-audit.md',
            '```',
            '',
        ]
    )
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit subscription-related env keys')
    parser.add_argument(
        '--env-file',
        type=Path,
        default=ROOT_DIR / '.env',
        help='Path to .env file (default: repo root .env)',
    )
    parser.add_argument(
        '--write',
        type=Path,
        default=None,
        help='Write markdown report to this path',
    )
    args = parser.parse_args()

    env_values = load_dotenv(args.env_file)
    env_values.update(os.environ)
    rows = build_audit_rows(env_values)
    markdown = render_markdown(rows, args.env_file)

    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(markdown, encoding='utf-8')
        print(f'Wrote {len(rows)} rows to {args.write}')
    else:
        print(markdown)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
