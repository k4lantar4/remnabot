from __future__ import annotations

import os
from pathlib import Path


def workspace_root() -> Path:
    env_root = os.environ.get('REMNAWAVE_WORKSPACE')
    if env_root:
        return Path(env_root).resolve()
    # tools/mcp/remnabot_dev/config.py → repo root
    return Path(__file__).resolve().parents[3]


def staging_compose_base() -> list[str]:
    root = workspace_root()
    return [
        'docker',
        'compose',
        '-f',
        str(root / 'docker-compose.staging.yml'),
        '--env-file',
        str(root / '.env.staging'),
        '-p',
        'remnawave-staging',
    ]


STAGING_BOT_HOST = '127.0.0.1'
STAGING_BOT_PORT = 8081


def staging_bot_base_url() -> str:
    return f'http://{STAGING_BOT_HOST}:{STAGING_BOT_PORT}'


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, '')
    if not raw:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def write_tools_enabled() -> bool:
    return env_bool('REMNAWAVE_DEV_MCP_WRITE')


def default_telegram_id() -> int | None:
    raw = os.environ.get('DEV_MCP_TELEGRAM_ID', '').strip()
    if raw:
        return int(raw)
    admin_ids = os.environ.get('ADMIN_IDS', '').strip()
    if not admin_ids:
        return None
    first = admin_ids.split(',')[0].strip()
    if first:
        return int(first)
    return None


def redact_token(value: str | None) -> str:
    if not value:
        return '(not set)'
    if len(value) <= 12:
        return '***'
    return f'{value[:8]}...'
