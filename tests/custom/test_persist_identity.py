"""M4-T5: persist_identity writes panel users.id onto User and/or Subscription.

M3-ID: uuid lookup is gone. The seam must take numeric ``.id`` (or an already
coerced id) and must not grow ``resolve_remnawave_id(uuid=...)``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.custom.identity.persist import persist_identity
from app.external.remnawave_api import RemnaWaveInvalidUserIdError

SEAM = Path(__file__).resolve().parents[2] / 'app' / 'custom' / 'identity' / 'persist.py'


def test_user_write_path_uses_panel_id() -> None:
    user = SimpleNamespace(remnawave_id=None)
    panel = SimpleNamespace(id=932, uuid='0f2a5f6c-1f4e-4f0c-9b3a-6f2d1c8e7a10')
    assert persist_identity(user=user, panel_user=panel) == 932
    assert user.remnawave_id == 932


def test_subscription_write_path_uses_panel_id() -> None:
    subscription = SimpleNamespace(remnawave_id=None)
    panel = SimpleNamespace(id=932, uuid='should-not-be-read')
    assert persist_identity(subscription=subscription, panel_user=panel) == 932
    assert subscription.remnawave_id == 932


def test_both_write_paths_share_the_same_numeric_id() -> None:
    user = SimpleNamespace(remnawave_id=None)
    subscription = SimpleNamespace(remnawave_id=None)
    persist_identity(
        user=user,
        subscription=subscription,
        panel_id=932,
    )
    assert user.remnawave_id == 932
    assert subscription.remnawave_id == 932


def test_uuid_panel_id_is_rejected() -> None:
    user = SimpleNamespace(remnawave_id=None)
    with pytest.raises(RemnaWaveInvalidUserIdError):
        persist_identity(user=user, panel_id='0f2a5f6c-1f4e-4f0c-9b3a-6f2d1c8e7a10')
    assert user.remnawave_id is None


def test_uuid_only_panel_user_is_rejected() -> None:
    user = SimpleNamespace(remnawave_id=None)
    panel = SimpleNamespace(uuid='0f2a5f6c-1f4e-4f0c-9b3a-6f2d1c8e7a10')
    with pytest.raises(RemnaWaveInvalidUserIdError):
        persist_identity(user=user, panel_user=panel)
    assert user.remnawave_id is None


def test_requires_a_write_target() -> None:
    with pytest.raises(ValueError, match='user and/or subscription'):
        persist_identity(panel_id=932)


def test_subscription_service_wires_both_write_paths() -> None:
    source = (SEAM.parents[2] / 'services' / 'subscription_service.py').read_text(encoding='utf-8')
    assert 'from app.custom.identity.persist import persist_identity' in source
    assert 'persist_identity(subscription=' in source
    assert 'persist_identity(user=' in source


def test_seam_source_has_no_uuid_lookup() -> None:
    source = SEAM.read_text(encoding='utf-8')
    assert 'def resolve_remnawave_id' not in source
    assert 'by-uuid' not in source
    assert "getattr(panel_user, 'uuid'" not in source
    assert 'getattr(panel_user, "uuid"' not in source
    assert 'persist_identity' in source
