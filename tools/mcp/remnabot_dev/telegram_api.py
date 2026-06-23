from __future__ import annotations

from typing import Any

import httpx


async def telegram_bot_api_info(*, bot_token: str) -> dict[str, Any]:
    base = f'https://api.telegram.org/bot{bot_token}'
    async with httpx.AsyncClient(timeout=15.0) as client:
        me_resp = await client.get(f'{base}/getMe')
        webhook_resp = await client.get(f'{base}/getWebhookInfo')

    return {
        'getMe': me_resp.json(),
        'getWebhookInfo': webhook_resp.json(),
    }
