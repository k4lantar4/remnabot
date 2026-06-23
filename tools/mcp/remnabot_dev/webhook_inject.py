from __future__ import annotations

import json
import subprocess
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx

from tools.mcp.remnabot_dev.config import staging_bot_base_url, staging_compose_base


FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures'
FIXTURE_NAMES = {
    'start': 'message_start.json',
    'callback_menu': 'callback_menu.json',
    'callback_my_subscriptions': 'callback_my_subscriptions.json',
}


def build_update_payload(*, template: str, telegram_id: int, update_id: int | None = None) -> dict[str, Any]:
    if template not in FIXTURE_NAMES:
        raise ValueError(f'Unknown template {template!r}. Use: {sorted(FIXTURE_NAMES)}')

    path = FIXTURE_DIR / FIXTURE_NAMES[template]
    payload = json.loads(path.read_text(encoding='utf-8'))
    payload = deepcopy(payload)
    payload['update_id'] = update_id or int(time.time())

    if 'message' in payload:
        payload['message']['chat']['id'] = telegram_id
        payload['message']['from']['id'] = telegram_id
        payload['message']['message_id'] = int(time.time()) % 1_000_000

    if 'callback_query' in payload:
        payload['callback_query']['from']['id'] = telegram_id
        payload['callback_query']['message']['chat']['id'] = telegram_id
        payload['callback_query']['message']['message_id'] = int(time.time()) % 1_000_000

    return payload


async def inject_staging_webhook(
    *,
    template: str,
    telegram_id: int,
    webhook_path: str,
    webhook_secret: str | None,
    custom_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if custom_payload is not None:
        payload = custom_payload
    else:
        payload = build_update_payload(template=template, telegram_id=telegram_id)

    url = f'{staging_bot_base_url()}{webhook_path}'
    headers = {'Content-Type': 'application/json'}
    if webhook_secret:
        headers['X-Telegram-Bot-Api-Secret-Token'] = webhook_secret

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    return {
        'url': url,
        'status_code': response.status_code,
        'body': response.text[:2000],
        'update_id': payload.get('update_id'),
        'template': template if custom_payload is None else 'custom',
    }


def send_test_notification(*, telegram_id: int, days: int = 1) -> str:
    return _run_staging_tool(
        [
            'python',
            'tools/send_monitoring_expiring_test.py',
            '--telegram-id',
            str(telegram_id),
            '--days',
            str(days),
        ]
    )


def _run_staging_tool(args: list[str]) -> str:
    cmd = [*staging_compose_base(), 'run', '--rm', 'bot', *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = (result.stdout or '') + (result.stderr or '')
    if result.returncode != 0:
        raise RuntimeError(output.strip() or 'staging tool failed')
    return output.strip()
