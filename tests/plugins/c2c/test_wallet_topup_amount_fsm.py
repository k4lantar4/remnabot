import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Chat, Message, User as TgUser

try:
    from app.handlers.subscription.tariff_purchase import AwaitingCustomTrafficFilter
except ImportError:  # 4.2 does not have this remnabot traffic-input filter
    pytest.skip(
        'AwaitingCustomTrafficFilter is remnabot-only; not required for C2C plugin port',
        allow_module_level=True,
    )


@pytest.mark.asyncio
async def test_awaiting_custom_traffic_filter_requires_flag():
    filt = AwaitingCustomTrafficFilter()
    message = Message(
        message_id=1,
        date=0,
        chat=Chat(id=1, type='private'),
        from_user=TgUser(id=1, is_bot=False, first_name='Test'),
        text='50000',
    )

    class _StateOff:
        async def get_data(self):
            return {}

    class _StateOn:
        async def get_data(self):
            return {'awaiting_custom_traffic_input': True}

    assert await filt(message, _StateOff()) is False
    assert await filt(message, _StateOn()) is True
