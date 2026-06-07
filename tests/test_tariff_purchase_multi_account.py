from app.handlers.subscription.tariff_purchase import should_extend_multi_tariff


def test_extend_only_when_subscription_pinned():
    """When target_subscription_id in FSM, extend; otherwise create."""
    pinned = {'target_subscription_id': 42}
    assert should_extend_multi_tariff(pinned, existing_sub=object()) is True
    assert should_extend_multi_tariff({}, existing_sub=object()) is False
