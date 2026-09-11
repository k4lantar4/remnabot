"""Cabinet admin balance edit is capped like the bot one (F-014).

Both ``UpdateBalanceRequest`` fields are Toman 1:1. The bot refuses a single edit
above ``ADMIN_BALANCE_EDIT_MAX_TOMAN``; the cabinet used to accept up to two billion,
so a typo with extra zeros went straight onto the balance.
"""

import pytest
from pydantic import ValidationError

from app.cabinet.schemas.users import UpdateBalanceRequest
from app.utils.price_display import ADMIN_BALANCE_EDIT_MAX_TOMAN


def test_cap_is_ten_million_toman() -> None:
    assert ADMIN_BALANCE_EDIT_MAX_TOMAN == 10_000_000


@pytest.mark.parametrize('field', ['amount_display', 'amount_kopeks'])
@pytest.mark.parametrize('amount', [10_000_000, -10_000_000])
def test_edit_at_the_cap_is_accepted(field: str, amount: int) -> None:
    req = UpdateBalanceRequest(**{field: amount})

    assert getattr(req, field) == amount


@pytest.mark.parametrize('field', ['amount_display', 'amount_kopeks'])
@pytest.mark.parametrize('amount', [10_000_001, -10_000_001, 10_000_000_000])
def test_edit_above_the_cap_is_rejected(field: str, amount: int) -> None:
    with pytest.raises(ValidationError):
        UpdateBalanceRequest(**{field: amount})
