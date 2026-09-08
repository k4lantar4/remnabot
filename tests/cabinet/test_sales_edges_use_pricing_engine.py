from pathlib import Path

ROOT = Path('app/cabinet/routes/subscription_modules')


def test_purchase_renewal_traffic_devices_switch_import_engine() -> None:
    files = {
        'purchase.py': 'PricingEngine',
        'renewal.py': 'pricing_engine',
        'traffic.py': 'PricingEngine',
        'servers.py': 'PricingEngine',
        'tariff_switch.py': 'pricing_engine',
    }
    for name, token in files.items():
        text = (ROOT / name).read_text(encoding='utf-8')
        assert token in text, f'{name} must use PricingEngine'
