from __future__ import annotations

import subprocess
from typing import Any

import httpx

from tools.mcp.remnabot_dev.config import staging_bot_base_url, staging_compose_base


def staging_compose_ps() -> str:
    cmd = [*staging_compose_base(), 'ps']
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'docker compose ps failed')
    return result.stdout.strip()


async def staging_bot_health(*, api_token: str | None) -> dict[str, Any]:
    base = staging_bot_base_url()
    headers: dict[str, str] = {}
    if api_token:
        headers['X-API-Key'] = api_token

    async with httpx.AsyncClient(timeout=10.0) as client:
        health_resp = await client.get(f'{base}/health', headers=headers)
        webhook_resp = await client.get(f'{base}/health/telegram-webhook', headers=headers)

    return {
        'health': {
            'status_code': health_resp.status_code,
            'body': _safe_json(health_resp),
        },
        'telegram_webhook': {
            'status_code': webhook_resp.status_code,
            'body': _safe_json(webhook_resp),
        },
    }


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text[:2000]
