"""Unit tests for unified promo group resolution in tariff CRUD."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.database.crud.tariff import resolve_user_promo_group_id
from app.database.models import PromoGroup, Tariff


def test_resolve_user_promo_group_id_none_user():
    assert resolve_user_promo_group_id(None) is None


def test_resolve_user_promo_group_id_primary_m2m():
    promo_group = SimpleNamespace(id=42)
    user = SimpleNamespace(
        promo_group_id=1,
        get_primary_promo_group=lambda: promo_group,
    )
    assert resolve_user_promo_group_id(user) == 42


def test_resolve_user_promo_group_id_legacy_fk_fallback():
    user = SimpleNamespace(promo_group_id=7)
    assert resolve_user_promo_group_id(user) == 7


def test_is_available_for_promo_group_none_with_restrictions():
    restricted_group = PromoGroup(id=2, name='شرکا')
    tariff = Tariff(name='Partner only')
    tariff.allowed_promo_groups = [restricted_group]

    assert tariff.is_available_for_promo_group(None) is False


def test_is_available_for_promo_group_none_without_restrictions():
    tariff = Tariff(name='Public')
    tariff.allowed_promo_groups = []

    assert tariff.is_available_for_promo_group(None) is True


def test_is_available_for_promo_group_matching_id():
    restricted_group = PromoGroup(id=2, name='شرکا')
    tariff = Tariff(name='Partner only')
    tariff.allowed_promo_groups = [restricted_group]

    assert tariff.is_available_for_promo_group(2) is True
    assert tariff.is_available_for_promo_group(1) is False
