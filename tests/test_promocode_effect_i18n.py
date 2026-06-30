import inspect
import re

from app.services.promocode_service import PromoCodeService


def test_promocode_effect_descriptions_use_locale_keys():
    """Effect lines must go through texts.t keys, not bare Cyrillic f-strings or ₽."""
    source = inspect.getsource(PromoCodeService._apply_promocode_effects)
    assert 'PROMOCODE_EFFECT_' in source
    assert '₽' not in source
    assert '/ 100' not in source
    bare_cyrillic_effects = re.findall(r"effects\.append\(f['\"]", source)
    assert bare_cyrillic_effects == []
