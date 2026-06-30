from app.config import settings
from app.utils.topup_suggestion import effective_c2c_topup_amount, suggest_topup_amount_toman


def test_suggest_topup_amount_rounds_to_1000_step():
    assert suggest_topup_amount_toman(10_500) == 11_000
    assert suggest_topup_amount_toman(10_000) == 10_000


def test_effective_c2c_topup_clamps_to_minimum(monkeypatch):
    monkeypatch.setattr(settings, 'C2C_MIN_AMOUNT_KOPEKS', 100_000)
    assert effective_c2c_topup_amount(10_000) == 100_000
    assert effective_c2c_topup_amount(150_000) == 150_000


def test_effective_c2c_topup_zero_when_no_amount():
    assert effective_c2c_topup_amount(0) == 0
