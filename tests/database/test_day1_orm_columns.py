from app.database.models import Subscription, User


def test_user_has_panel_brand_prefix() -> None:
    assert hasattr(User, 'panel_brand_prefix')


def test_subscription_has_purchase_note_and_user_disabled() -> None:
    assert hasattr(Subscription, 'purchase_note')
    assert hasattr(Subscription, 'user_disabled')


def test_subscription_has_identity_a_columns() -> None:
    assert hasattr(Subscription, 'panel_username')
    assert hasattr(Subscription, 'account_sequence')


def test_subscription_model_does_not_declare_user_tariff_unique() -> None:
    index_names = {idx.name for idx in Subscription.__table__.indexes}
    assert 'uq_subscriptions_user_tariff_active' not in index_names

