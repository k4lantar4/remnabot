from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from tools.mcp.remnabot_dev.config import default_telegram_id, write_tools_enabled
from tools.mcp.remnabot_dev.health import (
    staging_bot_health as fetch_staging_bot_health,
    staging_compose_ps as fetch_staging_compose_ps,
)
from tools.mcp.remnabot_dev.logs import (
    read_staging_log_file as read_staging_log_file_impl,
    tail_staging_bot_logs as tail_staging_bot_logs_impl,
)
from tools.mcp.remnabot_dev.telegram_api import telegram_bot_api_info as fetch_telegram_bot_api_info
from tools.mcp.remnabot_dev.webhook_inject import (
    inject_staging_webhook as inject_staging_webhook_impl,
    send_test_notification as send_test_notification_impl,
)


mcp = FastMCP(
    'remnawave-dev',
    instructions=(
        'Staging-only remnabot dev tools: health, logs, Telegram Bot API status. '
        'Use remnawave-staging-postgres/redis for DB/cache. Never use write tools on production.'
    ),
)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _require_telegram_id(telegram_id: int | None) -> int:
    resolved = telegram_id or default_telegram_id()
    if resolved is None:
        raise ValueError('telegram_id required — set DEV_MCP_TELEGRAM_ID or ADMIN_IDS in .env.staging')
    return resolved


@mcp.tool()
def staging_compose_ps() -> str:
    """Show staging Docker Compose container status (remnawave-staging stack)."""
    return fetch_staging_compose_ps()


@mcp.tool()
async def staging_bot_health() -> str:
    """Fetch staging bot /health and /health/telegram-webhook from localhost:8081."""
    token = os.environ.get('WEB_API_DEFAULT_TOKEN') or None
    return _json(await fetch_staging_bot_health(api_token=token))


@mcp.tool()
def tail_staging_bot_logs(lines: int = 100) -> str:
    """Return the last N lines of staging bot container stdout (no follow)."""
    return tail_staging_bot_logs_impl(lines=lines)


@mcp.tool()
def read_staging_log_file(name: str = 'bot', lines: int = 200) -> str:
    """Read tail of a rotated staging log file from logs-staging/current/. Allowed: bot, error, payments, info, warning."""
    return read_staging_log_file_impl(name=name, lines=lines)


@mcp.tool()
async def telegram_bot_api_info() -> str:
    """Call Telegram getMe and getWebhookInfo for the staging BOT_TOKEN."""
    token = os.environ.get('BOT_TOKEN', '').strip()
    if not token:
        raise ValueError('BOT_TOKEN not set in environment')
    data = await fetch_telegram_bot_api_info(bot_token=token)
    return _json(data)


if write_tools_enabled():

    @mcp.tool()
    async def inject_staging_webhook(
        template: str = 'start',
        telegram_id: int | None = None,
    ) -> str:
        """POST a synthetic Telegram Update to staging webhook (runs real handlers). Staging only; requires REMNAWAVE_DEV_MCP_WRITE=1."""
        resolved_id = _require_telegram_id(telegram_id)
        webhook_path = os.environ.get('WEBHOOK_PATH', '/webhook').strip() or '/webhook'
        secret = os.environ.get('WEBHOOK_SECRET_TOKEN', '').strip() or None
        result = await inject_staging_webhook_impl(
            template=template,
            telegram_id=resolved_id,
            webhook_path=webhook_path,
            webhook_secret=secret,
        )
        return _json(result)

    @mcp.tool()
    def send_test_notification(telegram_id: int | None = None, days: int = 1) -> str:
        """Send a real expiring-subscription test DM via staging bot. Staging only; requires REMNAWAVE_DEV_MCP_WRITE=1."""
        resolved_id = _require_telegram_id(telegram_id)
        return send_test_notification_impl(telegram_id=resolved_id, days=days)


def main() -> None:
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
