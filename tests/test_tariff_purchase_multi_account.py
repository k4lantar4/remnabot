from app.handlers.subscription.tariff_purchase import should_extend_multi_tariff


def test_extend_only_when_subscription_pinned():
    """When target_subscription_id in FSM, extend; otherwise create."""
    pinned = {'target_subscription_id': 42}
    assert should_extend_multi_tariff(pinned, existing_sub=object()) is True
    assert should_extend_multi_tariff({}, existing_sub=object()) is False


def test_extend_when_active_subscription_id_with_renew_only():
    """Renew-only paths may extend via active_subscription_id match."""
    existing = type('Sub', (), {'id': 7})()
    assert should_extend_multi_tariff(
        {'active_subscription_id': 7},
        existing_sub=existing,
        renew_only=True,
    )
    assert not should_extend_multi_tariff(
        {'active_subscription_id': 7},
        existing_sub=existing,
        renew_only=False,
    )
