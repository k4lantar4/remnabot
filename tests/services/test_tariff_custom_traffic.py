import pytest

from app.services.tariff_custom_traffic import (
    parse_positive_gb,
    parse_positive_toman,
    validate_custom_traffic_configuration,
)


@pytest.mark.parametrize(
    ('raw', 'expected'),
    # '1.001' is European thousands to the shared normalizer, the same as in the top-up field.
    [('2', 2), ('2500', 2500), ('2,000', 2000), ('1 500', 1500), ('2.00', 2), ('1.001', 1001)],
)
def test_parse_positive_toman(raw: str, expected: int) -> None:
    """The typed number is the stored number: `traffic_price_per_gb_kopeks` is Toman since 0115."""
    assert parse_positive_toman(raw) == expected


@pytest.mark.parametrize('raw', ['', 'abc', '0', '-1', 'nan', 'NaN', 'inf', '-inf', '2.50', '0.01', '1.5'])
def test_parse_positive_toman_rejects_invalid_values(raw: str) -> None:
    """Toman has no subunit here, so a fractional price is a typo — rejected, never rounded away."""
    with pytest.raises(ValueError):
        parse_positive_toman(raw)


@pytest.mark.parametrize(('raw', 'expected'), [('1', 1), ('5', 5), ('100', 100)])
def test_parse_positive_gb(raw: str, expected: int) -> None:
    assert parse_positive_gb(raw) == expected


@pytest.mark.parametrize('raw', ['', '0', '-1', '1.5', 'abc'])
def test_parse_positive_gb_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_positive_gb(raw)


def test_valid_custom_traffic_configuration_has_no_errors() -> None:
    assert (
        validate_custom_traffic_configuration(
            price_per_gb_kopeks=200,
            min_traffic_gb=5,
            max_traffic_gb=100,
        )
        == ()
    )


@pytest.mark.parametrize(
    ('price', 'minimum', 'maximum', 'expected_fragment'),
    [
        (None, 5, 100, 'не указана цена'),
        (0, 5, 100, 'цена за 1 ГБ должна быть больше нуля'),
        (-1, 5, 100, 'цена за 1 ГБ должна быть больше нуля'),
        (200, None, 100, 'не указан минимальный объём'),
        (200, 0, 100, 'минимальный объём должен быть больше нуля'),
        (200, -1, 100, 'минимальный объём должен быть больше нуля'),
        (200, 5, None, 'не указан максимальный объём'),
        (200, 5, 0, 'максимальный объём должен быть больше нуля'),
        (200, 5, -1, 'максимальный объём должен быть больше нуля'),
        (200, 100, 5, 'максимальный объём не может быть меньше минимального'),
    ],
)
def test_invalid_custom_traffic_configuration_reports_specific_error(
    price: int | None,
    minimum: int | None,
    maximum: int | None,
    expected_fragment: str,
) -> None:
    errors = validate_custom_traffic_configuration(
        price_per_gb_kopeks=price,
        min_traffic_gb=minimum,
        max_traffic_gb=maximum,
    )
    assert any(expected_fragment in error for error in errors)


def test_invalid_configuration_reports_all_independent_missing_fields() -> None:
    errors = validate_custom_traffic_configuration(
        price_per_gb_kopeks=None,
        min_traffic_gb=None,
        max_traffic_gb=None,
    )
    assert errors == (
        'не указана цена за 1 ГБ',
        'не указан минимальный объём',
        'не указан максимальный объём',
    )
