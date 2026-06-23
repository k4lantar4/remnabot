from __future__ import annotations

import subprocess

from tools.mcp.remnabot_dev.config import staging_compose_base, workspace_root


ALLOWED_LOG_FILES = {'bot', 'error', 'payments', 'info', 'warning'}


def tail_staging_bot_logs(*, lines: int = 100) -> str:
    limit = max(1, min(lines, 500))
    cmd = [*staging_compose_base(), 'logs', '--tail', str(limit), 'bot']
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'docker compose logs failed')
    return result.stdout.strip()


def read_staging_log_file(*, name: str, lines: int = 200) -> str:
    if name not in ALLOWED_LOG_FILES:
        raise ValueError(f'Unsupported log file {name!r}. Allowed: {sorted(ALLOWED_LOG_FILES)}')

    limit = max(1, min(lines, 1000))
    path = workspace_root() / 'logs-staging' / 'current' / f'{name}.log'
    if not path.is_file():
        raise FileNotFoundError(f'Log file not found: {path}')

    content = path.read_text(encoding='utf-8', errors='replace').splitlines()
    tail = content[-limit:]
    return '\n'.join(tail)
