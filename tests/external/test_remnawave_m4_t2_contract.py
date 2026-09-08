"""M4-T2: remnabot1 3.x client vs rehearsal 3.4.3 identity contract.

M3-ID: uuid lookup is gone. Live client paths must not call the removed 2.8
routes, and ``coerce_panel_user_id`` must reject leftover panel UUIDs before
any request (panel ``numberParamSchema = z.coerce.number().positive()``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.external.remnawave_api import (
    RemnaWaveAPI,
    RemnaWaveInvalidUserIdError,
    coerce_panel_user_id,
)

CLIENT_PATH = Path(__file__).resolve().parents[2] / 'app' / 'external' / 'remnawave_api.py'

REMOVED_28_USER_PATH_PREFIXES = (
    '/api/users/by-uuid',
    '/api/users/by-subscription-uuid',
    '/api/users/by-telegram-id',
)


def _string_fragments(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        fragments: list[str] = []
        for value in node.values:
            fragments.extend(_string_fragments(value))
        return fragments
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _string_fragments(node.left) + _string_fragments(node.right)
    return []


def _matches_removed_prefix(fragment: str, prefix: str) -> bool:
    return fragment == prefix or fragment.startswith(prefix + '/') or fragment.startswith(prefix + '{')


def forbidden_make_request_hits(source: str) -> list[tuple[int, str, str]]:
    """Return (lineno, fragment, prefix) for ``_make_request`` endpoints that hit removed 2.8 user routes."""
    tree = ast.parse(source)
    hits: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_make_request = (isinstance(func, ast.Attribute) and func.attr == '_make_request') or (
            isinstance(func, ast.Name) and func.id == '_make_request'
        )
        if not is_make_request:
            continue
        endpoint_node = node.args[1] if len(node.args) >= 2 else None
        if endpoint_node is None:
            for keyword in node.keywords:
                if keyword.arg in {'endpoint', 'path', 'url'}:
                    endpoint_node = keyword.value
                    break
        if endpoint_node is None:
            continue
        for fragment in _string_fragments(endpoint_node):
            for prefix in REMOVED_28_USER_PATH_PREFIXES:
                if _matches_removed_prefix(fragment, prefix):
                    hits.append((node.lineno, fragment, prefix))
    return hits


def test_scanner_detects_removed_by_uuid_path_in_make_request():
    source = "await self._make_request('GET', '/api/users/by-uuid/dead')\n"
    hits = forbidden_make_request_hits(source)
    assert hits == [(1, '/api/users/by-uuid/dead', '/api/users/by-uuid')]


def test_scanner_does_not_treat_by_short_uuid_as_removed_by_uuid():
    source = "await self._make_request('GET', f'/api/users/by-short-uuid/{short_uuid}')\n"
    assert forbidden_make_request_hits(source) == []


def test_live_client_make_request_paths_omit_removed_28_user_routes():
    hits = forbidden_make_request_hits(CLIENT_PATH.read_text(encoding='utf-8'))
    assert hits == [], hits


def test_client_has_no_uuid_user_lookup_methods():
    assert not hasattr(RemnaWaveAPI, 'get_user_by_uuid')
    assert not hasattr(RemnaWaveAPI, 'get_user_by_subscription_uuid')
    assert not hasattr(RemnaWaveAPI, 'get_user_by_telegram_id')


@pytest.mark.parametrize(
    'value',
    [
        '11111111-1111-1111-1111-111111111111',
        '0f2a5f6c-1f4e-4f0c-9b3a-6f2d1c8e7a10',
    ],
)
def test_coerce_panel_user_id_rejects_uuids(value: str):
    with pytest.raises(RemnaWaveInvalidUserIdError):
        coerce_panel_user_id(value)
