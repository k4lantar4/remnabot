"""Tests for admin partner list search helpers."""

from app.cabinet.routes.admin_partners import _partner_list_filters, _partner_search_conditions


class TestPartnerSearchConditions:
    def test_text_search_has_three_ilike_fields(self):
        conditions = _partner_search_conditions('farsbazar')
        assert len(conditions) == 3

    def test_digit_search_adds_telegram_id(self):
        conditions = _partner_search_conditions('5077628345')
        assert len(conditions) == 4

    def test_non_digit_long_number_still_has_text_fields_only(self):
        conditions = _partner_search_conditions('5077628345abc')
        assert len(conditions) == 3

    def test_partner_list_filters_without_search(self):
        filters = _partner_list_filters(None)
        assert len(filters) == 1

    def test_partner_list_filters_with_search(self):
        filters = _partner_list_filters('farsbazar')
        assert len(filters) == 2
