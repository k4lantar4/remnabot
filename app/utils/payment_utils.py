from typing import List, Dict, Tuple

from app.config import settings
from app.localization.texts import get_texts

def get_available_payment_methods() -> List[Dict[str, str]]:
    """
    Returns a list of available payment methods with their settings
    """
    methods = []
    
    if settings.TELEGRAM_STARS_ENABLED:
        methods.append({
            "id": "stars",
            "name": "Telegram Stars",
            "icon": "⭐",
            "description": "fast and convenient",
            "callback": "topup_stars"
        })
    
    if settings.is_yookassa_enabled():
        if getattr(settings, "YOOKASSA_SBP_ENABLED", False):
            methods.append({
                "id": "yookassa_sbp",
                "name": "SBP (YooKassa)",
                "icon": "🏦",
                "description": "instant payment via QR",
                "callback": "topup_yookassa_sbp",
            })

        methods.append({
            "id": "yookassa",
            "name": "Bank card",
            "icon": "💳",
            "description": "via YooKassa",
            "callback": "topup_yookassa",
        })
    
    if settings.TRIBUTE_ENABLED:
        methods.append({
            "id": "tribute",
            "name": "Bank card",
            "icon": "💳",
            "description": "via Tribute",
            "callback": "topup_tribute"
        })

    if settings.is_mulenpay_enabled():
        mulenpay_name = settings.get_mulenpay_display_name()
        methods.append({
            "id": "mulenpay",
            "name": "Bank card",
            "icon": "💳",
            "description": f"via {mulenpay_name}",
            "callback": "topup_mulenpay"
        })

    if settings.is_wata_enabled():
        methods.append({
            "id": "wata",
            "name": "Bank card",
            "icon": "💳",
            "description": "via WATA",
            "callback": "topup_wata"
        })

    if settings.is_pal24_enabled():
        methods.append({
            "id": "pal24",
            "name": "SBP",
            "icon": "🏦",
            "description": "via PayPalych",
            "callback": "topup_pal24"
        })

    if settings.is_cryptobot_enabled():
        methods.append({
            "id": "cryptobot",
            "name": "Cryptocurrency",
            "icon": "🪙",
            "description": "via CryptoBot",
            "callback": "topup_cryptobot"
        })

    if settings.is_heleket_enabled():
        methods.append({
            "id": "heleket",
            "name": "Cryptocurrency",
            "icon": "🪙",
            "description": "via Heleket",
            "callback": "topup_heleket"
        })

    if settings.is_platega_enabled() and settings.get_platega_active_methods():
        methods.append({
            "id": "platega",
            "name": "Bank card",
            "icon": "💳",
            "description": "via Platega (cards + SBP)",
            "callback": "topup_platega",
        })

    if settings.is_support_topup_enabled():
        methods.append({
            "id": "support",
            "name": "Via support",
            "icon": "🛠️",
            "description": "other methods",
            "callback": "topup_support"
        })
    
    return methods

def get_payment_methods_text(language: str) -> str:
    """
    Generates text with description of available payment methods
    """
    texts = get_texts(language)
    methods = get_available_payment_methods()

    if not methods:
        return texts.t(
            "PAYMENT_METHODS_NONE_AVAILABLE",
            """💳 <b>Balance top-up methods</b>

⚠️ Payment methods are temporarily unavailable at the moment.
Please try again later.

Select a top-up method:""",
        )

    if len(methods) == 1 and methods[0]["id"] == "support":
        return texts.t(
            "PAYMENT_METHODS_ONLY_SUPPORT",
            """💳 <b>Balance top-up methods</b>

⚠️ Automatic payment methods are temporarily unavailable at the moment.
Contact support to top up your balance.

Select a top-up method:""",
        )

    text = texts.t(
        "PAYMENT_METHODS_TITLE",
        "💳 <b>Balance top-up methods</b>",
    ) + "\n\n"
    text += texts.t(
        "PAYMENT_METHODS_PROMPT",
        "Choose a convenient payment method:",
    ) + "\n\n"

    for method in methods:
        method_id = method['id'].upper()
        name = texts.t(
            f"PAYMENT_METHOD_{method_id}_NAME",
            f"{method['icon']} <b>{method['name']}</b>",
        )
        description = texts.t(
            f"PAYMENT_METHOD_{method_id}_DESCRIPTION",
            method['description'],
        )
        if method_id == "MULENPAY":
            mulenpay_name = settings.get_mulenpay_display_name()
            mulenpay_name_html = settings.get_mulenpay_display_name_html()
            name = name.format(mulenpay_name=mulenpay_name_html)
            description = description.format(mulenpay_name=mulenpay_name)

        text += f"{name} - {description}\n"

    text += "\n" + texts.t(
        "PAYMENT_METHODS_FOOTER",
        "Select a top-up method:",
    )

    return text

def is_payment_method_available(method_id: str) -> bool:
    """
    Checks if a specific payment method is available
    """
    if method_id == "stars":
        return settings.TELEGRAM_STARS_ENABLED
    elif method_id == "yookassa":
        return settings.is_yookassa_enabled()
    elif method_id == "tribute":
        return settings.TRIBUTE_ENABLED
    elif method_id == "mulenpay":
        return settings.is_mulenpay_enabled()
    elif method_id == "wata":
        return settings.is_wata_enabled()
    elif method_id == "pal24":
        return settings.is_pal24_enabled()
    elif method_id == "cryptobot":
        return settings.is_cryptobot_enabled()
    elif method_id == "heleket":
        return settings.is_heleket_enabled()
    elif method_id == "platega":
        return settings.is_platega_enabled() and bool(settings.get_platega_active_methods())
    elif method_id == "support":
        return settings.is_support_topup_enabled()
    else:
        return False

def get_payment_method_status() -> Dict[str, bool]:
    """
    Returns the status of all payment methods
    """
    return {
        "stars": settings.TELEGRAM_STARS_ENABLED,
        "yookassa": settings.is_yookassa_enabled(),
        "tribute": settings.TRIBUTE_ENABLED,
        "mulenpay": settings.is_mulenpay_enabled(),
        "wata": settings.is_wata_enabled(),
        "pal24": settings.is_pal24_enabled(),
        "cryptobot": settings.is_cryptobot_enabled(),
        "heleket": settings.is_heleket_enabled(),
        "platega": settings.is_platega_enabled() and bool(settings.get_platega_active_methods()),
        "support": settings.is_support_topup_enabled()
    }

def get_enabled_payment_methods_count() -> int:
    """
    Returns the number of enabled payment methods (excluding support)
    """
    count = 0
    if settings.TELEGRAM_STARS_ENABLED:
        count += 1
    if settings.is_yookassa_enabled():
        count += 1
    if settings.TRIBUTE_ENABLED:
        count += 1
    if settings.is_mulenpay_enabled():
        count += 1
    if settings.is_wata_enabled():
        count += 1
    if settings.is_pal24_enabled():
        count += 1
    if settings.is_cryptobot_enabled():
        count += 1
    if settings.is_heleket_enabled():
        count += 1
    if settings.is_platega_enabled() and settings.get_platega_active_methods():
        count += 1
    return count
