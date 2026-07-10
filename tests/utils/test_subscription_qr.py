from app.utils.purchase_success_delivery import build_config_delivery_caption
from app.utils.subscription_qr import generate_subscription_qr_png


class _FakeTexts:
    def t(self, key: str, fallback: str) -> str:
        return fallback


def test_build_config_delivery_caption_includes_link():
    texts = _FakeTexts()
    subscription = type('Sub', (), {'subscription_url': 'https://example.com/sub'})()

    caption = build_config_delivery_caption(texts, subscription)

    assert '<code>https://example.com/sub</code>' in caption
    assert 'конфигурация' in caption.lower() or 'کانفیگ' in caption


def test_generate_subscription_qr_png_is_valid_png_and_stable_length():
    url = 'https://example.com/subscription/abc123'
    payload = generate_subscription_qr_png(url)

    assert payload.startswith(b'\x89PNG\r\n\x1a\n')
    assert len(payload) > 256
    assert len(payload) == len(generate_subscription_qr_png(url))
