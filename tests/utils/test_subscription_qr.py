from app.utils.subscription_qr import generate_subscription_qr_png


def test_generate_subscription_qr_png_is_valid_png_and_stable_length():
    url = 'https://example.com/subscription/abc123'
    payload = generate_subscription_qr_png(url)

    assert payload.startswith(b'\x89PNG\r\n\x1a\n')
    assert len(payload) > 256
    assert len(payload) == len(generate_subscription_qr_png(url))
