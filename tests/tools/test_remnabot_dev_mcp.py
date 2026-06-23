from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tools.mcp.remnabot_dev.config import default_telegram_id, env_bool, write_tools_enabled
from tools.mcp.remnabot_dev.health import staging_bot_health, staging_compose_ps
from tools.mcp.remnabot_dev.logs import read_staging_log_file, tail_staging_bot_logs
from tools.mcp.remnabot_dev.webhook_inject import build_update_payload, inject_staging_webhook


def test_env_bool() -> None:
    assert env_bool('TEST_FLAG', default=False) is False


def test_default_telegram_id_from_admin_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('DEV_MCP_TELEGRAM_ID', raising=False)
    monkeypatch.setenv('ADMIN_IDS', '111,222')
    assert default_telegram_id() == 111


def test_default_telegram_id_prefers_dev_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DEV_MCP_TELEGRAM_ID', '999')
    monkeypatch.setenv('ADMIN_IDS', '111')
    assert default_telegram_id() == 999


def test_build_update_payload_start() -> None:
    payload = build_update_payload(template='start', telegram_id=42, update_id=1)
    assert payload['update_id'] == 1
    assert payload['message']['chat']['id'] == 42
    assert payload['message']['from']['id'] == 42
    assert payload['message']['text'] == '/start'


def test_build_update_payload_callback_menu() -> None:
    payload = build_update_payload(template='callback_menu', telegram_id=77, update_id=2)
    assert payload['callback_query']['from']['id'] == 77
    assert payload['callback_query']['data'] == 'menu'


def test_staging_compose_ps_success() -> None:
    with patch('tools.mcp.remnabot_dev.health.subprocess.run') as run:
        run.return_value = MagicMock(returncode=0, stdout='NAME\nbot\n', stderr='')
        assert 'bot' in staging_compose_ps()


def test_staging_compose_ps_failure() -> None:
    with patch('tools.mcp.remnabot_dev.health.subprocess.run') as run:
        run.return_value = MagicMock(returncode=1, stdout='', stderr='compose error')
        with pytest.raises(RuntimeError, match='compose error'):
            staging_compose_ps()


@pytest.mark.anyio
async def test_staging_bot_health() -> None:
    health_json = {'status': 'ok'}
    webhook_json = {'mode': 'webhook'}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/health':
            return httpx.Response(200, json=health_json)
        if request.url.path == '/health/telegram-webhook':
            return httpx.Response(200, json=webhook_json)
        raise AssertionError(f'unexpected path {request.url.path}')

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch('tools.mcp.remnabot_dev.health.httpx.AsyncClient') as client_cls:
            client_cls.return_value.__aenter__.return_value = client
            result = await staging_bot_health(api_token='secret')

    assert result['health']['body'] == health_json
    assert result['telegram_webhook']['body'] == webhook_json


def test_tail_staging_bot_logs() -> None:
    with patch('tools.mcp.remnabot_dev.logs.subprocess.run') as run:
        run.return_value = MagicMock(returncode=0, stdout='log line\n', stderr='')
        assert tail_staging_bot_logs(lines=10) == 'log line'


def test_read_staging_log_file_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match='Unsupported log file'):
        read_staging_log_file(name='unknown', lines=10)


def test_read_staging_log_file_tail(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_dir = tmp_path / 'logs-staging' / 'current'
    log_dir.mkdir(parents=True)
    (log_dir / 'bot.log').write_text('line1\nline2\nline3\n', encoding='utf-8')
    monkeypatch.setattr('tools.mcp.remnabot_dev.logs.workspace_root', lambda: tmp_path)
    content = read_staging_log_file(name='bot', lines=2)
    assert content == 'line2\nline3'


@pytest.mark.anyio
async def test_inject_staging_webhook() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured['path'] = request.url.path
        captured['headers'] = dict(request.headers)
        captured['body'] = json.loads(request.content.decode())
        return httpx.Response(200, json={'status': 'ok'})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch('tools.mcp.remnabot_dev.webhook_inject.httpx.AsyncClient') as client_cls:
            client_cls.return_value.__aenter__.return_value = client
            result = await inject_staging_webhook(
                template='start',
                telegram_id=123,
                webhook_path='/webhook',
                webhook_secret='sekret',
            )

    assert result['status_code'] == 200
    assert captured['path'] == '/webhook'
    assert captured['headers']['x-telegram-bot-api-secret-token'] == 'sekret'
    assert captured['body']['message']['text'] == '/start'


def test_write_tools_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('REMNAWAVE_DEV_MCP_WRITE', raising=False)
    assert write_tools_enabled() is False
