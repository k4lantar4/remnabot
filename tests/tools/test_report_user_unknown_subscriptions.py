from __future__ import annotations

from tools.report_user_unknown_subscriptions import is_user_unknown_panel_username


def test_is_user_unknown_panel_username_true() -> None:
    assert is_user_unknown_panel_username('user_unknown_41103d') is True


def test_is_user_unknown_panel_username_false_for_legacy() -> None:
    assert is_user_unknown_panel_username('Germany(2)-134500') is False


def test_is_user_unknown_panel_username_false_for_new() -> None:
    assert is_user_unknown_panel_username('user_1713374557_41103d') is False
