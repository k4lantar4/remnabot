from types import SimpleNamespace

from app.utils.subscription_purchase_intent import should_extend_multi_tariff


def test_extend_when_pinned_and_row_present() -> None:
    sub = SimpleNamespace(id=10, tariff_id=3)
    assert should_extend_multi_tariff({'target_subscription_id': 10}, existing_sub=sub) is True


def test_create_when_pin_cleared() -> None:
    sub = SimpleNamespace(id=10, tariff_id=3)
    assert should_extend_multi_tariff({'target_subscription_id': None}, existing_sub=sub) is False
    assert should_extend_multi_tariff({}, existing_sub=sub) is False


def test_create_when_no_row() -> None:
    assert should_extend_multi_tariff({'target_subscription_id': 10}, existing_sub=None) is False
