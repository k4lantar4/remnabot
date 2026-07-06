"""Tests for C2C finalize_approved_topup admin notification flag."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.plugins.c2c.service import C2cPaymentService


@pytest.mark.asyncio
async def test_finalize_skips_admin_balance_notification_when_disabled():
    user = SimpleNamespace(
        id=1,
        telegram_id=123,
        has_made_first_topup=True,
        referred_by_id=None,
        get_primary_promo_group=lambda: None,
    )
    transaction = SimpleNamespace(id=10)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    bot = AsyncMock()
    service = C2cPaymentService(bot)

    with patch('app.services.referral_service.process_referral_topup', new=AsyncMock()), patch(
        'app.services.payment_service.PaymentService',
    ) as payment_service_cls, patch(
        'app.services.admin_notification_service.AdminNotificationService',
    ) as admin_notify_cls, patch(
        'app.services.payment.common.send_cart_notification_after_topup',
        new=AsyncMock(return_value=False),
    ):
        payment_service_cls.return_value._send_payment_success_notification = AsyncMock()
        admin_notify_cls.return_value.send_balance_topup_notification = AsyncMock()

        await service.finalize_approved_topup(
            db,
            user,
            transaction,
            100_000,
            old_balance=0,
            was_first_topup=False,
            send_admin_balance_notification=False,
        )

        admin_notify_cls.return_value.send_balance_topup_notification.assert_not_awaited()
        payment_service_cls.return_value._send_payment_success_notification.assert_awaited_once()
        call_kwargs = payment_service_cls.return_value._send_payment_success_notification.await_args.kwargs
        assert call_kwargs.get('cart_autopurchase_failed') is False


@pytest.mark.asyncio
async def test_finalize_passes_cart_autopurchase_failed_for_checkout_cart():
    user = SimpleNamespace(
        id=1,
        telegram_id=123,
        has_made_first_topup=True,
        referred_by_id=None,
        get_primary_promo_group=lambda: None,
    )
    transaction = SimpleNamespace(id=10)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    bot = AsyncMock()
    service = C2cPaymentService(bot)
    checkout_cart = {'return_to_cart': True, 'cart_mode': 'tariff_purchase', 'total_price': 50000}

    with patch('app.services.referral_service.process_referral_topup', new=AsyncMock()), patch(
        'app.services.payment_service.PaymentService',
    ) as payment_service_cls, patch(
        'app.services.admin_notification_service.AdminNotificationService',
    ) as admin_notify_cls, patch(
        'app.services.payment.common.send_cart_notification_after_topup',
        new=AsyncMock(return_value=False),
    ), patch(
        'app.services.user_cart_service.user_cart_service.get_user_cart',
        new=AsyncMock(return_value=checkout_cart),
    ), patch(
        'app.services.user_cart_service.user_cart_service.refresh_topup_intent',
        new=AsyncMock(),
    ):
        payment_service_cls.return_value._send_payment_success_notification = AsyncMock()
        admin_notify_cls.return_value.send_balance_topup_notification = AsyncMock()

        await service.finalize_approved_topup(
            db,
            user,
            transaction,
            100_000,
            old_balance=0,
            was_first_topup=False,
        )

        call_kwargs = payment_service_cls.return_value._send_payment_success_notification.await_args.kwargs
        assert call_kwargs.get('cart_autopurchase_failed') is True


@pytest.mark.asyncio
async def test_finalize_sends_admin_balance_notification_by_default():
    user = SimpleNamespace(
        id=1,
        telegram_id=123,
        has_made_first_topup=True,
        referred_by_id=None,
        get_primary_promo_group=lambda: None,
    )
    transaction = SimpleNamespace(id=10)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    bot = AsyncMock()
    service = C2cPaymentService(bot)

    with patch('app.services.referral_service.process_referral_topup', new=AsyncMock()), patch(
        'app.services.payment_service.PaymentService',
    ) as payment_service_cls, patch(
        'app.services.admin_notification_service.AdminNotificationService',
    ) as admin_notify_cls, patch(
        'app.services.payment.common.send_cart_notification_after_topup',
        new=AsyncMock(return_value=False),
    ):
        payment_service_cls.return_value._send_payment_success_notification = AsyncMock()
        admin_notify_cls.return_value.send_balance_topup_notification = AsyncMock()

        await service.finalize_approved_topup(
            db,
            user,
            transaction,
            100_000,
            old_balance=0,
            was_first_topup=False,
        )

        admin_notify_cls.return_value.send_balance_topup_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_skips_topup_notification_when_autopurchase_succeeds():
    user = SimpleNamespace(
        id=1,
        telegram_id=123,
        has_made_first_topup=True,
        referred_by_id=None,
        get_primary_promo_group=lambda: None,
    )
    transaction = SimpleNamespace(id=10)
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    bot = AsyncMock()
    service = C2cPaymentService(bot)
    cart_notify = AsyncMock(return_value=True)

    with patch('app.services.referral_service.process_referral_topup', new=AsyncMock()), patch(
        'app.services.payment_service.PaymentService',
    ) as payment_service_cls, patch(
        'app.services.admin_notification_service.AdminNotificationService',
    ) as admin_notify_cls, patch(
        'app.services.payment.common.send_cart_notification_after_topup',
        new=cart_notify,
    ):
        payment_service_cls.return_value._send_payment_success_notification = AsyncMock()
        admin_notify_cls.return_value.send_balance_topup_notification = AsyncMock()

        await service.finalize_approved_topup(
            db,
            user,
            transaction,
            100_000,
            old_balance=0,
            was_first_topup=False,
        )

        cart_notify.assert_awaited_once()
        payment_service_cls.return_value._send_payment_success_notification.assert_not_awaited()
